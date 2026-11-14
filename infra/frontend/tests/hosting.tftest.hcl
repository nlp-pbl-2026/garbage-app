mock_provider "aws" {}

run "private_static_hosting" {
  command = plan
  variables {
    aws_account_id      = "088066169748"
    github_oidc_subject = "repo:nlp-pbl-2026@287387317/garbage-app@1304887747:environment:frontend-production"
  }
  assert {
    condition     = aws_s3_bucket.web.force_destroy == false && aws_s3_bucket_public_access_block.web.block_public_acls && aws_s3_bucket_public_access_block.web.block_public_policy && aws_s3_bucket_public_access_block.web.ignore_public_acls && aws_s3_bucket_public_access_block.web.restrict_public_buckets
    error_message = "Web bucket must remain private and protected."
  }
  assert {
    condition     = aws_s3_bucket_versioning.web.versioning_configuration[0].status == "Enabled" && aws_s3_bucket_ownership_controls.web.rule[0].object_ownership == "BucketOwnerEnforced"
    error_message = "Require versioning and disabled ACLs."
  }
  assert {
    condition     = aws_cloudfront_origin_access_control.web.signing_behavior == "always" && aws_cloudfront_distribution.web.default_root_object == "index.html" && aws_cloudfront_distribution.web.viewer_certificate[0].cloudfront_default_certificate
    error_message = "Use signed S3 access and the standard HTTPS domain."
  }
  assert {
    condition     = aws_cloudfront_cache_policy.web.min_ttl == 0 && aws_cloudfront_cache_policy.web.default_ttl == 0 && aws_cloudfront_distribution.web.default_cache_behavior[0].viewer_protocol_policy == "redirect-to-https"
    error_message = "Entry points must revalidate and viewers must use HTTPS."
  }
  assert {
    condition     = length(aws_iam_openid_connect_provider.github) == 0 && jsondecode(aws_iam_role.deploy.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == var.github_oidc_subject
    error_message = "Reuse an existing provider without changing it; trust only the exact environment."
  }
}

run "reject_wildcard_subject" {
  command = plan
  variables {
    aws_account_id      = "088066169748"
    github_oidc_subject = "repo:nlp-pbl-2026/*:environment:frontend-production"
  }
  expect_failures = [var.github_oidc_subject]
}

run "reject_branch_subject_without_environment" {
  command = plan
  variables {
    aws_account_id      = "088066169748"
    github_oidc_subject = "repo:nlp-pbl-2026/garbage-app:ref:refs/heads/main"
  }
  expect_failures = [var.github_oidc_subject]
}
