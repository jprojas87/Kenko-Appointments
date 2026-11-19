resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Alarma: DLQ con mensajes visibles >=1 en 5min
resource "aws_cloudwatch_metric_alarm" "dlq_visible" {
  alarm_name          = "${local.name_prefix}-dlq-visible"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 1
  alarm_description   = "DLQ appointments con mensajes."
  dimensions = {
    QueueName = "${var.profile_queue_name}-dlq"
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  tags          = local.common_tags
}

# Alarma: edad del mensaje más viejo >300s (2 periodos 5min)
resource "aws_cloudwatch_metric_alarm" "queue_age" {
  alarm_name          = "${local.name_prefix}-queue-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 300
  alarm_description   = "Cola appointments sin drenar."
  dimensions = {
    QueueName = var.profile_queue_name
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  tags          = local.common_tags
}

# Alarma: API sin tasks corriendo
resource "aws_cloudwatch_metric_alarm" "api_running" {
  alarm_name          = "${local.name_prefix}-api-no-running"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 300
  statistic           = "Minimum"
  threshold           = 1
  alarm_description   = "API appointments sin tasks."
  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = aws_ecs_service.api.name
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  tags          = local.common_tags
}
