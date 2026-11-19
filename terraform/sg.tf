# SG: abrir 8002 (appointments API) en el SG ECS existente. Aditivo, no toca 3000/8080.
resource "aws_vpc_security_group_ingress_rule" "appointments_8002" {
  security_group_id = var.ecs_security_group_id
  description       = "kenko-dev-appointments-api-8002-dev-only"
  ip_protocol       = "tcp"
  from_port         = 8002
  to_port           = 8002
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.common_tags
}
