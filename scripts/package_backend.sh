#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/backend/dist/lambda-build"
ZIP_PATH="${PROJECT_ROOT}/backend/dist/backend-lambda.zip"

# Both clients must ship the same reviewed dates, even if assets were edited
# after the last data build. The full official-source gate is documented in
# docs/data.md and must be run before packaging.
cmp "${PROJECT_ROOT}/data/regions/matsuyama/generated/calendar-2026.json" \
    "${PROJECT_ROOT}/frontend/assets/data/municipality_calendar.json"

rm -rf "${BUILD_DIR}" "${ZIP_PATH}"
mkdir -p "${BUILD_DIR}/app/routers" "${BUILD_DIR}/app/services"

uv pip install \
  --target "${BUILD_DIR}" \
  --python-version 3.12 \
  --python-platform aarch64-manylinux2014 \
  --only-binary :all: \
  mangum fastapi pydantic 'boto3>=1.43.53' numpy

cp "${PROJECT_ROOT}/backend/app/__init__.py" "${BUILD_DIR}/app/"
cp "${PROJECT_ROOT}/backend/app/config.py" "${BUILD_DIR}/app/"
cp "${PROJECT_ROOT}/backend/app/schemas.py" "${BUILD_DIR}/app/"
cp "${PROJECT_ROOT}/backend/app/lambda_main.py" "${BUILD_DIR}/app/"
cp "${PROJECT_ROOT}/backend/app/routers/__init__.py" "${BUILD_DIR}/app/routers/"
cp "${PROJECT_ROOT}/backend/app/routers/search_router.py" "${BUILD_DIR}/app/routers/"
cp "${PROJECT_ROOT}/backend/app/services/__init__.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/calendar_service.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/search_log_service.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/item_search_service.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/embedding_search_service.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/region_registry_service.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/nakajima_search_service.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/nakajima_rule_service.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/matsuyama_prompt_rules.py" "${BUILD_DIR}/app/services/"
cp "${PROJECT_ROOT}/backend/app/services/waste_guide_service.py" "${BUILD_DIR}/app/services/"

PYTHONDONTWRITEBYTECODE=1 python3 "${PROJECT_ROOT}/scripts/package_backend_data.py" "${BUILD_DIR}"

(cd "${BUILD_DIR}" && zip -q -r "${ZIP_PATH}" .)
echo "Lambda package: ${ZIP_PATH}"
