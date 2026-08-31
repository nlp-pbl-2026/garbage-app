provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Application = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Project     = var.organization_project_tag
    }
  }
}

# The account allows creation of Bedrock service-role policies but does not
# allow iam:TagPolicy. Use the same untagged policy flow as the AWS Console.
provider "aws" {
  alias   = "untagged_iam"
  region  = var.aws_region
  profile = var.aws_profile
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
