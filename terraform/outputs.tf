output "ecr_url" {
  value = aws_ecr_repository.appointments.repository_url
}

output "secret_arn" {
  value = aws_secretsmanager_secret.appointments.arn
}

output "ecs_api_service" {
  value = aws_ecs_service.api.name
}

output "ecs_worker_service" {
  value = aws_ecs_service.worker.name
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "log_group" {
  value = aws_cloudwatch_log_group.appointments.name
}
