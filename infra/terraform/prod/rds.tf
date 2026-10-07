# PostgreSQL 16, single-AZ, in the private subnets. Reachable only from the web
# security group (security_groups.tf). Deliberate cost trade-offs, restated in
# docs/runbooks/aws-deploy.md: single-AZ (an AZ outage means downtime until
# restore), 7-day backups, db.t4g.micro.

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = local.name }
}

resource "aws_db_instance" "main" {
  identifier = local.name

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage = var.db_allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username

  # RDS creates the master password and stores it in Secrets Manager. It never
  # passes through Terraform, so it is not in state. RDS ROTATES it (every 7
  # days by default) and the old password stops working at once: running
  # containers keep their open connections but cannot open new ones. The host's
  # 15-minute refresh-secrets timer detects the change and recreates the backend
  # -- see docs/runbooks/aws-deploy.md, "Database password rotation".
  manage_master_user_password = true

  multi_az               = false
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]

  backup_retention_period = var.db_backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:30-sun:05:30"
  copy_tags_to_snapshot   = true

  auto_minor_version_upgrade = true
  apply_immediately          = false

  deletion_protection       = var.db_deletion_protection
  skip_final_snapshot       = false
  final_snapshot_identifier = var.db_final_snapshot_identifier

  lifecycle {
    # "16" tracks the newest 16.x minor; an automatic minor upgrade must not
    # show up as drift on the next plan.
    ignore_changes = [engine_version]
  }

  tags = { Name = local.name }
}
