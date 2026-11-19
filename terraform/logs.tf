resource "aws_cloudwatch_log_group" "appointments" {
  name              = "/ecs/${var.project}-${var.environment}-appointments"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}
