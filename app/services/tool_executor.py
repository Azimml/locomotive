from __future__ import annotations

from datetime import datetime

from . import locomotive_service as loco


class ToolExecutorService:
    def execute_function(self, function_name: str, args: dict) -> dict:
        match function_name:
            case "get_total_locomotives_count":
                return self.get_total_locomotives_count()
            case "get_locomotives_by_state":
                return self.get_locomotives_by_state(args.get("state"))
            case "get_stats":
                return self.get_stats()
            case "get_locomotive_types":
                return self.get_locomotive_types()
            case "get_locomotive_models":
                return self.get_locomotive_models()
            case "get_active_repairs":
                return self.get_active_repairs()
            case "get_locomotive_last_repair":
                return self.get_locomotive_last_repair(args.get("locomotive_name"))
            case "get_all_last_repairs":
                return self.get_all_last_repairs()
            case "search_locomotive_by_name":
                return self.search_locomotive_by_name(args.get("name"))
            case "get_locomotive_detailed_info":
                return self.get_locomotive_detailed_info(args.get("locomotive_name"))
            case "get_current_inspections":
                return self.get_current_inspections()
            case "get_total_inspection_counts":
                return self.get_total_inspection_counts()
            case "get_depo_info":
                return self.get_depo_info(args.get("depo_id"))
            case "get_all_depos_info":
                return self.get_all_depos_info()
            case "get_repair_stats_by_year":
                return self.get_repair_stats_by_year()
            case _:
                return {
                    "success": False,
                    "data": None,
                    "summary": f"Noma'lum funksiya: {function_name}",
                }

    def get_total_locomotives_count(self) -> dict:
        stats = loco.get_stats()
        return {
            "success": True,
            "data": {"total": stats["total_locomotives"]},
            "summary": f"Jami lokomotivlar soni: {stats['total_locomotives']} ta",
        }

    def get_locomotives_by_state(self, state: str | None) -> dict:
        stats = loco.get_stats()

        if state == "all":
            state_details = [
                {"state": self.translate_state(sc["state"]), "count": sc["count"]}
                for sc in stats["state_counts"]
            ]
            return {
                "success": True,
                "data": {
                    "total": stats["total_locomotives"],
                    "states": state_details,
                },
                "summary": self.format_states_summary(stats),
            }

        state_count = next(
            (sc for sc in stats["state_counts"] if sc["state"] == state), None
        )
        translated_state = self.translate_state(state)

        if state_count:
            percentage = (state_count["count"] / stats["total_locomotives"]) * 100
            return {
                "success": True,
                "data": {
                    "state": translated_state,
                    "count": state_count["count"],
                    "total": stats["total_locomotives"],
                    "percentage": f"{percentage:.1f}",
                },
                "summary": f"{translated_state} holatidagi lokomotivlar: {state_count['count']} ta (jami {stats['total_locomotives']} tadan {percentage:.1f}%)",
            }

        return {"success": False, "data": None, "summary": f'"{state}" holati topilmadi'}

    def get_stats(self) -> dict:
        stats = loco.get_stats()
        return {
            "success": True,
            "data": {
                "total_locomotives": stats["total_locomotives"],
                "total_models": stats["total_models"],
                "state_counts": [
                    {
                        "state": self.translate_state(sc["state"]),
                        "state_code": sc["state"],
                        "count": sc["count"],
                    }
                    for sc in stats["state_counts"]
                ],
            },
            "summary": self.format_full_stats_summary(stats),
        }

    def get_locomotive_types(self) -> dict:
        types = loco.list_locomotive_types()
        active_types = [t for t in types if t["locomotive_count"] > 0]
        return {
            "success": True,
            "data": [
                {
                    "type": self.translate_locomotive_type(t["locomotive_type"]),
                    "type_code": t["locomotive_type"],
                    "count": t["locomotive_count"],
                }
                for t in active_types
            ],
            "summary": self.format_types_summary(active_types),
        }

    def get_locomotive_models(self) -> dict:
        models = loco.list_locomotive_models()
        return {
            "success": True,
            "data": [
                {
                    "name": m["name"],
                    "type": self.translate_locomotive_type(m["locomotive_type"]),
                    "count": m["locomotive_count"],
                }
                for m in models
            ],
            "summary": self.format_models_summary(models),
        }

    def get_active_repairs(self) -> dict:
        repairs = loco.list_active_repairs()
        return {
            "success": True,
            "data": {
                "count": len(repairs),
                "repairs": [
                    {
                        "locomotive_name": r["locomotive_name"],
                        "repair_type": r["repair_type_name_uz"] or r["repair_type_name"],
                    }
                    for r in repairs
                ],
            },
            "summary": self.format_active_repairs_summary(repairs),
        }

    def get_locomotive_last_repair(self, locomotive_name: str | None) -> dict:
        repair = loco.get_last_repair(None, locomotive_name)
        if not repair:
            return {
                "success": False,
                "data": None,
                "summary": f'"{locomotive_name}" raqamli lokomotiv topilmadi yoki ta\'mir ma\'lumotlari mavjud emas',
            }

        last_date = (
            datetime.fromisoformat(str(repair["last_updated_at"]))
            if repair["last_updated_at"]
            else None
        )
        last_date_str = (
            last_date.strftime("%Y-%m-%d %H:%M") if last_date else "Ma'lumot yo'q"
        )

        return {
            "success": True,
            "data": {
                "locomotive_name": repair["locomotive_name"],
                "repair_type": repair["repair_type_name_uz"] or repair["repair_type_name"],
                "last_updated": repair["last_updated_at"],
            },
            "summary": f"{repair['locomotive_name']} lokomotivining oxirgi ta'miri: {repair['repair_type_name_uz'] or repair['repair_type_name']} ({last_date_str})",
        }

    def get_all_last_repairs(self) -> dict:
        repairs = loco.list_last_repairs_all()
        return {
            "success": True,
            "data": {
                "count": len(repairs),
                "repairs": [
                    {
                        "locomotive_name": r["locomotive_name"],
                        "repair_type": r["repair_type_name_uz"] or r["repair_type_name"],
                        "last_updated": r["last_updated_at"],
                    }
                    for r in repairs[:20]
                ],
            },
            "summary": f"Jami {len(repairs)} ta lokomotivning oxirgi ta'mir ma'lumotlari mavjud",
        }

    def search_locomotive_by_name(self, name: str | None) -> dict:
        locomotives = loco.list_locomotives()
        active_repairs = loco.list_active_repairs()
        all_last_repairs = loco.list_last_repairs_all()

        search_term = (name or "").strip().lower()

        exact_match = next(
            (l for l in locomotives if (l.get("locomotive_full_name") or "").lower() == search_term),
            None,
        )
        if exact_match:
            return self.get_detailed_locomotive_info(
                exact_match, active_repairs, all_last_repairs
            )

        partial_matches = []
        for l in locomotives:
            if not l.get("locomotive_full_name") or not name:
                continue
            loc_name = l["locomotive_full_name"].lower()
            if search_term in loc_name or loc_name in search_term:
                partial_matches.append(l)
                continue
            if loc_name.endswith(search_term) or search_term.endswith(loc_name):
                partial_matches.append(l)
                continue
            if search_term in loc_name.split(" ") or search_term in loc_name.split("-"):
                partial_matches.append(l)

        if len(partial_matches) == 0:
            return {
                "success": False,
                "data": {"query": name, "matches": []},
                "summary": f'"{name}" raqamli lokomotiv topilmadi. Iltimos, lokomotiv raqamini to\'liq va to\'g\'ri kiriting yoki boshqa raqamni sinab ko\'ring.',
            }

        if len(partial_matches) == 1:
            return self.get_detailed_locomotive_info(
                partial_matches[0], active_repairs, all_last_repairs
            )

        matches_with_details = []
        for l in partial_matches[:10]:
            active_repair = next(
                (r for r in active_repairs if r["locomotive_name"] == l["locomotive_full_name"]),
                None,
            )
            last_repair = next(
                (r for r in all_last_repairs if r["locomotive_name"] == l["locomotive_full_name"]),
                None,
            )
            matches_with_details.append(
                {
                    "name": l["locomotive_full_name"],
                    "state": self.translate_state(l["state"]),
                    "state_code": l["state"],
                    "current_repair": active_repair["repair_type_name_uz"]
                    if active_repair
                    else None,
                    "last_repair": last_repair["repair_type_name_uz"]
                    if last_repair
                    else None,
                }
            )

        return {
            "success": True,
            "data": {
                "query": name,
                "multiple_matches": True,
                "total_matches": len(partial_matches),
                "matches": matches_with_details,
            },
            "summary": self.format_multiple_matches_summary(name, matches_with_details),
        }

    def get_detailed_locomotive_info(self, locomotive: dict, active_repairs: list, all_last_repairs: list) -> dict:
        active_repair = next(
            (r for r in active_repairs if r["locomotive_name"] == locomotive["locomotive_full_name"]),
            None,
        )
        last_repair = next(
            (r for r in all_last_repairs if r["locomotive_name"] == locomotive["locomotive_full_name"]),
            None,
        )

        enriched = dict(locomotive)
        enriched["current_repair"] = (
            {
                "type": active_repair.get("repair_type_name_uz")
                or active_repair.get("repair_type_name"),
            }
            if active_repair
            else None
        )
        enriched["last_repair"] = (
            {
                "type": last_repair.get("repair_type_name_uz")
                or last_repair.get("repair_type_name"),
                "date": last_repair.get("last_updated_at"),
            }
            if last_repair
            else None
        )

        return {
            "success": True,
            "data": enriched,
            "summary": self.format_locomotive_detailed_info(enriched),
        }

    def get_locomotive_detailed_info(self, locomotive_name: str | None) -> dict:
        info = loco.get_locomotive_info(None, locomotive_name)
        if info:
            return {
                "success": True,
                "data": info,
                "summary": self.format_locomotive_detailed_info(info),
            }
        return self.search_locomotive_by_name(locomotive_name)

    def get_current_inspections(self) -> dict:
        inspections = loco.list_inspection_counts(active_only=True)
        active_inspections = [i for i in inspections if i["locomotive_count"] > 0]
        total = sum(i["locomotive_count"] for i in inspections)
        return {
            "success": True,
            "data": {"total": total, "inspections": active_inspections},
            "summary": self.format_current_inspections(active_inspections, total),
        }

    def get_total_inspection_counts(self) -> dict:
        inspections = loco.list_inspection_counts(active_only=False)
        active_inspections = [i for i in inspections if i["locomotive_count"] > 0]
        total = sum(i["locomotive_count"] for i in inspections)
        return {
            "success": True,
            "data": {"total": total, "inspections": active_inspections},
            "summary": self.format_total_inspection_counts(active_inspections, total),
        }

    def get_depo_info(self, depo_id: int | None) -> dict:
        if depo_id is None:
            return {
                "success": False,
                "data": None,
                "summary": "Depo ID kiritilmadi",
            }
        depo = loco.get_depo_info(depo_id)
        if not depo:
            return {
                "success": False,
                "data": None,
                "summary": f"{depo_id} raqamli depo topilmadi. Mavjud depolar: 1-Chuqursoy, 2-Andijon, 3-Termez, 4-Qarshi, 5-Tinchlik, 6-Buxoro, 7-Urganch, 8-Qo'ng'irot.",
            }
        return {"success": True, "data": depo, "summary": self.format_depo_info(depo)}

    def get_all_depos_info(self) -> dict:
        depos = loco.get_depo_info_all()
        total_locomotives = sum(d["locomotive_count"] for d in depos)
        return {
            "success": True,
            "data": {
                "total_depos": len(depos),
                "total_locomotives": total_locomotives,
                "depos": depos,
            },
            "summary": self.format_all_depos_info(depos, total_locomotives),
        }

    def get_repair_stats_by_year(self) -> dict:
        stats = loco.list_repair_stats_by_year()
        return {"success": True, "data": stats, "summary": self.format_repair_stats_by_year(stats)}

    def translate_state(self, state: str | None) -> str:
        translations = {
            "in_use": "Foydalanishda",
            "in_inspection": "Tamirda",
            "in_reserve": "Rezervda",
        }
        if state is None:
            return "Unknown"
        return translations.get(state, state)

    def translate_locomotive_type(self, type_value: str | None) -> str:
        translations = {
            "electric_loco": "Elektrovoz",
            "diesel_loco": "Teplovoz",
            "electric_train": "Elektropoyezd",
            "high_speed": "Yuqori tezlikli poyezd",
            "carriage": "Vagon",
        }
        if type_value is None:
            return "Unknown"
        return translations.get(type_value, type_value)

    def format_multiple_matches_summary(self, query: str | None, matches: list) -> str:
        lines = [
            f"⚠️ \"{query}\" so'rovi bo'yicha {len(matches)} ta o'xshash lokomotiv topildi.",
            "",
            "Quyidagilardan birini tanlang:",
            "",
        ]
        for idx, m in enumerate(matches, start=1):
            status = m["state"]
            if m.get("current_repair"):
                status = f"Tamirda ({m['current_repair']})"
            lines.append(f"{idx}. **{m['name']}** — {status}")
        lines.append("")
        if matches:
            lines.append(
                f"Aniq ma'lumot olish uchun to'liq raqamni yozing (masalan: \"{matches[0]['name']}\")"
            )
        return "\n".join(lines)

    def format_detailed_locomotive_info(self, locomotive: dict, active_repair: dict | None, last_repair: dict | None) -> str:
        lines = [f"🚂 **Lokomotiv: {locomotive['locomotive_full_name']}**", ""]
        lines.append(f"📍 **Holati:** {self.translate_state(locomotive['state'])}")
        if active_repair:
            lines.append("")
            lines.append("🔧 **Hozirgi ta'mir:**")
            lines.append(
                f"   • Turi: {active_repair.get('repair_type_name_uz') or active_repair.get('repair_type_name')}"
            )
        if last_repair:
            last_date = last_repair.get("last_updated_at")
            lines.append("")
            lines.append("📋 **Oxirgi ta'mir:**")
            lines.append(
                f"   • Turi: {last_repair.get('repair_type_name_uz') or last_repair.get('repair_type_name')}"
            )
            lines.append(f"   • Sana: {last_date if last_date else 'Noma\'lum'}")
        return "\n".join(lines)

    def format_states_summary(self, stats: dict) -> str:
        lines = [f"Jami lokomotivlar: {stats['total_locomotives']} ta"]
        for sc in stats["state_counts"]:
            percentage = (sc["count"] / stats["total_locomotives"]) * 100
            lines.append(
                f"• {self.translate_state(sc['state'])}: {sc['count']} ta ({percentage:.1f}%)"
            )
        return "\n".join(lines)

    def format_full_stats_summary(self, stats: dict) -> str:
        lines = [
            "📊 Umumiy statistika:",
            f"• Jami lokomotivlar: {stats['total_locomotives']} ta",
            f"• Jami modellar: {stats['total_models']} ta",
            "",
            "📈 Holat bo'yicha taqsimot:",
        ]
        for sc in stats["state_counts"]:
            percentage = (sc["count"] / stats["total_locomotives"]) * 100
            lines.append(
                f"• {self.translate_state(sc['state'])}: {sc['count']} ta ({percentage:.1f}%)"
            )
        return "\n".join(lines)

    def format_types_summary(self, types: list) -> str:
        total = sum(t["locomotive_count"] for t in types)
        lines = [f"🚂 Lokomotiv turlari (jami {total} ta):"]
        for t in types:
            percentage = (t["locomotive_count"] / total) * 100 if total else 0
            lines.append(
                f"• {self.translate_locomotive_type(t['locomotive_type'])}: {t['locomotive_count']} ta ({percentage:.1f}%)"
            )
        return "\n".join(lines)

    def format_models_summary(self, models: list) -> str:
        total_count = sum(m["locomotive_count"] for m in models)
        lines = [
            f"🚂 Lokomotiv modellari (jami {len(models)} ta model, {total_count} ta lokomotiv):"
        ]
        top_models = sorted(models, key=lambda m: m["locomotive_count"], reverse=True)[:10]
        for m in top_models:
            lines.append(
                f"• {m['name']} ({self.translate_locomotive_type(m['locomotive_type'])}): {m['locomotive_count']} ta"
            )
        if len(models) > 10:
            lines.append(f"... va yana {len(models) - 10} ta model")
        return "\n".join(lines)

    def format_active_repairs_summary(self, repairs: list) -> str:
        if len(repairs) == 0:
            return "Hozirda tamirda bo'lgan lokomotiv yo'q"
        lines = [f"🔧 Hozirda tamirda: {len(repairs)} ta lokomotiv", "", "Ta'mir turlari bo'yicha:"]
        repair_types: dict[str, int] = {}
        for r in repairs:
            type_name = r.get("repair_type_name_uz") or r.get("repair_type_name")
            repair_types[type_name] = repair_types.get(type_name, 0) + 1
        for type_name, count in repair_types.items():
            lines.append(f"• {type_name}: {count} ta")
        return "\n".join(lines)

    def format_locomotive_detailed_info(self, info: dict) -> str:
        lines = [
            f"🚂 **{info['locomotive_full_name']}**",
            "",
            "📍 **Asosiy ma'lumotlar:**",
            f"• Turi: {self.translate_locomotive_type(info.get('locomotive_type'))}",
            f"• Holati: {self.translate_state(info.get('state'))}",
            f"• Joylashuvi: {info.get('location_name')}",
            f"• Depo: {info.get('organization_name')}",
        ]

        if info.get("current_repair"):
            lines.append("")
            lines.append("🔧 **Hozirgi ta'mir:**")
            lines.append(f"• Turi: {info['current_repair'].get('type')}")

        if info.get("last_repair"):
            lines.append("")
            lines.append("📋 **Oxirgi ta'mir:**")
            lines.append(f"• Turi: {info['last_repair'].get('type')}")
            last_repair_date = info["last_repair"].get("date") or "Ma'lumot yo'q"
            lines.append(f"• Sana: {last_repair_date}")

        years = sorted(info.get("repair_counts_by_year", {}).keys(), reverse=True)
        if years:
            lines.append("")
            lines.append("📊 **Yillik ta'mir statistikasi:**")
            for year in years:
                year_data = info["repair_counts_by_year"][year]
                lines.append(f"• {year} yil: jami {year_data['total']} ta ta'mir")
                counts = "\n".join([f"  - {t}: {c} ta" for t, c in year_data["counts"].items()])
                lines.append(counts)

        inspection_entries = list(info.get("inspection_details", {}).items())
        if inspection_entries:
            lines.append("")
            lines.append("🔧 **Tekshiruv ma'lumotlari:**")
            for key, value in inspection_entries:
                lines.append(f"• {key.strip()}: {value}")
        return "\n".join(lines)

    def format_current_inspections(self, inspections: list, total: int) -> str:
        lines = [f"🔧 **Hozirda tekshiruvda: {total} ta lokomotiv**", ""]
        if len(inspections) == 0:
            lines.append("Hozirda tekshiruvda lokomotiv yo'q.")
            return "\n".join(lines)
        sorted_list = sorted(inspections, key=lambda i: i["locomotive_count"], reverse=True)
        for i in sorted_list:
            lines.append(f"• {i.get('name_uz') or i.get('name')}: {i['locomotive_count']} ta")
        return "\n".join(lines)

    def format_total_inspection_counts(self, inspections: list, total: int) -> str:
        lines = [f"📊 **Umumiy tekshiruv statistikasi (jami {total} ta):**", ""]
        sorted_list = sorted(inspections, key=lambda i: i["locomotive_count"], reverse=True)
        for i in sorted_list:
            percentage = (i["locomotive_count"] / total) * 100 if total else 0
            lines.append(
                f"• {i.get('name_uz') or i.get('name')}: {i['locomotive_count']} ta ({percentage:.1f}%)"
            )
        return "\n".join(lines)

    def format_depo_info(self, depo: dict) -> str:
        lines = [
            f"🏭 **{depo['depo_name']}**",
            "",
            "📊 **Umumiy ma'lumot:**",
            f"• Jami lokomotivlar: {depo['locomotive_count']} ta",
        ]
        type_entries = list(depo.get("locomotive_type_counts", {}).items())
        if type_entries:
            lines.append("")
            lines.append("🚂 **Lokomotiv turlari:**")
            for type_name, count in type_entries:
                percentage = (count / depo["locomotive_count"]) * 100 if depo["locomotive_count"] else 0
                lines.append(
                    f"• {self.translate_locomotive_type(type_name)}: {count} ta ({percentage:.1f}%)"
                )
        state_entries = list(depo.get("state_counts", {}).items())
        if state_entries:
            lines.append("")
            lines.append("📍 **Holat bo'yicha:**")
            for state, count in state_entries:
                percentage = (count / depo["locomotive_count"]) * 100 if depo["locomotive_count"] else 0
                lines.append(
                    f"• {self.translate_state(state)}: {count} ta ({percentage:.1f}%)"
                )
        return "\n".join(lines)

    def format_all_depos_info(self, depos: list, total_locomotives: int) -> str:
        lines = [
            f"🏭 **Barcha depolar (jami {len(depos)} ta depo, {total_locomotives} ta lokomotiv)**",
            "",
        ]
        sorted_list = sorted(depos, key=lambda d: d["locomotive_count"], reverse=True)
        for depo in sorted_list:
            percentage = (depo["locomotive_count"] / total_locomotives) * 100 if total_locomotives else 0
            states = ", ".join(
                [f"{self.translate_state(s)}: {c}" for s, c in depo.get("state_counts", {}).items()]
            )
            lines.append(
                f"📍 **{depo['depo_name']}**: {depo['locomotive_count']} ta ({percentage:.1f}%)"
            )
            lines.append(f"   └ {states}")
        return "\n".join(lines)

    def format_repair_stats_by_year(self, stats: list) -> str:
        lines = ["📊 **Yillar bo'yicha ta'mir statistikasi:**", ""]
        sorted_list = sorted(stats, key=lambda s: s["year"], reverse=True)
        for year_stat in sorted_list:
            lines.append(
                f"📅 **{year_stat['year']} yil** (jami {year_stat['total_locomotives']} ta lokomotiv)"
            )
            repair_entries = sorted(year_stat["repair_type_counts"].items(), key=lambda i: i[1], reverse=True)
            for repair_type, count in repair_entries:
                lines.append(f"   • {repair_type}: {count} ta")
            lines.append("")
        return "\n".join(lines)
