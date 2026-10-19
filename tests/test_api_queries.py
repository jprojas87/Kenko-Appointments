from datetime import date, time, timedelta
from urllib.parse import urlencode
from uuid import UUID

from fastapi.testclient import TestClient

from app.models import AppointmentType

TEST_USER_ID = UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000")
OTHER_USER_ID = UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8001")


def auth_headers(token_factory, user_id=TEST_USER_ID, **token_options) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_factory(user_id=user_id, **token_options)}"}


def test_health_works_with_test_database(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "databaseStatus": "ok"}
    assert response.headers["X-Correlation-Id"]


def test_errors_use_uniform_schema(client: TestClient, token_factory) -> None:
    missing = client.get("/api/v1/no-such-route")
    invalid_query = client.get(
        "/api/v1/appointments/available?page=0",
        headers=auth_headers(token_factory),
    )

    assert missing.status_code == 404
    assert invalid_query.status_code == 422
    for response in (missing, invalid_query):
        assert set(response.json()["error"]) == {"code", "message", "correlationId"}
        assert response.json()["error"]["correlationId"] == response.headers["X-Correlation-Id"]


def test_jwt_missing_invalid_and_expired_are_unauthorized(
    client: TestClient, token_factory
) -> None:
    path = "/api/v1/appointments/available"
    responses = (
        client.get(path),
        client.get(path, headers={"Authorization": "Bearer malformed"}),
        client.get(path, headers=auth_headers(token_factory, expires_in_minutes=-1)),
    )

    assert [response.status_code for response in responses] == [401, 401, 401]
    assert all(response.json()["error"]["code"] == "unauthorized" for response in responses)


def test_catalog_endpoints_return_camel_case_and_specialties(
    client: TestClient,
    token_factory,
    records,
) -> None:
    first_center = records["center"]("Sede primaria")
    second_center = records["center"]("Sede secundaria")
    general_physician = records["physician"](
        first_center,
        AppointmentType.GENERAL,
        secondary_center=second_center,
    )
    records["physician"](second_center, AppointmentType.ODONTOLOGIA)
    headers = auth_headers(token_factory)

    physicians_response = client.get("/api/v1/catalog/physicians", headers=headers)
    centers_response = client.get("/api/v1/catalog/medical-centers", headers=headers)

    assert physicians_response.status_code == centers_response.status_code == 200
    physicians = physicians_response.json()
    centers = centers_response.json()
    assert len(physicians) == 2
    assert {"physicianId", "firstName", "lastName", "specialty", "primaryMedCenterId"} <= set(
        physicians[0]
    )
    assert general_physician.physician_id
    center_types = {center["name"]: center["appointmentTypes"] for center in centers}
    assert center_types["Sede primaria"] == ["GENERAL"]
    assert center_types["Sede secundaria"] == ["GENERAL", "ODONTOLOGIA"]
    assert all("medicalCenterId" in center and "location" in center for center in centers)


def test_catalog_endpoints_require_jwt(client: TestClient) -> None:
    for path in ("/api/v1/catalog/physicians", "/api/v1/catalog/medical-centers"):
        response = client.get(path)
        assert response.status_code == 401
        assert set(response.json()["error"]) == {"code", "message", "correlationId"}


def test_available_filters_pagination_order_and_future_unoccupied_only(
    client: TestClient,
    token_factory,
    records,
) -> None:
    center_general = records["center"]("Centro general")
    center_dental = records["center"]("Centro dental")
    general = records["physician"](center_general, AppointmentType.GENERAL)
    dental = records["physician"](center_dental, AppointmentType.ODONTOLOGIA)
    today = date.today()
    first_day, second_day, third_day = (
        today + timedelta(days=1),
        today + timedelta(days=2),
        today + timedelta(days=3),
    )
    first = records["appointment"](general, center_general, first_day, time(9, 0))
    second = records["appointment"](general, center_general, second_day, time(9, 0))
    third = records["appointment"](dental, center_dental, third_day, time(10, 0))
    records["appointment"](
        general,
        center_general,
        first_day,
        time(11, 0),
        user_id=OTHER_USER_ID,
    )
    records["appointment"](
        general,
        center_general,
        today - timedelta(days=1),
        time(9, 0),
    )
    headers = auth_headers(token_factory)
    path = "/api/v1/appointments/available"

    all_items = client.get(path + "?page_size=10", headers=headers).json()
    page_one = client.get(path + "?page_size=1&page=1", headers=headers).json()
    page_two = client.get(path + "?page_size=1&page=2", headers=headers).json()
    by_type = client.get(path + "?type=GENERAL", headers=headers).json()
    by_center = client.get(
        path + "?" + urlencode({"medical_center_id": str(center_dental.medical_center_id)}),
        headers=headers,
    ).json()
    by_physician = client.get(
        path + "?" + urlencode({"physician_id": str(general.physician_id)}),
        headers=headers,
    ).json()
    from_date = client.get(path + f"?date_from={second_day.isoformat()}", headers=headers).json()
    through_date = client.get(path + f"?date_to={second_day.isoformat()}", headers=headers).json()

    assert all_items["total"] == 3
    assert {item["appointmentId"] for item in all_items["items"]} == {
        str(first.appointment_id),
        str(second.appointment_id),
        str(third.appointment_id),
    }
    assert page_one["items"][0]["appointmentId"] != page_two["items"][0]["appointmentId"]
    assert page_one["total"] == page_two["total"] == 3
    assert all(item["type"] == "GENERAL" for item in by_type["items"])
    assert all(
        item["medicalCenter"]["medicalCenterId"] == str(center_dental.medical_center_id)
        for item in by_center["items"]
    )
    assert all(
        item["physician"]["physicianId"] == str(general.physician_id)
        for item in by_physician["items"]
    )
    assert all(item["date"] >= second_day.isoformat() for item in from_date["items"])
    assert all(item["date"] <= second_day.isoformat() for item in through_date["items"])
    ordered = [(item["date"], item["startTime"]) for item in all_items["items"]]
    assert ordered == sorted(ordered)
    assert all(item["startTime"].count(":") == 1 for item in all_items["items"])


def test_my_appointments_is_empty_for_user_without_bookings(
    client: TestClient,
    token_factory,
) -> None:
    response = client.get("/api/v1/appointments/me", headers=auth_headers(token_factory))

    assert response.status_code == 200
    assert response.json() == []
