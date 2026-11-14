variable "aws_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Set the intended twelve-digit AWS account."
  }
}
variable "aws_region" {
  type    = string
  default = "ap-northeast-1"
}
variable "environment" {
  type    = string
  default = "dev"
  validation {
    condition     = can(regex("^[a-z0-9-]{1,12}$", var.environment))
    error_message = "Use a short lowercase environment name."
  }
}
variable "project_tag" {
  type    = string
  default = "U-22"
}
variable "github_oidc_subject" {
  description = "Exact subject for the protected GitHub Environment; confirm immutable owner/repository IDs."
  type        = string
  validation {
    condition     = can(regex("^repo:[^*]+:environment:[^*]+$", var.github_oidc_subject))
    error_message = "Use one exact repository/environment subject, without wildcards."
  }
}
variable "create_github_oidc_provider" {
  description = "Keep false when this account already has the GitHub OIDC provider. Never import or alter an existing provider here."
  type        = bool
  default     = false
}
variable "deploy_role_name" {
  type    = string
  default = "U-22-GarbageGuideWebDeployDev"
}
