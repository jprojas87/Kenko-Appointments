import json
from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.config import settings
from app.events.envelope import EVENT_SOURCE

MAX_EVENT_SIZE_BYTES = 256 * 1024


class EventBridgePublisher:
    def __init__(self, client: BaseClient | None = None) -> None:
        self.client = client or boto3.client(
            "events",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url or None,
            config=Config(
                connect_timeout=3,
                read_timeout=3,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def publish(self, detail_type: str, detail: dict[str, object]) -> None:
        serialized_detail = json.dumps(detail, ensure_ascii=False, separators=(",", ":"))
        entry: dict[str, Any] = {
            "Source": EVENT_SOURCE,
            "DetailType": detail_type,
            "Detail": serialized_detail,
            "EventBusName": settings.event_bus_name,
        }
        event_size = len(
            json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        if event_size >= MAX_EVENT_SIZE_BYTES:
            raise ValueError("El evento de EventBridge debe pesar menos de 256 KB")

        response = self.client.put_events(Entries=[entry])
        failed_entry_count = response.get("FailedEntryCount", 0)
        if failed_entry_count > 0:
            raise RuntimeError(
                f"EventBridge no publicó {failed_entry_count} entrada(s): "
                f"{response.get('Entries', [])}"
            )
