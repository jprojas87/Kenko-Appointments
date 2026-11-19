resource "aws_secretsmanager_secret" "appointments" {
  name                    = "${var.project}/${var.environment}/appointments"
  description             = "Secrets appointments dev: DATABASE_URL, JWT_SECRET y config no sensible."
  recovery_window_in_days = 0

  tags = local.common_tags

  lifecycle {
    ignore_changes = [description]
  }
}

# Placeholder inicial. El valor real se pone vía put-secret-value fuera de TF
# y se ignora en cambios posteriores para no pisarlo.
resource "aws_secretsmanager_secret_version" "appointments_placeholder" {
  secret_id = aws_secretsmanager_secret.appointments.id
  secret_string = jsonencode({
    DATABASE_URL = "REEMPLAZAR-VIA-PUT-SECRET-VALUE"
    JWT_SECRET   = "REEMPLAZAR-VIA-PUT-SECRET-VALUE"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
