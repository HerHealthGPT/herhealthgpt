# One private bucket, two prefixes:
#
#   index/<version>/        the retrieval index (vectors.npy, passages.jsonl,
#                           manifest.json, build-info.json). Written ONCE per
#                           version by a person running scripts/publish-index.sh;
#                           read by CI to build the retrieval image. It must
#                           never contain quote-only (NHS) text -- the publish
#                           script refuses to upload any.
#   deploy/<git-sha>/       compose.prod.yml, Caddyfile and the deploy scripts
#                           for one release. Written by CI, read by the host.
#   caddy-backup/           Caddy's certificate store, saved before a destroy so
#                           a recreated server does not burn Let's Encrypt's
#                           duplicate-certificate limit.
#
# SSE-S3 (AES256), not KMS: no key to manage, no key policy to get wrong, and
# nothing in here is secret -- it is a public-domain index and deploy files.

locals {
  artifacts_bucket = "herhealthgpt-artifacts-${local.account_id}"
}

resource "aws_s3_bucket" "artifacts" {
  bucket = local.artifacts_bucket
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Deploy files are only needed for the release that is running and the one
# before it. index/ is NOT expired: an index version is the provenance of an
# image label and must stay retrievable.
resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-deploy-files"
    status = "Enabled"

    filter {
      prefix = "deploy/"
    }

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }

  rule {
    id     = "expire-noncurrent-everywhere"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

data "aws_iam_policy_document" "artifacts_tls_only" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = data.aws_iam_policy_document.artifacts_tls_only.json

  depends_on = [aws_s3_bucket_public_access_block.artifacts]
}
