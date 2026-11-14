output "web_url" { value = "https://${aws_cloudfront_distribution.web.domain_name}" }
output "deploy_role_arn" { value = aws_iam_role.deploy.arn }
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
