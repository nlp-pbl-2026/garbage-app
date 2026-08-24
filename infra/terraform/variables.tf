variable "aws_region" {
  description = "AWS region in which the RAG resources are created."
  type        = string
  default     = "ap-northeast-1"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used by Terraform."
  type        = string
  default     = "default"
}

variable "project_name" {
  description = "Resource name prefix."
  type        = string
  default     = "garbage-guide"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "organization_project_tag" {
  description = "Project tag required by the AWS account guardrail when resources are created."
  type        = string
  default     = "U-22"
}

variable "force_destroy_bucket" {
  description = "Delete all object versions when destroying the knowledge bucket. Enable only for an intentional full teardown."
  type        = bool
  default     = false
}

variable "knowledge_base_name" {
  description = "Name of the new Bedrock managed knowledge base."
  type        = string
  default     = "garbage-guide-matsuyama-shimizu-dev"
}

variable "backend_package_path" {
  description = "Lambda deployment zip built by scripts/package_backend.sh."
  type        = string
  default     = "../../backend/dist/backend-lambda.zip"
}

variable "collection_cutoff_hour" {
  description = "Optional global cutoff override. Null uses official category cutoffs: combustible 7:00, others 8:00."
  type        = number
  default     = null

  validation {
    condition     = var.collection_cutoff_hour == null || (var.collection_cutoff_hour >= 0 && var.collection_cutoff_hour <= 23)
    error_message = "collection_cutoff_hour must be between 0 and 23."
  }
}

variable "search_log_retention_days" {
  description = "Days before DynamoDB automatically expires search analytics logs."
  type        = number
  default     = 90
}
