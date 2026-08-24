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
