variable "project" {
  description = "Prefijo común Kenko."
  type        = string
  default     = "kenko"
}

variable "environment" {
  description = "Entorno."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment debe ser dev o prod."
  }
}

variable "aws_region" {
  description = "Región AWS."
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC existente a reusar."
  type        = string
  default     = "vpc-014ec1d1e62527b66"
}

variable "ecs_cluster_name" {
  description = "Cluster ECS existente."
  type        = string
  default     = "kenko-dev-auth-cluster"
}

variable "public_subnet_ids" {
  description = "Subnets públicas para tasks awsvpc con IP pública (dev)."
  type        = list(string)
  default = [
    "subnet-0043c71cab6cc9422",
    "subnet-053d5bc1211afe9aa",
  ]
}

variable "ecs_security_group_id" {
  description = "SG ECS existente a reusar."
  type        = string
  default     = "sg-033261f5a0531fe94"
}

variable "image_tag" {
  description = "Tag inmutable de la imagen en ECR."
  type        = string
  default     = "0.1.0"
}

variable "api_desired_count" {
  description = "Tasks deseadas API. 0 en primer apply, 1 tras push."
  type        = number
  default     = 0
}

variable "worker_desired_count" {
  description = "Tasks deseadas worker."
  type        = number
  default     = 0
}

variable "alert_email" {
  description = "Email para alarmas SNS."
  type        = string
  default     = "kenko.salud.eps@gmail.com"
}

variable "event_bus_name" {
  type    = string
  default = "kenko-dev-bus"
}

variable "profile_queue_name" {
  type    = string
  default = "kenko-dev-appointments-profile"
}

variable "log_retention_days" {
  type    = number
  default = 14
}
