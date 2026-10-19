import logging
import time
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    def publish(self, detail_type: str, detail: dict[str, object]) -> None: ...


def get_event_publisher() -> EventPublisher:
    if settings.event_publisher == "log":
        from app.events.log_publisher import LogPublisher

        return LogPublisher()
    if settings.event_publisher == "eventbridge":
        from app.events.eventbridge_publisher import EventBridgePublisher

        return EventBridgePublisher()
    raise RuntimeError("EVENT_PUBLISHER debe ser log o eventbridge")


def publish_safely(
    publisher: EventPublisher,
    detail_type: str,
    detail: dict[str, object],
) -> None:
    metadata = detail.get("metadata")
    data = detail.get("data")
    metadata = metadata if isinstance(metadata, dict) else {}
    data = data if isinstance(data, dict) else {}
    correlation_id = metadata.get("correlationId", "-")
    event_id = metadata.get("eventId", "-")
    user_id = data.get("userId", "-")

    for attempt in range(1, 4):
        try:
            publisher.publish(detail_type, detail)
            return
        except Exception as exception:
            if attempt < 3:
                time.sleep(0.1 * attempt)
            else:
                logger.error(
                    "Event publication failed after 3 attempts: detailType=%s "
                    "correlationId=%s eventId=%s userId=%s error=%r",
                    detail_type,
                    correlation_id,
                    event_id,
                    user_id,
                    exception,
                )
