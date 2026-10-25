"""Worker separado: lee kenko-dev-appointments-profile (SQS) y puebla users.

Uso:
    python -m app.workers.profile_consumer

Lee en loop con long-polling, procesa ProfileCreated de forma idempotente
y hace DELETE solo tras guardar en BD. Los fallos se dejan para reintento
y tras maxReceiveCount caen a la DLQ (redrive configurado en infra).
"""

import logging
import signal
import time

import boto3
from botocore.config import Config
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, create_tables
from app.logging_config import configure_logging
from app.services.profile_ingest import parse_profile_created, upsert_user

logger = logging.getLogger(__name__)

_running = True


def _handle_stop(signum, _frame) -> None:
    global _running
    logger.info("Worker profile: señal %s, cerrando...", signum)
    _running = False


def build_sqs_client():
    return boto3.client(
        "sqs",
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url or None,
        config=Config(
            connect_timeout=5,
            read_timeout=70,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def resolve_queue_url(sqs_client) -> str:
    if settings.profile_queue_url:
        return settings.profile_queue_url
    response = sqs_client.get_queue_url(QueueName=settings.profile_queue_name)
    return response["QueueUrl"]


def process_body(body: str, database_session: Session) -> bool:
    """Procesa un Body SQS. True = OK para DELETE. False = ignorado sin error."""
    parsed = parse_profile_created(body)
    if parsed is None:
        return True
    user_id, email = parsed
    upsert_user(database_session, user_id, email)
    return True


def run_forever() -> None:
    configure_logging()
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    create_tables()

    sqs = build_sqs_client()
    queue_url = resolve_queue_url(sqs)
    logger.info(
        "Worker profile escuchando cola=%s url=%s region=%s",
        settings.profile_queue_name,
        queue_url,
        settings.aws_region,
    )

    while _running:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=min(max(settings.sqs_max_messages, 1), 10),
                WaitTimeSeconds=settings.sqs_wait_time_seconds,
                VisibilityTimeout=settings.sqs_visibility_timeout,
            )
        except Exception as exception:
            logger.error("SQS receive_message falló: %r", exception)
            time.sleep(5)
            continue

        for message in response.get("Messages", []):
            receipt = message.get("ReceiptHandle", "")
            body = message.get("Body", "")
            message_id = message.get("MessageId", "-")
            try:
                with SessionLocal() as database_session:
                    process_body(body, database_session)
            except ValueError as exception:
                # Mensaje envenenado (ProfileCreated inválido): log y DELETE
                # para no bloquear la cola; el caso queda en logs con messageId.
                logger.error(
                    "ProfileCreated inválido, se descarta: messageId=%s error=%s",
                    message_id,
                    exception,
                )
                try:
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                except Exception as delete_error:
                    logger.error("No se pudo borrar mensaje inválido: %r", delete_error)
                continue
            except Exception as exception:
                logger.error(
                    "Fallo procesando messageId=%s, se deja para reintento/DLQ: %r",
                    message_id,
                    exception,
                )
                continue
            try:
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
            except Exception as exception:
                logger.error("No se pudo borrar messageId=%s: %r", message_id, exception)


if __name__ == "__main__":
    run_forever()
