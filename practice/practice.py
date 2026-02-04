import os
import re
from datetime import datetime
from typing import List

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:12345@localhost:5432/dejurka",
)

app = FastAPI(title="Locomotive Info API")


def _get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def _load_table(table_name: str, columns: list[str] | None = None):
    engine = _get_engine()
    return pd.read_sql_table(table_name, con=engine, columns=columns)


def _records_without_nan(df: pd.DataFrame):
    cleaned = df.astype(object).where(pd.notna(df), None)
    return cleaned.to_dict(orient="records")


def _normalize_inspection_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", value or "").upper()


def _canonical_repair_name(name: str) -> str:
    match = re.match(r"^([A-Za-z]+)(\d+)$", name.strip())
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    return name.strip()


def _collect_inspection_dates(
    loco_record: dict,
    selected_columns: list[str],
    latest_repair_dates: dict | None = None,
) -> dict:
    dates: dict[str, datetime] = {}
    for column in selected_columns:
        raw_value = loco_record.get(column)
        if raw_value is None:
            continue
        dt_value = pd.to_datetime(raw_value, errors="coerce", utc=True)
        if pd.isna(dt_value):
            continue
        if hasattr(dt_value, "tz_convert"):
            dt_value = dt_value.tz_convert(None)
        inspection_name = _canonical_repair_name(column.split("_")[0].upper())
        dates[inspection_name] = dt_value.to_pydatetime() if hasattr(dt_value, "to_pydatetime") else dt_value

    if latest_repair_dates:
        for name, dt_value in latest_repair_dates.items():
            if pd.isna(dt_value):
                continue
            if hasattr(dt_value, "tz_convert"):
                dt_value = dt_value.tz_convert(None)
            dates[_canonical_repair_name(name)] = dt_value.to_pydatetime() if hasattr(dt_value, "to_pydatetime") else dt_value

    return dates


def _augment_counts_with_dates(repair_counts_by_year: dict, dates_by_name: dict) -> dict:
    for name, dt_value in dates_by_name.items():
        if dt_value is None:
            continue
        year = int(getattr(dt_value, "year", None) or 0)
        if year == 0:
            continue
        year_entry = repair_counts_by_year.setdefault(year, {"counts": {}, "total": 0})
        counts = year_entry.setdefault("counts", {})
        if name not in counts:
            counts[name] = 1
            year_entry["total"] = int(year_entry.get("total", 0)) + 1
    return repair_counts_by_year


def _inspection_details_from_record(
    loco_record: dict,
    selected_columns: list[str],
    latest_repair_dates: dict | None = None,
) -> dict:
    if not selected_columns:
        details = {}
    else:
        details: dict = {}
        for column in selected_columns:
            raw_value = loco_record.get(column)
            inspection_name = column.split("_")[0].upper()
            if raw_value is None:
                details[inspection_name] = "Grafik vaqti kelmagan"
                continue
            dt_value = pd.to_datetime(raw_value, errors="coerce", utc=True)
            if pd.isna(dt_value):
                details[inspection_name] = "Grafik vaqti kelmagan"
                continue
            if hasattr(dt_value, "tz_convert"):
                dt_value = dt_value.tz_convert(None)
            details[f"Oxirgi {inspection_name} "] = (
                f" {dt_value.strftime('%Y-%m-%d %H:%M')} kuni bo'lgan."
            )
    if not latest_repair_dates:
        return details

    key_by_norm: dict[str, str] = {}
    for key in details.keys():
        key_clean = key.replace("Oxirgi ", "").strip()
        key_by_norm[_normalize_inspection_name(key_clean)] = key

    for name, dt_value in latest_repair_dates.items():
        norm_name = _normalize_inspection_name(name)
        existing_key = key_by_norm.get(norm_name)
        if existing_key and details.get(existing_key) != "Grafik vaqti kelmagan":
            continue
        if pd.isna(dt_value):
            continue
        if hasattr(dt_value, "tz_convert"):
            dt_value = dt_value.tz_convert(None)
        formatted = f" {dt_value.strftime('%Y-%m-%d %H:%M')} kuni bo'lgan."
        if existing_key:
            details.pop(existing_key, None)
            details[f"Oxirgi {existing_key.replace('Oxirgi ', '').strip()} "] = formatted
        else:
            details[f"Oxirgi {name} "] = formatted
    return details


class LocomotiveInfo(BaseModel):
    locomotive_id: int
    locomotive_full_name: str
    locomotive_type: str | None
    location_id: int | None
    location_name: str | None
    organization_id: int | None
    organization_name: str | None
    state: str | None
    repair_counts_by_year: dict
    inspection_details: dict


def _repair_counts_by_year_for_loco(locomotive_id: int) -> dict:
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["locomotive_id", "inspection_type_id", "last_updated_time"],
    )
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name"],
    )

    df_inspection = df_inspection[df_inspection["locomotive_id"] == locomotive_id]
    df_inspection["last_updated_time"] = pd.to_datetime(
        df_inspection["last_updated_time"], errors="coerce"
    )
    df_inspection = df_inspection[pd.notna(df_inspection["last_updated_time"])]
    if df_inspection.empty:
        return {}

    df_inspection = df_inspection.assign(
        year=df_inspection["last_updated_time"].dt.year
    )
    merged = df_inspection.merge(
        df_types, left_on="inspection_type_id", right_on="id", how="left"
    )

    counts = (
        merged.groupby(["year", "name"])
        .size()
        .reset_index(name="repair_count")
    )

    result: dict = {}
    for year, group in counts.groupby("year"):
        group = group.sort_values(by="name")
        per_type = {
            (row["name"] if row["name"] is not None else "Unknown"): int(row["repair_count"])
            for row in _records_without_nan(group)
        }
        result[int(year)] = {
            "counts": per_type,
            "total": int(group["repair_count"].sum()),
        }

    return dict(sorted(result.items(), key=lambda item: item[0], reverse=True))


def _latest_repair_dates_by_loco(df_inspection: pd.DataFrame, df_types: pd.DataFrame) -> dict:
    if df_inspection.empty:
        return {}

    df_inspection = df_inspection.copy()
    df_inspection["last_updated_time"] = pd.to_datetime(
        df_inspection["last_updated_time"], errors="coerce", utc=True
    )
    df_inspection = df_inspection[pd.notna(df_inspection["last_updated_time"])]
    if df_inspection.empty:
        return {}

    merged = df_inspection.merge(
        df_types, left_on="inspection_type_id", right_on="id", how="left"
    )
    merged = merged.sort_values(by="last_updated_time")
    latest = merged.groupby(["locomotive_id", "name"], as_index=False).last()

    result: dict = {}
    for row in _records_without_nan(latest):
        loco_id = int(row["locomotive_id"])
        name = row.get("name") or "Unknown"
        result.setdefault(loco_id, {})[name] = row.get("last_updated_time")

    return result


@app.get("/locomotive-info", response_model=LocomotiveInfo)
def get_locomotive_info(
    locomotive_id: int | None = None, locomotive_name: str | None = None
) -> LocomotiveInfo:
    if locomotive_id is None and not locomotive_name:
        raise HTTPException(status_code=400, detail="Provide locomotive_id or locomotive_name")

    df_loco = _load_table("locomotive_locomotive")
    if locomotive_id is not None:
        df_loco = df_loco[df_loco["id"] == locomotive_id]
    else:
        df_loco_exact = df_loco[df_loco["name"] == locomotive_name]
        if not df_loco_exact.empty:
            df_loco = df_loco_exact
        else:
            df_loco = df_loco[
                df_loco["name"].astype(str).str.endswith(str(locomotive_name))
            ]

    if df_loco.empty:
        raise HTTPException(status_code=404, detail="Locomotive not found")

    selected_columns = [col for col in df_loco.columns if col.endswith("_date")]
    if selected_columns:
        df_loco[selected_columns] = df_loco[selected_columns].apply(
            pd.to_datetime, errors="coerce", utc=True
        )
    df_loco = df_loco.sort_values(by="name")
    loco_record = _records_without_nan(df_loco.iloc[[0]])[0]

    model_record = None
    model_id = loco_record.get("locomotive_model_id")
    if model_id is not None:
        df_models = _load_table("locomotive_locomotivemodel")
        df_models = df_models[df_models["id"] == model_id]
        if not df_models.empty:
            model_record = _records_without_nan(df_models.iloc[[0]])[0]

    loco_name = loco_record.get("name") or ""
    model_name = model_record.get("name") if model_record else None
    full_name = f"{model_name} {loco_name}".strip() if model_name else loco_name

    location_id = loco_record.get("location_id")
    organization_id = (
        loco_record.get("operating_organization_id")
        or loco_record.get("registered_organization_id")
    )

    location_name = None
    if location_id is not None:
        df_locations = _load_table("organization_location")
        df_locations = df_locations[df_locations["id"] == location_id]
        if not df_locations.empty:
            location_name = _records_without_nan(df_locations.iloc[[0]])[0].get("name")

    organization_name = None
    if organization_id is not None:
        df_orgs = _load_table("organization_organization")
        df_orgs = df_orgs[df_orgs["id"] == organization_id]
        if not df_orgs.empty:
            organization_name = _records_without_nan(df_orgs.iloc[[0]])[0].get("name")

    repair_counts_by_year = _repair_counts_by_year_for_loco(int(loco_record.get("id")))
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["locomotive_id", "inspection_type_id", "last_updated_time"],
    )
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name"],
    )
    latest_repair_dates = _latest_repair_dates_by_loco(df_inspection, df_types).get(
        int(loco_record.get("id")),
        {},
    )
    all_dates = _collect_inspection_dates(
        loco_record,
        [col for col in df_loco.columns if col.endswith("_date")],
        latest_repair_dates,
    )
    repair_counts_by_year = _augment_counts_with_dates(repair_counts_by_year, all_dates)

    inspection_details = _inspection_details_from_record(
        loco_record,
        [col for col in df_loco.columns if col.endswith("_date")],
        latest_repair_dates,
    )

    return LocomotiveInfo(
        locomotive_id=int(loco_record.get("id")),
        locomotive_full_name=full_name,
        locomotive_type=(model_record.get("locomotive_type") if model_record else None),
        location_id=location_id,
        location_name=location_name,
        organization_id=organization_id,
        organization_name=organization_name,
        state=loco_record.get("state"),
        repair_counts_by_year=repair_counts_by_year,
        inspection_details=inspection_details,
    )
