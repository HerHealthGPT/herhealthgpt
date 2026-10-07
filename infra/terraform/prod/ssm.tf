# The ONE thing CI may ask the host to do: deploy a release.
#
# The deploy role is allowed ssm:SendCommand on THIS document and on this
# instance (iam_oidc.tf), and not on AWS-RunShellScript. AWS-RunShellScript runs
# whatever command string it is given; this document runs a fixed command with
# a single parameter that SSM validates against allowedPattern BEFORE the command
# is built. A caller can therefore choose which release to deploy (a git sha) and
# nothing else: no shell metacharacters can reach the command line.
#
# Residual risk, stated plainly: the sha selects s3://<bucket>/deploy/<sha>/,
# whose files run as root. Whoever can write that prefix (only the main-branch
# deploy role, iam_oidc.tf) controls what runs. See docs/runbooks/aws-deploy.md,
# "Who can write what the host executes".

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
