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
variable "enable_github_actions" {
  description = "Opt in to the GitHub OIDC provider lookup and deploy role. Local deployment needs neither."
  type        = bool
  default     = false
}
variable "github_oidc_subject" {
  description = "Exact subject for the protected GitHub Environment; confirm immutable owner/repository IDs."
  type        = string
  default     = null
  validation {
    condition     = !var.enable_github_actions || can(regex("^repo:[^*]+:environment:[^*]+$", var.github_oidc_subject))
    error_message = "GitHub Actions requires one exact repository/environment subject, without wildcards."
  }
}
variable "create_github_oidc_provider" {
  description = "Keep false when this account already has the GitHub OIDC provider. Never import or alter an existing provider here."
  type        = bool
  default     = false
  validation {
    condition     = !var.create_github_oidc_provider || var.enable_github_actions
    error_message = "OIDC creation requires enable_github_actions=true and a confirmed missing provider."
  }
}
variable "deploy_role_name" {
  type    = string
  default = "U-22-GarbageGuideWebDeployDev"
}
