# Kenko Appointments

Microservicio backend de citas de la sucursal virtual de Kenko. Permite consultar disponibilidad, agendar, cancelar y reagendar citas, consultar el catálogo médico y publicar eventos para Notifications. Appointments opera con su propia base PostgreSQL y no consume eventos ni llama a otros servicios.

## Requisitos

- Python 3.12 y [uv](https://docs.astral.sh/uv/).
- Docker y Docker Compose.
- WSL2/Ubuntu recomendado para desarrollo en Windows.
- Para publicar en AWS: cuenta y credenciales válidas con permiso mínimo `events:PutEvents` sobre el bus configurado.

## Inicio desde cero

Desde la raíz del repositorio:

```bash
uv sync
docker network inspect kenko-net >/dev/null 2>&1 || docker network create kenko-net
cp .env.example .env
docker compose up -d --build
docker compose ps
curl http://localhost:8002/health
docker compose exec appointments-api python -m seeds.run
```

La red externa `kenko-net` conecta Appointments con los otros microservicios. Se crea una sola vez con `docker network create kenko-net`. El healthcheck de Compose espera a PostgreSQL antes de iniciar la API. `/health` responde `200` cuando el proceso y la base de datos están disponibles.

Comandos útiles:

```bash
docker compose logs -f appointments-api
docker compose exec appointments-api python -m seeds.run
DATABASE_URL='postgresql+psycopg://appointments:appointments@localhost:5433/appointments_db' uv run python -m seeds.demo
DATABASE_URL='postgresql+psycopg://appointments:appointments@localhost:5433/appointments_db' uv run python -m app.console
docker compose down
docker compose down -v  # elimina también el volumen y todos los datos locales
```

La base de datos está disponible en el host en `localhost:5433`; dentro de Compose, la API se conecta a `appointments-db:5432`. La API escucha en el puerto `8002`.

## Demostración local desde consola

La demostración no requiere frontend ni levantar la API: la consola se conecta directamente a PostgreSQL. Desde la raíz del proyecto:

```bash
uv sync
docker compose up -d appointments-db
export DATABASE_URL='postgresql+psycopg://appointments:appointments@localhost:5433/appointments_db'
uv run python -m seeds.demo
uv run python -m app.console
```

`seeds.demo` crea 20 citas futuras compartidas y es seguro volverlo a ejecutar. La consola muestra solo ese conjunto demo, aunque la base también tenga citas del seed estándar. `seeds.run` es la carga masiva existente y no es necesario para esta demostración. Al iniciar, la consola crea las tablas si hacen falta y migra `appointments.user_id` de UUID a texto, conservando los IDs existentes.

Configura los usuarios en `.env` con `DEMO_USER_IDS=USR01,USR02`. Se aceptan dos o más IDs únicos, de cinco caracteres alfanuméricos; se normalizan a mayúsculas. En la consola elige el usuario, luego selecciona una opción: `1` agendar, `2` reagendar, `3` cancelar, `4` cambiar usuario o `0` salir. Las citas se seleccionan por el número de la lista. Todos los usuarios comparten los mismos espacios: una cita agendada aparece como ocupada para los demás.

Se aplican las reglas de negocio existentes: reagendar requiere elegir una cita disponible del mismo tipo; cancelar y reagendar requieren al menos 24 horas de anticipación. La consola escribe los eventos localmente en los logs y no envía operaciones a EventBridge.

Para inspeccionar los cambios en TablePlus, conecta a PostgreSQL con **Host** `localhost`, **Port** `5433`, **Database** `appointments_db`, **User** `appointments` y **Password** `appointments`. Consulta `public.appointments`: `user_id` es `NULL` en espacios disponibles y contiene el ID (por ejemplo, `USR01`) cuando está agendada. No uses `docker compose down -v` para detener la demostración: esa opción elimina el volumen y los datos locales.

Para ejecutar la API desde WSL en el host, con PostgreSQL de Compose activo:

```bash
DATABASE_URL='postgresql+psycopg://appointments:appointments@localhost:5433/appointments_db' \
  uv run uvicorn app.main:app --reload --port 8002
```

Swagger está disponible en <http://localhost:8002/docs>. Usa **Authorize** y pega el token como Bearer.

## Tokens de desarrollo

Authentication es el emisor esperado en los entornos integrados. Para desarrollo local, genera un token firmado con la configuración local:

```bash
uv run python -m scripts.make_token \
  --user-id 0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000 \
  --email usuario@correo.com \
  --minutes 60
```

El token contiene `sub` (ID de usuario), `email`, `iat` y `exp`. La API acepta UUID existentes y también IDs de texto como los usuarios locales configurados en `DEMO_USER_IDS`. Para probar un token sin correo, agrega `--omit-email`; la API registra un warning y los eventos llevan `"email": null`. Para probar un token vencido, usa `--minutes -1`.

Con `JWT_ALGORITHM=RS256`, el validador usa `JWT_PUBLIC_KEY`; para firmar un token de prueba, pasa la clave privada PEM con `--private-key /ruta/privada.pem`.

## API REST

Todas las rutas, excepto `/health`, requieren `Authorization: Bearer <token>`. El `userId` se obtiene exclusivamente de `sub`; nunca se recibe en el body. Las respuestas usan camelCase. Las horas y fechas de las citas se interpretan en `America/Bogota`.

En estos ejemplos, primero define un token y reemplaza los UUID de cita/centro/médico por los valores devueltos por la API:

```bash
TOKEN="$(uv run python -m scripts.make_token --user-id 0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000 --email usuario@correo.com)"
```

### Salud

```bash
curl http://localhost:8002/health
```

### Citas disponibles

Filtros opcionales: `type`, `medical_center_id`, `physician_id`, `date_from`, `date_to`; paginación con `page` y `page_size`.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8002/api/v1/appointments/available?page=1&page_size=20'

curl -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8002/api/v1/appointments/available?type=ODONTOLOGIA&medical_center_id=UUID&physician_id=UUID&date_from=2026-10-20&date_to=2026-11-20&page=1&page_size=20'
```

Solo aparecen citas futuras con `userId` nulo. La respuesta contiene `page`, `pageSize`, `total`, `items`, y cada cita incluye médico y centro con ubicación.

### Mis citas

Por defecto devuelve solo citas futuras. `include_past=true` incluye también citas pasadas.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8002/api/v1/appointments/me'

curl -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8002/api/v1/appointments/me?include_past=true'
```

### Agendar, reagendar y cancelar

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8002/api/v1/appointments/UUID_CITA/schedule'

curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"newAppointmentId":"UUID_NUEVA_CITA"}' \
  'http://localhost:8002/api/v1/appointments/UUID_CITA/reschedule'

curl -X POST -H "Authorization: Bearer $TOKEN" \
  'http://localhost:8002/api/v1/appointments/UUID_CITA/cancel'
```

Agendar requiere una cita disponible, futura y dentro de `MAX_DAYS_AHEAD_TO_SCHEDULE`. Cancelar y reagendar requieren que la cita actual pertenezca al usuario y que se cumpla `MIN_HOURS_BEFORE_CANCEL_OR_RESCHEDULE`. Reagendar exige que la cita nueva esté disponible, sea futura y tenga el mismo tipo.

### Catálogos

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/api/v1/catalog/physicians

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/api/v1/catalog/medical-centers
```

Los centros incluyen `appointmentTypes`, calculado a partir de las especialidades de los médicos asignados a su sede principal o secundaria.

## Errores

Todos los errores siguen este esquema, incluyendo errores de validación y rutas inexistentes:

```json
{
  "error": {
    "code": "not_found",
    "message": "Cita no encontrada",
    "correlationId": "9f6c9f73-9200-4e60-a1b6-d9498f6c4819"
  }
}
```

Los códigos HTTP usados incluyen `400`, `401`, `403`, `404`, `409`, `422` y `503`. Una cita no disponible produce `409`; una regla de negocio incumplida o validación produce `422`. Cancelar o reagendar una cita inexistente o ajena devuelve `404` para no revelar su existencia. Cada respuesta incluye `X-Correlation-Id`, recibido del request o generado por el servicio.

## Variables de entorno

La configuración se carga desde `.env` o el entorno del proceso. No versionar `.env`; `.gitignore` lo excluye. `.env.example` contiene los valores de desarrollo.

| Variable | Valor predeterminado | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://appointments:appointments@appointments-db:5432/appointments_db` | URL desde Docker. Desde el host usa `postgresql+psycopg://appointments:appointments@localhost:5433/appointments_db`. |
| `ENVIRONMENT` | `dev` | Entorno. |
| `LOG_LEVEL` | `INFO` | Nivel de logs. |
| `JWT_ALGORITHM` | `HS256` | Algoritmo aceptado: `HS256` o `RS256`. |
| `JWT_SECRET` | `change-me-dev-only` | Clave HS256 local; reemplazar fuera de desarrollo. |
| `JWT_PUBLIC_KEY` | vacío | Clave pública PEM para RS256. |
| `JWT_ISSUER` | vacío | Emisor validado solo cuando está configurado. |
| `JWT_AUDIENCE` | vacío | Audiencia validada solo cuando está configurada. |
| `DEMO_USER_IDS` | `USR01,USR02` | Usuarios locales disponibles; IDs únicos de cinco caracteres alfanuméricos separados por comas. |
| `MIN_HOURS_BEFORE_CANCEL_OR_RESCHEDULE` | `24` | Anticipación mínima para cancelar/reagendar. |
| `MAX_DAYS_AHEAD_TO_SCHEDULE` | `90` | Antelación máxima para agendar. |
| `EVENT_PUBLISHER` | `log` | `log` o `eventbridge`. |
| `EVENT_BUS_NAME` | `kenko-dev-bus` | Bus de EventBridge. En producción: `kenko-prod-bus`. |
| `AWS_REGION` | `us-east-1` | Región AWS. |
| `AWS_ENDPOINT_URL` | vacío | Vacío usa AWS real; no se usan credenciales en el código. |

Para AWS, configura credenciales mediante la cadena estándar de AWS (rol de ejecución/perfil/variables del entorno), fuera del repositorio. El permiso de mínimo privilegio es `events:PutEvents` sobre el bus requerido; no uses credenciales de administrador.

## Eventos y limitación de publicación

Appointments publica únicamente al bus de EventBridge; no crea colas, DLQ ni reglas. `EVENT_PUBLISHER=log` es el valor predeterminado y permite desarrollar sin AWS; `eventbridge` activa el publicador boto3. EventBridge usa `Source=kenko.appointments`, `DetailType` PascalCase y el detalle `metadata` + `data`. El contrato, ejemplos completos y recomendaciones para Notifications están en [`docs/events.md`](docs/events.md).

La publicación sucede después del `commit`, con hasta tres intentos. Si el commit funciona y la publicación falla, la operación de negocio permanece confirmada, pero el evento se pierde. La mejora futura para cerrar esa ventana es el patrón Outbox.

## Pruebas y calidad

PostgreSQL de Docker debe estar activo. `pytest` crea y limpia automáticamente una base independiente `appointments_test` (por defecto, `localhost:5433`); no usa la base de desarrollo.

```bash
docker compose up -d appointments-db
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Supuestos

- `/health` se sirve en la raíz, sin prefijo `/api/v1`, para healthchecks.
- Intentar cancelar o reagendar una cita ajena equivale a `404`.
- `appointmentTypes` de cada centro deriva de médicos en su sede principal/secundaria.
- `page` empieza en 1, `page_size` predeterminado es 20; `/me` usa `include_past=false` por defecto.
- `date_from` posterior a `date_to` produce `422`.
- El seed usa UUID v5 deterministas para que sea idempotente; los UUID operativos usan `uuid4`.
- Para generar tokens RS256 se requiere la clave privada PEM mediante `--private-key`; el servicio valida con `JWT_PUBLIC_KEY`.
- PyJWT usa su extra oficial `crypto` para habilitar la validación RS256, que requiere el backend criptográfico de PyJWT.
- El claim `email` puede faltar: se registra warning y se publica como `null` sin consultar otros servicios.

## Pendientes

- [ ] Confirmar con el equipo EventBridge + SQS frente a HTTP interno. La implementación actual sigue la decisión EventBridge + SQS.
- [ ] Confirmar con Authentication los claims `sub`, `email`, `role` y el algoritmo definitivo. Es crítico que incluya `email`.
- [ ] Confirmar quién crea bus, colas y reglas; se recomienda un repositorio compartido `kenko-infra`.
- [ ] Confirmar cómo Notifications obtiene el correo; en esta versión llega en el evento como `email`.
- [ ] Acordar el formato común de errores y el contrato de `X-Correlation-Id`.
- [ ] Confirmar si los servicios migrarán a UUID v7; Appointments usa UUID v4 fuera de los IDs deterministas del seed.

## Checklist final de entrega

- [x] Stack de la sección 3 y restricciones de la sección 4 — `pyproject.toml`, `Dockerfile`; sin Alembic, LocalStack, colas propias ni tecnologías prohibidas.
- [x] Tres tablas, enums, relaciones, `user_id` sin FK e índices — `app/models.py`; evidencia: `docker compose exec appointments-db psql ... '\d appointments'`.
- [x] Endpoints de citas, consultas, catálogos y health — `app/routes/appointments.py`, `app/routes/catalog.py`, `app/routes/health.py`.
- [x] Doble reserva protegida por `UPDATE` condicional y reagendamiento con bloqueo ordenado — `app/services/appointment_service.py`.
- [x] JWT, `sub` como `userId`, email opcional y script de tokens — `app/security.py`, `scripts/make_token.py`.
- [x] Tres eventos con contrato camelCase, `userId`, `email` y timestamps UTC — `app/events/envelope.py`, `tests/test_event_contract.py`, `docs/events.md`.
- [x] Publicación tras commit, reintentos, control de `FailedEntryCount`, tamaño y timeouts — `app/services/appointment_service.py`, `app/events/publisher.py`, `app/events/eventbridge_publisher.py`.
- [x] Publicadores intercambiables `log`, `eventbridge` y fake; `log` predeterminado — `app/events/`, `.env.example`.
- [x] Correlation ID en logs, headers y metadata — `app/logging_config.py`, `app/events/envelope.py`.
- [x] Docker multi-etapa no root, healthchecks y red externa documentada — `Dockerfile`, `docker-compose.yml`, esta guía.
- [x] Seed idempotente de centros, médicos y citas — `seeds/run.py`; evidencia: ejecución doble con conteos estables.
- [x] Seed demo de 20 citas y consola interactiva para usuarios locales — `seeds/demo.py`, `app/console.py`.
- [x] Variables de entorno, `.gitignore` y `.dockerignore`; sin `.env` versionado — `.env.example`, `.gitignore`, `.dockerignore`.
- [x] Guía de ejecución, endpoints, supuestos, pendientes, eventos e IAM — `README.md`, `docs/events.md`.
- [x] Pruebas y Ruff — `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`.
