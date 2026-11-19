data "aws_vpc" "main" {
  id = var.vpc_id
}

data "aws_ecs_cluster" "main" {
  cluster_name = var.ecs_cluster_name
}

data "aws_cloudwatch_event_bus" "kenko" {
  name = var.event_bus_name
}

data "aws_sqs_queue" "profile" {
  name = var.profile_queue_name
}

data "aws_sqs_queue" "profile_dlq" {
  name = "${var.profile_queue_name}-dlq"
}

data "aws_security_group" "ecs" {
  id = var.ecs_security_group_id
}

locals {
  name_prefix = "${var.project}-${var.environment}-appointments"
  common_tags = {
    Project     = var.project
    Environment = var.environment
    Service     = "appointments"
    ManagedBy   = "terraform"
  }
}
