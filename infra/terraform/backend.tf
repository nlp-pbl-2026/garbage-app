locals {
  backend_role_name = "U-22-LambdaExecutionRole-GarbageGuideDev"
  # このアカウントのCreatePolicyガードレールが許可するBedrock service-role命名。
  backend_policy_name = "AmazonBedrockLambdaRuntimePolicyForKnowledgeBase_${local.knowledge_role_name}"
  backend_policy_arn  = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:policy/service-role/${local.backend_policy_name}"
  backend_zip_path    = abspath("${path.module}/${var.backend_package_path}")
}

resource "random_password" "analytics_api_key" {
  length  = 32
  special = false
}

resource "aws_dynamodb_table" "search_logs" {
  name         = "${local.resource_prefix}-search-logs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false
  }
}

resource "aws_iam_role" "backend" {
  name = local.backend_role_name
  path = "/service-role/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "backend" {
  provider    = aws.untagged_iam
  name        = local.backend_policy_name
  path        = "/service-role/"
  description = "Least-privilege runtime access for the garbage guide Lambda."
  tags        = {}

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "WriteLambdaLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.backend.arn}:*"
      },
      {
        Sid      = "RetrieveGarbageKnowledge"
        Effect   = "Allow"
        Action   = ["bedrock:Retrieve"]
        Resource = "arn:${data.aws_partition.current.partition}:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"
      },
      {
        Sid      = "InvokeNovaLite"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "arn:${data.aws_partition.current.partition}:bedrock:${var.aws_region}::foundation-model/amazon.nova-lite-v1:0"
      },
      {
        Sid      = "SearchAnalytics"
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:Scan"]
        Resource = aws_dynamodb_table.search_logs.arn
      }
    ]
  })

  lifecycle {
    ignore_changes = [tags, tags_all]
  }
}

resource "aws_iam_role_policy_attachment" "backend" {
  role       = aws_iam_role.backend.name
  policy_arn = local.backend_policy_arn

  depends_on = [aws_iam_policy.backend]
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/aws/lambda/${local.resource_prefix}-api"
  retention_in_days = 30
}

resource "aws_lambda_function" "backend" {
  function_name    = "${local.resource_prefix}-api"
  description      = "Serverless fuzzy garbage classification API"
  role             = aws_iam_role.backend.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "app.lambda_main.handler"
  filename         = local.backend_zip_path
  source_code_hash = fileexists(local.backend_zip_path) ? filebase64sha256(local.backend_zip_path) : null
  memory_size      = 512
  timeout          = 30

  environment {
    variables = merge({
      BEDROCK_KNOWLEDGE_BASE_ID           = aws_bedrockagent_knowledge_base.this.id
      BEDROCK_MODEL_ID                    = "amazon.nova-lite-v1:0"
      TIMEZONE                            = "Asia/Tokyo"
      CALENDAR_PATH                       = "/var/task/data/regions/matsuyama/shimizu/calendar/2026.csv"
      SEARCH_LOG_TABLE                    = aws_dynamodb_table.search_logs.name
      SEARCH_LOG_RETENTION_DAYS           = tostring(var.search_log_retention_days)
      ANALYTICS_API_KEY                   = random_password.analytics_api_key.result
      RAG_REQUEST_TIMEOUT_SECONDS         = "25"
      CLASSIFICATION_CONFIDENCE_THRESHOLD = "0.75"
      RAG_TOP_K                           = "8"
      }, var.collection_cutoff_hour == null ? {} : {
      COLLECTION_CUTOFF_HOUR = tostring(var.collection_cutoff_hour)
    })
  }

  depends_on = [
    aws_cloudwatch_log_group.backend,
    aws_iam_role_policy_attachment.backend,
  ]
}

resource "aws_apigatewayv2_api" "backend" {
  name          = "${local.resource_prefix}-http-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_headers = ["Content-Type", "X-Analytics-Key"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_origins = ["*"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_integration" "backend" {
  api_id                 = aws_apigatewayv2_api.backend.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.backend.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "backend" {
  api_id    = aws_apigatewayv2_api.backend.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.backend.id}"
}

resource "aws_apigatewayv2_stage" "backend" {
  api_id      = aws_apigatewayv2_api.backend.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.backend.execution_arn}/*"
}
