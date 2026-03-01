"""
Helper to write normalized records to filesystem (mock S3 path).

Path format:
/mock_s3/rag_ingested/onedrive/{tenant}/{YYYY}/{MM}/{DD}/{file_id}.json
Partitioning is based on the record's modified_time when available, otherwise current UTC time.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, Any


def _partition_path(base: str, tenant_id: str, object_id: str, modified_time: str) -> str:
    try:
        ts = datetime.fromisoformat(modified_time.replace("Z", "+00:00"))
    except Exception:
        ts = datetime.now(timezone.utc)
    year = ts.year
    month = f"{ts.month:02d}"
    day = f"{ts.day:02d}"
    return os.path.join(base, tenant_id, str(year), month, day, f"{object_id}.json")


def write_record(base: str, tenant_id: str, object_id: str, record: Dict[str, Any]) -> str:
    """
    Write a normalized record and return the absolute path written.
    """
    modified_time = (
        record.get("modified_time")
        or record.get("lastModifiedDateTime")
        or record.get("ingested_at")
    )
    path = _partition_path(
        base, tenant_id, object_id, modified_time or datetime.now(timezone.utc).isoformat()
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return path
