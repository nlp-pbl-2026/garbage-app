#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/backend/dist/lambda-build"
ZIP_PATH="${PROJECT_ROOT}/backend/dist/backend-lambda.zip"

rm -rf "${BUILD_DIR}" "${ZIP_PATH}"
mkdir -p "${BUILD_DIR}/app/routers" "${BUILD_DIR}/app/services"

uv pip install \
  --target "${BUILD_DIR}" \
  --python-version 3.12 \
  --python-platform aarch64-manylinux2014 \
  --only-binary :all: \
  mangum fastapi pydantic 'boto3>=1.43.53'

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
cp "${PROJECT_ROOT}/backend/app/services/waste_guide_service.py" "${BUILD_DIR}/app/services/"

mkdir -p "${BUILD_DIR}/data/regions/matsuyama/shimizu/calendar"
cp "${PROJECT_ROOT}/data/regions/matsuyama/shimizu/calendar/2026.csv" \
  "${BUILD_DIR}/data/regions/matsuyama/shimizu/calendar/"
mkdir -p "${BUILD_DIR}/data/regions/matsuyama/common/knowledge"
cp "${PROJECT_ROOT}/data/regions/matsuyama/common/knowledge/items.csv" \
  "${BUILD_DIR}/data/regions/matsuyama/common/knowledge/"

(cd "${BUILD_DIR}" && zip -q -r "${ZIP_PATH}" .)
echo "Lambda package: ${ZIP_PATH}"
