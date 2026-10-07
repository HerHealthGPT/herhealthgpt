# The instance role: what the HOST (and, through IMDS with hop limit 2, the
# containers on it) may do. Each statement below is the narrowest thing the
# running system needs.

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${local.name}-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.name}-instance"
  role = aws_iam_role.app.name
}

# Session Manager / Run Command: the only way in.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "app" {
  # Pull images. GetAuthorizationToken has no resource-level form.
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPull"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchCheckLayerAvailability",
    ]
    resources = [for r in aws_ecr_repository.app : r.arn]
  }

  # Only the four secrets the host needs: the three above plus the RDS-managed
  # master secret.
  statement {
    sid     = "ReadAppSecrets"
    actions = ["secretsmanager:GetSecretValue"]
    resources = concat(
      [for s in aws_secretsmanager_secret.app : s.arn],
      [aws_db_instance.main.master_user_secret[0].secret_arn],
    )
  }

  # Container logs (the awslogs driver runs in dockerd, i.e. as this role). The
  # log groups are created by Terraform, so no CreateLogGroup. Stream-level
  # actions need the ":*" suffix on the group ARN. The provider documents
  # `arn` as WITHOUT it (the API's own trailing ":*" is stripped), but that is
  # not visible in the provider schema, so trim first: this is correct whether
  # or not the suffix is present and can never produce "...:*:*".
  statement {
    sid       = "WriteLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [for g in aws_cloudwatch_log_group.app : "${trimsuffix(g.arn, ":*")}:*"]
  }

  # Deploy files for the release being installed, and the Caddy certificate
  # backup. Nothing else in the bucket -- in particular not index/.
  statement {
    sid       = "ReadDeployFiles"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/deploy/*"]
  }

  statement {
    sid       = "CaddyBackupObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/caddy-backup/*"]
  }

  statement {
    sid       = "ListDeployAndBackupPrefixes"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["deploy/*", "caddy-backup/*"]
    }
  }

  # Disk and memory metrics from the CloudWatch agent, and only into our
  # namespace.
  statement {
    sid       = "PutAgentMetrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["HerHealth/EC2"]
    }
  }
}

resource "aws_iam_role_policy" "app" {
  name   = "app"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app.json
}
