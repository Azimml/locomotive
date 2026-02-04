import os

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:12345@localhost:5432/dejurka",
)

app = FastAPI(title="Stats API")


def _get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def _load_table(table_name: str, columns: list[str] | None = None):
    engine = _get_engine()
    return pd.read_sql_table(table_name, con=engine, columns=columns)


def _records_without_nan(df: pd.DataFrame):
    cleaned = df.astype(object).where(pd.notna(df), None)
    return cleaned.to_dict(orient="records")


class StateCount(BaseModel):
    state: str | None
    count: int


class Stats(BaseModel):
    total_locomotives: int
    total_models: int
    state_counts: list[StateCount]


@app.get("/stats", response_model=Stats)
def get_stats():
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
