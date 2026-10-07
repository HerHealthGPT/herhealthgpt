# The ONE thing CI may ask the host to do: deploy a release.
#
# What this document restricts, and what it does not. The deploy role may call
# ssm:SendCommand on THIS document and this instance (iam_oidc.tf), and not on
# AWS-RunShellScript, which runs whatever command string it is handed. This
# document runs a fixed command with a single parameter that SSM validates
# against allowedPattern BEFORE the command is built, so no shell metacharacters
# can reach the command LINE.
#
# That restricts the command line. It does NOT restrict what runs. The command is
# /opt/herhealth/deploy.sh <sha>, and deploy.sh replaces itself from, and then
# executes, whatever s3://<bucket>/deploy/<sha>/ contains (deploy.sh, the compose
# file, the Caddyfile, helper scripts), as root. The deploy role is also the only
# principal that writes that prefix, and a push to main is the only way to assume
# it. So: CONTROL OF MAIN IS CONTROL OF THE SERVER (root, the database credentials
# in /run/herhealth, every user's data). That is the deliberate cost of deploying
# on a push, not something this document prevents. See docs/runbooks/aws-deploy.md,
# "Deliberate trade-offs" and "Who can write what the host executes".

resource "aws_ssm_document" "deploy" {
  name            = "herhealth-deploy"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy one HerHealthGPT release by git sha (runs /opt/herhealth/deploy.sh)."

    parameters = {
      Sha = {
        type           = "String"
        description    = "Full or abbreviated git commit sha (7-64 lowercase hex characters) of the release to deploy."
        allowedPattern = "^[0-9a-f]{7,64}$"
      }
    }

    mainSteps = [{
      action = "aws:runShellScript"
      name   = "deploy"
      inputs = {
        timeoutSeconds = "3300"
        runCommand     = ["/opt/herhealth/deploy.sh {{ Sha }}"]
      }
    }]
  })
}
