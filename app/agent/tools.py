from __future__ import annotations

from datetime import datetime
import re

from agents import function_tool

from ..sources import sql, rag
from ..sources import api as brigade_api


def _normalize_fio(name: str) -> str:
    """Normalize FIO for matching: collapse spaces, remove ўғли/угли suffix."""
    n = re.sub(r"\s+", " ", name.strip())
    n = re.sub(r"\s*(ўғли|угли|Угли|ўғлi|улы)\s*$", "", n).strip()
    return n


def _clean_fio_display(name: str) -> str:
    """Clean FIO for display: collapse spaces, fix o'g'li encoding."""
    n = re.sub(r"\s+", " ", name.strip())
    # Fix common encoding artifacts in o'g'li/qizi
    n = n.replace("о\u0027г\u0027ли", "o'g'li")
    n = n.replace("о'г'ли", "o'g'li")
    n = n.replace("ўғли", "o'g'li")
    n = n.replace("угли", "o'g'li")
    n = n.replace("Угли", "O'g'li")
    n = n.replace("қизи", "qizi")
    n = n.replace("кизи", "qizi")
    return n


# ---------------------------------------------------------------------------
# Translation helpers
# ---------------------------------------------------------------------------

_STATE_LABELS = {
    "in_use": "Foydalanishda",
    "in_inspection": "Tamirda",
    "in_reserve": "Rezervda",
}

_TYPE_LABELS = {
    "electric_loco": "Elektrovoz",
    "diesel_loco": "Teplovoz",
    "electric_train": "Elektropoyezd",
    "high_speed": "Yuqori tezlikli poyezd",
    "carriage": "Vagon",
}

_SQL_DEPO_QUERY_ALIASES: dict[int, tuple[str, ...]] = {
    1: ("angren", "ангрен"),
    2: ("andijon", "андиж"),
    3: ("denov", "денов"),
    4: ("qarshi", "карши", "қарши"),
    5: ("tinchlik", "uchquduq", "тинчлик", "учкудук"),
    6: ("buxoro", "bukhara", "бухара", "бухоро"),
    7: ("miskin", "мискин"),
    8: ("qongirot", "qo ng irot", "kungrad", "кунград", "қўнғирот"),
    9: ("liniyada", "liniya", "line"),
}

_BRIGADE_DEPO_QUERY_ALIASES: dict[int, tuple[str, ...]] = {
    1: ("uzbekiston", "o zbekiston", "o'zbekiston", "узбекистан"),
    2: ("kokand", "qoqon", "коканд", "қўқон"),
    3: ("tinchlik", "uchquduq", "тинчлик", "учкудук"),
    4: ("buxoro", "bukhara", "бухара", "бухоро"),
    5: ("kungrad", "kungrad", "qongirot", "qo ng irot", "кунград", "қўнғирот"),
    6: ("qarshi", "карши", "қарши"),
    7: ("termez", "termiz", "термез", "термиз"),
    8: ("urganch", "urgench", "ургенч", "урганч"),
}


def _ts(state: str | None) -> str:
    """Translate state code to Uzbek."""
    return _STATE_LABELS.get(state or "", state or "Noma'lum")


def _tt(loco_type: str | None) -> str:
    """Translate locomotive type to Uzbek."""
    return _TYPE_LABELS.get(loco_type or "", loco_type or "Noma'lum")


def _pct(part: int | float, total: int | float) -> str:
    return f"{(part / total * 100):.1f}%" if total else "0%"


def _bm_name(member: dict) -> str:
    return member.get("full_name") or member.get("fio") or "Noma'lum"


def _bm_type(member: dict) -> str:
    return member.get("mashinist_type_name") or member.get("type") or "Noma'lum"


def _bm_status(member: dict) -> str:
    return member.get("status_name") or member.get("status") or "Noma'lum"


def _bm_brigade(member: dict) -> str | None:
    if member.get("brigade_name"):
        return member["brigade_name"]
    brigada_group_id = member.get("brigada_group_id")
    if brigada_group_id:
        return f"Brigada #{brigada_group_id}"
    return None


def _format_brigade_member(member: dict, idx: int | None = None) -> list[str]:
    prefix = f"{idx}. " if idx is not None else "• "
    lines = [f"{prefix}{_bm_name(member)} — {_bm_type(member)}"]
    details = [f"Status: {_bm_status(member)}"]
    if member.get("depo_name"):
        details.append(f"Depo: {member['depo_name']}")
    if _bm_brigade(member):
        details.append(f"Brigada: {_bm_brigade(member)}")
    if member.get("lok_nomer") or member.get("lok_name"):
        lok_label = member.get("lok_name") or "Lokomotiv"
        if member.get("lok_nomer"):
            details.append(f"Lokomotiv: {lok_label} ({member['lok_nomer']})")
        else:
            details.append(f"Lokomotiv: {lok_label}")
    if member.get("phone"):
        details.append(f"Telefon: {member['phone']}")
    details.append(f"ID: {member.get('id')}")
    details.append(f"Tabel: {member.get('tabelnum')}")
    lines.append("  " + " | ".join(str(d) for d in details if d))
    return lines


def _format_filter_context(
    *,
    query: str | None = None,
    depo_id: int | None = None,
    brigada_group_id: int | None = None,
    status_id: int | None = None,
    lok_nomer: str | None = None,
    lok_name: str | None = None,
    mashinist_type: str | None = None,
    assigned_only: bool | None = None,
    has_phone: bool | None = None,
    has_image: bool | None = None,
    is_active: bool | None = None,
) -> str:
    parts: list[str] = []
    if query:
        parts.append(f"so'rov: {query}")
    if depo_id is not None:
        parts.append(f"depo_id: {depo_id}")
    if brigada_group_id is not None:
        parts.append(f"brigada_id: {brigada_group_id}")
    if status_id is not None:
        parts.append(f"status_id: {status_id}")
    if lok_nomer:
        parts.append(f"lok_nomer: {lok_nomer}")
    if lok_name:
        parts.append(f"lok_name: {lok_name}")
    if mashinist_type:
        parts.append(f"type: {mashinist_type}")
    if assigned_only is not None:
        parts.append("faqat biriktirilganlar" if assigned_only else "biriktirilmaganlar")
    if has_phone is not None:
        parts.append("telefoni bor" if has_phone else "telefoni yo'q")
    if has_image is not None:
        parts.append("rasmi bor" if has_image else "rasmi yo'q")
    if is_active is not None:
        parts.append("aktiv" if is_active else "aktiv emas")
    return ", ".join(parts) if parts else "barcha yozuvlar"


def _normalize_query_text(value: str | None) -> str:
    text = (value or "").casefold()
    for ch in ("'", "`", '"', "’", "ʻ", "ʼ", "-", "_", ".", ",", "(", ")", "/", "\\", "|", ":", ";", "#", "№"):
        text = text.replace(ch, " ")
    return " ".join(text.split())


def _extract_depo_id_hint(query: str | None) -> int | None:
    normalized = _normalize_query_text(query)
    for pattern in (
        r"\b(\d{1,2})\s*(?:depo|deposi|депо)\b",
        r"\b(?:depo|deposi|депо)\s*(\d{1,2})\b",
        r"^\s*(\d{1,2})\s*$",
    ):
        match = re.search(pattern, normalized)
        if match:
            return int(match.group(1))
    return None


def _resolve_depo_id_by_query(
    query: str | None,
    aliases: dict[int, tuple[str, ...]],
    *,
    allow_numeric_fallback: bool,
) -> tuple[int | None, str | None]:
    normalized = _normalize_query_text(query)
    if normalized:
        for depo_id, depot_aliases in aliases.items():
            for alias in depot_aliases:
                alias_normalized = _normalize_query_text(alias)
                if alias_normalized and alias_normalized in normalized:
                    return depo_id, "name"

    if allow_numeric_fallback:
        depo_id_hint = _extract_depo_id_hint(query)
        if depo_id_hint in aliases:
            return depo_id_hint, "numeric"

    return None, None


def _brigade_depo_id_for_sql_depo(depo_name: str | None) -> int | None:
    name = (depo_name or "").casefold()
    if "chuqursoy" in name:
        return 1
    if "termez" in name:
        return 7
    if "qarshi" in name:
        return 6
    if "tinchlik" in name or "uchquduq" in name:
        return 3
    if "buxoro" in name or "bukhara" in name:
        return 4
    if "urganch" in name or "urgench" in name:
        return 8
    if "qo'ng" in name or "qong" in name or "kungrad" in name:
        return 5
    return None


def _resolve_sql_depo(query: str | None, *, allow_numeric_fallback: bool) -> tuple[int | None, str | None]:
    return _resolve_depo_id_by_query(
        query,
        _SQL_DEPO_QUERY_ALIASES,
        allow_numeric_fallback=allow_numeric_fallback,
    )


def _resolve_brigade_depo(query: str | None, *, allow_numeric_fallback: bool) -> tuple[int | None, str | None]:
    return _resolve_depo_id_by_query(
        query,
        _BRIGADE_DEPO_QUERY_ALIASES,
        allow_numeric_fallback=allow_numeric_fallback,
    )


def _render_depo_info(depo: dict) -> str:
    loco_count = depo["locomotive_count"]
    lines = [
        f"🏭 **{depo['depo_name']}**",
        "",
        f"📊 Jami lokomotivlar: {loco_count} ta",
    ]

    if depo["locomotive_type_counts"]:
        lines.append("")
        lines.append("🚂 **Lokomotiv turlari:**")
        for type_name, count in depo["locomotive_type_counts"].items():
            lines.append(f"• {_tt(type_name)}: {count} ta ({_pct(count, loco_count)})")

    if depo["state_counts"]:
        lines.append("")
        lines.append("📍 **Holat bo'yicha:**")
        for state, count in depo["state_counts"].items():
            lines.append(f"• {_ts(state)}: {count} ta ({_pct(count, loco_count)})")

    return "\n".join(lines)


def _render_depo_brigade_info(depo_name: str, brigades: list[dict], sql_depo_id: int | None = None) -> str:
    lines = [f"🚂 {depo_name} deposidagi brigadalar ({len(brigades)} ta):"]
    if sql_depo_id is not None:
        lines.append(f"• SQL depo ID: {sql_depo_id}")
    total_members = sum(int(b.get("member_count", 0)) for b in brigades)
    total_working = sum(int(b.get("working_count", 0)) for b in brigades)
    total_resting = sum(int(b.get("resting_count", 0)) for b in brigades)
    total_other = sum(int(b.get("other_count", 0)) for b in brigades)
    lines.append(f"• Jami mashinistlar: {total_members} ta")
    status_parts = [f"Aktiv: {total_working} ta", f"Dam olishda: {total_resting} ta"]
    if total_other:
        status_parts.append(f"Smenadan tashqari: {total_other} ta")
    lines.append(f"  {' | '.join(status_parts)}")
    for b in brigades:
        mc = int(b.get("member_count", 0))
        wc = int(b.get("working_count", 0))
        rc = int(b.get("resting_count", 0))
        oc = int(b.get("other_count", 0))
        extra = []
        if b.get("assigned_locomotive_count"):
            extra.append(f"lokomotivlar: {b['assigned_locomotive_count']} ta")
        if b.get("instruktor_fio"):
            extra.append(f"instruktor: {b['instruktor_fio']}")
        extra_str = f" ({'; '.join(extra)})" if extra else ""
        lines.append(f"• {b['name']}{extra_str}: {mc} ta")
        b_parts = [f"Aktiv: {wc}", f"Dam olishda: {rc}"]
        if oc:
            b_parts.append(f"Smenadan tashqari: {oc}")
        lines.append(f"  {' | '.join(b_parts)}")
    return "\n".join(lines)


def _get_brigade_summary_by_query(query: str) -> tuple[int | None, str | None, list[dict]]:
    brigade_depo_id, _ = _resolve_brigade_depo(query, allow_numeric_fallback=True)
    if brigade_depo_id is None:
        return None, None, []
    depot_name = brigade_api.BRIGADE_DEPOTS.get(brigade_depo_id, f"Depo {brigade_depo_id}")
    brigades = brigade_api.get_brigade_list(brigade_depo_id)
    return brigade_depo_id, depot_name, brigades


# ---------------------------------------------------------------------------
# 1. get_total_locomotives_count
# ---------------------------------------------------------------------------
@function_tool
def get_total_locomotives_count() -> str:
    """Jami lokomotivlar sonini olish. Foydalaning: 'Nechta lokomotiv bor?', 'Lokomotivlar soni', 'Jami lokomotivlar'"""
    stats = sql.get_stats()
    return f"Jami lokomotivlar soni: {stats['total_locomotives']} ta"


# ---------------------------------------------------------------------------
# 2. get_locomotives_by_state
# ---------------------------------------------------------------------------
@function_tool
def get_locomotives_by_state(state: str) -> str:
    """Holatiga qarab lokomotivlarni olish. Foydalaning: 'Foydalanishdagi lokomotivlar', 'Tamirdagi lokomotivlar', 'Rezervdagi lokomotivlar'.

    Args:
        state: Holat kodi. Qiymatlar: in_use, in_inspection, in_reserve, all
    """
    stats = sql.get_stats()
    total = stats["total_locomotives"]

    if state == "all":
        lines = [f"Jami lokomotivlar: {total} ta"]
        for sc in stats["state_counts"]:
            lines.append(f"• {_ts(sc['state'])}: {sc['count']} ta ({_pct(sc['count'], total)})")
        return "\n".join(lines)

    sc = next((s for s in stats["state_counts"] if s["state"] == state), None)
    if not sc:
        return f'"{state}" holati topilmadi'
    return f"{_ts(state)} holatidagi lokomotivlar: {sc['count']} ta (jami {total} tadan {_pct(sc['count'], total)})"


# ---------------------------------------------------------------------------
# 3. get_stats
# ---------------------------------------------------------------------------
@function_tool
def get_stats() -> str:
    """Umumiy statistikani olish: jami lokomotivlar, modellar soni va holat bo'yicha taqsimot. Foydalaning: 'Statistika', 'Umumiy ma'lumot'"""
    stats = sql.get_stats()
    total = stats["total_locomotives"]
    lines = [
        "📊 Umumiy statistika:",
        f"• Jami lokomotivlar: {total} ta",
        f"• Jami modellar: {stats['total_models']} ta",
        "",
        "📈 Holat bo'yicha taqsimot:",
    ]
    for sc in stats["state_counts"]:
        lines.append(f"• {_ts(sc['state'])}: {sc['count']} ta ({_pct(sc['count'], total)})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. get_locomotive_types
# ---------------------------------------------------------------------------
@function_tool
def get_locomotive_types() -> str:
    """Lokomotiv turlarini va ularning sonini olish. Foydalaning: 'Lokomotiv turlari', 'Elektrovozlar soni', 'Teplovozlar soni'"""
    types = sql.list_locomotive_types()
    active = [t for t in types if t["locomotive_count"] > 0]
    total = sum(t["locomotive_count"] for t in active)
    lines = [f"🚂 Lokomotiv turlari (jami {total} ta):"]
    for t in active:
        lines.append(f"• {_tt(t['locomotive_type'])}: {t['locomotive_count']} ta ({_pct(t['locomotive_count'], total)})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. get_locomotive_models
# ---------------------------------------------------------------------------
@function_tool
def get_locomotive_models() -> str:
    """Lokomotiv modellarini olish. Foydalaning: 'Lokomotiv modellari', 'Qanday modellar bor?'"""
    models = sql.list_locomotive_models()
    total = sum(m["locomotive_count"] for m in models)
    lines = [f"🚂 Lokomotiv modellari (jami {len(models)} ta model, {total} ta lokomotiv):"]
    top = sorted(models, key=lambda m: m["locomotive_count"], reverse=True)[:10]
    for m in top:
        lines.append(f"• {m['name']} ({_tt(m['locomotive_type'])}): {m['locomotive_count']} ta")
    if len(models) > 10:
        lines.append(f"... va yana {len(models) - 10} ta model")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. get_active_repairs
# ---------------------------------------------------------------------------
@function_tool
def get_active_repairs() -> str:
    """Hozirda tamirda bo'lgan lokomotivlarni olish. Foydalaning: 'Tamirdagi lokomotivlar', 'Faol ta'mirlar'"""
    repairs = sql.list_active_repairs()
    if not repairs:
        return "Hozirda tamirda bo'lgan lokomotiv yo'q"

    # Group by repair type
    type_counts: dict[str, int] = {}
    for r in repairs:
        name = r.get("repair_type_name_uz") or r.get("repair_type_name", "")
        type_counts[name] = type_counts.get(name, 0) + 1

    lines = [f"🔧 Hozirda tamirda: {len(repairs)} ta lokomotiv", "", "Ta'mir turlari bo'yicha:"]
    for name, count in type_counts.items():
        lines.append(f"• {name}: {count} ta")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. get_locomotive_last_repair
# ---------------------------------------------------------------------------
@function_tool
def get_locomotive_last_repair(locomotive_name: str) -> str:
    """Aniq bir lokomotivning oxirgi ta'miri haqida ma'lumot. Foydalaning: '026 lokomotivning oxirgi ta'miri', 'Lokomotiv 1255 qachon ta'mirlangan?'

    Args:
        locomotive_name: Lokomotiv nomi yoki raqami (masalan: 026, 1255)
    """
    repair = sql.get_last_repair(locomotive_name=locomotive_name)
    if not repair:
        return f'"{locomotive_name}" raqamli lokomotiv topilmadi yoki ta\'mir ma\'lumotlari mavjud emas'

    last_date = repair.get("last_updated_at")
    date_str = last_date.strftime("%Y-%m-%d %H:%M") if isinstance(last_date, datetime) else "Ma'lumot yo'q"
    repair_type = repair.get("repair_type_name_uz") or repair.get("repair_type_name", "")

    return f"{repair['locomotive_name']} lokomotivining oxirgi ta'miri: {repair_type} ({date_str})"


# ---------------------------------------------------------------------------
# 8. get_all_last_repairs
# ---------------------------------------------------------------------------
@function_tool
def get_all_last_repairs() -> str:
    """Barcha lokomotivlarning oxirgi ta'mirlari ro'yxati. Foydalaning: 'Oxirgi ta'mirlar ro'yxati', 'Barcha ta'mirlar'"""
    repairs = sql.list_last_repairs_all()
    return f"Jami {len(repairs)} ta lokomotivning oxirgi ta'mir ma'lumotlari mavjud"


# ---------------------------------------------------------------------------
# 9. search_locomotive_by_name
# ---------------------------------------------------------------------------
@function_tool
def search_locomotive_by_name(name: str) -> str:
    """Lokomotivni nomi bo'yicha qidirish. Agar noaniq raqam berilsa, o'xshash barcha lokomotivlarni topadi va variantlarni taklif qiladi.

    Args:
        name: Lokomotiv nomi yoki raqami. To'liq yoki qisman bo'lishi mumkin (masalan: 020, 0207, 1255)
    """
    matches = sql.search_locomotives(name)

    if not matches:
        return f'"{name}" raqamli lokomotiv topilmadi. Iltimos, raqamni to\'liq va to\'g\'ri kiriting.'

    if len(matches) == 1:
        return _format_detailed(matches[0])

    # Multiple matches — check for exact match first
    search_lower = name.strip().lower()
    exact = next(
        (m for m in matches if (m.get("locomotive_full_name") or "").lower() == search_lower),
        None,
    )
    if exact:
        return _format_detailed(exact)

    # Show list of options
    active_repairs = sql.list_active_repairs()
    lines = [
        f'⚠️ "{name}" so\'rovi bo\'yicha {len(matches)} ta o\'xshash lokomotiv topildi.',
        "",
        "Quyidagilardan birini tanlang:",
        "",
    ]
    for idx, m in enumerate(matches[:10], 1):
        state = _ts(m.get("state"))
        active = next(
            (r for r in active_repairs if r.get("locomotive_name") == m.get("locomotive_full_name", "").split(" ")[-1]),
            None,
        )
        if active:
            state = f"Tamirda ({active.get('repair_type_name_uz') or active.get('repair_type_name', '')})"
        lines.append(f"{idx}. **{m['locomotive_full_name']}** — {state}")

    lines.append("")
    lines.append(f'Aniq ma\'lumot olish uchun to\'liq raqamni yozing (masalan: "{matches[0]["locomotive_full_name"]}")')
    return "\n".join(lines)


def _format_detailed(loco: dict) -> str:
    """Format single locomotive with full details."""
    info = sql.get_locomotive_info(locomotive_id=loco["locomotive_id"])
    if not info:
        # Fallback to basic info
        return (
            f"🚂 **{loco['locomotive_full_name']}**\n"
            f"• Turi: {_tt(loco.get('locomotive_type'))}\n"
            f"• Holati: {_ts(loco.get('state'))}\n"
            f"• Joylashuvi: {loco.get('location_name')}\n"
            f"• Depo: {loco.get('organization_name')}"
        )

    # Check for active repair
    active_repairs = sql.list_active_repairs()
    loco_name_part = info["locomotive_full_name"].split(" ")[-1] if info["locomotive_full_name"] else ""
    active_repair = next(
        (r for r in active_repairs if r.get("locomotive_name") == loco_name_part),
        None,
    )

    # Check for last repair
    last_repairs = sql.list_last_repairs_all()
    last_repair = next(
        (r for r in last_repairs if r.get("locomotive_name") == loco_name_part),
        None,
    )

    lines = [
        f"🚂 **{info['locomotive_full_name']}**",
        "",
        "📍 **Asosiy ma'lumotlar:**",
        f"• Turi: {_tt(info.get('locomotive_type'))}",
        f"• Holati: {_ts(info.get('state'))}",
        f"• Joylashuvi: {info.get('location_name')}",
        f"• Depo: {info.get('organization_name')}",
    ]

    if active_repair:
        lines.append("")
        lines.append("🔧 **Hozirgi ta'mir:**")
        lines.append(f"• Turi: {active_repair.get('repair_type_name_uz') or active_repair.get('repair_type_name', '')}")

    if last_repair:
        lines.append("")
        lines.append("📋 **Oxirgi ta'mir:**")
        lines.append(f"• Turi: {last_repair.get('repair_type_name_uz') or last_repair.get('repair_type_name', '')}")
        last_date = last_repair.get("last_updated_at")
        date_str = last_date.strftime("%Y-%m-%d %H:%M") if isinstance(last_date, datetime) else "Ma'lumot yo'q"
        lines.append(f"• Sana: {date_str}")

    years = sorted(info.get("repair_counts_by_year", {}).keys(), reverse=True)
    if years:
        lines.append("")
        lines.append("📊 **Yillik ta'mir statistikasi:**")
        for year in years:
            year_data = info["repair_counts_by_year"][year]
            lines.append(f"• {year} yil: jami {year_data['total']} ta ta'mir")
            for t, c in year_data["counts"].items():
                lines.append(f"  - {t}: {c} ta")

    inspection_entries = list(info.get("inspection_details", {}).items())
    if inspection_entries:
        lines.append("")
        lines.append("🔧 **Tekshiruv ma'lumotlari:**")
        for key, value in inspection_entries:
            lines.append(f"• {key.strip()}: {value}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 10. get_locomotive_detailed_info
# ---------------------------------------------------------------------------
@function_tool
def get_locomotive_detailed_info(locomotive_name: str) -> str:
    """Aniq bir lokomotiv haqida batafsil ma'lumot olish: joylashuvi, deposi, ta'mir tarixi, yillik ta'mirlar soni va kelgusi tekshiruvlar.

    Args:
        locomotive_name: Lokomotiv raqami (masalan: 0406, 0204, 1255). Faqat raqamni kiriting.
    """
    info = sql.get_locomotive_info(locomotive_name=locomotive_name)
    if info:
        return _format_detailed_info(info)
    # Fallback to search
    return search_locomotive_by_name(name=locomotive_name)


def _format_detailed_info(info: dict) -> str:
    """Format locomotive detail dict into human-readable string."""
    lines = [
        f"🚂 **{info['locomotive_full_name']}**",
        "",
        "📍 **Asosiy ma'lumotlar:**",
        f"• Turi: {_tt(info.get('locomotive_type'))}",
        f"• Holati: {_ts(info.get('state'))}",
        f"• Joylashuvi: {info.get('location_name')}",
        f"• Depo: {info.get('organization_name')}",
    ]

    years = sorted(info.get("repair_counts_by_year", {}).keys(), reverse=True)
    if years:
        lines.append("")
        lines.append("📊 **Yillik ta'mir statistikasi:**")
        for year in years:
            year_data = info["repair_counts_by_year"][year]
            lines.append(f"• {year} yil: jami {year_data['total']} ta ta'mir")
            for t, c in year_data["counts"].items():
                lines.append(f"  - {t}: {c} ta")

    inspection_entries = list(info.get("inspection_details", {}).items())
    if inspection_entries:
        lines.append("")
        lines.append("🔧 **Tekshiruv ma'lumotlari:**")
        for key, value in inspection_entries:
            lines.append(f"• {key.strip()}: {value}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 11. get_current_inspections
# ---------------------------------------------------------------------------
@function_tool
def get_current_inspections() -> str:
    """Hozirda qanday tekshiruvlar bo'layotganini ko'rsatadi. Foydalaning: 'Hozir qancha lokomotiv tekshiruvda?', 'Joriy inspeksiyalar'"""
    inspections = sql.list_inspection_counts(active_only=True)
    active = [i for i in inspections if i["locomotive_count"] > 0]
    total = sum(i["locomotive_count"] for i in inspections)

    lines = [f"🔧 **Hozirda tekshiruvda: {total} ta lokomotiv**", ""]
    if not active:
        lines.append("Hozirda tekshiruvda lokomotiv yo'q.")
        return "\n".join(lines)
    for i in sorted(active, key=lambda x: x["locomotive_count"], reverse=True):
        lines.append(f"• {i.get('name_uz') or i.get('name')}: {i['locomotive_count']} ta")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 12. get_total_inspection_counts
# ---------------------------------------------------------------------------
@function_tool
def get_total_inspection_counts() -> str:
    """Umumiy tekshiruv statistikasi. Foydalaning: 'Umumiy tekshiruv statistikasi', 'Inspeksiya hisoboti'"""
    inspections = sql.list_inspection_counts(active_only=False)
    active = [i for i in inspections if i["locomotive_count"] > 0]
    total = sum(i["locomotive_count"] for i in inspections)

    lines = [f"📊 **Umumiy tekshiruv statistikasi (jami {total} ta):**", ""]
    for i in sorted(active, key=lambda x: x["locomotive_count"], reverse=True):
        lines.append(f"• {i.get('name_uz') or i.get('name')}: {i['locomotive_count']} ta ({_pct(i['locomotive_count'], total)})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 13. get_depo_info
# ---------------------------------------------------------------------------
@function_tool
def get_depo_info(depo_id: int) -> str:
    """SQL bazadagi depo bo'yicha faqat lokomotiv statistikasi. Brigada yoki xodim savollari uchun ishlatmang.

    Foydalaning: 'Andijon deposida nechta lokomotiv bor?', 'Buxoro deposidagi lokomotiv holatlari'

    Args:
        depo_id: SQL depo ID raqami (1-Angren, 2-Andijon, 3-Denov, 4-Qarshi, 5-Tinchlik, 6-Buxoro, 7-Miskin, 8-Qo'ng'irot, 9-Liniyada)
    """
    depo = sql.get_depo_info(depo_id)
    if not depo:
        return (
            f"{depo_id} raqamli SQL depo topilmadi. Mavjud depolar: "
            "1-Angren, 2-Andijon, 3-Denov, 4-Qarshi, 5-Tinchlik, 6-Buxoro, 7-Miskin, 8-Qo'ng'irot, 9-Liniyada."
        )
    return _render_depo_info(depo)


# ---------------------------------------------------------------------------
# 14. get_all_depos_info
# ---------------------------------------------------------------------------
@function_tool
def get_all_depos_info() -> str:
    """SQL bazadagi barcha depolar bo'yicha lokomotiv statistikasi. Brigada savollari uchun ishlatmang."""
    depos = sql.get_depo_info_all()
    total = sum(d["locomotive_count"] for d in depos)

    lines = [f"🏭 **Barcha depolar (jami {len(depos)} ta depo, {total} ta lokomotiv)**", ""]
    for depo in sorted(depos, key=lambda d: d["locomotive_count"], reverse=True):
        states = ", ".join(f"{_ts(s)}: {c}" for s, c in depo.get("state_counts", {}).items())
        lines.append(f"📍 **{depo['depo_name']}**: {depo['locomotive_count']} ta ({_pct(depo['locomotive_count'], total)})")
        lines.append(f"   └ {states}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 14a. get_depo_brigade_info
# ---------------------------------------------------------------------------
@function_tool
def get_depo_brigade_info(depo_query: str) -> str:
    """Depo bo'yicha brigadalar, xodimlar va brigada sonini olish. Depo nomi bilan ishlating.

    Foydalaning: 'Urganch deposida nechta brigada bor?', 'Buxoro depo brigadalari', 'Qongirot deposi brigada malumoti'
    """
    try:
        brigade_depo_id, depo_name, brigades = _get_brigade_summary_by_query(depo_query)
    except brigade_api.BrigadeApiError as exc:
        return f"Brigada datasetni o'qib bo'lmadi: {exc}"

    if brigade_depo_id is None or depo_name is None:
        return f'"{depo_query}" bo\'yicha brigada deposi topilmadi'

    if not brigades:
        return f"{depo_name} deposida brigadalar topilmadi"

    return _render_depo_brigade_info(depo_name, brigades)


# ---------------------------------------------------------------------------
# 14b. get_all_brigade_depos_info
# ---------------------------------------------------------------------------
@function_tool
def get_all_brigade_depos_info() -> str:
    """Barcha brigada depolari va ularning brigadalarini ko'rsatadi.

    ❗ MUHIM: Javobni HECH QACHON qisqartirmang! Barcha depolar va barcha brigadalarni TO'LIQ ko'rsating!

    Foydalaning: 'Nechta depo bor va ularning brigadalari', 'Barcha brigada depolari', 'Depolar va brigadalar'
    """
    try:
        depot_rows = []
        for depo_id, depo_name in sorted(brigade_api.BRIGADE_DEPOTS.items()):
            brigades = brigade_api.get_brigade_list(depo_id)
            depot_rows.append((depo_id, depo_name, brigades))
    except brigade_api.BrigadeApiError as exc:
        return f"Brigada datasetni o'qib bo'lmadi: {exc}"

    total_brigades = sum(len(brigades) for _, _, brigades in depot_rows)
    lines = [
        f"🏭 Brigada ma'lumoti mavjud depolar: {len(depot_rows)} ta",
        f"• Jami brigadalar: {total_brigades} ta",
    ]
    for depo_id, depo_name, brigades in depot_rows:
        total_members = sum(int(b.get("member_count", 0)) for b in brigades)
        total_working = sum(int(b.get("working_count", 0)) for b in brigades)
        total_resting = sum(int(b.get("resting_count", 0)) for b in brigades)
        total_other = sum(int(b.get("other_count", 0)) for b in brigades)
        lines.append("")
        lines.append(f"📍 {depo_name} (ID: {depo_id})")
        lines.append(f"• Brigadalar: {len(brigades)} ta")
        lines.append(f"• Jami mashinistlar: {total_members} ta")
        status_parts = [f"Aktiv: {total_working} ta", f"Dam olishda: {total_resting} ta"]
        if total_other:
            status_parts.append(f"Smenadan tashqari: {total_other} ta")
        lines.append(f"  {' | '.join(status_parts)}")
        for brigade in brigades:
            mc = int(brigade.get("member_count", 0))
            wc = int(brigade.get("working_count", 0))
            rc = int(brigade.get("resting_count", 0))
            oc = int(brigade.get("other_count", 0))
            lines.append(f"• Brigada #{brigade['id']}: {mc} ta")
            b_parts = [f"Aktiv: {wc}", f"Dam olishda: {rc}"]
            if oc:
                b_parts.append(f"Smenadan tashqari: {oc}")
            lines.append(f"  {' | '.join(b_parts)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 14c. get_depo_full_info
# ---------------------------------------------------------------------------
@function_tool
def get_depo_full_info(depo_query: str) -> str:
    """Depo haqida umumiy ma'lumot: mavjud bo'lsa SQL lokomotiv statistikasi va DasUtyAI brigada ma'lumoti.

    Foydalaning: 'Urganch deposi haqida malumot ber', 'Buxoro depo haqida', 'Qongirot deposi haqida'
    """
    sql_depo_id, sql_match_source = _resolve_sql_depo(depo_query, allow_numeric_fallback=False)
    brigade_depo_id, brigade_match_source = _resolve_brigade_depo(depo_query, allow_numeric_fallback=False)

    if sql_depo_id is None and brigade_depo_id is None:
        sql_depo_id, sql_match_source = _resolve_sql_depo(depo_query, allow_numeric_fallback=True)

    sql_depo = sql.get_depo_info(sql_depo_id) if sql_depo_id is not None else None

    if brigade_depo_id is None and sql_depo is not None:
        brigade_depo_id = _brigade_depo_id_for_sql_depo(sql_depo.get("depo_name"))
        if brigade_depo_id is not None:
            brigade_match_source = "mapped_from_sql"

    if sql_depo is None and brigade_depo_id is None:
        return f'"{depo_query}" bo\'yicha depo topilmadi'

    sections: list[str] = []

    if sql_depo is not None:
        sections.append(_render_depo_info(sql_depo))

    if brigade_depo_id is not None:
        try:
            brigades = brigade_api.get_brigade_list(brigade_depo_id)
        except brigade_api.BrigadeApiError as exc:
            sections.append(f"Brigada datasetni o'qib bo'lmadi: {exc}")
        else:
            brigade_depo_name = brigade_api.BRIGADE_DEPOTS.get(brigade_depo_id, f"Depo {brigade_depo_id}")
            sections.append(_render_depo_brigade_info(brigade_depo_name, brigades))
    elif brigade_match_source is None and sql_match_source == "name":
        sections.append("🚂 Bu depo uchun brigada datasetda mos yozuv topilmadi")

    return "\n\n".join(section for section in sections if section)


# ---------------------------------------------------------------------------
# 15. get_repair_stats_by_year
# ---------------------------------------------------------------------------
@function_tool
def get_repair_stats_by_year() -> str:
    """Yillar bo'yicha ta'mir statistikasi. Foydalaning: '2025 yilda qancha ta'mir bo'lgan?', 'Yillik ta'mir statistikasi'"""
    stats = sql.list_repair_stats_by_year()
    lines = ["📊 **Yillar bo'yicha ta'mir statistikasi:**", ""]
    for year_stat in stats:
        lines.append(f"📅 **{year_stat['year']} yil** (jami {year_stat['total_locomotives']} ta lokomotiv)")
        for repair_type, count in sorted(year_stat["repair_type_counts"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"   • {repair_type}: {count} ta")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 16. search_repair_docs
# ---------------------------------------------------------------------------
@function_tool
def search_repair_docs(query: str, locomotive_model: str | None = None) -> str:
    """Ta'mir qo'llanmalaridan qidirish. Lokomotiv ta'miri, texnik xizmat ko'rsatish (TXK-2), ehtiyot qismlar, ta'mir tartibi va texnik xususiyatlar haqida ma'lumot olish uchun ishlatiladi.

    Args:
        query: Qidirish so'rovi - ta'mir, texnik xizmat, ehtiyot qism yoki texnik xususiyat haqida savol (masalan: 'tormoz tizimini tekshirish tartibi')
        locomotive_model: Lokomotiv modeli nomi (ixtiyoriy). Masalan: 'ТЭМ2', 'ВЛ80С', '3ЭС5К', 'UZ-EL(R)', 'ТЭП70БС', '2UZ-EL(R)'.
    """
    results = rag.search(query, locomotive_model=locomotive_model, n_results=5)
    if not results:
        model_info = f" ({locomotive_model} modeli uchun)" if locomotive_model else ""
        return f'"{query}" bo\'yicha ta\'mir qo\'llanmalaridan{model_info} ma\'lumot topilmadi'

    lines = [f"Ta'mir qo'llanmalaridan {len(results)} ta natija topildi:"]
    for i, r in enumerate(results, 1):
        model = r["metadata"].get("locomotive_model") or "Noma'lum"
        section = r["metadata"].get("section_heading") or "Umumiy"
        score = round(1 - r["distance"], 3)
        lines.append(f"\n{i}. {model} - {section} (moslik: {score})")
        lines.append(r["text"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 17. get_brigade_list
# ---------------------------------------------------------------------------
@function_tool
def get_brigade_list(depo_id: int) -> str:
    """Brigada depo ID ma'lum bo'lsa, lokomotiv brigadalar ro'yxatini olish.

    Depo nomi bilan savol bo'lsa `get_depo_brigade_info` ishlatish afzal.

    Args:
        depo_id: Depo ID raqami (1-ТЧ-1 Узбекистан, 2-ТЧ-2 Коканд, 3-ТЧ-5 Тинчлик, 4-ТЧ-6 Бухара, 5-ТЧ-7 Кунград, 6-ТЧ-8 Карши, 7-ТЧ-9 Термез, 8-ТЧ-10 Ургенч)
    """
    try:
        brigades = brigade_api.get_brigade_list(depo_id)
    except brigade_api.BrigadeApiError as exc:
        return f"Brigada API ishlamayapti: {exc}"

    if not brigades:
        depo_name = brigade_api.BRIGADE_DEPOTS.get(depo_id, f"Depo {depo_id}")
        return f"{depo_name} deposida brigadalar topilmadi"

    depo_name = brigade_api.BRIGADE_DEPOTS.get(depo_id, f"Depo {depo_id}")
    lines = [f"🚂 {depo_name} deposidagi brigadalar ({len(brigades)} ta):"]
    for b in brigades:
        details = [f"a'zolar: {b.get('member_count', 0)} ta"]
        if b.get("active_count") is not None:
            details.append(f"aktiv: {b['active_count']} ta")
        if b.get("assigned_locomotive_count"):
            details.append(f"lokomotivlar: {b['assigned_locomotive_count']} ta")
        if b.get("instruktor_fio"):
            details.append(f"instruktor: {b['instruktor_fio']}")
        lines.append(f"• ID: {b['id']} — {b['name']} ({'; '.join(details)})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 18. get_machinists_on_locomotive
# ---------------------------------------------------------------------------
@function_tool
def get_machinists_on_locomotive(lok_nomer: str, lok_name: str | None = None) -> str:
    """Aniq bir lokomotivda hozir qaysi mashinistlar ishlayotganini ko'rsatadi.

    Args:
        lok_nomer: Lokomotiv raqami (masalan: 2469, 9205, 0406)
        lok_name: Lokomotiv modeli nomi (masalan: '3ВЛ-80С', 'Talgo-250', 'UZ-Y', 'ЭПЗД', 'ТЭМ-2'). Ixtiyoriy, natijani toraytiradi.
    """
    try:
        machinists = brigade_api.get_machinists_on_locomotive(lok_nomer, lok_name=lok_name)
    except brigade_api.BrigadeApiError as exc:
        return f"Brigada API ishlamayapti: {exc}"

    if not machinists:
        return f"{lok_nomer} lokomotivda hozir hech kim ishlamayapti yoki ma'lumot topilmadi"

    lname = machinists[0].get("lok_name") or lok_name or lok_nomer
    depo_name = machinists[0].get("depo_name")
    brigada_group_id = machinists[0].get("brigada_group_id")
    lines = [f"🚂 {lname} ({lok_nomer}) lokomotivdagi ekipaj:"]
    if depo_name:
        lines.append(f"• Depo: {depo_name}")
    if brigada_group_id:
        lines.append(f"• Brigada: #{brigada_group_id}")
    for m in machinists:
        mtype = _bm_type(m)
        mfio = _bm_name(m)
        line = f"• {mtype}: {mfio}"
        if m.get("status_id") != brigade_api.ACTIVE_STATUS_ID and _bm_status(m):
            line += f" ({_bm_status(m)})"
        lines.append(line)
        if m.get("phone"):
            lines.append(f"  📞 {m['phone']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 19. get_brigade_details
# ---------------------------------------------------------------------------
@function_tool
def get_brigade_details(brigada_group_id: int, depo_id: int | None = None) -> str:
    """Brigada (kolonna) tarkibi: a'zolar, holatlar va biriktirilgan lokomotivlar.

    Args:
        brigada_group_id: Brigada (kolonna) ID raqami. Avval get_brigade_list funksiyasidan brigada ID sini oling.
        depo_id: Ixtiyoriy depo ID. Bir xil brigada ID turli depolarda takrorlansa, aniq depoga toraytirish uchun bering.
    """
    try:
        members = brigade_api.get_brigade_details(brigada_group_id, depo_id=depo_id)
    except brigade_api.BrigadeApiError as exc:
        return f"Brigada API ishlamayapti: {exc}"

    if not members:
        if depo_id is not None:
            return f"Depo {depo_id} ichida brigada {brigada_group_id} topilmadi"
        return f"Brigada {brigada_group_id} da a'zolar topilmadi"

    working = [m for m in members if m.get("status_id") == brigade_api.ACTIVE_STATUS_ID]
    total_machinists = sum(1 for m in members if _bm_type(m) == "Mashinist")
    total_helpers = sum(1 for m in members if "yordamchi" in _bm_type(m).casefold())
    depo_name = next((m.get("depo_name") for m in members if m.get("depo_name")), None)
    instruktor = next((m.get("instruktor_fio") for m in members if m.get("instruktor_fio")), None)

    status_counts: dict[str, int] = {}
    for member in members:
        status = _bm_status(member)
        status_counts[status] = status_counts.get(status, 0) + 1

    locomotives = sorted({
        (m.get("lok_nomer"), m.get("lok_name"))
        for m in members
        if m.get("lok_nomer")
    })

    lines = [
        f"👥 Brigada #{brigada_group_id} tarkibi ({len(members)} ta a'zo):",
        f"• Mashinistlar: {total_machinists} ta",
        f"• Yordamchilar: {total_helpers} ta",
        f"• Aktiv: {len(working)} ta",
    ]
    if depo_id is not None:
        lines.append(f"• So'ralgan depo ID: {depo_id}")
    if depo_name:
        lines.append(f"• Depo: {depo_name}")
    if instruktor:
        lines.append(f"• Instruktor: {instruktor}")
    if status_counts:
        lines.append("• Holatlar: " + ", ".join(f"{name}: {count} ta" for name, count in status_counts.items()))
    if locomotives:
        lines.append("• Biriktirilgan lokomotivlar:")
        for lok_nomer, lok_name in locomotives[:10]:
            if lok_name:
                lines.append(f"  - {lok_name} ({lok_nomer})")
            else:
                lines.append(f"  - {lok_nomer}")
        if len(locomotives) > 10:
            lines.append(f"  - ... va yana {len(locomotives) - 10} ta")
    lines.append("• A'zolar:")
    for idx, member in enumerate(members[:15], 1):
        lok_info = ""
        if member.get("lok_nomer"):
            lok_info = f" | Lok: {member.get('lok_name', '')} ({member['lok_nomer']})"
        phone_info = f" | Tel: {member['phone']}" if member.get("phone") else ""
        lines.append(f"  - {idx}. {_bm_name(member)} — {_bm_type(member)} ({_bm_status(member)}){lok_info}{phone_info}")
    if len(members) > 15:
        lines.append(f"  - ... va yana {len(members) - 15} ta a'zo")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 20. refresh_brigade_dataset_cache
# ---------------------------------------------------------------------------
@function_tool
def refresh_brigade_dataset_cache() -> str:
    """DasUtyAI brigade dataset keshini yangilash. Foydalaning: 'Brigada ma'lumotlarini yangila', 'DasUtyAI cache refresh'"""
    try:
        result = brigade_api.refresh_dataset_cache()
    except brigade_api.BrigadeApiError as exc:
        return f"Brigada dataset yangilanmadi: {exc}"

    return (
        "Brigada dataset yangilandi: "
        f"{result['record_count']} ta yozuv, manba={result['source']}, vaqt={result['fetched_at']}"
    )


# ---------------------------------------------------------------------------
# 21. get_brigade_dataset_overview
# ---------------------------------------------------------------------------
@function_tool
def get_brigade_dataset_overview() -> str:
    """DasUtyAI dataset bo'yicha umumiy statistikani olish. Foydalaning: 'Brigada dataset statistikasi', 'DasUtyAI overview', 'Jami mashinistlar soni'"""
    try:
        overview = brigade_api.get_dataset_overview()
    except brigade_api.BrigadeApiError as exc:
        return f"Brigada datasetni o'qib bo'lmadi: {exc}"

    cache_status = overview.get("cache_status", {})
    source = cache_status.get("source") or "noma'lum"
    lines = [
        "📊 DasUtyAI brigade dataset umumiy ko'rinishi:",
        f"• Jami yozuvlar: {overview['total_records']} ta",
        f"• Aktiv xodimlar: {overview['active_records']} ta ({_pct(overview['active_records'], overview['total_records'])})",
        f"• Lokomotiv biriktirilganlar: {overview['with_locomotive']} ta ({_pct(overview['with_locomotive'], overview['total_records'])})",
        f"• Telefoni borlar: {overview['with_phone']} ta ({_pct(overview['with_phone'], overview['total_records'])})",
        f"• Rasmi borlar: {overview['with_image']} ta ({_pct(overview['with_image'], overview['total_records'])})",
        f"• Depolar: {overview['unique_depots']} ta",
        f"• Brigadalar: {overview['unique_brigades']} ta",
        f"• Biriktirilgan lokomotivlar: {overview['unique_locomotives']} ta",
        f"• Cache manbasi: {source}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 22. search_brigade_people
# ---------------------------------------------------------------------------
@function_tool
def search_brigade_people(
    query: str | None = None,
    depo_id: int | None = None,
    brigada_group_id: int | None = None,
    status_id: int | None = None,
    lok_nomer: str | None = None,
    lok_name: str | None = None,
    mashinist_type: str | None = None,
    assigned_only: bool | None = None,
    has_phone: bool | None = None,
    has_image: bool | None = None,
    is_active: bool | None = None,
    limit: int = 10,
) -> str:
    """DasUtyAI datasetdan xodimlarni qidirish (ro'yxat). Ism, familiya, telefon, depo, brigada, lokomotiv, status yoki tur bo'yicha qidiradi.

    ⚠️ MUHIM: Agar foydalanuvchi BITTA ANIQ SHAXS haqida to'liq ma'lumot so'rasa, bu tool emas, `get_brigade_person_details` ishlating!
    Bu tool faqat RO'YXAT ko'rish yoki FILTRLAB qidirish uchun.

    Args:
        query: Ism, familiya, telefon, ID, tabel, depo yoki boshqa matnli qidiruv
        depo_id: Depo ID si
        brigada_group_id: Brigada ID si
        status_id: Status ID si (0, 10, 11, 12, 13, 14)
        lok_nomer: Lokomotiv raqami
        lok_name: Lokomotiv modeli nomi
        mashinist_type: M, П, Mashinist, Mashinist yordamchisi
        assigned_only: True bo'lsa faqat lokomotiv biriktirilganlar
        has_phone: Telefoni bor/yo'qligi
        has_image: Rasmi bor/yo'qligi
        is_active: Aktiv yoki aktiv emas
        limit: Natija soni
    """
    try:
        records = brigade_api.search_records(
            query=query,
            depo_id=depo_id,
            brigada_group_id=brigada_group_id,
            status_id=status_id,
            lok_nomer=lok_nomer,
            lok_name=lok_name,
            mashinist_type=mashinist_type,
            assigned_only=assigned_only,
            has_phone=has_phone,
            has_image=has_image,
            is_active=is_active,
            limit=limit,
        )
    except (brigade_api.BrigadeApiError, ValueError) as exc:
        return f"Brigada dataset qidiruvi bajarilmadi: {exc}"

    if not records:
        return f"Qidiruv bo'yicha xodim topilmadi ({_format_filter_context(query=query, depo_id=depo_id, brigada_group_id=brigada_group_id, status_id=status_id, lok_nomer=lok_nomer, lok_name=lok_name, mashinist_type=mashinist_type, assigned_only=assigned_only, has_phone=has_phone, has_image=has_image, is_active=is_active)})"

    lines = [
        f"👥 Topilgan xodimlar: {len(records)} ta",
        f"• Filtr: {_format_filter_context(query=query, depo_id=depo_id, brigada_group_id=brigada_group_id, status_id=status_id, lok_nomer=lok_nomer, lok_name=lok_name, mashinist_type=mashinist_type, assigned_only=assigned_only, has_phone=has_phone, has_image=has_image, is_active=is_active)}",
    ]
    for idx, record in enumerate(records, 1):
        lines.extend(_format_brigade_member(record, idx=idx))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 23. count_brigade_people
# ---------------------------------------------------------------------------
@function_tool
def count_brigade_people(
    query: str | None = None,
    depo_id: int | None = None,
    brigada_group_id: int | None = None,
    status_id: int | None = None,
    lok_nomer: str | None = None,
    lok_name: str | None = None,
    mashinist_type: str | None = None,
    assigned_only: bool | None = None,
    has_phone: bool | None = None,
    has_image: bool | None = None,
    is_active: bool | None = None,
) -> str:
    """DasUtyAI dataset bo'yicha aniq hisob olish. Foydalaning: 'Qancha?', 'Nechta aktiv?', 'Nechta yordamchi bor?'"""
    try:
        total = brigade_api.count_records(
            query=query,
            depo_id=depo_id,
            brigada_group_id=brigada_group_id,
            status_id=status_id,
            lok_nomer=lok_nomer,
            lok_name=lok_name,
            mashinist_type=mashinist_type,
            assigned_only=assigned_only,
            has_phone=has_phone,
            has_image=has_image,
            is_active=is_active,
        )
    except brigade_api.BrigadeApiError as exc:
        return f"Brigada dataset hisobi bajarilmadi: {exc}"

    return f"🔢 Natija: {total} ta yozuv ({_format_filter_context(query=query, depo_id=depo_id, brigada_group_id=brigada_group_id, status_id=status_id, lok_nomer=lok_nomer, lok_name=lok_name, mashinist_type=mashinist_type, assigned_only=assigned_only, has_phone=has_phone, has_image=has_image, is_active=is_active)})"


# ---------------------------------------------------------------------------
# 24. group_brigade_people
# ---------------------------------------------------------------------------
@function_tool
def group_brigade_people(
    group_by: str,
    query: str | None = None,
    depo_id: int | None = None,
    brigada_group_id: int | None = None,
    status_id: int | None = None,
    lok_nomer: str | None = None,
    lok_name: str | None = None,
    mashinist_type: str | None = None,
    assigned_only: bool | None = None,
    has_phone: bool | None = None,
    has_image: bool | None = None,
    is_active: bool | None = None,
    limit: int = 10,
) -> str:
    """DasUtyAI datasetni guruhlab statistikani chiqarish.

    Args:
        group_by: depo_name, depo_id, brigada_group_id, brigade_name, status_name, status_id, mashinist_type_name, mashinist_type_code, lok_name, lok_nomer, position_id, instruktor_fio, has_locomotive, has_phone, has_image, is_active
    """
    try:
        groups = brigade_api.group_records(
            group_by,
            query=query,
            depo_id=depo_id,
            brigada_group_id=brigada_group_id,
            status_id=status_id,
            lok_nomer=lok_nomer,
            lok_name=lok_name,
            mashinist_type=mashinist_type,
            assigned_only=assigned_only,
            has_phone=has_phone,
            has_image=has_image,
            is_active=is_active,
            limit=limit,
        )
    except (brigade_api.BrigadeApiError, ValueError) as exc:
        return f"Guruhlangan statistika olinmadi: {exc}"

    if not groups:
        return "Guruhlash uchun ma'lumot topilmadi"

    total = sum(item["count"] for item in groups)
    lines = [
        f"📊 {group_by} bo'yicha taqsimot:",
        f"• Filtr: {_format_filter_context(query=query, depo_id=depo_id, brigada_group_id=brigada_group_id, status_id=status_id, lok_nomer=lok_nomer, lok_name=lok_name, mashinist_type=mashinist_type, assigned_only=assigned_only, has_phone=has_phone, has_image=has_image, is_active=is_active)}",
    ]
    for item in groups:
        lines.append(f"• {item['group']}: {item['count']} ta ({_pct(item['count'], total)})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 25. get_brigade_person_details
# ---------------------------------------------------------------------------
@function_tool
def get_brigade_person_details(query: str) -> str:
    """BITTA ANIQ SHAXS haqida TO'LIQ PROFIL olish: shaxsiy ma'lumotlar + ish holati (smena) + ishga chiqish soni (EMM) + lokomotiv + brigada.

    Foydalanuvchi ism/familiya/ID/tabel bo'yicha bitta xodim haqida so'rasa DOIM shu tool ishlating.
    Bu tool barcha 4 ta API endpointdan ma'lumot yig'ib beradi."""
    try:
        matches = brigade_api.get_person_details(query)
    except brigade_api.BrigadeApiError as exc:
        return f"Xodim ma'lumotini olib bo'lmadi: {exc}"

    if not matches:
        return f'"{query}" bo\'yicha xodim topilmadi'

    exact = next(
        (
            member for member in matches
            if str(member.get("id")) == query
            or str(member.get("tabelnum")) == query
            or (_bm_name(member).casefold() == query.strip().casefold())
        ),
        None,
    )

    if exact is None and len(matches) > 1:
        lines = [f'"{query}" bo\'yicha {len(matches)} ta o\'xshash xodim topildi:']
        for idx, member in enumerate(matches[:10], 1):
            lines.extend(_format_brigade_member(member, idx=idx))
        if len(matches) > 10:
            lines.append(f"... va yana {len(matches) - 10} ta")
        return "\n".join(lines)

    member = exact or matches[0]
    person_id = member.get("id")
    tabelnum = member.get("tabelnum")

    # --- Photo URL marker (will be picked up by chainlit for display) ---
    image_url = member.get("image_url")

    # --- Basic profile from MashinistListInfo ---
    lines = [
        f"👤 {_bm_name(member)}",
    ]
    if image_url:
        lines.append(f"[PHOTO_URL:{image_url}]")
    lines += [
        "",
        "📋 **Shaxsiy ma'lumotlar:**",
        f"• ID: {person_id}",
        f"• Tabel raqami: {tabelnum}",
    ]
    if member.get("birthday"):
        lines.append(f"• Tug'ilgan sana: {member['birthday'][:10]}")
    if member.get("phone"):
        lines.append(f"• Telefon: {member['phone']}")
    else:
        lines.append("• Telefon: yo'q")

    lines.append("")
    lines.append("🏢 **Ish joyi:**")
    lines.append(f"• Lavozim (asosiy): {_bm_type(member)}")
    main_type = member.get("main_type_id")
    if main_type is not None:
        type_label = "Mashinist" if main_type == 1 else ("Pomoshnik" if main_type == 2 else ("Instruktor" if main_type == 3 else f"ID: {main_type}"))
        lines.append(f"• Asosiy lavozim turi: {type_label}")
    lines.append(f"• Status: {_bm_status(member)}")
    if member.get("depo_name"):
        lines.append(f"• Depo: {member['depo_name']} (ID: {member.get('depo_id')})")
    if _bm_brigade(member):
        lines.append(f"• Brigada: {_bm_brigade(member)}")
    if member.get("instruktor_fio"):
        lines.append(f"• Instruktor: {member['instruktor_fio']}")
    if member.get("lok_nomer") or member.get("lok_name"):
        lok_label = member.get("lok_name") or "Lokomotiv"
        if member.get("lok_nomer"):
            lines.append(f"• Biriktirilgan lokomotiv: {lok_label} ({member['lok_nomer']})")
        else:
            lines.append(f"• Biriktirilgan lokomotiv: {lok_label}")
    else:
        lines.append("• Biriktirilgan lokomotiv: yo'q")

    # --- WorkInfo: current shift status ---
    try:
        work_records = brigade_api.get_work_info()
        person_work = [r for r in work_records if r.get("id") == person_id]
        if person_work:
            w = person_work[0]
            ws = w.get("work_status", 0)
            ws_name = brigade_api.WORK_STATUS_NAMES.get(ws, f"Noma'lum ({ws})")
            mash_type = w.get("mashinist_type_id")
            main_t = w.get("main_type_id")

            lines.append("")
            lines.append("⏰ **Hozirgi ish holati:**")
            lines.append(f"• Smena holati: {ws_name}")
            if main_t is not None and mash_type is not None and main_t != mash_type:
                m_label = "Mashinist" if mash_type == 1 else ("Pomoshnik" if mash_type == 2 else "Instruktor")
                lines.append(f"• Hozirgi ishdagi lavozim: {m_label} (asosiy lavozimdan farq qiladi)")
            if w.get("lok_name") or w.get("lok_nomer"):
                lok_str = w.get("lok_name") or ""
                if w.get("lok_nomer"):
                    lok_str += f" ({w['lok_nomer']})"
                if w.get("type_name"):
                    lok_str += f" [{w['type_name']}]"
                lines.append(f"• Ishlayotgan lokomotiv: {lok_str}")
            # Show leave_diff (dam olish davomiyligi) only if resting
            if ws == 1:
                leave_d = w.get("leave_diff")
                if isinstance(leave_d, dict):
                    days = leave_d.get("days", 0)
                    hours = leave_d.get("hours", 0)
                    mins = leave_d.get("minutes", 0)
                    if days:
                        lines.append(f"• Dam olish davomiyligi: {days} kun {hours} soat {mins} min")
                    else:
                        lines.append(f"• Dam olish davomiyligi: {hours} soat {mins} min")
            # Show come_diff (ishda bo'lgan vaqt) only if working
            if ws == 2:
                come_d = w.get("come_diff")
                if isinstance(come_d, dict):
                    days = come_d.get("days", 0)
                    hours = come_d.get("hours", 0)
                    mins = come_d.get("minutes", 0)
                    if days:
                        lines.append(f"• Ishda bo'lgan vaqt: {days} kun {hours} soat {mins} min")
                    else:
                        lines.append(f"• Ishda bo'lgan vaqt: {hours} soat {mins} min")
    except Exception:
        pass

    # --- CountEmm: how many times worked (cumulative total) ---
    try:
        emm_records = brigade_api.get_count_emm_info()
        person_emm = [r for r in emm_records if r.get("id") == person_id]
        if person_emm:
            total_emm = sum(r.get("count_emm", 0) for r in person_emm)
            lines.append("")
            lines.append(f"📊 **Ishga chiqish soni (2026-yil boshidan jami):** {total_emm} marta")
            for er in sorted(person_emm, key=lambda x: x.get("count_emm", 0), reverse=True):
                lok = er.get("lok_name") or "Noma'lum"
                nomer = er.get("lok_nomer") or ""
                cnt = er.get("count_emm", 0)
                lines.append(f"  • {lok} {nomer}: {cnt} marta")
    except Exception:
        pass

    # --- MedFullData: match by mashinist_fio ---
    try:
        med_records = brigade_api.get_med_full_data()
        fio = _normalize_fio(_bm_name(member))
        person_med = [r for r in med_records if _normalize_fio(r.get("mashinist_fio") or "") == fio]
        if person_med:
            # Sort by date descending
            person_med.sort(key=lambda x: x.get("create_date", ""), reverse=True)
            total_med = len(person_med)
            healthy = sum(1 for r in person_med if r.get("allow_work") == 1)
            sick = sum(1 for r in person_med if r.get("allow_work") == 2)
            alcohol_found = sum(1 for r in person_med if str(r.get("alcohol")) == "2")
            lines.append("")
            lines.append(f"🏥 **Tibbiy ko'rik tarixi:** jami {total_med} ta ko'rik")
            lines.append(f"  Sog'lom: {healthy} | Kasal: {sick} | Alkogol aniqlangan: {alcohol_found}")
            # Show last 3 checkups
            lines.append("  Oxirgi ko'riklar:")
            for r in person_med[:3]:
                date_str = (r.get("create_date") or "")[:16].replace("T", " ")
                allow = "✅ Sog'lom" if r.get("allow_work") == 1 else "❌ Kasal"
                alc = "🍺 Alkogol!" if str(r.get("alcohol")) == "2" else ""
                doctor = r.get("create_user_name") or ""
                medpunkt = r.get("medpunkt_name") or ""
                symptom = r.get("symptom") or ""
                pulse = r.get("pulse") or ""
                temp = r.get("temperature") or ""
                after = "Ishdan keyin" if r.get("after_work") is False else "Ishdan oldin"
                detail_parts = [f"{date_str}", allow]
                if alc:
                    detail_parts.append(alc)
                detail_parts.append(after)
                if pulse:
                    detail_parts.append(f"Puls: {pulse}")
                if temp:
                    detail_parts.append(f"Harorat: {temp}")
                if symptom:
                    detail_parts.append(f"Belgi: {symptom}")
                if doctor:
                    detail_parts.append(f"Shifokor: {doctor}")
                lines.append(f"    • {' | '.join(detail_parts)}")
        else:
            lines.append("")
            lines.append("🏥 **Tibbiy ko'rik:** Bu shaxs bo'yicha tibbiy ko'rik ma'lumoti topilmadi")
    except Exception:
        pass

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 26. get_mashinist_work_info
# ---------------------------------------------------------------------------
@function_tool
def get_mashinist_work_info(
    depo_id: int = 0,
    mashinist_type_id: int = 0,
    status_id: int = 0,
    working_type: int = 0,
    date_filter: str = "",
) -> str:
    """Mashinistlarning ish holati ma'lumotlarini olish: smenada yoki dam olishda, ishga kelish/ketish vaqtlari, leave_diff, come_diff.

    ❗ "Kecha ishga chiqqanlar", "bugun ishga chiqqanlar", "15-mart kuni ishga chiqqanlar" — SHU TOOL ishlatilsin!
    ❗ date_filter bilan em_come_date bo'yicha sanaga filtr qo'yiladi.

    mashinist_type_id: 0=barchasi. Ishdagi lavozim bo'yicha filter.
    working_type (work_status): 0=barchasi, 1=dam olishda, 2=ishda, 3=marshrut ochilmagan.

    Izoh:
    - work_status: 1=dam olishda, 2=ishda, 3=marshrut ochilmagan
    - em_come_date = asosiy yavka (ishni boshlash vaqti)
    - leave_diff = oxirgi dam olishdan hozirgacha bo'lgan vaqt
    - come_diff = oxirgi ishga chiqqan vaqtdan hozirgacha bo'lgan vaqt

    Args:
        depo_id: Brigada depo ID (0=barchasi, 1-8)
        mashinist_type_id: 0=barchasi. Ishdagi lavozim filtri.
        status_id: 0=barchasi, 10=aktiv
        working_type: 0=barchasi, 1=dam olishda, 2=ishda, 3=marshrut ochilmagan
        date_filter: Sana filtri (format: 2026-03-15). em_come_date shu sanadan boshlangan yozuvlar qaytariladi. "kecha"=kechagi sana.
    """
    try:
        records = brigade_api.get_work_info(
            mashinist_type_id=mashinist_type_id,
            status_id=status_id,
            depo_id=depo_id,
            working_type=working_type,
        )
    except brigade_api.BrigadeApiError as exc:
        return f"Ish holati ma'lumotlarini olib bo'lmadi: {exc}"

    if not records:
        return "Berilgan filtr bo'yicha ish holati ma'lumotlari topilmadi"

    # Date filtering on em_come_date
    if date_filter:
        records = [r for r in records if (r.get("em_come_date") or "").startswith(date_filter)]
        if not records:
            return f"{date_filter} sanasida ishga chiqqan mashinistlar topilmadi"

    work_status_names = brigade_api.WORK_STATUS_NAMES

    def _fmt_diff(diff_obj) -> str:
        """Format leave_diff/come_diff object to readable string."""
        if diff_obj is None:
            return "-"
        if isinstance(diff_obj, dict):
            days = diff_obj.get("days", 0)
            hours = diff_obj.get("hours", 0)
            minutes = diff_obj.get("minutes", 0)
            if days:
                return f"{days} kun {hours} soat {minutes} min"
            return f"{hours} soat {minutes} min"
        return str(diff_obj)

    # Cross-reference depo info from MashinistListInfo (records)
    try:
        all_records = brigade_api.get_dataset()
        id_to_depo = {r["id"]: r.get("depo_name", "Noma'lum") for r in all_records}
    except Exception:
        id_to_depo = {}

    # Group by work_status
    by_status: dict[int, list[dict]] = {}
    for r in records:
        ws = r.get("work_status", 0)
        by_status.setdefault(ws, []).append(r)

    lines = [f"👷 Mashinistlar ish holati: jami {len(records)} ta"]

    for ws in sorted(by_status.keys()):
        group = by_status[ws]
        ws_name = work_status_names.get(ws, f"Noma'lum ({ws})")
        lines.append(f"\n📋 **{ws_name}**: {len(group)} ta")

        # Show depo breakdown
        from collections import Counter
        depo_counts = Counter(id_to_depo.get(r.get("id"), "Noma'lum") for r in group)
        if depo_counts:
            lines.append("  Depo bo'yicha:")
            for depo_name, cnt in depo_counts.most_common():
                lines.append(f"  • {depo_name}: {cnt} ta")

        # Show sample people (max 10)
        lines.append("")
        for r in group[:10]:
            fio = f"{r.get('last_name', '')} {r.get('first_name', '')} {r.get('second_name', '')}".strip()
            em_come = r.get("em_come_date") or "-"
            r3_come = r.get("r3_come_date") or "-"
            leave_date = r.get("leave_date") or "-"
            leave_d = _fmt_diff(r.get("leave_diff"))
            come_d = _fmt_diff(r.get("come_diff"))
            lok = r.get("lok_name") or ""
            lok_n = r.get("lok_nomer") or ""
            type_name = r.get("type_name") or ""
            type_short = r.get("type_shortname") or ""
            main_type = r.get("main_type_id")
            mash_type = r.get("mashinist_type_id")
            birthday = r.get("birthday") or ""

            mid = r.get("id") or ""
            tabel = r.get("tabelnum") or ""
            phone = r.get("phone") or ""
            status = r.get("status_name") or ""
            depo = id_to_depo.get(r.get("id"), "")

            line = f"• {fio} (ID: {mid}, Tabel: {tabel})"
            details = []
            if depo:
                details.append(f"Depo: {depo}")
            if type_short:
                if main_type != mash_type:
                    details.append(f"Asosiy: {'M' if main_type == 1 else 'P'}, Ishdagi: {'M' if mash_type == 1 else 'P'}")
                else:
                    details.append(f"Lavozim: {type_short}")
            if status:
                details.append(f"Status: {status}")
            if phone:
                details.append(f"Tel: {phone}")
            if lok:
                lok_str = lok
                if lok_n:
                    lok_str += f" ({lok_n})"
                if type_name:
                    lok_str += f" [{type_name}]"
                details.append(f"Lokomotiv: {lok_str}")
            if em_come != "-":
                details.append(f"Yavka: {em_come}")
            if r3_come != "-" and r3_come != em_come:
                details.append(f"R3 yavka: {r3_come}")
            if leave_date != "-":
                details.append(f"Ketish: {leave_date}")
            if leave_d != "-":
                details.append(f"Dam olishdan: {leave_d}")
            if come_d != "-":
                details.append(f"Ishga chiqqanidan: {come_d}")
            if birthday:
                details.append(f"Tug'ilgan: {birthday[:10]}")
            if details:
                line += f"\n  {' | '.join(details)}"
            lines.append(line)
        if len(group) > 10:
            lines.append(f"  ... va yana {len(group) - 10} ta")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 27. get_mashinist_emm_count
# ---------------------------------------------------------------------------
@function_tool
def get_mashinist_emm_count(
    depo_id: int = 0,
    mashinist_type_id: int = 0,
    brigada_group_id: int = 0,
    from_date: str = "",
    to_date: str = "",
    mashinist_name: str = "",
) -> str:
    """Mashinistlar necha marta ishga chiqqanini ko'rsatadi (EMM soni).

    Sana bo'yicha filtrlanadi! from_date/to_date bilan oylik, haftalik, kunlik ma'lumot olish mumkin.
    from_date/to_date bo'lmasa — 2026-yil boshidan bugungi kungacha JAMI (keshdan).
    ❗ "Kecha ishga chiqqanlar" uchun get_mashinist_work_info(date_filter=...) ishlating!
    ❗ brigada_group_id bilan aniq brigada a'zolarining EMM hisobini ko'rish mumkin!
    ❗ mashinist_name bilan aniq shaxs bo'yicha EMM hisobini ko'rish mumkin!

    Foydalaning: 'Yanvar oyida kim necha marta ishga chiqqan?', 'Mart oyidagi EMM hisobi', 'Eng ko'p ishga chiqqan mashinistlar', '13-brigada jami necha marta ishladi?', 'Jamolov yanvar oyida necha marta ishlagan?'

    Args:
        depo_id: Brigada depo ID (0=barchasi, 1-8)
        mashinist_type_id: 0=barchasi
        brigada_group_id: Brigada ID (0=barchasi). Brigada a'zolarining EMM hisobini ko'rish uchun.
        from_date: Boshlanish sanasi (format: 2026-01-01T00:00:00). Bo'sh = boshidan.
        to_date: Tugash sanasi (format: 2026-03-18T23:59:59). Bo'sh = bugunga qadar.
        mashinist_name: Mashinist ismi (familiyasi yoki to'liq FIO). Bo'sh = barchasi.
    """
    try:
        records = brigade_api.get_count_emm_info(
            mashinist_type_id=mashinist_type_id,
            depo_id=depo_id,
            brigada_group_id=brigada_group_id,
            from_date=from_date,
            to_date=to_date,
        )
    except brigade_api.BrigadeApiError as exc:
        return f"EMM hisob ma'lumotlarini olib bo'lmadi: {exc}"

    if not records:
        return "EMM ma'lumotlari topilmadi"

    # Filter by mashinist name if provided
    if mashinist_name:
        name_lower = mashinist_name.lower()
        records = [
            r for r in records
            if name_lower in f"{(r.get('last_name') or '')} {(r.get('first_name') or '')} {(r.get('second_name') or '')}".lower()
        ]
        if not records:
            return f"'{mashinist_name}' ismli mashinist EMM ma'lumotlari topilmadi"

    # Aggregate per person (sum across all locomotives)
    from collections import defaultdict
    person_agg: dict[int, dict] = {}
    person_loks: dict[int, list] = defaultdict(list)
    for r in records:
        pid = r.get("id")
        cnt = r.get("count_emm", 0)
        if pid not in person_agg:
            person_agg[pid] = {
                "fio": f"{r.get('last_name', '')} {r.get('first_name', '')} {r.get('second_name', '')}".strip(),
                "id": pid,
                "tabelnum": r.get("tabelnum") or "",
                "type_shortname": r.get("type_shortname") or "",
                "total": 0,
            }
        person_agg[pid]["total"] += cnt
        lok = r.get("lok_name") or ""
        lok_n = r.get("lok_nomer") or ""
        if lok or lok_n:
            lok_str = lok
            if lok_n:
                lok_str += f" ({lok_n})"
            person_loks[pid].append((lok_str, cnt))

    persons_sorted = sorted(person_agg.values(), key=lambda p: p["total"], reverse=True)

    total_emm = sum(p["total"] for p in persons_sorted)
    if from_date or to_date:
        fd = from_date[:10] if from_date else "2026-01-01"
        td = to_date[:10] if to_date else "bugun"
        period_label = f"{fd} — {td}"
    else:
        period_label = "2026-yil boshidan bugungi kungacha jami"
    lines = [
        f"📊 EMM hisobi ({period_label}): {len(persons_sorted)} ta mashinist, jami {total_emm} marta ishga chiqish",
    ]

    for p in persons_sorted[:20]:
        pid = p["id"]
        line = f"• {p['fio']} (ID: {pid}, Tabel: {p['tabelnum']}) [{p['type_shortname']}]: jami {p['total']} marta"
        lines.append(line)
        # Show locomotive breakdown
        loks = sorted(person_loks.get(pid, []), key=lambda x: x[1], reverse=True)
        for lok_str, cnt in loks[:5]:
            lines.append(f"  — {lok_str}: {cnt} marta")
        if len(loks) > 5:
            lines.append(f"  — ... va yana {len(loks) - 5} ta lokomotiv")

    if len(persons_sorted) > 20:
        lines.append(f"... va yana {len(persons_sorted) - 20} ta mashinist")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 28. get_mashinist_med_info
# ---------------------------------------------------------------------------
@function_tool
def get_mashinist_med_info(
    from_date: str = "",
    to_date: str = "",
    depo_id: int = 0,
    mashinist_type_id: int = 0,
    allow_work: int = 0,
    after_work: int = 0,
    alcohol: int = 0,
    brigada_group_id: int = 0,
    mashinist_name: str = "",
) -> str:
    """Mashinistlarning tibbiy ko'rik natijalarini olish: sog'lom/kasal, alkogol test, ishdan oldin/keyin ko'rik.

    ❗ MUHIM: Ma'lumotlar keshda 2026-01-01 dan bugungi kungacha saqlangan. from_date/to_date bo'sh qoldirilsa barcha kesh ma'lumotlari qaytariladi.
    ❗ Bu yozuvlar KO'RIK SONINI ko'rsatadi, ODAM SONINI emas! Bir mashinist kuniga 2 marta ko'rikdan o'tishi mumkin.
    ❗ mashinist_fio maydoni orqali ANIQ SHAXS va BRIGADA bo'yicha filtrlab bo'ladi!

    allow_work: 0=barchasi, 1=sog'lom (ishga ruxsat), 2=kasal (ishga ruxsat yo'q). "O'tolmagan" = 2.
    after_work: 0=barchasi, 1=ishdan oldin ko'rik, 2=ishdan keyin ko'rik
    alcohol: 0=barchasi, 1=alkogol aniqlanmadi, 2=alkogol aniqlandi

    Foydalaning: 'Tibbiy ko'rik natijalari', 'Kim kasal?', 'Alkogol aniqlangan', 'Alkogol test', '13-brigada tibbiy ko'rikdan o'tganmi?', 'Мирзаев tibbiy ko'rik tarixi', 'O\'tolmagan mashinistlar'

    Args:
        from_date: Boshlanish sanasi (ixtiyoriy), format: 2026-01-01T00:00:00. Bo'sh = kesh boshidan.
        to_date: Tugash sanasi (ixtiyoriy), format: 2026-03-16T23:59:59. Bo'sh = kesh oxirigacha.
        depo_id: Brigada depo ID (0=barchasi, 1-8)
        mashinist_type_id: 0=barchasi
        allow_work: 0=barchasi, 1=sog'lom, 2=kasal (o'tolmagan)
        after_work: 0=barchasi, 1=ishdan oldin, 2=ishdan keyin
        alcohol: 0=barchasi, 1=alkogol aniqlanmadi, 2=alkogol aniqlandi
        brigada_group_id: Brigada ID (0=barchasi). Brigada a'zolarining tibbiy ko'riklarini ko'rish uchun.
        mashinist_name: Mashinist ismi bo'yicha qidirish (to'liq yoki qisman). Masalan: "Мирзаев" yoki "Мирзаев Акбар"
    """
    try:
        records = brigade_api.get_med_full_data(
            mashinist_type_id=mashinist_type_id,
            depo_id=depo_id,
            from_date=from_date,
            to_date=to_date,
            allow_work=allow_work,
            after_work=after_work,
        )
    except brigade_api.BrigadeApiError as exc:
        return f"Tibbiy ma'lumotlarni olib bo'lmadi: {exc}"

    if not records:
        return "Berilgan filtr bo'yicha tibbiy ko'rik ma'lumotlari topilmadi"

    # Filter by brigade: find brigade member names, then filter med records
    if brigada_group_id:
        try:
            all_people = brigade_api.get_dataset()
            brigade_members = [r for r in all_people if r.get("brigada_group_id") == brigada_group_id]
            if depo_id:
                brigade_members = [r for r in brigade_members if r.get("depo_id") == depo_id]
            member_names = {
                _normalize_fio(f"{r.get('last_name', '')} {r.get('first_name', '')} {r.get('second_name', '')}")
                for r in brigade_members
            }
            records = [r for r in records if _normalize_fio(r.get("mashinist_fio") or "") in member_names]
        except Exception:
            pass

    # Filter by alcohol
    if alcohol:
        records = [r for r in records if str(r.get("alcohol")) == str(alcohol)]

    # Filter by mashinist name
    if mashinist_name:
        q = mashinist_name.strip().casefold()
        records = [r for r in records if q in (r.get("mashinist_fio") or "").casefold()]

    if not records:
        return "Berilgan filtr bo'yicha tibbiy ko'rik ma'lumotlari topilmadi"

    allow_work_names = brigade_api.ALLOW_WORK_NAMES
    alcohol_names = brigade_api.ALCOHOL_NAMES

    # Determine actual date range for display
    date_label_from = from_date[:10] if from_date else "2026-01-01"
    date_label_to = to_date[:10] if to_date else datetime.now().strftime("%Y-%m-%d")

    # Summary stats
    total = len(records)
    healthy = sum(1 for r in records if r.get("allow_work") == 1)
    sick = sum(1 for r in records if r.get("allow_work") == 2)
    alcohol_clean = sum(1 for r in records if str(r.get("alcohol")) == "1")
    alcohol_detected = sum(1 for r in records if str(r.get("alcohol")) == "2")
    before_work_cnt = sum(1 for r in records if r.get("after_work") is True)
    after_work_cnt = sum(1 for r in records if r.get("after_work") is False)

    # Determine output mode
    is_filtered = bool(brigada_group_id or mashinist_name)
    is_problem_query = bool(allow_work == 2 or alcohol == 2)

    # For problem queries (kasal/alkogol) without person/brigade filter — simplified output
    if is_problem_query and not is_filtered:
        # Cross-reference with dataset for depo info
        try:
            all_people = brigade_api.get_dataset()
            fio_to_info: dict[str, dict] = {}
            for p in all_people:
                norm = _normalize_fio(f"{p.get('last_name', '')} {p.get('first_name', '')} {p.get('second_name', '')}")
                fio_to_info[norm] = {
                    "depo_name": p.get("depo_name") or "",
                    "depo_id": p.get("depo_id"),
                    "brigada_group_id": p.get("brigada_group_id"),
                }
        except Exception:
            fio_to_info = {}

        # Group by depo → unique people (use normalized FIO for uniqueness)
        from collections import defaultdict
        depo_people: dict[str, set[str]] = defaultdict(set)
        depo_records: dict[str, list] = defaultdict(list)
        # Keep best display name per normalized FIO
        norm_to_display: dict[str, str] = {}
        for r in records:
            fio_raw = (r.get("mashinist_fio") or "").strip()
            fio_norm = _normalize_fio(fio_raw)
            if fio_norm not in norm_to_display:
                norm_to_display[fio_norm] = _clean_fio_display(fio_raw)
            info = fio_to_info.get(fio_norm, {})
            depo = info.get("depo_name") or r.get("depo_name") or "Noma'lum"
            depo_people[depo].add(fio_norm)
            depo_records[depo].append((r, info))

        total_unique = sum(len(v) for v in depo_people.values())

        if depo_id:
            # Specific depo — show full person list
            problem_label = "kasal (o'tolmagan)" if allow_work == 2 else "alkogol aniqlangan"
            lines = [
                f"📊📍 Tibbiy ko'rikdan {problem_label} mashinistlar",
                "",
            ]
            for depo in sorted(depo_people.keys()):
                unique_fios = depo_people[depo]
                lines.append(f"📍 **{depo}**: {len(unique_fios)} ta mashinist")
                lines.append("")

                # Group records by person (normalized FIO), show latest per person
                from collections import defaultdict as _dd
                person_recs: dict[str, list[dict]] = _dd(list)
                person_info: dict[str, dict] = {}
                for r, info in depo_records[depo]:
                    fio_norm = _normalize_fio((r.get("mashinist_fio") or "").strip())
                    person_recs[fio_norm].append(r)
                    person_info[fio_norm] = info

                for fio_norm in sorted(person_recs.keys()):
                    p_recs = sorted(person_recs[fio_norm], key=lambda x: x.get("create_date", ""), reverse=True)
                    fio_display = norm_to_display.get(fio_norm, fio_norm)
                    bg = person_info[fio_norm].get("brigada_group_id")
                    bg_str = f" (Brigada #{bg})" if bg else ""
                    latest = p_recs[0]
                    date_str = (latest.get("create_date") or "")[:16].replace("T", " ")
                    symptom = latest.get("symptom") or ""
                    doctor = latest.get("create_user_name") or ""
                    medpunkt = latest.get("medpunkt_name") or ""
                    pulse = latest.get("pulse")
                    temp = latest.get("temperature")

                    lines.append(f"  • **{fio_display}**{bg_str}")
                    lines.append(f"    Sana: {date_str}")
                    med_parts = []
                    if pulse:
                        med_parts.append(f"Puls: {pulse}")
                    if temp:
                        med_parts.append(f"Harorat: {temp}°C")
                    if med_parts:
                        lines.append(f"    {' | '.join(med_parts)}")
                    if symptom:
                        lines.append(f"    Sabab: {symptom}")
                    lines.append(f"    Shifokor: {doctor} | Joy: {medpunkt}")
                lines.append("")

            lines.append(f"👥 Jami: {total_unique} ta mashinist")
        else:
            # No specific depo — summary only
            problem_label = "o'tolmagan" if allow_work == 2 else "alkogol aniqlangan"
            lines = [
                f"📊📍 Tibbiy ko'rikdan {problem_label} mashinistlar soni depolar bo'yicha",
                "",
            ]
            for depo in sorted(depo_people.keys()):
                lines.append(f"{depo}: {len(depo_people[depo])} ta mashinist")
            lines.append("")
            lines.append(f"Jami: {total_unique} ta mashinist")
            lines.append("")
            lines.append("ℹ️ Aniq depo bo'yicha batafsil mashinistlar ro'yxati uchun depo nomini ayting.")

        return "\n".join(lines)

    lines = [
        f"🏥 Tibbiy ko'rik natijalari ({date_label_from} — {date_label_to}): jami {total} ta ko'rik yozuvi",
        "",
        "📊 **Umumiy natija (ko'rik soni, odam soni emas!):**",
        f"  Sog'lom: {healthy} ta | Kasal: {sick} ta | Alkogol aniqlangan: {alcohol_detected} ta",
        f"  Ishdan oldin: {before_work_cnt} ta | Ishdan keyin: {after_work_cnt} ta",
    ]

    # If filtered by brigade or person — show per-person grouped view
    if is_filtered:
        from collections import defaultdict
        by_person: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            fio = (r.get("mashinist_fio") or "Noma'lum").strip()
            by_person[fio].append(r)

        lines.append("")
        lines.append(f"👥 **Shaxslar bo'yicha:** {len(by_person)} ta mashinist")

        for fio in sorted(by_person.keys()):
            p_recs = sorted(by_person[fio], key=lambda x: x.get("create_date", ""), reverse=True)
            p_total = len(p_recs)
            p_healthy = sum(1 for r in p_recs if r.get("allow_work") == 1)
            p_sick = sum(1 for r in p_recs if r.get("allow_work") == 2)
            p_alc = sum(1 for r in p_recs if str(r.get("alcohol")) == "2")
            mtype = p_recs[0].get("mashinist_type_name") or ""

            status_parts = [f"Sog'lom: {p_healthy}"]
            if p_sick:
                status_parts.append(f"❌ Kasal: {p_sick}")
            if p_alc:
                status_parts.append(f"🍺 Alkogol: {p_alc}")

            lines.append(f"")
            lines.append(f"• **{fio}** ({mtype}) — {p_total} ta ko'rik ({' | '.join(status_parts)})")

            # Show last checkup with full details
            r = p_recs[0]
            date_str = (r.get("create_date") or "")[:16].replace("T", " ")
            allow = "✅ Sog'lom" if r.get("allow_work") == 1 else "❌ Kasal"
            alc = " | 🍺 Alkogol!" if str(r.get("alcohol")) == "2" else ""
            after = "Ishdan oldin" if r.get("after_work") is True else "Ishdan keyin"
            doctor = r.get("create_user_name") or ""
            medpunkt = r.get("medpunkt_name") or ""
            pulse = r.get("pulse")
            temp = r.get("temperature")
            symptom = r.get("symptom") or ""

            lines.append(f"  Oxirgi ko'rik: {date_str} | {allow}{alc} | {after}")
            med_parts = []
            if pulse:
                med_parts.append(f"Puls: {pulse}")
            if temp:
                med_parts.append(f"Harorat: {temp}°C")
            if med_parts:
                lines.append(f"  {' | '.join(med_parts)}")
            if symptom:
                lines.append(f"  Belgilar: {symptom}")
            lines.append(f"  Shifokor: {doctor}")
            if medpunkt:
                lines.append(f"  Joy: {medpunkt}")
    else:
        # General view (no problem filter, no person/brigade filter) — show overall stats
        unique_people = {(r.get("mashinist_fio") or "").strip() for r in records if r.get("mashinist_fio")}
        if unique_people:
            lines.append("")
            lines.append(f"👥 Jami {len(unique_people)} ta noyob mashinist ko'rikdan o'tgan")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 31. update_brigade_dataset_cache
# ---------------------------------------------------------------------------
@function_tool
def update_brigade_dataset_cache() -> str:
    """Datasetni yangilash (incremental update). Mavjud keshga yangi ma'lumotlarni qo'shadi.

    MashinistListInfo va WorkInfo — to'liq yangilanadi.
    CountEmm va MedFullData — oxirgi 7 kunlik yangi yozuvlar qo'shiladi (eskilari saqlanadi).

    Foydalaning: 'Yangilab ber', 'Update qil', 'Ma'lumotlarni yangila'"""
    try:
        result = brigade_api.update_dataset_cache()
    except brigade_api.BrigadeApiError as exc:
        return f"Dataset yangilashda xatolik: {exc}"

    return (
        f"✅ Dataset yangilandi (incremental):\n"
        f"• Xodimlar: {result['record_count']} ta\n"
        f"• Ish holati: {result['work_info_count']} ta\n"
        f"• EMM hisob: {result['count_emm_count']} ta\n"
        f"• Tibbiy ko'rik: {result['med_data_count']} ta\n"
        f"• Yangilangan: {result['fetched_at']}"
    )


# ---------------------------------------------------------------------------
# All tools list (for agent registration)
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    get_total_locomotives_count,
    get_locomotives_by_state,
    get_stats,
    get_locomotive_types,
    get_locomotive_models,
    get_active_repairs,
    get_locomotive_last_repair,
    get_all_last_repairs,
    search_locomotive_by_name,
    get_locomotive_detailed_info,
    get_current_inspections,
    get_total_inspection_counts,
    get_depo_info,
    get_all_depos_info,
    get_depo_brigade_info,
    get_all_brigade_depos_info,
    get_depo_full_info,
    get_repair_stats_by_year,
    search_repair_docs,
    get_brigade_list,
    get_machinists_on_locomotive,
    get_brigade_details,
    refresh_brigade_dataset_cache,
    get_brigade_dataset_overview,
    search_brigade_people,
    count_brigade_people,
    group_brigade_people,
    get_brigade_person_details,
    get_mashinist_work_info,
    get_mashinist_emm_count,
    get_mashinist_med_info,
    update_brigade_dataset_cache,
]
