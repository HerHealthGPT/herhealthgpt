variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Single region. SES production access and the Route 53 zone are already here; changing it strands both."

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "SES production access was granted in us-east-1 only (docs/runbooks/ses-production-access.md), and the app hardcodes that region."
  }
}

variable "domain_name" {
  type        = string
  default     = "herhealthgpt.org"
  description = "The apex domain. Its Route 53 hosted zone already exists and is READ, never created."
}

variable "expected_name_servers" {
  type = list(string)
  default = [
    "ns-1322.awsdns-37.org",
    "ns-1758.awsdns-27.co.uk",
    "ns-508.awsdns-63.com",
    "ns-991.awsdns-59.net",
  ]
  description = "The four name servers of the existing zone. `terraform plan` fails if the zone found by name does not carry exactly these -- the guard against pointing records at a look-alike zone."
}

variable "github_repo" {
  type        = string
  default     = "HerHealthGPT/herhealthgpt"
  description = "owner/name, exact casing: the OIDC `sub` claim is matched case-sensitively. Confirmed against `git remote -v`."
}

variable "github_owner_and_repo_with_ids" {
  type        = string
  default     = "HerHealthGPT@307429918/herhealthgpt@1307895992"
  description = "owner@id/name@id, as GitHub's OIDC `sub` claim spells this repository. Read from a refused AssumeRoleWithWebIdentity in CloudTrail (userIdentity.userName), 2026-10-09."
}

variable "create_github_oidc_provider" {
  type        = bool
  default     = true
  description = "An account can hold only one OIDC provider per URL, and creating a second fails the apply. RUN `aws iam list-open-id-connect-providers` FIRST (docs/runbooks/aws-deploy.md, section 1): if it already lists token.actions.githubusercontent.com, set this to false so the existing provider is read instead of created."
}

variable "create_plan_role" {
  type        = bool
  default     = false
  description = "Create the read-only GitHub role used by the PR `terraform plan` job. Off by default: AWS's ReadOnlyAccess policy is account-wide and can read S3 objects and CloudWatch Logs events, which matters if logs can contain user text (docs/runbooks/aws-deploy.md, section 5). With false there is no plan role, no AWS_PLAN_ROLE_ARN, and the plan job in terraform.yml stays skipped; fmt and validate still run on every PR."
}

variable "alert_email" {
  type        = string
  description = "Receives the SNS alarm mail, the AWS Budget alert and Let's Encrypt expiry notices. The SNS subscription must be confirmed by clicking the link AWS sends."
}

# --- EC2 ------------------------------------------------------------------

variable "instance_type" {
  type        = string
  default     = "t3.large"
  description = "8 GB. bge-m3 is about 2 GB resident plus torch, then backend, frontend and Caddy. t3.xlarge (16 GB) if measurement says so; m6i.large for non-burstable CPU."
}

variable "root_volume_gb" {
  type        = number
  default     = 60
  description = "Holds the OS, the Docker image store and Caddy's certificates. During a deploy the running release and the new one are both on disk, and the previous release is kept for rollback afterwards; the retrieval image alone is roughly 8-10 GB extracted (see docs/runbooks/aws-deploy.md, Disk space)."
}

variable "compose_version" {
  type        = string
  default     = "v2.39.4"
  description = "Docker Compose plugin release installed at first boot. AL2023 does not package it. Verify the tag exists and take the checksum from the same release page before applying."
}

variable "compose_sha256" {
  type        = string
  description = "sha256 of docker-compose-linux-x86_64 for compose_version. No default on purpose: first boot downloads a binary and runs it as root, so a person must have looked the checksum up."

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.compose_sha256))
    error_message = "compose_sha256 must be 64 lowercase hex characters."
  }
}

# --- RDS ------------------------------------------------------------------

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "herhealth"
}

variable "db_username" {
  type    = string
  default = "herhealth"
}

variable "db_backup_retention_days" {
  type    = number
  default = 7
}

variable "db_deletion_protection" {
  type        = bool
  default     = true
  description = "Leave true. To tear down: set false, apply, then destroy -- see docs/runbooks/aws-deploy.md, \"Destroy and recreate\"."
}

variable "db_final_snapshot_identifier" {
  type        = string
  default     = "herhealth-prod-final"
  description = "Taken on destroy. A second destroy fails if a snapshot with this name already exists; delete or rename the old one first."
}

# --- Logs, ECR, budget ----------------------------------------------------

variable "log_retention_days" {
  type    = number
  default = 30

  validation {
    condition     = var.log_retention_days >= 14 && var.log_retention_days <= 30
    error_message = "Keep retention between 14 and 30 days: long enough to debug a bad week, short enough to cost nothing."
  }
}

variable "ecr_keep_images" {
  type        = number
  default     = 5
  description = "Images kept per repository. The retrieval image is several GB, so this is the main ECR cost lever."
}

variable "monthly_budget_usd" {
  type        = number
  default     = 120
  description = "AWS Budget alert threshold. The 24/7 estimate for t3.large is about $93; the alert fires at 80% actual and 100% forecast."
}
