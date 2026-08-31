#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GARBAGE_API_BASE_URL="${GARBAGE_API_BASE_URL:-}"
GARBAGE_FLUTTER_DEVICE="${GARBAGE_FLUTTER_DEVICE:-chrome}"
GARBAGE_CHECK_ONLY=false

if [[ "${1:-}" == "--check" ]]; then
  GARBAGE_CHECK_ONLY=true
elif [[ -n "${1:-}" ]]; then
  echo "使い方: $0 [--check]" >&2
  exit 2
fi

if [[ -z "${GARBAGE_API_BASE_URL}" ]]; then
  echo "ERROR: GARBAGE_API_BASE_URL を設定してください。" >&2
  echo "例: export GARBAGE_API_BASE_URL=https://example.execute-api.ap-northeast-1.amazonaws.com" >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curlが必要です。" >&2
  exit 1
fi
if [[ "${GARBAGE_CHECK_ONLY}" == "false" ]] && ! command -v flutter >/dev/null 2>&1; then
  echo "ERROR: Flutter SDKをPATHへ追加してください。" >&2
  exit 1
fi

echo "AWS検索APIを確認しています: ${GARBAGE_API_BASE_URL%/}"
curl --fail --silent --show-error --max-time 10 \
  "${GARBAGE_API_BASE_URL%/}/api/health"
echo

if [[ "${GARBAGE_CHECK_ONLY}" == "true" ]]; then
  echo "AWS検索APIは利用可能です。"
  exit 0
fi

cd "${PROJECT_ROOT}/frontend"
flutter pub get
exec flutter run -d "${GARBAGE_FLUTTER_DEVICE}" \
  "--dart-define=API_BASE_URL=${GARBAGE_API_BASE_URL%/}"
