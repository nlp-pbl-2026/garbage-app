#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TERRAFORM_BIN="${TERRAFORM_BIN:-terraform}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/service-role/AmazonBedrockS3PolicyForKnowledgeBase_U-22-BedrockKnowledgeBaseRole-GarbageGuideDev"
POLICY_VERSION="$(aws iam get-policy --policy-arn "${POLICY_ARN}" --query 'Policy.DefaultVersionId' --output text 2>/dev/null || true)"
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-garbage-guide-dev-api}"

update_existing_backend_only() {
  if ! aws lambda get-function \
    --function-name "${LAMBDA_FUNCTION_NAME}" >/dev/null 2>&1; then
    echo "ERROR: IAM読取権限がなく、更新対象の既存Lambdaも確認できません。" >&2
    echo "新規リソースは作成せず終了します。" >&2
    exit 1
  fi

  echo "INFO: IAM読取権限が不足しているため、既存Backendだけを更新する制限モードで続行します。"
  "${PROJECT_ROOT}/scripts/package_backend.sh"
  aws lambda update-function-code \
    --function-name "${LAMBDA_FUNCTION_NAME}" \
    --zip-file "fileb://${PROJECT_ROOT}/backend/dist/backend-lambda.zip" \
    --query 'FunctionName' --output text >/dev/null
  aws lambda wait function-updated --function-name "${LAMBDA_FUNCTION_NAME}"

  API_URL="$(aws apigatewayv2 get-apis \
    --query "Items[?Name=='garbage-guide-dev-http-api'].ApiEndpoint | [0]" \
    --output text)"
  if [[ -z "${API_URL}" || "${API_URL}" == "None" ]]; then
    echo "ERROR: 既存Backendは更新しましたが、API Gateway URLを取得できませんでした。" >&2
    exit 1
  fi
  echo
  echo "既存Backend更新完了（制限モード）: ${API_URL}"
  echo "Terraform・Knowledge Base・S3には変更を加えていません。"
  echo "Flutter起動:"
  echo "  cd frontend && flutter run -d chrome --dart-define=API_BASE_URL=${API_URL}"
}

if [[ -n "${POLICY_VERSION}" ]] && {
  ! aws iam get-policy-version \
    --policy-arn "${POLICY_ARN}" --version-id "${POLICY_VERSION}" >/dev/null 2>&1 ||
  ! aws iam list-policy-versions \
    --policy-arn "${POLICY_ARN}" >/dev/null 2>&1
}; then
  update_existing_backend_only
  exit 0
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
