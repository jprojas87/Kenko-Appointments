from copy import deepcopy

from app.events.envelope import EVENT_SOURCE


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def publish(self, detail_type: str, detail: dict[str, object]) -> None:
        self.events.append(
            {
                "source": EVENT_SOURCE,
                "detail-type": detail_type,
                "detail": deepcopy(detail),
            }
        )
