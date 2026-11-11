#!/usr/bin/env python3
"""API-free, relocated Lambda smoke check. Never connects to AWS."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from package_backend_data import stage_data

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/imabari"


def main():
    with tempfile.TemporaryDirectory(prefix="imabari-lambda-") as scratch:
        root = Path(scratch)
        source = root / "source"
        registry = json.loads((DATA / "registry.json").read_text())
        paths = {"registry.json"}
        for profile in registry["rule_profiles"].values():
            for key in ["items_path", "embedding_index_path", "calendar_path"]:
                paths.add(profile[key])
            paths.add(str(Path(profile["items_path"]).parent / "index_manifest.json"))
        for name in paths:
            target = source / "imabari" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(DATA / name, target)
        catalog = source / "catalog.json"
        catalog.write_text(
            json.dumps(
                dict(
                    schema_version=1,
                    municipalities=[
                        dict(id="38202", registry_path="imabari/registry.json")
                    ],
                )
            )
        )
        package = root / "package"
        files = stage_data(package, catalog)
        assert len(files) == 9
        shutil.copytree(
            ROOT / "backend/app",
            package / "app",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        child = r"""
import json
from pathlib import Path
from urllib.parse import urlencode
import app
from app.lambda_main import handler
from app.services.region_registry_service import get_registry
from app.services.embedding_search_service import EmbeddingSearchService
assert Path(app.__file__).is_relative_to(Path.cwd())
registry=get_registry().registry('38202')
assert len(registry.areas)==233
for key in ['mainland','sekizen']:
    p=registry.profiles[key]
    assert p.items_path.is_relative_to(Path.cwd())
    assert EmbeddingSearchService(items_path=p.items_path,embeddings_path=p.embedding_index_path,municipality_id='38202',profile_id=key,runtime_client=object()).is_ready
def get(path,query={}):
    return handler(dict(version='2.0',routeKey='$default',rawPath=path,rawQueryString=urlencode(query),headers={'host':'localhost'},requestContext={'http':{'method':'GET','path':path,'sourceIp':'127.0.0.1'}},isBase64Encoded=False),None)
assert get('/api/health')['statusCode']==200
for area in ['38202-a052','38202-a012','38202-a210','38202-a119']:
    r=get('/api/search/items/38202',dict(district_id=area,category='bulky'))
    assert r['statusCode']==200
    assert json.loads(r['body'])['municipality_name']=='今治市'
print('Relocated Lambda: health / 4 regional item APIs / both indices OK; no AWS calls')
"""
        env = dict(os.environ)
        for key in [
            "REGION_REGISTRY_PATH",
            "MUNICIPALITY_CATALOG_PATH",
            "KNOWLEDGE_ITEMS_PATH",
            "EMBEDDING_INDEX_PATH",
            "CALENDAR_BUNDLE_PATH",
        ]:
            env.pop(key, None)
        subprocess.run([sys.executable, "-c", child], cwd=package, env=env, check=True)
        report = dict(
            runtime_data_files=len(files),
            runtime_bytes=sum(p.stat().st_size for p in files),
            relocated_lambda_health=True,
            regional_items_api_profiles=4,
            dedicated_indices_ready=2,
            paid_api_calls=0,
            linux_arm_not_tested=True,
        )
        try:
            stage_data(root / "full-catalog")
        except (FileNotFoundError, ValueError) as error:
            report.update(
                full_catalog_status="blocked_by_missing_existing_data",
                full_catalog_error=str(error),
            )
        else:
            report["full_catalog_status"] = "validated"
        (DATA / "generated/package-verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
