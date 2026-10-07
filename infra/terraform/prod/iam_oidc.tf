# GitHub Actions -> AWS with no stored keys: the workflow presents a short-lived
# OIDC token and assumes one of two roles.
#
#   deploy role  trusted ONLY for pushes to main of this repo. Can push images,
#                upload deploy files, read the index prefix, and tell the SSM
#                agent on THIS ONE instance to run a shell script. Nothing else.
#   plan role    trusted for pull_request runs of this repo. Read-only, plus the
#                state lock file `terraform plan` needs to write. PR tokens carry
#                a different `sub` than main, which is why this is a separate
#                role and not a widening of the deploy role.
#
# `terraform apply` is NOT done by either role. It is run by a person, manually.
#
# The `sub` claim is matched CASE-SENSITIVELY. var.github_repo is
# "HerHealthGPT/herhealthgpt", copied from `git remote -v`.

locals {
  github_oidc_url = "token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://${local.github_oidc_url}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://${local.github_oidc_url}"
}

locals {
  github_oidc_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

# --- deploy role (main only) -------------------------------------------------

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${local.name}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.deploy_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [for r in aws_ecr_repository.app : r.arn]
  }

  statement {
    sid       = "UploadDeployFiles"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/deploy/*"]
  }

  # Read-only on the index prefix: CI builds the retrieval image from a
  # published, versioned index and can never alter one.
  statement {
    sid       = "ReadIndex"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/index/*"]
  }

  statement {
    sid       = "ListIndex"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["index/*"]
    }
  }

  # Run the custom deploy document (ssm.tf) on exactly this instance, and
  # nothing else: not AWS-RunShellScript, which would run any command string.
  # The document takes one parameter, a git sha, validated by SSM against a
  # regex before the command is built.
  statement {
    sid     = "RunDeployDocument"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ssm:${local.region}:${local.account_id}:document/${aws_ssm_document.deploy.name}",
      "arn:aws:ec2:${local.region}:${local.account_id}:instance/${aws_instance.app.id}",
    ]
  }

  # GetCommandInvocation has no resource-level permissions.
  statement {
    sid       = "ReadCommandResult"
    actions   = ["ssm:GetCommandInvocation"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}

# --- plan role (pull requests, read-only) --------------------------------------

data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_url}:sub"
      values   = ["repo:${var.github_repo}:pull_request"]
    }
  }
}

resource "aws_iam_role" "plan" {
  name                 = "${local.name}-github-plan"
  assume_role_policy   = data.aws_iam_policy_document.plan_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# `terraform plan` takes the S3 native lock by writing a .tflock object, so a
# strictly read-only role cannot plan. This is the one write it is allowed.
data "aws_iam_policy_document" "plan_lock" {
  statement {
    sid     = "StateLockFile"
    actions = ["s3:PutObject", "s3:DeleteObject"]
    resources = [
      "arn:aws:s3:::herhealthgpt-tfstate-${local.account_id}/prod/terraform.tfstate.tflock",
    ]
  }
}

resource "aws_iam_role_policy" "plan_lock" {
  name   = "state-lock"
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.plan_lock.json
}
