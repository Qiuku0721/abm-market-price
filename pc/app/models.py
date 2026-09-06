"""Pydantic 请求/响应模型 —— 与 docs/PROTOCOL.md v1 字段对齐。"""

from pydantic import BaseModel, Field


class RecordIn(BaseModel):
    bullet_name: str = Field(min_length=1, max_length=64)
    price: int = Field(ge=1, le=10_000_000)
    currency: str = "Koen"
    market_type: str = "market"
    captured_at: str = Field(min_length=1)
    source: str = "list_scan"
    snapshot_id: str | None = None


class RecordsBatch(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    records: list[RecordIn] = Field(max_length=200)


class BulletIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class RecordsResult(BaseModel):
    accepted: int
    duplicates: int
    rejected: list[dict] = []
