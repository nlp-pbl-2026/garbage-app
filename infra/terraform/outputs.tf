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

