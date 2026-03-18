"""PostgreSQL data access layer."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text

from ..config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rows(result) -> list[dict]:
    """Convert SQLAlchemy result to list of plain dicts."""
    return [dict(r) for r in result.mappings().all()]


def _row(result) -> dict | None:
    """Convert first row of SQLAlchemy result to dict, or None."""
    r = result.mappings().first()
    return dict(r) if r else None


def _canonical_repair_name(name: str) -> str:
    """Normalize repair type names: 'JT1' -> 'JT-1'."""
    m = re.match(r"^([A-Za-z]+)(\d+)$", name.strip())
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return name.strip()


# ---------------------------------------------------------------------------
# Stats & Counts
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    """Overall statistics: locomotive count, model count, state distribution."""
    with engine.connect() as conn:
        total_locos = conn.execute(
            text("SELECT COUNT(*) AS total FROM locomotive_locomotive")
        ).scalar()

        total_models = conn.execute(
            text("SELECT COUNT(*) AS total FROM locomotive_locomotivemodel")
        ).scalar()

        state_rows = _rows(conn.execute(text(
            "SELECT state, COUNT(*) AS count "
            "FROM locomotive_locomotive "
            "GROUP BY state ORDER BY state"
        )))

    return {
        "total_locomotives": total_locos,
        "total_models": total_models,
        "state_counts": state_rows,
    }


def list_locomotive_models() -> list[dict]:
    """All locomotive models with counts."""
    with engine.connect() as conn:
        return _rows(conn.execute(text(
            "SELECT m.id, m.name, m.locomotive_type, "
            "  COUNT(l.id) AS locomotive_count "
            "FROM locomotive_locomotivemodel m "
            "LEFT JOIN locomotive_locomotive l ON l.locomotive_model_id = m.id "
            "GROUP BY m.id, m.name, m.locomotive_type "
            "ORDER BY m.id"
        )))


def list_locomotive_types() -> list[dict]:
    """Locomotive types with counts."""
    with engine.connect() as conn:
        return _rows(conn.execute(text(
            "SELECT m.locomotive_type, COUNT(l.id) AS locomotive_count "
            "FROM locomotive_locomotivemodel m "
            "LEFT JOIN locomotive_locomotive l ON l.locomotive_model_id = m.id "
            "GROUP BY m.locomotive_type "
            "ORDER BY m.locomotive_type"
        )))


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------

def list_inspection_counts(active_only: bool) -> list[dict]:
    """Inspection type counts. If active_only, only open inspections."""
    filter_clause = ""
    if active_only:
        filter_clause = "AND i.is_closed = FALSE AND i.is_cancelled = FALSE"

    q = f"""
        SELECT t.id AS inspection_type_id, t.name, t.name_ru, t.name_uz,
               COUNT(DISTINCT i.locomotive_id) AS locomotive_count
        FROM inspection_inspectiontype t
        LEFT JOIN inspection_inspection i
            ON i.inspection_type_id = t.id {filter_clause}
        GROUP BY t.id, t.name, t.name_ru, t.name_uz
        ORDER BY t.id
    """
    with engine.connect() as conn:
        return _rows(conn.execute(text(q)))


# ---------------------------------------------------------------------------
# Depot Information
# ---------------------------------------------------------------------------

def get_depo_info(depo_id: int) -> dict | None:
    """Info for a single depot: name, loco count, type/state breakdown."""
    with engine.connect() as conn:
        depo_name_row = _row(conn.execute(text(
            "SELECT name FROM organization_branch "
            "WHERE organization_id = :did LIMIT 1"
        ), {"did": depo_id}))

        if not depo_name_row:
            return None

        loco_count = conn.execute(text(
            "SELECT COUNT(*) FROM locomotive_locomotive "
            "WHERE registered_organization_id = :did"
        ), {"did": depo_id}).scalar()

        type_rows = _rows(conn.execute(text(
            "SELECT m.locomotive_type, COUNT(*) AS count "
            "FROM locomotive_locomotive l "
            "JOIN locomotive_locomotivemodel m ON m.id = l.locomotive_model_id "
            "WHERE l.registered_organization_id = :did "
            "GROUP BY m.locomotive_type"
        ), {"did": depo_id}))

        state_rows = _rows(conn.execute(text(
            "SELECT state, COUNT(*) AS count "
            "FROM locomotive_locomotive "
            "WHERE registered_organization_id = :did "
            "GROUP BY state"
        ), {"did": depo_id}))

    return {
        "depo_id": depo_id,
        "depo_name": depo_name_row["name"],
        "locomotive_count": loco_count,
        "locomotive_type_counts": {r["locomotive_type"]: r["count"] for r in type_rows},
        "state_counts": {r["state"]: r["count"] for r in state_rows},
    }


def get_depo_info_all() -> list[dict]:
    """Info for all depots."""
    with engine.connect() as conn:
        rows = _rows(conn.execute(text("""
            SELECT
                l.registered_organization_id AS depo_id,
                b.name AS depo_name,
                m.locomotive_type,
                l.state,
                COUNT(*) AS cnt
            FROM locomotive_locomotive l
            LEFT JOIN locomotive_locomotivemodel m ON m.id = l.locomotive_model_id
            LEFT JOIN organization_branch b ON b.organization_id = l.registered_organization_id
            WHERE l.registered_organization_id IS NOT NULL
            GROUP BY l.registered_organization_id, b.name, m.locomotive_type, l.state
            ORDER BY l.registered_organization_id
        """)))

    depots: dict[int, dict] = {}
    for r in rows:
        did = r["depo_id"]
        if did not in depots:
            depots[did] = {
                "depo_id": did,
                "depo_name": r["depo_name"],
                "locomotive_count": 0,
                "locomotive_type_counts": {},
                "state_counts": {},
            }
        d = depots[did]
        d["locomotive_count"] += r["cnt"]

        lt = r["locomotive_type"]
        d["locomotive_type_counts"][lt] = d["locomotive_type_counts"].get(lt, 0) + r["cnt"]

        st = r["state"]
        d["state_counts"][st] = d["state_counts"].get(st, 0) + r["cnt"]

    return list(depots.values())


# ---------------------------------------------------------------------------
# Repairs
# ---------------------------------------------------------------------------

def list_active_repairs() -> list[dict]:
    """Currently active (open) repairs."""
    with engine.connect() as conn:
        return _rows(conn.execute(text("""
            SELECT
                i.locomotive_id,
                l.name  AS locomotive_name,
                l.state AS locomotive_state,
                t.name  AS repair_type_name,
                t.name_ru AS repair_type_name_ru,
                t.name_uz AS repair_type_name_uz
            FROM inspection_inspection i
            JOIN inspection_inspectiontype t ON t.id = i.inspection_type_id
            JOIN locomotive_locomotive l     ON l.id = i.locomotive_id
            WHERE i.is_closed = FALSE AND i.is_cancelled = FALSE
            ORDER BY t.name, l.name
        """)))


def list_last_repairs_all() -> list[dict]:
    """Latest repair for every locomotive."""
    with engine.connect() as conn:
        return _rows(conn.execute(text("""
            SELECT DISTINCT ON (l.id)
                l.id   AS locomotive_id,
                l.name AS locomotive_name,
                t.name    AS repair_type_name,
                t.name_ru AS repair_type_name_ru,
                t.name_uz AS repair_type_name_uz,
                i.last_updated_time AS last_updated_at
            FROM locomotive_locomotive l
            LEFT JOIN inspection_inspection i   ON i.locomotive_id = l.id
            LEFT JOIN inspection_inspectiontype t ON t.id = i.inspection_type_id
            ORDER BY l.id, i.last_updated_time DESC NULLS LAST
        """)))


def get_last_repair(
    locomotive_id: int | None = None,
    locomotive_name: str | None = None,
) -> dict | None:
    """Latest repair for a specific locomotive (by id or name)."""
    with engine.connect() as conn:
        row = _row(conn.execute(text("""
            SELECT
                l.id   AS locomotive_id,
                l.name AS locomotive_name,
                t.name    AS repair_type_name,
                t.name_ru AS repair_type_name_ru,
                t.name_uz AS repair_type_name_uz,
                i.last_updated_time AS last_updated_at
            FROM locomotive_locomotive l
            LEFT JOIN inspection_inspection i   ON i.locomotive_id = l.id
            LEFT JOIN inspection_inspectiontype t ON t.id = i.inspection_type_id
            WHERE (l.id = :lid OR l.name = :lname)
              AND i.last_updated_time IS NOT NULL
            ORDER BY i.last_updated_time DESC
            LIMIT 1
        """), {"lid": locomotive_id, "lname": locomotive_name}))

    if row and row.get("repair_type_name") is None and row.get("last_updated_at") is None:
        return None
    return row


def list_repair_stats_by_year() -> list[dict]:
    """Repair statistics grouped by year."""
    with engine.connect() as conn:
        type_rows = _rows(conn.execute(text("""
            SELECT
                EXTRACT(YEAR FROM i.last_updated_time)::int AS year,
                t.name AS repair_type,
                COUNT(DISTINCT i.locomotive_id) AS locomotive_count
            FROM inspection_inspection i
            JOIN inspection_inspectiontype t ON t.id = i.inspection_type_id
            WHERE i.last_updated_time IS NOT NULL
            GROUP BY year, t.name
            ORDER BY year DESC, t.name
        """)))

        total_rows = _rows(conn.execute(text("""
            SELECT
                EXTRACT(YEAR FROM last_updated_time)::int AS year,
                COUNT(DISTINCT locomotive_id) AS total_locomotives
            FROM inspection_inspection
            WHERE last_updated_time IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
        """)))

    totals_by_year = {r["year"]: r["total_locomotives"] for r in total_rows}

    years: dict[int, dict] = {}
    for r in type_rows:
        y = r["year"]
        if y not in years:
            years[y] = {"year": y, "repair_type_counts": {}, "total_locomotives": totals_by_year.get(y, 0)}
        years[y]["repair_type_counts"][r["repair_type"]] = r["locomotive_count"]

    return sorted(years.values(), key=lambda x: x["year"], reverse=True)


# ---------------------------------------------------------------------------
# Repair counts by year (for locomotive detail views)
# ---------------------------------------------------------------------------

def _repair_counts_by_year(locomotive_id: int) -> dict[int, dict]:
    """Repair counts grouped by year for a single locomotive."""
    with engine.connect() as conn:
        rows = _rows(conn.execute(text("""
            SELECT
                EXTRACT(YEAR FROM i.last_updated_time)::int AS year,
                t.name AS repair_type,
                COUNT(*) AS repair_count
            FROM inspection_inspection i
            JOIN inspection_inspectiontype t ON t.id = i.inspection_type_id
            WHERE i.locomotive_id = :lid AND i.last_updated_time IS NOT NULL
            GROUP BY year, t.name
            ORDER BY year DESC, t.name
        """), {"lid": locomotive_id}))

    result: dict[int, dict] = {}
    for r in rows:
        y = r["year"]
        if y not in result:
            result[y] = {"counts": {}, "total": 0}
        result[y]["counts"][r["repair_type"]] = r["repair_count"]
        result[y]["total"] += r["repair_count"]
    return result


def _latest_repair_dates(locomotive_id: int) -> dict[str, Any]:
    """Latest repair date per type for a single locomotive."""
    with engine.connect() as conn:
        rows = _rows(conn.execute(text("""
            SELECT DISTINCT ON (t.name)
                t.name,
                i.last_updated_time
            FROM inspection_inspection i
            JOIN inspection_inspectiontype t ON t.id = i.inspection_type_id
            WHERE i.locomotive_id = :lid AND i.last_updated_time IS NOT NULL
            ORDER BY t.name, i.last_updated_time DESC
        """), {"lid": locomotive_id}))

    return {r["name"]: r["last_updated_time"] for r in rows}


def _inspection_details(locomotive_id: int, date_columns: dict[str, Any]) -> dict:
    """Build inspection detail dict from _date columns and latest repair dates."""
    latest = _latest_repair_dates(locomotive_id)
    details: dict[str, str] = {}

    # Process date columns from the locomotive record
    for col_name, raw_value in date_columns.items():
        inspection_name = col_name.split("_")[0].upper()
        canonical = _canonical_repair_name(inspection_name)
        if raw_value is None:
            details[canonical] = "Grafik vaqti kelmagan"
        else:
            dt = raw_value if isinstance(raw_value, datetime) else None
            if dt:
                details[canonical] = f"{dt.strftime('%Y-%m-%d %H:%M')} kuni bo'lgan."
            else:
                details[canonical] = "Grafik vaqti kelmagan"

    # Merge latest repair dates (overwrite "Grafik vaqti kelmagan" if real date exists)
    for name, dt_value in latest.items():
        canonical = _canonical_repair_name(name)
        if dt_value and (canonical not in details or details[canonical] == "Grafik vaqti kelmagan"):
            if isinstance(dt_value, datetime):
                details[canonical] = f"{dt_value.strftime('%Y-%m-%d %H:%M')} kuni bo'lgan."

    return details


# ---------------------------------------------------------------------------
# Locomotive Info
# ---------------------------------------------------------------------------

def get_locomotive_info(
    locomotive_id: int | None = None,
    locomotive_name: str | None = None,
) -> dict | None:
    """Detailed info for a single locomotive."""
    if locomotive_id is None and not locomotive_name:
        raise ValueError("Provide locomotive_id or locomotive_name")

    # Build WHERE dynamically to avoid SQLAlchemy/psycopg2 cast conflicts
    if locomotive_id is not None:
        where = "l.id = :lid"
        params = {"lid": locomotive_id}
    else:
        where = "(l.name = :lname OR l.name LIKE '%' || :lname)"
        params = {"lname": locomotive_name}

    with engine.connect() as conn:
        row = _row(conn.execute(text(f"""
            SELECT l.*,
                   m.name AS model_name, m.locomotive_type,
                   loc.name AS location_name,
                   COALESCE(o1.name, o2.name) AS organization_name
            FROM locomotive_locomotive l
            LEFT JOIN locomotive_locomotivemodel m   ON m.id  = l.locomotive_model_id
            LEFT JOIN organization_location loc      ON loc.id = l.location_id
            LEFT JOIN organization_organization o1   ON o1.id = l.operating_organization_id
            LEFT JOIN organization_organization o2   ON o2.id = l.registered_organization_id
            WHERE {where}
            ORDER BY l.name
            LIMIT 1
        """), params))

    if not row:
        return None

    loco_id = row["id"]
    loco_name = row.get("name") or ""
    model_name = row.get("model_name")
    full_name = f"{model_name} {loco_name}".strip() if model_name else loco_name

    # Collect _date columns
    date_cols = {k: v for k, v in row.items() if k.endswith("_date")}

    repair_counts = _repair_counts_by_year(loco_id)
    inspection_details = _inspection_details(loco_id, date_cols)

    # Augment repair counts with dates from inspection details
    latest = _latest_repair_dates(loco_id)
    for name, dt_value in latest.items():
        if dt_value and isinstance(dt_value, datetime):
            year = dt_value.year
            entry = repair_counts.setdefault(year, {"counts": {}, "total": 0})
            canonical = _canonical_repair_name(name)
            if canonical not in entry["counts"]:
                entry["counts"][canonical] = 1
                entry["total"] += 1

    return {
        "locomotive_id": loco_id,
        "locomotive_full_name": full_name,
        "locomotive_type": row.get("locomotive_type"),
        "location_id": row.get("location_id"),
        "location_name": row.get("location_name"),
        "organization_id": row.get("operating_organization_id") or row.get("registered_organization_id"),
        "organization_name": row.get("organization_name"),
        "state": row.get("state"),
        "repair_counts_by_year": dict(sorted(repair_counts.items(), reverse=True)),
        "inspection_details": inspection_details,
    }


# ---------------------------------------------------------------------------
# Locomotive Listing
# ---------------------------------------------------------------------------

def list_locomotives() -> list[dict]:
    """List all locomotives with basic info."""
    with engine.connect() as conn:
        rows = _rows(conn.execute(text("""
            SELECT
                l.id AS locomotive_id,
                TRIM(CONCAT(m.name, ' ', l.name)) AS locomotive_full_name,
                m.locomotive_type,
                l.location_id,
                loc.name AS location_name,
                COALESCE(l.operating_organization_id, l.registered_organization_id) AS organization_id,
                COALESCE(o1.name, o2.name) AS organization_name,
                l.state
            FROM locomotive_locomotive l
            LEFT JOIN locomotive_locomotivemodel m ON m.id = l.locomotive_model_id
            LEFT JOIN organization_location loc   ON loc.id = l.location_id
            LEFT JOIN organization_organization o1 ON o1.id = l.operating_organization_id
            LEFT JOIN organization_organization o2 ON o2.id = l.registered_organization_id
            ORDER BY l.id
        """)))

    return rows


def search_locomotives(name: str) -> list[dict]:
    """Search locomotives by name/number at the SQL level."""
    search_term = name.strip()
    with engine.connect() as conn:
        rows = _rows(conn.execute(text("""
            SELECT
                l.id AS locomotive_id,
                TRIM(CONCAT(m.name, ' ', l.name)) AS locomotive_full_name,
                m.locomotive_type,
                l.location_id,
                loc.name AS location_name,
                COALESCE(l.operating_organization_id, l.registered_organization_id) AS organization_id,
                COALESCE(o1.name, o2.name) AS organization_name,
                l.state
            FROM locomotive_locomotive l
            LEFT JOIN locomotive_locomotivemodel m ON m.id = l.locomotive_model_id
            LEFT JOIN organization_location loc   ON loc.id = l.location_id
            LEFT JOIN organization_organization o1 ON o1.id = l.operating_organization_id
            LEFT JOIN organization_organization o2 ON o2.id = l.registered_organization_id
            WHERE l.name ILIKE :exact
               OR l.name ILIKE :suffix
               OR TRIM(CONCAT(m.name, ' ', l.name)) ILIKE :anywhere
            ORDER BY l.id
            LIMIT 20
        """), {
            "exact": search_term,
            "suffix": f"%{search_term}",
            "anywhere": f"%{search_term}%",
        }))

    return rows
