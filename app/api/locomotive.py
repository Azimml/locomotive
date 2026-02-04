from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services import locomotive_service as loco

router = APIRouter(tags=["locomotive"])


@router.get("/locomotives")
def list_locomotives():
    return loco.list_locomotives()


@router.get("/locomotive-info")
def get_locomotive_info(
    locomotive_id: int | None = Query(default=None),
    locomotive_name: str | None = Query(default=None),
):
    if locomotive_id is None and not locomotive_name:
        raise HTTPException(status_code=400, detail="Provide locomotive_id or locomotive_name")
    result = loco.get_locomotive_info(locomotive_id, locomotive_name)
    if not result:
        raise HTTPException(status_code=404, detail="Locomotive not found")
    return result


@router.get("/locomotive-models")
def list_locomotive_models():
    return loco.list_locomotive_models()


@router.get("/stats")
def get_stats():
    return loco.get_stats()


@router.get("/locomotive-types")
def list_locomotive_types():
    return loco.list_locomotive_types()


@router.get("/in_inspection_now")
def list_inspection_counts():
    return loco.list_inspection_counts(active_only=True)


@router.get("/inspection-counts/total")
def list_inspection_counts_total():
    return loco.list_inspection_counts(active_only=False)


@router.get("/depo-info")
def get_depo_info(depo_id: int):
    result = loco.get_depo_info(depo_id)
    if not result:
        raise HTTPException(status_code=404, detail="Depo not found")
    return result


@router.get("/depo-info-all")
def get_depo_info_all():
    return loco.get_depo_info_all()


@router.get("/repairs/active")
def list_active_repairs():
    return loco.list_active_repairs()


@router.get("/repairs/last-all")
def list_last_repairs_all():
    return loco.list_last_repairs_all()


@router.get("/repairs/last")
def get_last_repair(
    locomotive_id: int | None = Query(default=None),
    locomotive_name: str | None = Query(default=None),
):
    if locomotive_id is None and not locomotive_name:
        raise HTTPException(status_code=400, detail="Provide locomotive_id or locomotive_name")
    result = loco.get_last_repair(locomotive_id, locomotive_name)
    if not result:
        raise HTTPException(status_code=404, detail="No repair record found for given locomotive")
    return result


@router.get("/repairs/stats-by-year")
def list_repair_stats_by_year():
    return loco.list_repair_stats_by_year()
