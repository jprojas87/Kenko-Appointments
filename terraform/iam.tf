data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Execution: pull ECR + logs + leer secreto appointments
resource "aws_iam_role" "execution" {
  name               = "${local.name_prefix}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "execution_base" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.appointments.arn]
  }
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.appointments.arn}:*"]
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "${local.name_prefix}-execution-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

# Task API: solo PutEvents al bus
resource "aws_iam_role" "api_task" {
  name               = "${local.name_prefix}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "api_task_policy" {
  statement {
    actions   = ["events:PutEvents"]
    resources = [data.aws_cloudwatch_event_bus.kenko.arn]
  }
}

resource "aws_iam_role_policy" "api_task" {
  name   = "${local.name_prefix}-api-task"
  role   = aws_iam_role.api_task.id
  policy = data.aws_iam_policy_document.api_task_policy.json
}

# Task Worker: solo SQS cola profile (+ GetQueueUrl para resolver por nombre)
resource "aws_iam_role" "worker_task" {
  name               = "${local.name_prefix}-worker-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "worker_task_policy" {
  statement {
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl"
    ]
    resources = [
      data.aws_sqs_queue.profile.arn,
      data.aws_sqs_queue.profile_dlq.arn,
    ]
  }
}

resource "aws_iam_role_policy" "worker_task" {
  name   = "${local.name_prefix}-worker-task"
  role   = aws_iam_role.worker_task.id
  policy = data.aws_iam_policy_document.worker_task_policy.json
}
