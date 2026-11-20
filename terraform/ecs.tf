locals {
  image = "${aws_ecr_repository.appointments.repository_url}:${var.image_tag}"

  api_env = [
    { name = "ENVIRONMENT", value = var.environment == "prod" ? "prod" : "dev" },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "EVENT_PUBLISHER", value = "eventbridge" },
    { name = "EVENT_BUS_NAME", value = var.event_bus_name },
    { name = "JWT_ALGORITHM", value = "HS256" },
    { name = "JWT_ISSUER", value = "kenko.auth" },
    { name = "JWT_AUDIENCE", value = "kenko-api" },
    { name = "JWT_LEEWAY_SECONDS", value = "120" },
    { name = "PROFILE_QUEUE_NAME", value = var.profile_queue_name },
    { name = "SQS_WAIT_TIME_SECONDS", value = "20" },
    { name = "SQS_MAX_MESSAGES", value = "10" },
    { name = "SQS_VISIBILITY_TIMEOUT", value = "30" },
    { name = "FRONTEND_ORIGINS", value = var.environment == "prod" ? "https://app.kenko.com" : "*" },
    { name = "CORS_ALLOW_CREDENTIALS", value = "true" },
    { name = "MIN_HOURS_BEFORE_CANCEL_OR_RESCHEDULE", value = "24" },
    { name = "MAX_DAYS_AHEAD_TO_SCHEDULE", value = "90" },
  ]

  worker_env = [
    { name = "ENVIRONMENT", value = var.environment == "prod" ? "prod" : "dev" },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "EVENT_PUBLISHER", value = "eventbridge" },
    { name = "EVENT_BUS_NAME", value = var.event_bus_name },
    { name = "JWT_ALGORITHM", value = "HS256" },
    { name = "JWT_ISSUER", value = "kenko.auth" },
    { name = "JWT_AUDIENCE", value = "kenko-api" },
    { name = "PROFILE_QUEUE_NAME", value = var.profile_queue_name },
    { name = "SQS_WAIT_TIME_SECONDS", value = "20" },
    { name = "SQS_MAX_MESSAGES", value = "10" },
    { name = "SQS_VISIBILITY_TIMEOUT", value = "30" },
  ]

  secret_refs = [
    {
      name      = "DATABASE_URL"
      valueFrom = "${aws_secretsmanager_secret.appointments.arn}:DATABASE_URL::"
    },
    {
      name      = "JWT_SECRET"
      valueFrom = "${aws_secretsmanager_secret.appointments.arn}:JWT_SECRET::"
    }
  ]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = local.image
      essential = true
      portMappings = [
        { containerPort = 8002, hostPort = 8002, protocol = "tcp" }
      ]
      environment = local.api_env
      secrets     = local.secret_refs
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.appointments.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health', timeout=3)\" || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])

  tags = local.common_tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn

  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name        = "worker"
      image       = local.image
      essential   = true
      command     = ["python", "-m", "app.workers.profile_consumer"]
      environment = local.worker_env
      secrets     = local.secret_refs
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.appointments.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])

  tags = local.common_tags
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = data.aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = true
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_vpc_security_group_ingress_rule.appointments_8002, aws_lb_listener.api_port]

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8002
  }

  tags = local.common_tags
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name_prefix}-worker"
  cluster         = data.aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = true
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = local.common_tags
}
