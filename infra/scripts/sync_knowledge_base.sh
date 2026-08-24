#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"
TERRAFORM_BIN="${TERRAFORM_BIN:-terraform}"
AWS_PROFILE_NAME="${AWS_PROFILE:-default}"
AWS_REGION_NAME="${AWS_REGION:-$("${TERRAFORM_BIN}" -chdir="${TERRAFORM_DIR}" output -raw aws_region)}"
KNOWLEDGE_BASE_ID="$("${TERRAFORM_BIN}" -chdir="${TERRAFORM_DIR}" output -raw knowledge_base_id)"
DATA_SOURCE_ID="$("${TERRAFORM_BIN}" -chdir="${TERRAFORM_DIR}" output -raw data_source_id)"

INGESTION_JOB_ID="$(
  aws bedrock-agent start-ingestion-job \
    --knowledge-base-id "${KNOWLEDGE_BASE_ID}" \
    --data-source-id "${DATA_SOURCE_ID}" \
    --region "${AWS_REGION_NAME}" \
    --profile "${AWS_PROFILE_NAME}" \
    --query 'ingestionJob.ingestionJobId' \
    --output text
)"

echo "Started ingestion job ${INGESTION_JOB_ID}."

while true; do
  JOB_STATUS="$(
    aws bedrock-agent get-ingestion-job \
      --knowledge-base-id "${KNOWLEDGE_BASE_ID}" \
      --data-source-id "${DATA_SOURCE_ID}" \
      --ingestion-job-id "${INGESTION_JOB_ID}" \
      --region "${AWS_REGION_NAME}" \
      --profile "${AWS_PROFILE_NAME}" \
      --query 'ingestionJob.status' \
      --output text
  )"

  echo "Ingestion status: ${JOB_STATUS}"

  case "${JOB_STATUS}" in
    COMPLETE)
      exit 0
      ;;
    FAILED|STOPPED)
      aws bedrock-agent get-ingestion-job \
        --knowledge-base-id "${KNOWLEDGE_BASE_ID}" \
        --data-source-id "${DATA_SOURCE_ID}" \
        --ingestion-job-id "${INGESTION_JOB_ID}" \
        --region "${AWS_REGION_NAME}" \
        --profile "${AWS_PROFILE_NAME}"
      exit 1
      ;;
  esac

  sleep 10
done
