from sqlalchemy.orm import Session, sessionmaker

import app.console as console
from app.models import Appointment
from seeds.demo import demo_appointment_ids, run_demo_seed


def test_console_selects_user_and_shows_shared_slots_and_user_appointments(
    test_engine,
    monkeypatch,
    capsys,
) -> None:
    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    run_demo_seed(test_session_factory)
    with Session(test_engine) as session:
        appointment = session.get(Appointment, demo_appointment_ids()[0])
        assert appointment is not None
        appointment.user_id = "USR02"
        session.commit()

    monkeypatch.setattr(console, "create_tables", lambda: None)
    monkeypatch.setattr(console, "SessionLocal", test_session_factory)
    choices = iter(("1", "q"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(choices))

    console.main()

    output = capsys.readouterr().out
    assert "Usuario actual: USR01" in output
    assert "Citas demo compartidas (20 de 20)" in output
    assert "Mis citas (0)" in output
    assert "OCUPADA" in output
    assert "USR02" in output


def test_console_schedules_for_selected_user(test_engine, monkeypatch, capsys) -> None:
    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    run_demo_seed(test_session_factory)
    monkeypatch.setattr(console, "create_tables", lambda: None)
    monkeypatch.setattr(console, "SessionLocal", test_session_factory)
    choices = iter(("1", "1", "1", "0"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(choices))

    console.main()

    with Session(test_engine) as session:
        appointment = session.get(Appointment, demo_appointment_ids()[0])
        assert appointment is not None
        assert appointment.user_id == "USR01"
    assert "Cita agendada" in capsys.readouterr().out


def test_console_reschedules_then_cancels_selected_user_appointments(
    test_engine,
    monkeypatch,
    capsys,
) -> None:
    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    run_demo_seed(test_session_factory)
    with Session(test_engine) as session:
        appointment = session.get(Appointment, demo_appointment_ids()[0])
        assert appointment is not None
        appointment.user_id = "USR01"
        session.commit()

    monkeypatch.setattr(console, "create_tables", lambda: None)
    monkeypatch.setattr(console, "SessionLocal", test_session_factory)
    choices = iter(("1", "2", "1", "2", "3", "2", "0"))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(choices))

    console.main()

    with Session(test_engine) as session:
        old_appointment = session.get(Appointment, demo_appointment_ids()[0])
        new_appointment = session.get(Appointment, demo_appointment_ids()[1])
        assert old_appointment is not None
        assert new_appointment is not None
        assert old_appointment.user_id is None
        assert new_appointment.user_id is None
    output = capsys.readouterr().out
    assert "Cita reagendada" in output
    assert "Cita cancelada" in output
