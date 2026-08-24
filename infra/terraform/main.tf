locals {
  resource_prefix = "${var.project_name}-${var.environment}"
  bucket_name = lower(
    "${local.resource_prefix}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  )
  knowledge_path                   = "${path.module}/../../data/regions/matsuyama/common/knowledge"
  knowledge_prefix                 = "knowledge/matsuyama/common"
  knowledge_role_name              = "U-22-BedrockKnowledgeBaseRole-GarbageGuideDev"
  knowledge_s3_policy_name         = "AmazonBedrockS3PolicyForKnowledgeBase_${local.knowledge_role_name}"
  knowledge_cloudwatch_policy_name = "AmazonBedrockCloudWatchPolicyForKnowledgeBase_${local.knowledge_role_name}"
  knowledge_s3_policy_arn          = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/service-role/${local.knowledge_s3_policy_name}"
  knowledge_cloudwatch_policy_arn  = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/service-role/${local.knowledge_cloudwatch_policy_name}"
}

resource "aws_s3_bucket" "knowledge" {
  bucket        = local.bucket_name
  force_destroy = var.force_destroy_bucket
}

resource "aws_s3_bucket_public_access_block" "knowledge" {
  bucket = aws_s3_bucket.knowledge.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "knowledge" {
  bucket = aws_s3_bucket.knowledge.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "knowledge" {
  bucket = aws_s3_bucket.knowledge.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_object" "knowledge" {
  for_each = fileset(local.knowledge_path, "**")

  bucket       = aws_s3_bucket.knowledge.id
  key          = "${local.knowledge_prefix}/${each.value}"
  source       = "${local.knowledge_path}/${each.value}"
  etag         = filemd5("${local.knowledge_path}/${each.value}")
  content_type = endswith(each.value, ".json") ? "application/json" : "text/csv; charset=utf-8"
}

resource "aws_iam_role" "knowledge_base" {
  name = local.knowledge_role_name
  path = "/service-role/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "bedrock.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id
        }
        ArnLike = {
          "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"
        }
      }
    }]
  })
}

resource "aws_iam_policy" "knowledge_base_s3" {
  provider    = aws.untagged_iam
  name        = local.knowledge_s3_policy_name
  path        = "/service-role/"
  description = "Read the Terraform-managed garbage guide knowledge documents."
  tags        = {}

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListKnowledgePrefix"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket"]
        Resource = aws_s3_bucket.knowledge.arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["${local.knowledge_prefix}/*"]
          }
        }
      },
      {
        Sid      = "ReadKnowledgeDocuments"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.knowledge.arn}/${local.knowledge_prefix}/*"
      }
    ]
  })

  lifecycle {
    ignore_changes = [tags, tags_all]
  }
}

resource "aws_iam_policy" "knowledge_base_cloudwatch" {
  provider    = aws.untagged_iam
  name        = local.knowledge_cloudwatch_policy_name
  path        = "/service-role/"
  description = "Publish metrics for the Terraform-managed Bedrock Knowledge Base."
  tags        = {}

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "CloudWatchWritePermissionStatement"
      Effect   = "Allow"
      Action   = ["cloudwatch:PutMetricData"]
      Resource = "*"
      Condition = {
        StringEquals = {
          "cloudwatch:namespace" = "AWS/Bedrock/KnowledgeBases"
        }
      }
    }]
  })


  lifecycle {
    ignore_changes = [tags, tags_all]
  }
}

resource "aws_iam_role_policy_attachment" "knowledge_base_s3" {
  role       = aws_iam_role.knowledge_base.name
  policy_arn = local.knowledge_s3_policy_arn

  depends_on = [aws_iam_policy.knowledge_base_s3]
}

resource "aws_iam_role_policy_attachment" "knowledge_base_cloudwatch" {
  role       = aws_iam_role.knowledge_base.name
  policy_arn = local.knowledge_cloudwatch_policy_arn

  depends_on = [aws_iam_policy.knowledge_base_cloudwatch]
}

resource "aws_bedrockagent_knowledge_base" "this" {
  name        = var.knowledge_base_name
  description = "Garbage classification knowledge for Matsuyama City, initially serving Shimizu district."
  role_arn    = aws_iam_role.knowledge_base.arn

  knowledge_base_configuration {
    type = "MANAGED"

    managed_knowledge_base_configuration {
      embedding_model_type = "MANAGED"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.knowledge_base_s3,
    aws_iam_role_policy_attachment.knowledge_base_cloudwatch,
  ]
}

resource "aws_bedrockagent_data_source" "knowledge" {
  knowledge_base_id    = aws_bedrockagent_knowledge_base.this.id
  name                 = "${local.resource_prefix}-matsuyama-knowledge"
  description          = "Version-controlled Matsuyama garbage items and classification rules."
  data_deletion_policy = "DELETE"

  data_source_configuration {
    type = "MANAGED_KNOWLEDGE_BASE_CONNECTOR"

    managed_knowledge_base_connector_configuration {
      connector_parameters = jsonencode({
        type    = "S3"
        version = "1"
        connectionConfiguration = {
          bucketName           = aws_s3_bucket.knowledge.id
          bucketOwnerAccountId = data.aws_caller_identity.current.account_id
          bucketArn            = aws_s3_bucket.knowledge.arn
        }
        aclEnabled = false
        filterConfiguration = {
          maxFileSizeInMegaBytes = "500"
          inclusionPrefixes      = ["${local.knowledge_prefix}/"]
        }
      })

      deletion_protection_configuration {
        deletion_protection_status = "DISABLED"
      }

      media_extraction_configuration {
        image_extraction_configuration {
          image_extraction_status = "DISABLED"
        }
        audio_extraction_configuration {
          audio_extraction_status = "DISABLED"
        }
        video_extraction_configuration {
          video_extraction_status = "DISABLED"
        }
      }
    }
  }

  vector_ingestion_configuration {
    parsing_configuration {
      parsing_strategy = "SMART_PARSING"
    }
  }

  depends_on = [aws_s3_object.knowledge]
}
