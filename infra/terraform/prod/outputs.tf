# Everything the runbook asks you to copy somewhere (GitHub repository
# variables, `aws ssm start-session`, publish-index.sh).

output "instance_id" {
  description = "GitHub variable EC2_INSTANCE_ID; target of `aws ssm start-session --target`"
  value       = aws_instance.app.id
}

output "elastic_ip" {
  value = aws_eip.app.public_ip
}

output "artifacts_bucket" {
  description = "GitHub variable ARTIFACTS_BUCKET; also the bucket scripts/publish-index.sh uploads to"
  value       = aws_s3_bucket.artifacts.bucket
}

output "deploy_role_arn" {
  description = "GitHub variable AWS_DEPLOY_ROLE_ARN"
  value       = aws_iam_role.deploy.arn
}

output "plan_role_arn" {
  description = "GitHub variable AWS_PLAN_ROLE_ARN"
  value       = aws_iam_role.plan.arn
}

output "ecr_registry" {
  value = local.ecr_registry
}

output "ecr_repositories" {
  value = { for k, r in aws_ecr_repository.app : k => r.repository_url }
}

output "secret_names" {
  description = "Empty until you fill them: aws secretsmanager put-secret-value"
  value       = { for k, s in aws_secretsmanager_secret.app : k => s.name }
}

output "rds_endpoint" {
  value = aws_db_instance.main.address
}

output "rds_master_secret_arn" {
  description = "RDS-managed; read by the host at deploy time, never by Terraform"
  value       = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
