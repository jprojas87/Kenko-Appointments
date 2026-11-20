variable "vpc_endpoint_security_group_id" {
  description = "SG de los VPC endpoints de logs/events (lo maneja otro equipo; solo agregamos regla aditiva 443 desde nuestro SG ECS)."
  type        = string
  default     = "sg-02d7fd1ba3cf7bbed"
}

# Regla ADITIVA: permite a las tasks de appointments (SG ECS) llegar a
# CloudWatch Logs y EventBridge via los VPC endpoints (DNS privado activo).
# Sigue el mismo patron que ya existe para Lambda/EC2/profile.
# Largo plazo: pedir al equipo dueño del SG que la incluya en su repo.
resource "aws_vpc_security_group_ingress_rule" "endpoints_from_appointments" {
  security_group_id            = var.vpc_endpoint_security_group_id
  description                  = "HTTPS desde kenko-dev-appointments-ecs (logs/events)"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = var.ecs_security_group_id
  tags                         = local.common_tags
}
