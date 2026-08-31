output "aws_region" {
  value       = var.aws_region
  description = "AWS region used by the backend."
}

output "knowledge_bucket_name" {
  value       = aws_s3_bucket.knowledge.id
  description = "S3 bucket containing the version-controlled knowledge documents."
}

output "knowledge_base_id" {
  value       = aws_bedrockagent_knowledge_base.this.id
  description = "New Bedrock Knowledge Base ID."
}

output "data_source_id" {
  value       = aws_bedrockagent_data_source.knowledge.data_source_id
  description = "Bedrock data source ID used by the ingestion script."
}

output "backend_environment" {
  value = {
    AWS_REGION                = var.aws_region
    BEDROCK_KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.this.id
  }
  description = "Environment values required by the backend."
}

output "backend_api_url" {
  value       = aws_apigatewayv2_api.backend.api_endpoint
  description = "Public base URL of the serverless backend API."
}

output "search_log_table_name" {
  value       = aws_dynamodb_table.search_logs.name
  description = "DynamoDB table containing structured search analytics."
}

output "analytics_api_key" {
  value       = random_password.analytics_api_key.result
  description = "Key required by the analytics endpoint. Enter it in the admin UI; do not embed it in a public Flutter build."
  sensitive   = true
}
