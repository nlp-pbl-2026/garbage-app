mock_provider "aws" {}

run "dedicated_state" {
  command = plan
  variables { aws_account_id = "088066169748" }
  assert {
    condition     = aws_s3_bucket.state.bucket == "garbage-guide-web-state-088066169748-ap-northeast-1" && !aws_s3_bucket.state.force_destroy
    error_message = "Create only the dedicated, protected frontend state bucket."
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.state.block_public_policy && aws_s3_bucket_public_access_block.state.restrict_public_buckets && aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled"
    error_message = "State must remain private and versioned."
  }
}
