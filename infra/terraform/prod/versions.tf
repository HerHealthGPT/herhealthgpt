terraform {
  required_version = ">= 1.10, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0, < 7.0"
    }
  }

  # State lives in the bucket created by ../bootstrap. use_lockfile is S3's
  # native locking (Terraform >= 1.10): a .tflock object next to the state, no
  # DynamoDB table. The bucket name embeds the account id, which the SES
  # provisioning record in docs/runbooks/ses-production-access.md fixes.
  backend "s3" {
    bucket       = "herhealthgpt-tfstate-508859666073"
    key          = "prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  # Every resource that supports tags gets these, so the console and the cost
  # explorer can filter on Project.
  default_tags {
    tags = {
      Project     = "herhealthgpt"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region
  name       = "herhealth-prod"
}
