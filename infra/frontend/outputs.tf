output "web_url" { value = "https://${aws_cloudfront_distribution.web.domain_name}" }
output "deploy_role_arn" {
  description = "Only present when GitHub Actions is explicitly enabled."
  value       = var.enable_github_actions ? aws_iam_role.deploy[0].arn : null
}
output "web_target" {
  value = {
    account         = var.aws_account_id
    region          = var.aws_region
    bucket          = aws_s3_bucket.web.id
    distribution_id = aws_cloudfront_distribution.web.id
    environment     = var.environment
    project_tag     = var.project_tag
  }
}
