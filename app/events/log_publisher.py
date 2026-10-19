import json
import logging

from app.events.envelope import EVENT_SOURCE

logger = logging.getLogger(__name__)


class LogPublisher:
    def publish(self, detail_type: str, detail: dict[str, object]) -> None:
        event = {
            "source": EVENT_SOURCE,
            "detail-type": detail_type,
            "detail": detail,
        }
        logger.info("EventBridge event: %s", json.dumps(event, ensure_ascii=False))
