provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]
  default_tags {
    tags = {
      Application = "garbage-guide"
      Component   = "frontend"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Project     = var.project_tag
    }
  }
}

locals {
  prefix      = "garbage-guide-web-${var.environment}"
  bucket_name = "${local.prefix}-${var.aws_account_id}-${var.aws_region}"
  oidc_arn    = var.enable_github_actions ? (var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn) : null
}

resource "aws_s3_bucket" "web" {
  bucket        = local.bucket_name
  force_destroy = false
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "web" {
  bucket = aws_s3_bucket.web.id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_versioning" "web" {
  bucket = aws_s3_bucket.web.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "web" {
  bucket = aws_s3_bucket.web.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "${local.prefix}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
resource "aws_cloudfront_cache_policy" "web" {
  name        = "${local.prefix}-cache"
  min_ttl     = 0
  default_ttl = 0
  max_ttl     = 31536000
  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true
    cookies_config { cookie_behavior = "none" }
    headers_config { header_behavior = "none" }
    query_strings_config { query_string_behavior = "none" }
  }
}
resource "aws_cloudfront_response_headers_policy" "web" {
  name = "${local.prefix}-headers"
  security_headers_config {
    content_type_options { override = true }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = false
      preload                    = false
      override                   = true
    }
  }
  custom_headers_config {
    items {
      header   = "Permissions-Policy"
      value    = "geolocation=(self)"
      override = true
    }
  }
}
resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  comment             = "${local.prefix} Flutter Web"
  default_root_object = "index.html"
  price_class         = "PriceClass_200"
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  wait_for_deployment = true
  origin {
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_id                = "web-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }
  default_cache_behavior {
    target_origin_id           = "web-s3"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    viewer_protocol_policy     = "redirect-to-https"
    compress                   = true
    cache_policy_id            = aws_cloudfront_cache_policy.web.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.web.id
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate { cloudfront_default_certificate = true }
}
resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "OnlyThisCloudFrontDistribution"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.web.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.web.arn } }
      }, {
      Sid       = "RequireConditionalReleaseWrites"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:PutObject"
      Resource  = "${aws_s3_bucket.web.arn}/releases/*"
      Condition = { Null = { "s3:if-none-match" = "true" } }
      }, {
      Sid       = "RequireConditionalEntryWrites"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:PutObject"
      Resource  = "${aws_s3_bucket.web.arn}/index.html"
      Condition = { Null = { "s3:if-match" = "true", "s3:if-none-match" = "true" } }
      }, {
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.web.arn, "${aws_s3_bucket.web.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.web]
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.enable_github_actions && var.create_github_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  lifecycle { prevent_destroy = true }
}
data "aws_iam_openid_connect_provider" "github" {
  count = var.enable_github_actions && !var.create_github_oidc_provider ? 1 : 0
  arn   = "arn:aws:iam::${var.aws_account_id}:oidc-provider/token.actions.githubusercontent.com"
}
resource "aws_iam_role" "deploy" {
  count                = var.enable_github_actions ? 1 : 0
  name                 = var.deploy_role_name
  path                 = "/service-role/"
  max_session_duration = 3600
  lifecycle { prevent_destroy = true }
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.oidc_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        "token.actions.githubusercontent.com:sub" = var.github_oidc_subject
      } }
    }]
  })
}
resource "aws_iam_role_policy" "deploy" {
  count = var.enable_github_actions ? 1 : 0
  role  = aws_iam_role.deploy[0].id
  name  = "WebReleaseOnly"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:GetBucketTagging", "s3:GetBucketVersioning", "s3:GetBucketPublicAccessBlock", "s3:GetEncryptionConfiguration", "s3:GetBucketOwnershipControls", "s3:GetBucketPolicyStatus"]
        Resource = aws_s3_bucket.web.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
        Resource = ["${aws_s3_bucket.web.arn}/index.html", "${aws_s3_bucket.web.arn}/releases/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["cloudfront:GetDistribution", "cloudfront:ListTagsForResource", "cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"]
        Resource = aws_cloudfront_distribution.web.arn
      },
      {
        Effect   = "Allow"
        Action   = ["cloudfront:GetOriginAccessControl"]
        Resource = "arn:aws:cloudfront::${var.aws_account_id}:origin-access-control/${aws_cloudfront_origin_access_control.web.id}"
      },
      {
        Effect   = "Allow"
        Action   = ["cloudfront:GetCachePolicy"]
        Resource = "arn:aws:cloudfront::${var.aws_account_id}:cache-policy/${aws_cloudfront_cache_policy.web.id}"
      }
    ]
  })
}
