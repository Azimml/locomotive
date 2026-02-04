from __future__ import annotations

from datetime import datetime
import re
from typing import List

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:12345@localhost:5432/dejurka",
)

app = FastAPI(title="Locomotive API", version="1.0.0")


def _get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def _load_table(table_name: str, columns: list[str] | None = None) -> pd.DataFrame:
    """Load a whole table via pandas with no raw SQL text."""
    engine = _get_engine()
    return pd.read_sql_table(table_name, con=engine, columns=columns)

def _records_without_nan(df: pd.DataFrame) -> list[dict]:
    """Convert NaN/NaT to None for Pydantic compatibility."""
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


class Locomotive(BaseModel):
    id: int
    name: str
    state: str


class LocomotiveModel(BaseModel):
    id: int
    name: str
    locomotive_type: str
    locomotive_count: int


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


class Stats(BaseModel):
    total_locomotives: int
    total_models: int
    state_counts: List["StateCount"]


class LocomotiveTypeCount(BaseModel):
    locomotive_type: str
    locomotive_count: int


class StateCount(BaseModel):
    state: str
    count: int


class InspectionTypeCount(BaseModel):
    inspection_type_id: int
    name: str
    name_ru: str | None
    name_uz: str | None
    locomotive_count: int


class DepoInfo(BaseModel):
    depo_id: int
    depo_name: str | None
    locomotive_count: int
    locomotive_type_counts: dict
    state_counts: dict


class ActiveRepair(BaseModel):
    locomotive_id: int
    locomotive_name: str
    locomotive_state: str
    repair_type_name: str
    repair_type_name_ru: str | None
    repair_type_name_uz: str | None


class LastRepairAll(BaseModel):
    locomotive_id: int
    locomotive_name: str
    repair_type_name: str | None
    repair_type_name_ru: str | None
    repair_type_name_uz: str | None
    last_updated_at: datetime | None


class LastRepair(BaseModel):
    locomotive_id: int
    locomotive_name: str
    repair_type_name: str | None
    repair_type_name_ru: str | None
    repair_type_name_uz: str | None
    last_updated_at: datetime | None


class RepairStatsYear(BaseModel):
    year: int
    repair_type_counts: dict
    total_locomotives: int

@app.get("/locomotives", response_model=List[LocomotiveInfo])
def list_locomotives() -> List[LocomotiveInfo]:
    df_loco = _load_table("locomotive_locomotive")
    df_loco = df_loco.sort_values(by="id")
    selected_columns = [col for col in df_loco.columns if col.endswith("_date")]
    if selected_columns:
        df_loco[selected_columns] = df_loco[selected_columns].apply(
            pd.to_datetime, errors="coerce", utc=True
        )
    loco_records = _records_without_nan(df_loco)

    df_models = _load_table("locomotive_locomotivemodel")
    model_records = _records_without_nan(df_models)
    model_by_id = {m["id"]: m for m in model_records}

    df_locations = _load_table("organization_location")
    location_records = _records_without_nan(df_locations)
    location_by_id = {l["id"]: l.get("name") for l in location_records}

    df_orgs = _load_table("organization_organization")
    org_records = _records_without_nan(df_orgs)
    org_by_id = {o["id"]: o.get("name") for o in org_records}
    repair_counts_by_loco = _repair_counts_by_year_all()
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["locomotive_id", "inspection_type_id", "last_updated_time"],
    )
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name"],
    )
    latest_repair_dates_by_loco = _latest_repair_dates_by_loco(df_inspection, df_types)
    

    results: list[LocomotiveInfo] = []
    for loco_record in loco_records:
        model_record = model_by_id.get(loco_record.get("locomotive_model_id"))
        loco_name = loco_record.get("name") or ""
        model_name = model_record.get("name") if model_record else None
        full_name = f"{model_name} {loco_name}".strip() if model_name else loco_name

        location_id = loco_record.get("location_id")
        organization_id = (
            loco_record.get("operating_organization_id")
            or loco_record.get("registered_organization_id")
        )

        repair_counts = repair_counts_by_loco.get(int(loco_record.get("id")), {})
        latest_repair_dates = latest_repair_dates_by_loco.get(int(loco_record.get("id")), {})
        all_dates = _collect_inspection_dates(
            loco_record,
            selected_columns,
            latest_repair_dates,
        )
        repair_counts = _augment_counts_with_dates(repair_counts, all_dates)
        inspection_details = _inspection_details_from_record(
            loco_record,
            selected_columns,
            latest_repair_dates,
        )

        results.append(
            LocomotiveInfo(
                locomotive_id=int(loco_record.get("id")),
                locomotive_full_name=full_name,
                locomotive_type=(model_record.get("locomotive_type") if model_record else None),
                location_id=location_id,
                location_name=location_by_id.get(location_id),
                organization_id=organization_id,
                organization_name=org_by_id.get(organization_id),
                state=loco_record.get("state"),
                repair_counts_by_year=repair_counts,
                inspection_details=inspection_details,
            )
        )

    return results


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


@app.get("/locomotive-models", response_model=List[LocomotiveModel])
def list_locomotive_models() -> List[LocomotiveModel]:
    df_models = _load_table(
        "locomotive_locomotivemodel",
        columns=["id", "name", "locomotive_type"],
    )
    df_loco = _load_table(
        "locomotive_locomotive",
        columns=["id", "locomotive_model_id"],
    )

    counts = (
        df_loco.groupby("locomotive_model_id")
        .size()
        .reset_index(name="locomotive_count")
    )
    merged = df_models.merge(
        counts,
        left_on="id",
        right_on="locomotive_model_id",
        how="left",
    )
    merged["locomotive_count"] = merged["locomotive_count"].fillna(0).astype(int)
    merged = merged.drop(columns=["locomotive_model_id"]).sort_values(by="id")
    return [LocomotiveModel(**row) for row in _records_without_nan(merged)]


@app.get("/stats", response_model=Stats)
def get_stats() -> Stats:
    df_loco = _load_table("locomotive_locomotive", columns=["id", "state"])
    df_models = _load_table("locomotive_locomotivemodel", columns=["id"])

    state_counts = (
        df_loco["state"]
        .value_counts(dropna=False)
        .rename_axis("state")
        .reset_index(name="count")
        .sort_values(by="state")
    )

    return Stats(
        total_locomotives=int(len(df_loco.index)),
        total_models=int(len(df_models.index)),
        state_counts=[StateCount(**row) for row in _records_without_nan(state_counts)],
    )


@app.get("/locomotive-types", response_model=List[LocomotiveTypeCount])
def list_locomotive_types() -> List[LocomotiveTypeCount]:
    df_models = _load_table(
        "locomotive_locomotivemodel",
        columns=["id", "locomotive_type"],
    )
    df_loco = _load_table(
        "locomotive_locomotive",
        columns=["id", "locomotive_model_id"],
    )

    merged = df_models.merge(
        df_loco,
        left_on="id",
        right_on="locomotive_model_id",
        how="left",
    )
    grouped = (
        merged.groupby("locomotive_type")["id_y"]
        .count()
        .reset_index(name="locomotive_count")
        .sort_values(by="locomotive_type")
    )
    return [LocomotiveTypeCount(**row) for row in _records_without_nan(grouped)]


def _inspection_type_counts(active_only: bool) -> list[dict]:
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name", "name_ru", "name_uz"],
    )
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["inspection_type_id", "locomotive_id", "is_closed", "is_cancelled"],
    )

    if active_only:
        df_inspection = df_inspection[
            (df_inspection["is_closed"] == False)
            & (df_inspection["is_cancelled"] == False)
        ]

    counts = (
        df_inspection.groupby("inspection_type_id")["locomotive_id"]
        .nunique()
        .reset_index(name="locomotive_count")
    )

    merged = df_types.merge(
        counts, left_on="id", right_on="inspection_type_id", how="left"
    )
    merged["locomotive_count"] = merged["locomotive_count"].fillna(0).astype(int)
    merged = merged.drop(columns=["inspection_type_id"])
    merged = merged.sort_values(by="id")

    return _records_without_nan(
        merged.rename(columns={"id": "inspection_type_id"})
    )


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


def _repair_counts_by_year_all() -> dict:
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["locomotive_id", "inspection_type_id", "last_updated_time"],
    )
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name"],
    )

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
        merged.groupby(["locomotive_id", "year", "name"])
        .size()
        .reset_index(name="repair_count")
    )

    result: dict = {}
    for (loco_id, year), group in counts.groupby(["locomotive_id", "year"]):
        group = group.sort_values(by="name")
        per_type = {
            (row["name"] if row["name"] is not None else "Unknown"): int(row["repair_count"])
            for row in _records_without_nan(group)
        }
        result.setdefault(int(loco_id), {})[int(year)] = {
            "counts": per_type,
            "total": int(group["repair_count"].sum()),
        }

    for loco_id, years in result.items():
        result[loco_id] = dict(sorted(years.items(), key=lambda item: item[0], reverse=True))

    return result


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


@app.get("/in_inspection_now", response_model=List[InspectionTypeCount])
def list_inspection_counts() -> List[InspectionTypeCount]:
    """Active inspections only."""
    return [InspectionTypeCount(**row) for row in _inspection_type_counts(active_only=True)]


@app.get("/inspection-counts/total", response_model=List[InspectionTypeCount])
def list_inspection_counts_total() -> List[InspectionTypeCount]:
    """All-time total inspections per type."""
    return [InspectionTypeCount(**row) for row in _inspection_type_counts(active_only=False)]


@app.get("/depo-info", response_model=DepoInfo)
def get_depo_info(depo_id: int) -> DepoInfo:
    df_loco = _load_table(
        "locomotive_locomotive",
        columns=["id", "locomotive_model_id", "state", "registered_organization_id"],
    )
    df_models = _load_table(
        "locomotive_locomotivemodel",
        columns=["id", "locomotive_type"],
    )
    df_branch = _load_table(
        "organization_branch",
        columns=["name", "organization_id"],
    )

    depo_data = df_loco[df_loco["registered_organization_id"] == depo_id]

    depo_name = None
    df_branch = df_branch[df_branch["organization_id"] == depo_id]
    if not df_branch.empty:
        depo_name = _records_without_nan(df_branch.iloc[[0]])[0].get("name")

    num_loco = int(depo_data["id"].count())

    merged = depo_data.merge(
        df_models, left_on="locomotive_model_id", right_on="id", how="left"
    )
    loco_type_counts = (
        merged["locomotive_type"]
        .value_counts(dropna=False)
        .to_dict()
    )
    state_counts = depo_data["state"].value_counts(dropna=False).to_dict()

    return DepoInfo(
        depo_id=depo_id,
        depo_name=depo_name,
        locomotive_count=num_loco,
        locomotive_type_counts=loco_type_counts,
        state_counts=state_counts,
    )


@app.get("/depo-info-all", response_model=List[DepoInfo])
def get_depo_info_all() -> List[DepoInfo]:
    df_loco = _load_table(
        "locomotive_locomotive",
        columns=["id", "locomotive_model_id", "state", "registered_organization_id"],
    )
    df_models = _load_table(
        "locomotive_locomotivemodel",
        columns=["id", "locomotive_type"],
    )
    df_branch = _load_table(
        "organization_branch",
        columns=["name", "organization_id"],
    )

    branch_names = {
        row["organization_id"]: row["name"]
        for row in _records_without_nan(df_branch)
    }

    merged = df_loco.merge(
        df_models, left_on="locomotive_model_id", right_on="id", how="left"
    )

    results: list[DepoInfo] = []
    for depo_id, group in merged.groupby("registered_organization_id"):
        if depo_id is None:
            continue
        loco_type_counts = group["locomotive_type"].value_counts(dropna=False).to_dict()
        state_counts = group["state"].value_counts(dropna=False).to_dict()
        results.append(
            DepoInfo(
                depo_id=int(depo_id),
                depo_name=branch_names.get(depo_id),
                locomotive_count=int(group["id_x"].count()),
                locomotive_type_counts=loco_type_counts,
                state_counts=state_counts,
            )
        )

    return results


@app.get("/repairs/active", response_model=List[ActiveRepair])
def list_active_repairs() -> List[ActiveRepair]:
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["inspection_type_id", "locomotive_id", "is_closed", "is_cancelled"],
    )
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name", "name_ru", "name_uz"],
    )
    df_loco = _load_table(
        "locomotive_locomotive",
        columns=["id", "name", "state"],
    )

    active = df_inspection[(df_inspection["is_closed"] == False) & (df_inspection["is_cancelled"] == False)]

    merged = (
        active.merge(df_types, left_on="inspection_type_id", right_on="id", how="inner")
        .merge(df_loco, left_on="locomotive_id", right_on="id", how="inner", suffixes=("_type", "_loco"))
    )

    result = merged[[
        "locomotive_id",
        "name_loco",
        "state",
        "name_type",
        "name_ru",
        "name_uz",
    ]].rename(
        columns={
            "name_loco": "locomotive_name",
            "state": "locomotive_state",
            "name_type": "repair_type_name",
            "name_ru": "repair_type_name_ru",
            "name_uz": "repair_type_name_uz",
        }
    )
    result = result.sort_values(by=["repair_type_name", "locomotive_name"])

    return [ActiveRepair(**row) for row in _records_without_nan(result)]


@app.get("/repairs/last-all", response_model=List[LastRepairAll])
def list_last_repairs_all() -> List[LastRepairAll]:
    df_loco = _load_table(
        "locomotive_locomotive",
        columns=["id", "name"],
    )
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["locomotive_id", "inspection_type_id", "last_updated_time"],
    )
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name", "name_ru", "name_uz"],
    )

    merged = (
        df_loco.merge(df_inspection, left_on="id", right_on="locomotive_id", how="left")
        .merge(df_types, left_on="inspection_type_id", right_on="id", how="left", suffixes=("_loco", "_type"))
    )

    merged["last_updated_time"] = pd.to_datetime(merged["last_updated_time"], errors="coerce")
    merged = merged.sort_values(by=["id_loco", "last_updated_time"], ascending=[True, False], na_position="last")
    latest = merged.groupby("id_loco", as_index=False).first()

    result = latest[[
        "id_loco",
        "name_loco",
        "name_type",
        "name_ru",
        "name_uz",
        "last_updated_time",
    ]].rename(
        columns={
            "id_loco": "locomotive_id",
            "name_loco": "locomotive_name",
            "name_type": "repair_type_name",
            "name_ru": "repair_type_name_ru",
            "name_uz": "repair_type_name_uz",
            "last_updated_time": "last_updated_at",
        }
    )

    return [LastRepairAll(**row) for row in _records_without_nan(result)]


@app.get("/repairs/last", response_model=LastRepair)
def get_last_repair(
    locomotive_id: int | None = None, locomotive_name: str | None = None
) -> LastRepair:
    if locomotive_id is None and not locomotive_name:
        raise HTTPException(status_code=400, detail="Provide locomotive_id or locomotive_name")

    df_loco = _load_table(
        "locomotive_locomotive",
        columns=["id", "name"],
    )
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["locomotive_id", "inspection_type_id", "last_updated_time"],
    )
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name", "name_ru", "name_uz"],
    )

    if locomotive_id is not None:
        df_loco = df_loco[df_loco["id"] == locomotive_id]
    else:
        df_loco = df_loco[df_loco["name"] == locomotive_name]

    if df_loco.empty:
        raise HTTPException(status_code=404, detail="Locomotive not found")

    merged = (
        df_loco.merge(df_inspection, left_on="id", right_on="locomotive_id", how="left")
        .merge(df_types, left_on="inspection_type_id", right_on="id", how="left", suffixes=("_loco", "_type"))
    )

    merged["last_updated_time"] = pd.to_datetime(merged["last_updated_time"], errors="coerce")
    merged = merged.sort_values(by="last_updated_time", ascending=False, na_position="last")

    if merged.empty:
        raise HTTPException(status_code=404, detail="No repair record found for given locomotive")

    row = merged.iloc[0]
    result = {
        "locomotive_id": int(row["id_loco"]),
        "locomotive_name": row["name_loco"],
        "repair_type_name": None if pd.isna(row["name_type"]) else row["name_type"],
        "repair_type_name_ru": None if pd.isna(row["name_ru"]) else row["name_ru"],
        "repair_type_name_uz": None if pd.isna(row["name_uz"]) else row["name_uz"],
        "last_updated_at": row["last_updated_time"].to_pydatetime() if pd.notna(row["last_updated_time"]) else None,
    }

    if result["repair_type_name"] is None and result["last_updated_at"] is None:
        raise HTTPException(status_code=404, detail="No repair record found for given locomotive")

    return LastRepair(**result)


@app.get("/repairs/stats-by-year", response_model=List[RepairStatsYear])
def list_repair_stats_by_year() -> List[RepairStatsYear]:
    df_inspection = _load_table(
        "inspection_inspection",
        columns=["locomotive_id", "inspection_type_id", "last_updated_time"],
    )
    df_types = _load_table(
        "inspection_inspectiontype",
        columns=["id", "name"],
    )

    df_inspection["last_updated_time"] = pd.to_datetime(
        df_inspection["last_updated_time"], errors="coerce"
    )
    df_inspection = df_inspection[pd.notna(df_inspection["last_updated_time"])]
    if df_inspection.empty:
        return []

    df_inspection = df_inspection.assign(
        year=df_inspection["last_updated_time"].dt.year
    )

    counts = (
        df_inspection.groupby(["year", "inspection_type_id"])["locomotive_id"]
        .nunique()
        .reset_index(name="locomotive_count")
    )

    merged = counts.merge(
        df_types,
        left_on="inspection_type_id",
        right_on="id",
        how="left",
    )

    totals = (
        df_inspection.groupby("year")["locomotive_id"]
        .nunique()
        .reset_index(name="total_locomotives")
    )
    totals_by_year = {
        int(row["year"]): int(row["total_locomotives"])
        for row in _records_without_nan(totals)
    }

    results: list[RepairStatsYear] = []
    for year, group in merged.groupby("year"):
        group = group.sort_values(by="name")
        repair_type_counts = {
            (row["name"] if row["name"] is not None else "Unknown"): int(row["locomotive_count"])
            for row in _records_without_nan(group)
        }
        results.append(
            RepairStatsYear(
                year=int(year),
                repair_type_counts=repair_type_counts,
                total_locomotives=totals_by_year.get(int(year), 0),
            )
        )

    results.sort(key=lambda item: item.year, reverse=True)
    return results