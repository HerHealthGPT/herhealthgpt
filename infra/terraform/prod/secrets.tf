# Secrets Manager entries are created EMPTY. Terraform never sees a value, so no
# secret can reach the state file. A person fills each one once:
#
#   aws secretsmanager put-secret-value --secret-id herhealth/prod/openrouter-api-key --secret-string '...'
#
# See docs/runbooks/aws-deploy.md, "Filling secrets". The database password is
# the RDS-managed secret (rds.tf), not one of these.

locals {
  app_secrets = {
    openrouter_api_key = {
      name        = "herhealth/prod/openrouter-api-key"
      description = "OpenRouter API key for the Base model (OPENROUTER_API_KEY)"
    }
    session_secret = {
      name        = "herhealth/prod/session-secret"
      description = "Signs access tokens (HERHEALTH_SESSION_SECRET). At least 32 chars: openssl rand -hex 32"
    }
    google_client_id = {
      name        = "herhealth/prod/google-client-id"
      description = "Google OAuth Client ID (HERHEALTH_GOOGLE_CLIENT_ID). Not a secret in Google's model, kept here so the env file has one source."
    }
  }
}

resource "aws_secretsmanager_secret" "app" {
  for_each = local.app_secrets

  name        = each.value.name
  description = each.value.description

  # 7 days rather than the 30 default: a destroy/recreate cycle can reuse the
  # name sooner, and the recovery window is not a backup strategy.
  recovery_window_in_days = 7
}
