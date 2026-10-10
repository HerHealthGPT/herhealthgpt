# SES is NOT managed here, on purpose.
#
# Verified read-only on 2026-10-06 (see docs/runbooks/aws-deploy.md, "SES: what
# already exists"): the domain identity herhealthgpt.org is verified in this
# account and us-east-1, Easy DKIM and the bounce.herhealthgpt.org MAIL FROM are
# SUCCESS, the DKIM/MAIL FROM/DMARC records are already in the Route 53 zone,
# and production access is GRANTED (50,000/24h, 14/s). Re-creating any of that
# here would risk breaking a working setup, so this file only builds the ARN and
# grants the instance role permission to send through it.
#
# The app (services/backend/.../email_sender.py) hardcodes region us-east-1,
# From "HerHealthGPT <no-reply@herhealthgpt.org>" and Reply-To
# support@herhealthgpt.org, and calls the SES v1 send_email API (IAM action
# ses:SendEmail).

locals {
  ses_identity_arn = "arn:aws:ses:${local.region}:${local.account_id}:identity/${var.domain_name}"
  ses_from_address = "no-reply@${var.domain_name}"
}

data "aws_iam_policy_document" "ses_send" {
  statement {
    sid       = "SendFromTheVerifiedIdentityOnly"
    actions   = ["ses:SendEmail"]
    resources = [local.ses_identity_arn]

    # Only the one address the app sends from. SES evaluates this against the
    # address in the Source header. UNVERIFIED until the first real send: if
    # the app's display-name form ("HerHealthGPT <no-reply@...>") is ever
    # rejected with AccessDenied, this condition is the first thing to check --
    # see docs/runbooks/aws-deploy.md, troubleshooting.
    condition {
      test     = "StringEquals"
      variable = "ses:FromAddress"
      values   = [local.ses_from_address]
    }
  }
}

resource "aws_iam_role_policy" "ses_send" {
  name   = "ses-send"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.ses_send.json
}
