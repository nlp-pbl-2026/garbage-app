#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
TERRAFORM_BIN="${TERRAFORM_BIN:-terraform}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/service-role/AmazonBedrockS3PolicyForKnowledgeBase_U-22-BedrockKnowledgeBaseRole-GarbageGuideDev"
POLICY_VERSION="$(aws iam get-policy --policy-arn "${POLICY_ARN}" --query 'Policy.DefaultVersionId' --output text 2>/dev/null || true)"

if [[ -n "${POLICY_VERSION}" ]] && ! aws iam get-policy-version \
  --policy-arn "${POLICY_ARN}" --version-id "${POLICY_VERSION}" >/dev/null 2>&1; then
  echo "ERROR: 安全な全削除には iam:GetPolicyVersion が必要です。" >&2
  echo "権限不足のまま部分削除せず、infra/operator-policy.example.json を管理者へ渡してください。" >&2
  exit 1
fi

if [[ "${1:-}" != "--yes" ]]; then
  echo "Knowledge Base、API、検索ログ、S3内の全versionを削除します。"
  read -r -p "費用を止めるためAWSリソースを削除しますか？ [yes/NO] " ANSWER
  [[ "${ANSWER}" == "yes" ]] || { echo "中止しました。"; exit 1; }
fi

"${TERRAFORM_BIN}" -chdir="${PROJECT_ROOT}/infra/terraform" plan \
  -destroy -var='force_destroy_bucket=true'
"${TERRAFORM_BIN}" -chdir="${PROJECT_ROOT}/infra/terraform" destroy \
  -var='force_destroy_bucket=true'

echo "AWSリソースを削除しました。リポジトリ内のコードとCSVは残っています。"
