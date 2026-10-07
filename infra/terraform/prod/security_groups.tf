# Two security groups, and the only inbound rules in the stack:
#
#   internet --80/443--> web (EC2) --5432--> db (RDS)
#
# No SSH. The host is reached through SSM Session Manager, which is an
# OUTBOUND connection from the SSM agent and needs no inbound rule.

resource "aws_security_group" "web" {
  name_prefix = "${local.name}-web-"
  description = "HerHealthGPT host: Caddy on 80/443, nothing else inbound"
  vpc_id      = aws_vpc.main.id

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name}-web" }
}

resource "aws_vpc_security_group_ingress_rule" "web_http" {
  security_group_id = aws_security_group.web.id
  description       = "HTTP: Let's Encrypt HTTP-01 challenge and redirect to HTTPS"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "web_https" {
  security_group_id = aws_security_group.web.id
  description       = "HTTPS"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# Outbound is open: ECR, Secrets Manager, SES, OpenRouter, the retrieval
# service's guarded web fallback, Let's Encrypt and SSM all live on the
# internet. Narrowing it would mean maintaining a list of AWS and third-party
# address ranges for no inbound-risk reduction.
resource "aws_vpc_security_group_egress_rule" "web_all" {
  security_group_id = aws_security_group.web.id
  description       = "All outbound"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "db" {
  name_prefix = "${local.name}-db-"
  description = "RDS PostgreSQL: 5432 from the web host only"
  vpc_id      = aws_vpc.main.id

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name}-db" }
}

resource "aws_vpc_security_group_ingress_rule" "db_from_web" {
  security_group_id            = aws_security_group.db.id
  description                  = "PostgreSQL from the web host"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.web.id
}
