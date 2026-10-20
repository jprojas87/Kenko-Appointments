import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("USR01,USR02", ("USR01", "USR02")),
        ("user1,abcde", ("USER1", "ABCDE")),
    ],
)
def test_demo_user_ids_are_normalized(value: str, expected: tuple[str, ...]) -> None:
    settings = Settings(_env_file=None, demo_user_ids=value)

    assert settings.configured_demo_user_ids == expected


@pytest.mark.parametrize("value", ["USR01", "USR01,USR01", "TOO-LONG,USR02", "USR0,USR02"])
def test_demo_user_ids_require_two_unique_five_character_alphanumeric_values(
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, demo_user_ids=value)
