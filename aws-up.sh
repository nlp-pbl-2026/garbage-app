#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
TERRAFORM_BIN="${TERRAFORM_BIN:-terraform}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/service-role/AmazonBedrockS3PolicyForKnowledgeBase_U-22-BedrockKnowledgeBaseRole-GarbageGuideDev"
POLICY_VERSION="$(aws iam get-policy --policy-arn "${POLICY_ARN}" --query 'Policy.DefaultVersionId' --output text 2>/dev/null || true)"

if [[ -n "${POLICY_VERSION}" ]] && {
  ! aws iam get-policy-version \
    --policy-arn "${POLICY_ARN}" --version-id "${POLICY_VERSION}" >/dev/null 2>&1 ||
  ! aws iam list-policy-versions \
    --policy-arn "${POLICY_ARN}" >/dev/null 2>&1
}; then
  echo "ERROR: AWSリソースの作成権限はありますが、Terraformが既存IAMポリシーを照合できません。" >&2
  echo "必要な権限: iam:GetPolicyVersion, iam:ListPolicyVersions" >&2
  echo "infra/operator-policy.example.json の権限を管理者に付与してもらってください。" >&2
  exit 1
fi

"${PROJECT_ROOT}/scripts/package_backend.sh"
"${TERRAFORM_BIN}" -chdir="${PROJECT_ROOT}/infra/terraform" init
"${TERRAFORM_BIN}" -chdir="${PROJECT_ROOT}/infra/terraform" apply
TERRAFORM_BIN="${TERRAFORM_BIN}" "${PROJECT_ROOT}/infra/scripts/sync_knowledge_base.sh"

API_URL="$("${TERRAFORM_BIN}" -chdir="${PROJECT_ROOT}/infra/terraform" output -raw backend_api_url)"
echo
echo "AWS構築完了: ${API_URL}"
echo "Flutter起動:"
echo "  cd frontend && flutter run -d chrome --dart-define=API_BASE_URL=${API_URL}"
echo "分析キー表示:"
echo "  ${TERRAFORM_BIN} -chdir=infra/terraform output -raw analytics_api_key"
