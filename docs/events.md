# Contrato de eventos de Appointments

Appointments publica eventos en EventBridge; no consume eventos, crea colas, DLQ ni reglas. Notifications crea su propia infraestructura SQS y consume el evento completo entregado por EventBridge.

## Bus, fuente y convenciones

- Desarrollo: `kenko-dev-bus`; producción: `kenko-prod-bus`.
- `Source`: `kenko.appointments`.
- `DetailType`: `AppointmentScheduled`, `AppointmentRescheduled` o `AppointmentCancelled`.
- `Detail`: JSON con `metadata` y `data`.
- Todas las claves son camelCase. El usuario siempre se identifica como `userId`, nunca `patientId`.
- `metadata.eventId` es UUID v4 nuevo por evento; `eventVersion` es la cadena `"1"`.
- `occurredAt`, `scheduledAt`, `rescheduledAt` y `cancelledAt` son ISO-8601 UTC con sufijo `Z`.
- `correlationId` toma `X-Correlation-Id` o se genera; el mismo ID aparece en logs y header de respuesta.
- `email` viene del claim `email` del JWT. Si falta, el evento lo incluye como `null` y el servicio registra un warning.
- Los eventos llevan la cita completa; Notifications no necesita consultar Appointments.
- `appointment.date` es `YYYY-MM-DD`; `startTime` y `endTime` son `HH:MM`, interpretados en `America/Bogota`.
- Se entrega al menos una vez. Notifications debe deduplicar con `metadata.eventId`.

## `AppointmentScheduled`

```json
{
  "source": "kenko.appointments",
  "detail-type": "AppointmentScheduled",
  "detail": {
    "metadata": {
      "eventId": "b6e7cfd2-4f84-4b65-8d63-0ef9ebd76784",
      "eventVersion": "1",
      "occurredAt": "2026-10-06T16:10:00Z",
      "correlationId": "7e8f9a0b-2c3d-4e5f-9a1b-3c4d5e6f7a8b"
    },
    "data": {
      "userId": "0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000",
      "email": "usuario@correo.com",
      "scheduledAt": "2026-10-06T16:10:00Z",
      "appointment": {
        "appointmentId": "c98ca986-23c2-4118-bdf4-5a0c6a90c63c",
        "type": "ODONTOLOGIA",
        "date": "2026-10-20",
        "weekday": "Tuesday",
        "startTime": "09:00",
        "endTime": "09:30",
        "physician": {
          "physicianId": "6c0e1e0f-22b3-4f75-99c1-00a8dcb6f763",
          "name": "Laura Gómez"
        },
        "medicalCenter": {
          "medicalCenterId": "4778d84a-ece8-49df-8e5e-0b4178359024",
          "name": "Centro Médico Norte",
          "location": "Calle 100 # 15-20, Bogotá"
        }
      }
    }
  }
}
```

## `AppointmentRescheduled`

```json
{
  "source": "kenko.appointments",
  "detail-type": "AppointmentRescheduled",
  "detail": {
    "metadata": {
      "eventId": "a0a9d3d6-13e3-4df1-8723-98db7f4c0e10",
      "eventVersion": "1",
      "occurredAt": "2026-10-07T09:20:00Z",
      "correlationId": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
    },
    "data": {
      "userId": "0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000",
      "email": "usuario@correo.com",
      "rescheduledAt": "2026-10-07T09:20:00Z",
      "previousAppointment": {
        "appointmentId": "c98ca986-23c2-4118-bdf4-5a0c6a90c63c",
        "type": "ODONTOLOGIA",
        "date": "2026-10-20",
        "weekday": "Tuesday",
        "startTime": "09:00",
        "endTime": "09:30",
        "physician": {
          "physicianId": "6c0e1e0f-22b3-4f75-99c1-00a8dcb6f763",
          "name": "Laura Gómez"
        },
        "medicalCenter": {
          "medicalCenterId": "4778d84a-ece8-49df-8e5e-0b4178359024",
          "name": "Centro Médico Norte",
          "location": "Calle 100 # 15-20, Bogotá"
        }
      },
      "appointment": {
        "appointmentId": "beae3111-92cd-4cb1-8e17-34f522b4868f",
        "type": "ODONTOLOGIA",
        "date": "2026-10-22",
        "weekday": "Thursday",
        "startTime": "14:30",
        "endTime": "15:00",
        "physician": {
          "physicianId": "6c0e1e0f-22b3-4f75-99c1-00a8dcb6f763",
          "name": "Laura Gómez"
        },
        "medicalCenter": {
          "medicalCenterId": "4778d84a-ece8-49df-8e5e-0b4178359024",
          "name": "Centro Médico Norte",
          "location": "Calle 100 # 15-20, Bogotá"
        }
      }
    }
  }
}
```

## `AppointmentCancelled`

```json
{
  "source": "kenko.appointments",
  "detail-type": "AppointmentCancelled",
  "detail": {
    "metadata": {
      "eventId": "e635e5c5-69c6-40b9-a70a-a65f9ac09861",
      "eventVersion": "1",
      "occurredAt": "2026-10-08T11:05:00Z",
      "correlationId": "9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a"
    },
    "data": {
      "userId": "0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000",
      "email": "usuario@correo.com",
      "cancelledAt": "2026-10-08T11:05:00Z",
      "appointment": {
        "appointmentId": "beae3111-92cd-4cb1-8e17-34f522b4868f",
        "type": "ODONTOLOGIA",
        "date": "2026-10-22",
        "weekday": "Thursday",
        "startTime": "14:30",
        "endTime": "15:00",
        "physician": {
          "physicianId": "6c0e1e0f-22b3-4f75-99c1-00a8dcb6f763",
          "name": "Laura Gómez"
        },
        "medicalCenter": {
          "medicalCenterId": "4778d84a-ece8-49df-8e5e-0b4178359024",
          "name": "Centro Médico Norte",
          "location": "Calle 100 # 15-20, Bogotá"
        }
      }
    }
  }
}
```

## Infraestructura del consumidor Notifications

Appointments solo publica al bus existente. Notifications/equipo de infraestructura crea las colas, DLQ, regla y permisos de entrega.

- Convención de colas: `{proyecto}-{entorno}-{consumidor}-{productor}[-dlq]`.
- Cola: `kenko-dev-notifications-appointments`.
- DLQ: `kenko-dev-notifications-appointments-dlq`.
- Regla: `appointments-to-notifications`.
- Patrón de evento:

```json
{
  "source": ["kenko.appointments"],
  "detail-type": [
    "AppointmentScheduled",
    "AppointmentRescheduled",
    "AppointmentCancelled"
  ]
}
```

El mensaje recibido por SQS es el evento completo de EventBridge; los datos propios de Appointments están bajo `detail.metadata` y `detail.data`.

Recomendaciones para la infraestructura compartida:

- Redrive con `maxReceiveCount=3`.
- Retención de 14 días en DLQ y 4 días en la cola de trabajo.
- Long polling de 20 segundos.
- SSE-SQS.
- Queue policy que autorice a EventBridge usando `aws:SourceArn` de la regla.
- Tag `project=kenko`.
- Entrega al menos una vez: Notifications deduplica por `detail.metadata.eventId`.

## Publicación e IAM

El productor envía `PutEvents` al bus con `Source=kenko.appointments`, `DetailType` del evento y `Detail` serializado como JSON. El permiso mínimo del rol de Appointments es `events:PutEvents` sobre el ARN del bus correspondiente. Appointments no necesita permisos SQS ni de administración de EventBridge.

El servicio confirma la transacción antes de publicar y hace hasta tres intentos. Si todos fallan, la operación queda confirmada y se registra el error con correlation ID, event ID y user ID; el evento puede perderse. Una mejora futura es Outbox.
