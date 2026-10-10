# The Route 53 zone for herhealthgpt.org already exists (created by the
# registrar when the domain was registered) and already carries the SES DKIM
# CNAMEs, the bounce.* MX/SPF records and the _dmarc TXT. This file READS that
# zone and adds exactly three A records. It never creates a zone, and it never
# touches the SES records.

data "aws_route53_zone" "main" {
  name         = var.domain_name
  private_zone = false

  lifecycle {
    # A zone found by name that is not THE zone would silently receive our
    # records and the real domain would never resolve to the server. Compare
    # the delegation set, which is what actually identifies the zone, and fail
    # the plan on any mismatch.
    postcondition {
      condition     = toset(self.name_servers) == toset(var.expected_name_servers)
      error_message = "Hosted zone ${var.domain_name} has name servers ${join(", ", sort(self.name_servers))}, expected ${join(", ", sort(var.expected_name_servers))}. Refusing to plan: this is not the zone the domain is registered against. See docs/runbooks/aws-deploy.md, \"Route 53 name server mismatch\"."
    }
  }
}

# allow_overwrite stays false (the default): if any of these names already has a
# record, apply fails instead of replacing it.
resource "aws_route53_record" "apex" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.app.public_ip]
}

resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.app.public_ip]
}

# Caddy answers www with a permanent redirect to the apex; DNS only has to get
# the request to the same server.
resource "aws_route53_record" "www" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.app.public_ip]
}
