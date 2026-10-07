# Three repositories, one per image. Tags are git SHAs and are IMMUTABLE: a SHA
# can never be re-pointed at different bytes, so "roll back to the previous tag"
# always means the image that was actually running. Nothing is ever tagged
# `latest`.

locals {
  ecr_repos = toset(["frontend", "backend", "retrieval"])
}

resource "aws_ecr_repository" "app" {
  for_each = local.ecr_repos

  name                 = "herhealth-${each.key}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each   = aws_ecr_repository.app
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the newest ${var.ecr_keep_images} images; the host itself keeps only current + previous"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.ecr_keep_images
      }
      action = { type = "expire" }
    }]
  })
}
