"""DasUtyAI brigade dataset client and query helpers."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import json
import logging
import os
import time
from typing import Any

import requests
import urllib3

from ..config import settings

# External API uses a self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

BRIGADE_DEPOTS: dict[int, str] = {
    1: "ТЧ-1 Узбекистан",
    2: "ТЧ-2 Коканд",
    3: "ТЧ-5 Тинчлик",
    4: "ТЧ-6 Бухара",
    5: "ТЧ-7 Кунград",
    6: "ТЧ-8 Карши",
    7: "ТЧ-9 Термез",
    8: "ТЧ-10 Ургенч",
}

MASHINIST_TYPES: dict[str, str] = {
    "М": "Mashinist",
    "П": "Mashinist yordamchisi",
}

STATUS_NAMES: dict[int, str] = {
    0: "Saqlangan",
    10: "Aktiv",
    11: "Komandirovka",
    12: "Kasallik varaqasi",
    13: "Ta'til",
    14: "Ishdan bo'shatilgan",
}

GROUP_BY_FIELDS: tuple[str, ...] = (
    "depo_id",
    "depo_name",
    "brigada_group_id",
    "brigade_name",
    "status_id",
    "status_name",
    "mashinist_type_code",
    "mashinist_type_name",
    "lok_name",
    "lok_nomer",
    "position_id",
    "instruktor_fio",
    "has_locomotive",
    "has_phone",
    "has_image",
    "is_active",
)

GROUP_BY_ALIASES: dict[str, str] = {
    "type": "mashinist_type_name",
    "mashinist_type": "mashinist_type_name",
    "brigade": "brigada_group_id",
    "depo": "depo_name",
    "status": "status_name",
    "locomotive": "lok_name",
}

WORK_STATUS_NAMES: dict[int, str] = {
    1: "Dam olishda",
    2: "Ishda",
    3: "Marshrut ochilmagan (dam olishda)",
}

ALLOW_WORK_NAMES: dict[int, str] = {
    1: "Sog'lom (ishga ruxsat)",
    2: "Kasal (ishga ruxsat yo'q)",
}

ALCOHOL_NAMES: dict[int, str] = {
    1: "Alkogol aniqlanmadi",
    2: "Alkogol aniqlandi",
}

ACTIVE_STATUS_ID = 10
LIST_CACHE_TTL_SECONDS = 60.0

CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "j",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "x",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sh",
    "ъ": "",
    "ы": "i",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "ў": "o",
    "ғ": "g",
    "қ": "q",
    "ҳ": "h",
}


# ---------------------------------------------------------------------------
# Auth and response caches
# ---------------------------------------------------------------------------

class BrigadeApiError(RuntimeError):
    """Raised when the brigade external API cannot be used."""


_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}
_list_cache: dict[tuple[int, int, int, int], dict[str, Any]] = {}
_dataset_cache: dict[str, Any] = {
    "records": None,       # MashinistListInfo (normalized)
    "work_info": None,     # MashinistWorkInfo (raw)
    "count_emm": None,     # MashinistCountEmmInfo (raw)
    "med_data": None,      # EmmMedFullData (raw)
    "loaded": False,
    "fetched_at": None,
    "source": None,
}


def _parse_expiry(expiry_date: str | None) -> float:
    if not expiry_date:
        return time.time() + 23 * 3600
    try:
        # Subtract a minute to avoid reusing a token at the boundary.
        return datetime.fromisoformat(expiry_date).timestamp() - 60
    except ValueError:
        return time.time() + 23 * 3600


def _get_token(force_refresh: bool = False) -> str:
    if force_refresh:
        _token_cache["token"] = None
        _token_cache["expires_at"] = 0.0

    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now:
        return str(_token_cache["token"])

    auth_url = f"{settings.BRIGADE_API_URL}/Authenticate"
    try:
        resp = requests.get(
            auth_url,
            params={
                "ClientId": settings.BRIGADE_API_CLIENT_ID,
                "ClientSecret": settings.BRIGADE_API_CLIENT_SECRET,
            },
            verify=False,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise BrigadeApiError(f"Authentication request failed: {exc}") from exc
    except ValueError as exc:
        raise BrigadeApiError("Authentication response is not valid JSON") from exc

    token = data.get("value")
    if not token:
        raise BrigadeApiError("Authentication succeeded but no token was returned")

    _token_cache["token"] = token
    _token_cache["expires_at"] = _parse_expiry(data.get("expiryDate"))
    return str(token)


def _api_get_mashinist_list(
    *,
    instruktor_id: int = 0,
    brigada_group_id: int = 0,
    status_id: int = 0,
    depo_id: int = 0,
) -> list[dict]:
    cache_key = (instruktor_id, brigada_group_id, status_id, depo_id)
    cached = _list_cache.get(cache_key)
    now = time.time()
    if cached and cached["expires_at"] > now:
        return list(cached["data"])

    url = f"{settings.BRIGADE_API_URL}/DasUtyAI/SearchMashinistListInfo"
    params = {
        "instruktor_id": instruktor_id,
        "brigada_group_id": brigada_group_id,
        "status_id": status_id,
        "depo_id": depo_id,
    }

    for attempt in (1, 2):
        token = _get_token(force_refresh=(attempt == 2))
        try:
            resp = requests.get(
                url,
                params=params,
                headers={"Authorization": token},
                verify=False,
                timeout=30,
            )
        except requests.RequestException as exc:
            if attempt == 2:
                raise BrigadeApiError(f"Request failed for DasUtyAI/SearchMashinistListInfo: {exc}") from exc
            continue

        if resp.status_code == 401:
            logger.warning("DasUtyAI unauthorized (attempt %s) params=%s", attempt, params)
            if attempt == 1:
                _token_cache["token"] = None
                _token_cache["expires_at"] = 0.0
                continue
            raise BrigadeApiError(
                "DasUtyAI returned 401 Unauthorized. "
                "Client credentials or endpoint permissions are invalid."
            )

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise BrigadeApiError(
                f"DasUtyAI returned HTTP {resp.status_code} for SearchMashinistListInfo"
            ) from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise BrigadeApiError("DasUtyAI returned invalid JSON for SearchMashinistListInfo") from exc

        data = payload.get("data")
        if not isinstance(data, list):
            raise BrigadeApiError("DasUtyAI response does not contain a valid data list")

        _list_cache[cache_key] = {
            "data": data,
            "expires_at": now + LIST_CACHE_TTL_SECONDS,
        }
        return list(data)

    raise BrigadeApiError("Unable to call DasUtyAI/SearchMashinistListInfo")


def _api_get_work_info(
    *,
    mashinist_type_id: int = 0,
    status_id: int = 0,
    depo_id: int = 0,
    working_type: int = 0,
) -> list[dict]:
    """Call SearchMashinistListWorkInfo — work status, shifts, come/leave times."""
    url = f"{settings.BRIGADE_API_URL}/DasUtyAI/SearchMashinistListWorkInfo"
    params = {
        "mashinist_type_id": mashinist_type_id,
        "status_id": status_id,
        "depo_id": depo_id,
        "working_type": working_type,
    }

    for attempt in (1, 2):
        token = _get_token(force_refresh=(attempt == 2))
        try:
            resp = requests.get(
                url, params=params, headers={"Authorization": token},
                verify=False, timeout=30,
            )
        except requests.RequestException as exc:
            if attempt == 2:
                raise BrigadeApiError(f"Request failed for SearchMashinistListWorkInfo: {exc}") from exc
            continue

        if resp.status_code == 401:
            if attempt == 1:
                _token_cache["token"] = None
                _token_cache["expires_at"] = 0.0
                continue
            raise BrigadeApiError("DasUtyAI returned 401 for SearchMashinistListWorkInfo")

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise BrigadeApiError(f"DasUtyAI returned HTTP {resp.status_code} for SearchMashinistListWorkInfo") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise BrigadeApiError("DasUtyAI returned invalid JSON for SearchMashinistListWorkInfo") from exc

        data = payload.get("data")
        if not isinstance(data, list):
            raise BrigadeApiError("SearchMashinistListWorkInfo response has no valid data list")
        return data

    raise BrigadeApiError("Unable to call DasUtyAI/SearchMashinistListWorkInfo")


def _api_get_count_emm_info(
    *,
    mashinist_type_id: int = 0,
    depo_id: int = 0,
    from_date: str = "",
    to_date: str = "",
) -> list[dict]:
    """Call SearchMashinistListCountEmmInfo — how many times each mashinist went to work."""
    url = f"{settings.BRIGADE_API_URL}/DasUtyAI/SearchMashinistListCountEmmInfo"
    params = {
        "mashinist_type_id": mashinist_type_id,
        "depo_id": depo_id,
        "from_date": from_date,
        "to_date": to_date,
    }

    for attempt in (1, 2):
        token = _get_token(force_refresh=(attempt == 2))
        try:
            resp = requests.get(
                url, params=params, headers={"Authorization": token},
                verify=False, timeout=30,
            )
        except requests.RequestException as exc:
            if attempt == 2:
                raise BrigadeApiError(f"Request failed for SearchMashinistListCountEmmInfo: {exc}") from exc
            continue

        if resp.status_code == 401:
            if attempt == 1:
                _token_cache["token"] = None
                _token_cache["expires_at"] = 0.0
                continue
            raise BrigadeApiError("DasUtyAI returned 401 for SearchMashinistListCountEmmInfo")

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise BrigadeApiError(f"DasUtyAI returned HTTP {resp.status_code} for SearchMashinistListCountEmmInfo") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise BrigadeApiError("DasUtyAI returned invalid JSON for SearchMashinistListCountEmmInfo") from exc

        data = payload.get("data")
        if not isinstance(data, list):
            raise BrigadeApiError("SearchMashinistListCountEmmInfo response has no valid data list")
        return data

    raise BrigadeApiError("Unable to call DasUtyAI/SearchMashinistListCountEmmInfo")


def _api_get_med_full_data(
    *,
    mashinist_type_id: int = 0,
    depo_id: int = 0,
    from_date: str = "",
    to_date: str = "",
    allow_work: int = 0,
    after_work: int = 0,
) -> list[dict]:
    """Call SearchEmmMedFullDataInfo — medical exam results (health check, alcohol test)."""
    url = f"{settings.BRIGADE_API_URL}/DasUtyAI/SearchEmmMedFullDataInfo"
    params = {
        "mashinist_type_id": mashinist_type_id,
        "depo_id": depo_id,
        "from_date": from_date,
        "to_date": to_date,
        "allow_work": allow_work,
        "after_work": after_work,
    }

    for attempt in (1, 2):
        token = _get_token(force_refresh=(attempt == 2))
        try:
            resp = requests.get(
                url, params=params, headers={"Authorization": token},
                verify=False, timeout=30,
            )
        except requests.RequestException as exc:
            if attempt == 2:
                raise BrigadeApiError(f"Request failed for SearchEmmMedFullDataInfo: {exc}") from exc
            continue

        if resp.status_code == 401:
            if attempt == 1:
                _token_cache["token"] = None
                _token_cache["expires_at"] = 0.0
                continue
            raise BrigadeApiError("DasUtyAI returned 401 for SearchEmmMedFullDataInfo")

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise BrigadeApiError(f"DasUtyAI returned HTTP {resp.status_code} for SearchEmmMedFullDataInfo") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise BrigadeApiError("DasUtyAI returned invalid JSON for SearchEmmMedFullDataInfo") from exc

        data = payload.get("data")
        if not isinstance(data, list):
            raise BrigadeApiError("SearchEmmMedFullDataInfo response has no valid data list")
        return data

    raise BrigadeApiError("Unable to call DasUtyAI/SearchEmmMedFullDataInfo")


# ---------------------------------------------------------------------------
# Public wrappers — read from unified local cache, filter in-memory
# ---------------------------------------------------------------------------

def _ensure_dataset_loaded() -> None:
    """Make sure the unified cache is loaded (from disk or API)."""
    get_dataset()


def _get_person_depo_map() -> dict[int, int]:
    """Build a map of person id -> depo_id from the main MashinistListInfo dataset."""
    records = _dataset_cache.get("records") or []
    return {r.get("id"): r.get("depo_id") for r in records if r.get("id") is not None and r.get("depo_id") is not None}


def _get_person_info_map() -> dict[int, dict]:
    """Build a map of person id -> {depo_id, brigada_group_id, ...} from MashinistListInfo."""
    records = _dataset_cache.get("records") or []
    return {
        r["id"]: {"depo_id": r.get("depo_id"), "brigada_group_id": r.get("brigada_group_id")}
        for r in records if r.get("id") is not None
    }


def get_work_info(
    *,
    mashinist_type_id: int = 0,
    status_id: int = 0,
    depo_id: int = 0,
    working_type: int = 0,
) -> list[dict]:
    """Get mashinist work status info from local cache, filtered in-memory."""
    _ensure_dataset_loaded()
    records = list(_dataset_cache.get("work_info") or [])
    if mashinist_type_id:
        records = [r for r in records if r.get("mashinist_type_id") == mashinist_type_id]
    if status_id:
        records = [r for r in records if r.get("status_id") == status_id]
    if depo_id:
        depo_map = _get_person_depo_map()
        records = [r for r in records if depo_map.get(r.get("id")) == depo_id]
    if working_type:
        records = [r for r in records if r.get("work_status") == working_type]
    return records


def _resolve_count_emm_from_monthly(
    monthly: dict[str, list[dict]],
    from_date: str,
    to_date: str,
) -> list[dict] | None:
    """Try to serve a date-filtered CountEmm query from cached monthly data.

    Returns merged records if the requested range is fully covered by cached months,
    or None if we need to fall back to the live API.

    For single-month queries, returns that month's data directly.
    For multi-month queries (e.g. quarter), sums count_emm per person across months.
    """
    if not monthly or not from_date or not to_date:
        return None

    # Parse requested range to determine which months are needed
    try:
        fd = from_date[:10]  # "2026-01-01"
        td = to_date[:10]    # "2026-01-31"
        fy, fm = int(fd[:4]), int(fd[5:7])
        ty, tm = int(td[:4]), int(td[5:7])
    except (ValueError, IndexError):
        return None

    # Collect needed month keys
    needed = []
    y, m = fy, fm
    while (y, m) <= (ty, tm):
        needed.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1

    # Check all needed months are cached
    if not all(mk in monthly for mk in needed):
        return None

    if len(needed) == 1:
        # Single month — return directly
        return list(monthly[needed[0]])

    # Multi-month — sum count_emm per person (by id)
    person_totals: dict[int, dict] = {}
    for mk in needed:
        for rec in monthly[mk]:
            pid = rec.get("id")
            if pid in person_totals:
                person_totals[pid]["count_emm"] = (
                    (person_totals[pid].get("count_emm") or 0)
                    + (rec.get("count_emm") or 0)
                )
            else:
                person_totals[pid] = dict(rec)  # copy

    return list(person_totals.values())


def get_count_emm_info(
    *,
    mashinist_type_id: int = 0,
    depo_id: int = 0,
    brigada_group_id: int = 0,
    from_date: str = "",
    to_date: str = "",
) -> list[dict]:
    """Get EMM count info filtered by parameters.

    If from_date/to_date are provided, calls API directly with date range.
    Otherwise returns cached cumulative data (Jan 1 - today).
    brigada_group_id: optional brigade filter (cross-references with MashinistListInfo).
    """
    if from_date or to_date:
        # Try to serve from cached monthly data first
        _ensure_dataset_loaded()
        monthly = _dataset_cache.get("count_emm_monthly") or {}
        cached_records = _resolve_count_emm_from_monthly(monthly, from_date, to_date)
        if cached_records is not None:
            records = cached_records
        else:
            # Date range doesn't match cached months — call API
            records = _api_get_count_emm_info(
                mashinist_type_id=mashinist_type_id,
                depo_id=depo_id,
                from_date=from_date,
                to_date=to_date,
            )
        if mashinist_type_id:
            records = [r for r in records if r.get("mashinist_type_id") == mashinist_type_id]
        if depo_id:
            person_map = _get_person_info_map()
            records = [r for r in records if person_map.get(r.get("id"), {}).get("depo_id") == depo_id]
    else:
        # Use cached cumulative data
        _ensure_dataset_loaded()
        records = list(_dataset_cache.get("count_emm") or [])
        if mashinist_type_id:
            records = [r for r in records if r.get("mashinist_type_id") == mashinist_type_id]
        if depo_id:
            person_map = _get_person_info_map()
            records = [r for r in records if person_map.get(r.get("id"), {}).get("depo_id") == depo_id]

    if brigada_group_id:
        person_map = _get_person_info_map()
        records = [r for r in records if person_map.get(r.get("id"), {}).get("brigada_group_id") == brigada_group_id]
    return records


def get_med_full_data(
    *,
    mashinist_type_id: int = 0,
    depo_id: int = 0,
    from_date: str = "",
    to_date: str = "",
    allow_work: int = 0,
    after_work: int = 0,
) -> list[dict]:
    """Get medical exam data from local cache, filtered in-memory."""
    _ensure_dataset_loaded()
    records = list(_dataset_cache.get("med_data") or [])
    if mashinist_type_id:
        records = [r for r in records if r.get("mashinist_type_id") == mashinist_type_id]
    if depo_id:
        records = [r for r in records if r.get("depo_id") == depo_id]
    if allow_work:
        records = [r for r in records if r.get("allow_work") == allow_work]
    if after_work:
        af = True if after_work == 1 else False
        records = [r for r in records if r.get("after_work") is af]
    # Date filtering on create_date
    if from_date:
        records = [r for r in records if (r.get("create_date") or "") >= from_date]
    if to_date:
        records = [r for r in records if (r.get("create_date") or "") <= to_date]
    return records


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------

def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_digits(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits or None


def _normalize_lower(value: Any) -> str:
    return (_normalize_text(value) or "").casefold()


def _same_text(left: Any, right: Any) -> bool:
    return (_normalize_text(left) or "") == (_normalize_text(right) or "")


def _transliterate_to_latin(text: str) -> str:
    return "".join(CYRILLIC_TO_LATIN.get(ch, ch) for ch in text.casefold())


def _normalize_search_text(value: Any) -> str:
    text = _normalize_text(value)
    if text is None:
        return ""

    transliterated = _transliterate_to_latin(text)
    for ch in ("'", "`", "’", "ʻ", "ʼ", "-", "_", ".", ",", "(", ")", "/", "\\", "|", ":", ";"):
        transliterated = transliterated.replace(ch, " ")

    normalized_chars: list[str] = []
    prev_space = True
    for ch in transliterated:
        if ch.isalnum():
            normalized_chars.append(ch)
            prev_space = False
        elif not prev_space:
            normalized_chars.append(" ")
            prev_space = True

    return "".join(normalized_chars).strip()


def _normalize_loose_search_text(value: Any) -> str:
    # Fold a few common Latin transliteration variants so user-entered Uzbek/Russian
    # names like "Rahim..." can still match data normalized as "Raxim...".
    return _normalize_search_text(value).replace("x", "h")


def _contains_text(haystack: Any, needle: Any) -> bool:
    left = _normalize_search_text(haystack)
    right = _normalize_search_text(needle)
    if bool(right) and right in left:
        return True

    loose_left = _normalize_loose_search_text(haystack)
    loose_right = _normalize_loose_search_text(needle)
    return bool(loose_right) and loose_right in loose_left


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "ha", "bor"}:
        return True
    if text in {"0", "false", "no", "yoq", "yo'q"}:
        return False
    return None


def _match_type(record: dict[str, Any], requested: str | None) -> bool:
    if not requested:
        return True
    requested_lower = _normalize_search_text(requested)
    return requested_lower in {
        _normalize_search_text(record.get("mashinist_type_code")),
        _normalize_search_text(record.get("mashinist_type_name")),
    }


def _normalize_member(item: dict[str, Any]) -> dict:
    status_id = item.get("status_id")
    last_name = _normalize_text(item.get("last_name"))
    first_name = _normalize_text(item.get("first_name"))
    second_name = _normalize_text(item.get("second_name"))
    full_name = " ".join(part for part in (last_name, first_name, second_name) if part)
    phone = _normalize_text(item.get("phone"))
    lok_nomer = _normalize_text(item.get("main_lok_nomer"))
    lok_name = _normalize_text(item.get("main_lok_name"))
    brigada_group_id = item.get("brigada_group_id")

    return {
        "id": item.get("id"),
        "tabelnum": item.get("tabelnum"),
        "last_name": last_name,
        "first_name": first_name,
        "second_name": second_name,
        "full_name": full_name,
        "main_type_id": item.get("main_type_id"),
        "mashinist_type_code": _normalize_text(item.get("mashinist_type_name")) or "",
        "mashinist_type_name": MASHINIST_TYPES.get(_normalize_text(item.get("mashinist_type_name")) or "", "Noma'lum"),
        "phone": phone,
        "phone_digits": _normalize_digits(phone),
        "has_phone": phone is not None,
        "status_id": status_id,
        "status_name": _normalize_text(item.get("status_name")) or STATUS_NAMES.get(status_id, "Noma'lum"),
        "status_label": STATUS_NAMES.get(status_id, "Noma'lum"),
        "is_active": status_id == ACTIVE_STATUS_ID,
        "main_lokomotiv_id": item.get("main_lokomotiv_id"),
        "lok_nomer": lok_nomer,
        "lok_name": lok_name,
        "has_locomotive": lok_nomer is not None or lok_name is not None,
        "brigada_group_id": brigada_group_id,
        "has_brigade": brigada_group_id not in (None, 0),
        "brigade_name": f"Brigada #{brigada_group_id}" if brigada_group_id not in (None, 0) else None,
        "image_url": _normalize_text(item.get("image_url")),
        "has_image": _normalize_text(item.get("image_url")) is not None,
        "position_id": item.get("position_id"),
        "depo_id": item.get("depo_id"),
        "depo_name": _normalize_text(item.get("depo_name")),
        "instruktor_fio": _normalize_text(item.get("instruktor_fio")),
        "birthday": _normalize_text(item.get("bithday") or item.get("birthday")),
        # The new endpoint does not expose these timing fields.
        "come_date": None,
        "leave_date": None,
        "rest_hours": None,
        "is_resting": status_id == 13,
    }


def _dedupe_members(members: list[dict]) -> list[dict]:
    unique: list[dict] = []
    seen: set[tuple[Any, ...]] = set()
    for member in members:
        key = (
            member.get("id"),
            member.get("tabelnum"),
            member.get("full_name"),
            member.get("status_id"),
            member.get("lok_nomer"),
            member.get("brigada_group_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(member)
    return unique


# ---------------------------------------------------------------------------
# Local snapshot cache
# ---------------------------------------------------------------------------

def _read_dataset_cache_file() -> dict[str, Any] | None:
    path = settings.BRIGADE_DATA_CACHE_PATH
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("records"), list):
        return None
    return payload


def _write_dataset_cache_file(
    records: list[dict],
    work_info: list[dict],
    count_emm: list[dict],
    med_data: list[dict],
    fetched_at: float,
    *,
    count_emm_monthly: dict[str, list[dict]] | None = None,
) -> None:
    path = settings.BRIGADE_DATA_CACHE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "fetched_at": datetime.fromtimestamp(fetched_at).isoformat(),
        "record_count": len(records),
        "records": records,
        "work_info": work_info,
        "work_info_count": len(work_info),
        "count_emm": count_emm,
        "count_emm_count": len(count_emm),
        "count_emm_monthly": count_emm_monthly or {},
        "med_data": med_data,
        "med_data_count": len(med_data),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)


def _normalize_records(rows: list[dict]) -> list[dict]:
    return _dedupe_members([_normalize_member(row) for row in rows])


def _load_cache_into_memory(payload: dict[str, Any], source: str, fetched_at: float) -> None:
    """Load a cache payload dict into the in-memory _dataset_cache."""
    _dataset_cache["records"] = payload.get("records") or []
    _dataset_cache["work_info"] = payload.get("work_info") or []
    _dataset_cache["count_emm"] = payload.get("count_emm") or []
    _dataset_cache["count_emm_monthly"] = payload.get("count_emm_monthly") or {}
    _dataset_cache["med_data"] = payload.get("med_data") or []
    _dataset_cache["fetched_at"] = fetched_at
    _dataset_cache["source"] = source


def refresh_dataset_cache() -> dict:
    """Fetch all 4 DasUtyAI endpoints and store them in a single local cache file.

    MashinistListInfo and WorkInfo — full (no date filter).
    CountEmmInfo and MedFullData — from 2026-01-01 to today.
    """
    now = time.time()
    now_dt = datetime.fromtimestamp(now)

    # 1. MashinistListInfo (all depos, full)
    rows = _api_get_mashinist_list()
    records = _normalize_records(rows)

    # 2. WorkInfo (all, no filters, full)
    try:
        work_info = _api_get_work_info()
    except BrigadeApiError as exc:
        logger.warning("Failed to fetch WorkInfo: %s", exc)
        work_info = []

    # 3. CountEmmInfo — full range (Jan 1 - today) for cache
    emm_from = "2026-01-01T00:00:00"
    emm_to = now_dt.strftime("%Y-%m-%dT23:59:59")
    try:
        count_emm = _api_get_count_emm_info(from_date=emm_from, to_date=emm_to)
    except BrigadeApiError as exc:
        logger.warning("Failed to fetch CountEmmInfo: %s", exc)
        count_emm = []

    # 3b. CountEmmInfo — monthly breakdown (Jan, Feb, Mar, ...)
    count_emm_monthly: dict[str, list[dict]] = {}
    current_year = now_dt.year
    current_month = now_dt.month
    for m in range(1, current_month + 1):
        m_from = f"{current_year}-{m:02d}-01T00:00:00"
        if m == current_month:
            m_to = now_dt.strftime("%Y-%m-%dT23:59:59")
        else:
            # Last day of month
            import calendar
            last_day = calendar.monthrange(current_year, m)[1]
            m_to = f"{current_year}-{m:02d}-{last_day:02d}T23:59:59"
        try:
            month_data = _api_get_count_emm_info(from_date=m_from, to_date=m_to)
            month_key = f"{current_year}-{m:02d}"
            count_emm_monthly[month_key] = month_data
            logger.info("Fetched CountEmm for %s: %d records", month_key, len(month_data))
        except BrigadeApiError as exc:
            logger.warning("Failed to fetch CountEmmInfo for month %d: %s", m, exc)

    # 4. MedFullData (from 2026-01-01 to today)
    med_from = "2026-01-01T00:00:00"
    med_to = now_dt.strftime("%Y-%m-%dT23:59:59")
    try:
        med_data = _api_get_med_full_data(from_date=med_from, to_date=med_to)
    except BrigadeApiError as exc:
        logger.warning("Failed to fetch MedFullData: %s", exc)
        med_data = []

    _dataset_cache["records"] = records
    _dataset_cache["work_info"] = work_info
    _dataset_cache["count_emm"] = count_emm
    _dataset_cache["count_emm_monthly"] = count_emm_monthly
    _dataset_cache["med_data"] = med_data
    _dataset_cache["loaded"] = True
    _dataset_cache["fetched_at"] = now
    _dataset_cache["source"] = "live_api"

    _write_dataset_cache_file(records, work_info, count_emm, med_data, now,
                              count_emm_monthly=count_emm_monthly)

    return {
        "record_count": len(records),
        "work_info_count": len(work_info),
        "count_emm_count": len(count_emm),
        "count_emm_monthly_months": list(count_emm_monthly.keys()),
        "med_data_count": len(med_data),
        "fetched_at": datetime.fromtimestamp(now).isoformat(),
        "source": "live_api",
    }


def update_dataset_cache() -> dict:
    """Incremental update: re-fetch all 4 endpoints, merge new/changed records on top of existing cache.

    For MashinistListInfo and WorkInfo — full replace (always current snapshot).
    For CountEmm and MedFullData — merge: keep existing records, add new ones by unique key.
    """
    now = time.time()
    now_dt = datetime.fromtimestamp(now)

    # Load existing cache first
    _ensure_dataset_loaded()
    old_count_emm = list(_dataset_cache.get("count_emm") or [])
    old_med_data = list(_dataset_cache.get("med_data") or [])

    # 1 & 2: MashinistListInfo + WorkInfo — always full snapshot
    rows = _api_get_mashinist_list()
    records = _normalize_records(rows)

    try:
        work_info = _api_get_work_info()
    except BrigadeApiError as exc:
        logger.warning("Failed to fetch WorkInfo: %s", exc)
        work_info = list(_dataset_cache.get("work_info") or [])

    # 3: CountEmm — re-fetch full range for cache
    emm_from = "2026-01-01T00:00:00"
    emm_to = now_dt.strftime("%Y-%m-%dT23:59:59")
    try:
        count_emm = _api_get_count_emm_info(from_date=emm_from, to_date=emm_to)
    except BrigadeApiError as exc:
        logger.warning("Failed to fetch CountEmmInfo for update: %s", exc)
        count_emm = old_count_emm

    # 3b: CountEmm monthly — re-fetch each month
    import calendar
    count_emm_monthly: dict[str, list[dict]] = dict(_dataset_cache.get("count_emm_monthly") or {})
    current_year = now_dt.year
    current_month = now_dt.month
    for m in range(1, current_month + 1):
        m_from = f"{current_year}-{m:02d}-01T00:00:00"
        if m == current_month:
            m_to = now_dt.strftime("%Y-%m-%dT23:59:59")
        else:
            last_day = calendar.monthrange(current_year, m)[1]
            m_to = f"{current_year}-{m:02d}-{last_day:02d}T23:59:59"
        try:
            month_data = _api_get_count_emm_info(from_date=m_from, to_date=m_to)
            count_emm_monthly[f"{current_year}-{m:02d}"] = month_data
        except BrigadeApiError as exc:
            logger.warning("Failed to fetch CountEmmInfo for month %d: %s", m, exc)

    # 4: MedFullData — fetch recent window and merge
    med_from = (now_dt - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")
    med_to = now_dt.strftime("%Y-%m-%dT23:59:59")
    try:
        new_med_data = _api_get_med_full_data(from_date=med_from, to_date=med_to)
    except BrigadeApiError as exc:
        logger.warning("Failed to fetch MedFullData for update: %s", exc)
        new_med_data = []

    # Merge: use (create_date, mashinist_type_id, depo_id, allow_work) as unique key
    med_seen: set[tuple] = set()
    merged_med: list[dict] = []
    for r in new_med_data:
        key = (r.get("create_date"), r.get("mashinist_type_id"), r.get("depo_id"), r.get("allow_work"), r.get("create_user_name"))
        med_seen.add(key)
        merged_med.append(r)
    for r in old_med_data:
        key = (r.get("create_date"), r.get("mashinist_type_id"), r.get("depo_id"), r.get("allow_work"), r.get("create_user_name"))
        if key not in med_seen:
            med_seen.add(key)
            merged_med.append(r)
    med_data = merged_med

    _dataset_cache["records"] = records
    _dataset_cache["work_info"] = work_info
    _dataset_cache["count_emm"] = count_emm
    _dataset_cache["count_emm_monthly"] = count_emm_monthly
    _dataset_cache["med_data"] = med_data
    _dataset_cache["loaded"] = True
    _dataset_cache["fetched_at"] = now
    _dataset_cache["source"] = "live_api_update"

    _write_dataset_cache_file(records, work_info, count_emm, med_data, now,
                              count_emm_monthly=count_emm_monthly)

    return {
        "record_count": len(records),
        "work_info_count": len(work_info),
        "count_emm_count": len(count_emm),
        "count_emm_monthly_months": list(count_emm_monthly.keys()),
        "med_data_count": len(med_data),
        "fetched_at": datetime.fromtimestamp(now).isoformat(),
        "source": "live_api_update",
    }


def get_dataset(force_refresh: bool = False) -> list[dict]:
    # 1. Already loaded in memory
    if not force_refresh and _dataset_cache.get("loaded"):
        return list(_dataset_cache["records"] or [])

    # 2. Try loading from disk
    if not force_refresh:
        cache_payload = _read_dataset_cache_file()
        if cache_payload is not None:
            fetched_at_raw = cache_payload.get("fetched_at")
            fetched_at = 0.0
            if isinstance(fetched_at_raw, str):
                try:
                    fetched_at = datetime.fromisoformat(fetched_at_raw).timestamp()
                except ValueError:
                    fetched_at = 0.0
            _load_cache_into_memory(cache_payload, "disk_cache", fetched_at)
            _dataset_cache["loaded"] = True
            return list(_dataset_cache["records"])

    # 3. No cache on disk — fetch from API
    refresh_dataset_cache()
    return list(_dataset_cache["records"] or [])


def get_dataset_cache_status() -> dict:
    records = get_dataset()
    return {
        "record_count": len(records),
        "work_info_count": len(_dataset_cache.get("work_info") or []),
        "count_emm_count": len(_dataset_cache.get("count_emm") or []),
        "med_data_count": len(_dataset_cache.get("med_data") or []),
        "source": _dataset_cache.get("source"),
        "fetched_at": _dataset_cache.get("fetched_at"),
        "cache_path": settings.BRIGADE_DATA_CACHE_PATH,
    }


# ---------------------------------------------------------------------------
# Generic dataset querying
# ---------------------------------------------------------------------------

def _record_matches(
    record: dict[str, Any],
    *,
    query: str | None = None,
    depo_id: int | None = None,
    depo_name: str | None = None,
    brigada_group_id: int | None = None,
    status_id: int | None = None,
    lok_nomer: str | None = None,
    lok_name: str | None = None,
    mashinist_type: str | None = None,
    assigned_only: bool | None = None,
    has_phone: bool | None = None,
    has_image: bool | None = None,
    is_active: bool | None = None,
) -> bool:
    if depo_id is not None and record.get("depo_id") != depo_id:
        return False
    if depo_name and not _contains_text(record.get("depo_name"), depo_name):
        return False
    if brigada_group_id is not None and record.get("brigada_group_id") != brigada_group_id:
        return False
    if status_id is not None and record.get("status_id") != status_id:
        return False
    if lok_nomer and not _same_text(record.get("lok_nomer"), lok_nomer):
        return False
    if lok_name and not _contains_text(record.get("lok_name"), lok_name):
        return False
    if not _match_type(record, mashinist_type):
        return False
    if assigned_only is not None and bool(record.get("has_locomotive")) != assigned_only:
        return False
    if has_phone is not None and bool(record.get("has_phone")) != has_phone:
        return False
    if has_image is not None and bool(record.get("has_image")) != has_image:
        return False
    if is_active is not None and bool(record.get("is_active")) != is_active:
        return False

    if not query:
        return True

    query_text = query.strip()
    if not query_text:
        return True

    query_normalized = _normalize_search_text(query_text)
    query_digits = _normalize_digits(query_text)
    search_blob = _normalize_search_text(
        " ".join(
            str(value) for value in (
                record.get("full_name"),
                record.get("last_name"),
                record.get("first_name"),
                record.get("second_name"),
                record.get("depo_name"),
                record.get("instruktor_fio"),
                record.get("lok_name"),
                record.get("lok_nomer"),
                record.get("status_name"),
                record.get("brigade_name"),
                record.get("phone"),
            )
            if value
        )
    )

    string_fields = (
        record.get("full_name"),
        record.get("last_name"),
        record.get("first_name"),
        record.get("second_name"),
        record.get("depo_name"),
        record.get("instruktor_fio"),
        record.get("lok_name"),
        record.get("lok_nomer"),
        record.get("status_name"),
        record.get("brigade_name"),
        record.get("phone"),
    )
    for value in string_fields:
        if value and _contains_text(value, query_text):
            return True

    if query_normalized and query_normalized in search_blob:
        return True

    tokens = [token for token in query_normalized.split() if token]
    if tokens and all(token in search_blob for token in tokens):
        return True

    exact_fields = (
        record.get("id"),
        record.get("tabelnum"),
        record.get("depo_id"),
        record.get("brigada_group_id"),
        record.get("position_id"),
    )
    if query_text.isdigit():
        if any(str(value) == query_text for value in exact_fields if value is not None):
            return True

    if query_digits:
        if record.get("phone_digits") and query_digits in record["phone_digits"]:
            return True
        if record.get("lok_nomer") and query_digits == _normalize_digits(record["lok_nomer"]):
            return True

    return False


def _search_score(record: dict[str, Any], query: str | None) -> tuple[int, int, str]:
    if not query:
        return (0, 0, record.get("full_name") or "")

    q = query.strip()
    q_normalized = _normalize_search_text(q)
    q_digits = _normalize_digits(q)
    score = 0

    if _normalize_search_text(record.get("full_name")) == q_normalized:
        score += 100
    if record.get("id") is not None and str(record["id"]) == q:
        score += 95
    if record.get("tabelnum") is not None and str(record["tabelnum"]) == q:
        score += 90
    if record.get("phone_digits") and q_digits and record["phone_digits"] == q_digits:
        score += 85
    if record.get("lok_nomer") and _normalize_digits(record["lok_nomer"]) == q_digits:
        score += 80
    if _contains_text(record.get("last_name"), q):
        score += 60
    if _contains_text(record.get("first_name"), q):
        score += 50
    if _contains_text(record.get("full_name"), q):
        score += 40
    if q_normalized:
        blob = _normalize_search_text(
            " ".join(
                str(value) for value in (
                    record.get("full_name"),
                    record.get("depo_name"),
                    record.get("instruktor_fio"),
                    record.get("lok_name"),
                    record.get("status_name"),
                )
                if value
            )
        )
        if q_normalized in blob:
            score += 35
        tokens = [token for token in q_normalized.split() if token]
        if tokens and all(token in blob for token in tokens):
            score += 30
    if _contains_text(record.get("lok_name"), q):
        score += 30
    if _contains_text(record.get("depo_name"), q):
        score += 20
    if record.get("is_active"):
        score += 5

    return (-score, 0 if record.get("is_active") else 1, record.get("full_name") or "")


def search_records(
    *,
    query: str | None = None,
    depo_id: int | None = None,
    depo_name: str | None = None,
    brigada_group_id: int | None = None,
    status_id: int | None = None,
    lok_nomer: str | None = None,
    lok_name: str | None = None,
    mashinist_type: str | None = None,
    assigned_only: bool | None = None,
    has_phone: bool | None = None,
    has_image: bool | None = None,
    is_active: bool | None = None,
    limit: int = 20,
) -> list[dict]:
    records = get_dataset()
    matched = [
        record for record in records
        if _record_matches(
            record,
            query=query,
            depo_id=depo_id,
            depo_name=depo_name,
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
    ]
    matched.sort(key=lambda record: _search_score(record, query))
    safe_limit = max(1, min(limit, 10000))
    return matched[:safe_limit]


def count_records(
    *,
    query: str | None = None,
    depo_id: int | None = None,
    depo_name: str | None = None,
    brigada_group_id: int | None = None,
    status_id: int | None = None,
    lok_nomer: str | None = None,
    lok_name: str | None = None,
    mashinist_type: str | None = None,
    assigned_only: bool | None = None,
    has_phone: bool | None = None,
    has_image: bool | None = None,
    is_active: bool | None = None,
) -> int:
    return len(search_records(
        query=query,
        depo_id=depo_id,
        depo_name=depo_name,
        brigada_group_id=brigada_group_id,
        status_id=status_id,
        lok_nomer=lok_nomer,
        lok_name=lok_name,
        mashinist_type=mashinist_type,
        assigned_only=assigned_only,
        has_phone=has_phone,
        has_image=has_image,
        is_active=is_active,
        limit=100000,
    ))


def group_records(
    group_by: str,
    *,
    query: str | None = None,
    depo_id: int | None = None,
    depo_name: str | None = None,
    brigada_group_id: int | None = None,
    status_id: int | None = None,
    lok_nomer: str | None = None,
    lok_name: str | None = None,
    mashinist_type: str | None = None,
    assigned_only: bool | None = None,
    has_phone: bool | None = None,
    has_image: bool | None = None,
    is_active: bool | None = None,
    limit: int = 20,
) -> list[dict]:
    group_by = GROUP_BY_ALIASES.get(group_by, group_by)
    if group_by not in GROUP_BY_FIELDS:
        raise ValueError(f"group_by must be one of: {', '.join(GROUP_BY_FIELDS)}")

    rows = search_records(
        query=query,
        depo_id=depo_id,
        depo_name=depo_name,
        brigada_group_id=brigada_group_id,
        status_id=status_id,
        lok_nomer=lok_nomer,
        lok_name=lok_name,
        mashinist_type=mashinist_type,
        assigned_only=assigned_only,
        has_phone=has_phone,
        has_image=has_image,
        is_active=is_active,
        limit=100000,
    )

    counts: Counter[Any] = Counter()
    for row in rows:
        value = row.get(group_by)
        if value in (None, ""):
            value = "Noma'lum"
        counts[value] += 1

    items = [
        {"group": key, "count": count}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    ]
    return items[: max(1, min(limit, 100))]


def get_person_details(query: str) -> list[dict]:
    return search_records(query=query, limit=20)


def get_dataset_overview() -> dict:
    records = get_dataset()
    depots = {r["depo_id"] for r in records if r.get("depo_id") is not None}
    brigades = {r["brigada_group_id"] for r in records if r.get("brigada_group_id") not in (None, 0)}
    locomotives = {
        (r.get("lok_nomer"), r.get("lok_name"))
        for r in records
        if r.get("lok_nomer") or r.get("lok_name")
    }
    return {
        "total_records": len(records),
        "active_records": sum(1 for r in records if r.get("is_active")),
        "with_locomotive": sum(1 for r in records if r.get("has_locomotive")),
        "with_phone": sum(1 for r in records if r.get("has_phone")),
        "with_image": sum(1 for r in records if r.get("has_image")),
        "unique_depots": len(depots),
        "unique_brigades": len(brigades),
        "unique_locomotives": len(locomotives),
        "cache_status": get_dataset_cache_status(),
    }


# ---------------------------------------------------------------------------
# Compatibility helpers used by the agent tools
# ---------------------------------------------------------------------------

def get_brigade_list(depo_id: int) -> list[dict]:
    """Get list of brigades/kolonnas for a depot."""
    rows = search_records(depo_id=depo_id, limit=100000)

    # Build work_status lookup from WorkInfo cache
    _ensure_dataset_loaded()
    work_info_list = _dataset_cache.get("work_info") or []
    work_status_map: dict[int, int] = {}
    for w in work_info_list:
        wid = w.get("id")
        if wid is not None:
            work_status_map[wid] = w.get("work_status", 0)

    brigades: dict[int, dict[str, Any]] = {}

    for row in rows:
        brigada_group_id = row.get("brigada_group_id")
        if not brigada_group_id:
            continue

        bid = int(brigada_group_id)
        brigade = brigades.setdefault(
            bid,
            {
                "id": bid,
                "name": row.get("brigade_name") or f"Brigada #{bid}",
                "instruktor_fio": row.get("instruktor_fio"),
                "depo_id": row.get("depo_id"),
                "depo_name": row.get("depo_name"),
                "member_count": 0,
                "active_count": 0,
                "resting_count": 0,
                "working_count": 0,
                "other_count": 0,
                "_lokomotives": set(),
            },
        )
        brigade["member_count"] += 1
        if row.get("is_active"):
            brigade["active_count"] += 1
        if row.get("instruktor_fio"):
            brigade["instruktor_fio"] = row.get("instruktor_fio")
        if row.get("lok_nomer"):
            brigade["_lokomotives"].add((row.get("lok_nomer"), row.get("lok_name")))

        # Work status from WorkInfo
        ws = work_status_map.get(row.get("id"))
        if ws == 1:
            brigade["resting_count"] += 1
        elif ws == 2:
            brigade["working_count"] += 1
        else:
            # ws=3 (marshrut ochilmagan), ws=0, or not in WorkInfo
            brigade["other_count"] += 1

    output: list[dict] = []
    for bid in sorted(brigades):
        brigade = brigades[bid]
        lokomotives = sorted(brigade.pop("_lokomotives"))
        brigade["assigned_locomotive_count"] = len(lokomotives)
        brigade["assigned_locomotives"] = [
            {"lok_nomer": lok_nomer, "lok_name": lok_name}
            for lok_nomer, lok_name in lokomotives
        ]
        output.append(brigade)
    return output


def _find_lok_name_by_number(lok_nomer: str) -> str | None:
    matches = [
        record.get("lok_name")
        for record in search_records(lok_nomer=lok_nomer, limit=100000)
        if record.get("lok_name")
    ]
    if not matches:
        return None
    return Counter(matches).most_common(1)[0][0]


def get_machinists_on_locomotive(
    lok_nomer: str,
    lok_name: str | None = None,
    model_id: int | None = None,
    for_date: str | None = None,
) -> list[dict]:
    """Get machinists currently working on a specific locomotive."""
    del model_id, for_date

    target_name = _normalize_text(lok_name) or _find_lok_name_by_number(lok_nomer)
    matches = search_records(
        lok_nomer=lok_nomer,
        lok_name=target_name,
        limit=100000,
    )
    if not matches and target_name is not None:
        matches = search_records(lok_nomer=lok_nomer, limit=100000)

    active_matches = [member for member in matches if member.get("is_active")]
    if active_matches:
        return active_matches
    return matches


def get_brigade_details(brigada_group_id: int, depo_id: int | None = None) -> list[dict]:
    """Get detailed brigade info from DasUtyAI."""
    members = search_records(
        brigada_group_id=brigada_group_id,
        depo_id=depo_id,
        limit=100000,
    )
    members.sort(key=lambda x: (not x.get("is_active"), x.get("mashinist_type_name") != "Mashinist", x.get("full_name") or ""))
    return members
