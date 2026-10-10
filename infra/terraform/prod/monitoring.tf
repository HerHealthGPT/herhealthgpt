# Log groups, an SNS email topic and the alarms that go to it. Everything
# alarming goes to ONE topic so there is one subscription to confirm.

locals {
  log_groups = toset(["caddy", "frontend", "backend", "retrieval"])
}

resource "aws_cloudwatch_log_group" "app" {
  for_each = local.log_groups

  name              = "/herhealth/prod/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

# AWS emails a confirmation link to this address; the subscription does nothing
# until someone clicks it (runbook, "First apply").
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# --- the server ---------------------------------------------------------------

# System status failing means the underlying hardware is impaired. EC2 recovers
# the SAME instance (same EBS volume, same Elastic IP) on healthy hardware.
resource "aws_cloudwatch_metric_alarm" "ec2_system_check" {
  alarm_name          = "${local.name}-ec2-status-check-system"
  alarm_description   = "EC2 system status check failed: auto-recovering the instance"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed_System"
  dimensions          = { InstanceId = aws_instance.app.id }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [
    "arn:aws:automate:${local.region}:ec2:recover",
    aws_sns_topic.alerts.arn,
  ]
}

# Instance status failing is the guest OS or the network config: AWS cannot fix
# that by moving hardware, so this one only notifies.
resource "aws_cloudwatch_metric_alarm" "ec2_instance_check" {
  alarm_name          = "${local.name}-ec2-status-check-instance"
  alarm_description   = "EC2 instance status check failed: the OS is unresponsive. Reboot via the console or SSM."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed_Instance"
  dimensions          = { InstanceId = aws_instance.app.id }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# t3 is burstable: sustained high CPU means credits are being burned (and, in
# unlimited mode, billed).
resource "aws_cloudwatch_metric_alarm" "ec2_cpu" {
  alarm_name          = "${local.name}-ec2-cpu-high"
  alarm_description   = "EC2 CPU above 80% for 30 minutes: bge-m3 inference under load, or burst credits running out"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  dimensions          = { InstanceId = aws_instance.app.id }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 6
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# Disk and memory come from the CloudWatch agent installed in user_data. A
# missing metric means the agent (or the host) is down, so treat it as breaching.
resource "aws_cloudwatch_metric_alarm" "disk_used" {
  alarm_name          = "${local.name}-disk-used-high"
  alarm_description   = "Root volume above 80%: prune images (docs/runbooks/aws-deploy.md, Disk space)"
  namespace           = "HerHealth/EC2"
  metric_name         = "disk_used_percent"
  dimensions          = { InstanceId = aws_instance.app.id, path = "/", fstype = "xfs" }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "mem_used" {
  alarm_name          = "${local.name}-memory-used-high"
  alarm_description   = "Host memory above 90%: the retrieval container is capped at 4 GB, so something else is growing"
  namespace           = "HerHealth/EC2"
  metric_name         = "mem_used_percent"
  dimensions          = { InstanceId = aws_instance.app.id }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 3
  threshold           = 90
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# --- the database ---------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.name}-rds-cpu-high"
  alarm_description   = "RDS CPU above 80% for 15 minutes"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.main.identifier }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "${local.name}-rds-free-storage-low"
  alarm_description   = "RDS free storage below 4 GiB (of ${var.db_allocated_storage_gb} GiB)"
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.main.identifier }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 4 * 1024 * 1024 * 1024
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
}
