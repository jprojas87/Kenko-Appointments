# Despliegue appointments dev — 2026-11-19 — 100% operativo

Reutiliza infra `auth` (cuenta `137696817246`, `us-east-1`), patrón `notifications`.

## Recursos reusados (no creados)
- VPC `vpc-014ec1d1e62527b66`, subnets públicas `subnet-0043c71cab6cc9422` (1a) + `subnet-053d5bc1211afe9aa` (1b), SG `sg-033261f5a0531fe94` (+ingress `8002` aditivo)
- Cluster `kenko-dev-auth-cluster`, RDS `kenko-dev-auth-db.cezucwi0oldg.us-east-1.rds.amazonaws.com:5432` (postgres 18.6)
- Bus `kenko-dev-bus` (`arn:aws:events:us-east-1:137696817246:event-bus/kenko-dev-bus`)
- SQS `kenko-dev-appointments-profile` + DLQ + regla `kenko-dev-profile-to-appointments` (ya existían, con 5 mensajes que el worker drenó a 0)
- SSM `/kenko/dev/rds_postgres_url`, `/kenko/dev/db_password`, `/kenko/dev/jwt_secret`
- Bastión `i-0803e33ee6b61438d` (SSM Online) para crear DB

## Recursos creados (Terraform `terraform/`, backend `s3://kenko-tfstate-137696817246-us-east-1/kenko-appointments-dev.tfstate`)
- ECR `137696817246.dkr.ecr.us-east-1.amazonaws.com/kenko-dev-appointments:0.1.0` (IMMUTABLE, scan on push)
- Secreto `arn:aws:sns:us-east-1:137696817246:secret:kenko/dev/appointments-OZnzPi` → `kenko/dev/appointments` (`DATABASE_URL` psycopg+ssl + `JWT_SECRET` de Auth)
- Log group `/ecs/kenko-dev-appointments` (14d)
- Roles: `kenko-dev-appointments-execution` (ECR+logs+secrets), `-api-task` (solo `events:PutEvents` bus), `-worker-task` (solo SQS `Receive/Delete/GetAttributes/GetQueueUrl` cola+DLQ)
- ECS Fargate ARM64 256/512: `kenko-dev-appointments-api` (8002, health `/health`) + `kenko-dev-appointments-worker` (`python -m app.workers.profile_consumer`), ambos `1/1 RUNNING`, `assignPublicIp=ENABLED`, circuit breaker+rollback
- SNS `arn:aws:sns:us-east-1:137696817246:kenko-dev-appointments-alerts` + sub email `kenko.salud.eps@gmail.com` (**pendiente confirmar** en correo, estado `PendingConfirmation`)
- Alarmas: DLQ visible>=1, queue age>300s, api running<1
- DB: `DATABASE appointments_db` + `USER appointments_user` (owner kenko_auth, grants schema public), verificado `SELECT 1` + write test

## E2E dev (IP pública efímera `3.224.127.142:8002`)
- `GET /health` → `{"status":"ok","databaseStatus":"ok"}`
- Worker consumió 5 `ProfileCreated` → `users` (logs `Usuario creado...`), cola `5→0`
- Token HS256 (`iss kenko.auth`, `aud kenko-api`, `sub` v7 real) → `available` 0 → seed `python -m seeds.run` vía `run-task` → `5880` citas → `POST .../schedule` 200 → `GET /me` con cita
- `EVENT_PUBLISHER=eventbridge`, `EVENT_BUS_NAME=kenko-dev-bus`, sin `FailedEntryCount` en logs
- `pytest`: `36 passed`, `terraform validate`: `Success`, `apply`: `22 added` + `2 changed`, `0 destroyed`

## Pendientes no bloqueantes
1. Confirmar suscripción SNS en el correo de `kenko.salud.eps@gmail.com`.
2. Backlog: Alembic (hoy `create_all`), Outbox para `PutEvents`, JWKS.
3. Prod: replicar con `prod.tfvars`, ALB+ACM+WAF, RDS propio Multi-AZ, `FRONTEND_ORIGINS=https://app.kenko.com`.

## Comandos útiles
```bash
terraform -chdir=terraform init
terraform -chdir=terraform plan -var-file=envs/dev.tfvars
aws ecs describe-services --cluster kenko-dev-auth-cluster --services kenko-dev-appointments-api kenko-dev-appointments-worker --region us-east-1
aws logs tail /ecs/kenko-dev-appointments --since 10m --region us-east-1
```
