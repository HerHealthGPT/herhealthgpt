# The single server: Amazon Linux 2023, x86_64 (no multi-arch builds), running
# docker compose (infra/compose.prod.yml). No key pair and no SSH port: the only
# way in is SSM Session Manager / Run Command.

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  ecr_registry = "${local.account_id}.dkr.ecr.${local.region}.amazonaws.com"

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    compose_version   = var.compose_version
    compose_sha256    = var.compose_sha256
    region            = local.region
    account_id        = local.account_id
    domain            = var.domain_name
    acme_email        = var.alert_email
    artifacts_bucket  = aws_s3_bucket.artifacts.bucket
    ecr_registry      = local.ecr_registry
    db_host           = aws_db_instance.main.address
    db_port           = aws_db_instance.main.port
    db_name           = var.db_name
    db_secret_arn     = aws_db_instance.main.master_user_secret[0].secret_arn
    secret_openrouter = aws_secretsmanager_secret.app["openrouter_api_key"].name
    secret_session    = aws_secretsmanager_secret.app["session_secret"].name
    secret_google     = aws_secretsmanager_secret.app["google_client_id"].name

    # Only two small scripts are embedded, to keep user_data far below EC2's 16 KB
    # limit: a stub deploy.sh that fetches the real one from S3 for the release
    # being installed, and caddy-data.sh (needed to restore certificates BEFORE
    # the first deploy). The real deploy.sh and refresh-secrets.sh arrive with
    # every release.
    deploy_stub_b64 = base64encode(file("${path.module}/../../deploy/bootstrap-deploy.sh"))
    caddy_data_b64  = base64encode(file("${path.module}/../../deploy/caddy-data.sh"))
  })
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  # No key_name: SSH is not an option, by design.

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required" # IMDSv2 only
    # 2, not the default 1. Containers reach the metadata service through the
    # Docker bridge, which costs a hop; with 1 the boto3 client inside the
    # backend container cannot fetch the instance role's credentials and SES
    # sending fails with NoCredentialsError.
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    encrypted             = true
    delete_on_termination = true
  }

  user_data_base64 = base64gzip(local.user_data)

  # AMIs are released constantly and user_data only runs at first boot, so
  # either changing would otherwise show as a perpetual diff that wants to
  # replace the server. To change bootstrapping, replace the instance on
  # purpose: terraform apply -replace=aws_instance.app (runbook, "Destroy and
  # recreate" -- and back up Caddy's certificates first).
  lifecycle {
    ignore_changes = [ami, user_data_base64]
  }

  depends_on = [aws_internet_gateway.main]

  tags = { Name = local.name }
}

# A public IPv4 address is billed whether or not the instance is running.
resource "aws_eip" "app" {
  domain   = "vpc"
  instance = aws_instance.app.id

  depends_on = [aws_internet_gateway.main]

  tags = { Name = local.name }
}
