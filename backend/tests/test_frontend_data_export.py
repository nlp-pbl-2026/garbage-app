"""Synthetic data only: no paid models, AWS access, or official data changes."""

import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
import pytest

from app.lambda_main import app
from app.services.frontend_data_service import build_snapshot

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import fetch_frontend_data as fetcher
import flutter_with_data as wrapper


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False))


@pytest.fixture
def source(tmp_path, monkeypatch):
    for cid in ("90001", "90002"):
        folder = tmp_path / cid
        write(
            folder / "registry.json",
            {
                "schema_version": 1,
                "municipality_id": cid,
                "municipality_name": cid + "試験市",
                "version": "v1",
                "valid_from": "2026-04-01",
                "valid_to": "2027-03-31",
                "collection_areas": [
                    {
                        "id": "same-area",
                        "name": "試験地区",
                        "calendar_id": "same-calendar",
                        "rule_profile_id": "standard",
                        "private_field": "never-export",
                    }
                ],
                "calendars": [{"id": "same-calendar", "rule_profile_id": "standard"}],
                "private_field": "never-export",
                "rule_profiles": {
                    "standard": {
                        "items_path": "private/items.csv",
                        "embedding_index_path": "private/item_embeddings.npz",
                        "calendar_path": "calendar.json",
                        "classification_rules": "never-export",
                        "categories": {
                            "burn": {
                                "name": "燃えるごみ",
                                "collection_type_id": "burn",
                                "cutoff": "08:00",
                            },
                            "paper": {
                                "name": "紙",
                                "collection_type_id": "paper",
                                "cutoff": "08:00",
                            },
                        },
                    }
                },
            },
        )
        write(
            folder / "calendar.json",
            {
                "municipality_id": cid,
                "version": "v1",
                "valid_from": "2026-04-01",
                "valid_to": "2027-03-31",
                "calendars": {
                    "same-calendar": {
                        "verification_status": "checked",
                        "days": {"2026-11-13": ["burn", "paper"]},
                    }
                },
            },
        )
    write(
        tmp_path / "90001/address.json",
        {
            "municipality_id": "90001",
            "version": "v1",
            "private_path": "never-export",
            "entries": [
                {"town": "試験町", "lookup_town": "試験町", "area_id": "same-area"}
            ],
        },
    )
    catalog = tmp_path / "catalog.json"
    write(
        catalog,
        {
            "schema_version": 1,
            "frontend_export_policy_path": "policy.json",
            "municipalities": [
                {
                    "id": cid,
                    "registry_path": f"{cid}/registry.json",
                    "addresses_path": "90001/address.json" if cid == "90001" else None,
                }
                for cid in ("90001", "90002")
            ],
        },
    )
    write(
        tmp_path / "policy.json",
        {
            "schema_version": 1,
            "scope": "flutter_ui_json_redistribution",
            "municipalities": {
                cid: {"status": "pending"} for cid in ("90001", "90002")
            },
        },
    )
    monkeypatch.setenv("MUNICIPALITY_CATALOG_PATH", str(catalog))
    monkeypatch.setenv("FRONTEND_DATA_ALLOW_UNREVIEWED_LOCAL", "1")
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_RUNTIME_API", raising=False)
    monkeypatch.setattr(fetcher.time, "sleep", lambda _: None)
    return catalog


def bridge(client):
    def get(url):
        parsed = urlsplit(url)
        response = client.get(
            parsed.path + ("?" + parsed.query if parsed.query else "")
        )
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")
        return response.json()

    return get


def local_client():
    return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1234))


def test_ui_only_snapshot_is_independent_of_csv_npz_and_backend_prompts(source):
    manifest, files = build_snapshot(source)
    assert len(files) == 6  # catalog + two registries/calendars + one address table
    assert b"never-export" not in b"".join(files.values())
    assert b"items.csv" not in b"".join(files.values())
    assert b"item_embeddings.npz" not in b"".join(files.values())
    first, second = manifest["catalog"]["municipalities"]
    assert "addresses_asset" in first and "addresses_asset" not in second
    assert (
        files["municipality_90001_0_calendar.json"]
        == (source.parent / "90001/calendar.json").read_bytes()
    )


@pytest.mark.parametrize(
    "case", ["default", "remote-client", "remote-host", "lambda", "proxy"]
)
def test_pending_publication_is_blocked_even_if_local_override_is_present(
    source, monkeypatch, case
):
    client = local_client()
    headers = {}
    if case == "default":
        monkeypatch.delenv("FRONTEND_DATA_ALLOW_UNREVIEWED_LOCAL")
    if case == "remote-client":
        client = TestClient(
            app, base_url="http://127.0.0.1", client=("198.51.100.1", 1)
        )
    if case == "remote-host":
        client = TestClient(app, base_url="https://example.test")
    if case == "lambda":
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test-function")
    if case == "proxy":
        headers = {"X-Forwarded-For": "127.0.0.1"}
    assert client.get("/api/frontend-data/manifest", headers=headers).status_code == 503
    assert client.get("/api/health").status_code == 200


def test_approved_policy_allows_export_without_local_switch(source, monkeypatch):
    policy = json.loads((source.parent / "policy.json").read_text())
    for review in policy["municipalities"].values():
        review.update(
            status="approved",
            evidence_url="https://example.test/synthetic-license",
            reviewed_by="Synthetic fixture",
            reviewed_on="2026-11-13",
        )
    write(source.parent / "policy.json", policy)
    monkeypatch.delenv("FRONTEND_DATA_ALLOW_UNREVIEWED_LOCAL")
    response = TestClient(app, base_url="https://example.test").get(
        "/api/frontend-data/manifest"
    )
    assert response.status_code == 200
    assert response.json()["redistribution_status"] == "approved"


@pytest.mark.parametrize(
    "case",
    [
        "missing-calendar",
        "missing-address",
        "address-version",
        "wrong-area",
        "outside-date",
        "unknown-stream",
        "bad-approval",
    ],
)
def test_incomplete_or_inconsistent_data_stops_export(source, case):
    root = source.parent
    if case == "missing-calendar":
        (root / "90001/calendar.json").unlink()
    elif case == "missing-address":
        (root / "90001/address.json").unlink()
    elif case in {"address-version", "wrong-area"}:
        path = root / "90001/address.json"
        value = json.loads(path.read_text())
        if case == "address-version":
            value["version"] = "v2"
        else:
            value["entries"][0]["area_id"] = "other-area"
        write(path, value)
    elif case in {"outside-date", "unknown-stream"}:
        path = root / "90001/calendar.json"
        value = json.loads(path.read_text())
        value["calendars"]["same-calendar"]["days"] = (
            {"2027-04-01": ["burn"]}
            if case == "outside-date"
            else {"2026-11-13": ["other"]}
        )
        write(path, value)
    else:
        path = root / "policy.json"
        value = json.loads(path.read_text())
        value["municipalities"]["90001"]["status"] = "approved"
        write(path, value)
    assert local_client().get("/api/frontend-data/manifest").status_code == 503


def test_fetch_preserves_partial_streams_and_unknown_dates(source, tmp_path):
    path = source.parent / "90001/calendar.json"
    raw = json.loads(path.read_text())
    record = raw["calendars"]["same-calendar"]
    record.update(
        verification_status="partially_checked",
        collection_type_verification={
            "burn": {"status": "checked"},
            "paper": {
                "status": "unverified",
                "message": "紙は未確認",
                "source_url": "https://example.test/calendar",
            },
        },
        unverified_dates={
            "burn": {
                "2026-11-14": {
                    "message": "当日未確認",
                    "source_url": "https://example.test/calendar",
                }
            }
        },
        days={"2026-11-13": ["burn"]},
    )
    write(path, raw)
    output = tmp_path / "downloaded"
    result = fetcher.fetch(
        "http://127.0.0.1",
        output,
        expected_ids={"90001", "90002"},
        allow_unreviewed_local=True,
        get=bridge(local_client()),
    )
    assert result["dataset_version"]
    assert (
        output / "municipality_90001_0_calendar.json"
    ).read_bytes() == path.read_bytes()
    assert not (output / "municipality_90002_addresses.json").exists()


@pytest.mark.parametrize(
    "case",
    ["hash", "version", "identity", "unsafe-path", "manifest-race", "missing-city"],
)
def test_fetch_rejects_tampered_or_mixed_responses_without_installing(
    source, tmp_path, case
):
    actual = bridge(local_client())
    calls = []

    def get(url):
        result = actual(url)
        calls.append(url)
        if "/municipalities/" in url:
            if case == "hash":
                result["files"][next(iter(result["files"]))] += " "
            if case == "version":
                result["dataset_version"] = "0" * 64
            if case == "identity":
                result["municipality_id"] = "other-city"
        elif case == "unsafe-path":
            result["catalog"]["municipalities"][0][
                "registry_asset"
            ] = "assets/data/../escape.json"
        elif case == "missing-city":
            result["catalog"]["municipalities"].pop()
        elif case == "manifest-race" and len(calls) > 1:
            result["dataset_version"] = "0" * 64
        return result

    output = tmp_path / "downloaded"
    with pytest.raises(ValueError):
        fetcher.fetch(
            "http://127.0.0.1",
            output,
            expected_ids={"90001", "90002"},
            allow_unreviewed_local=True,
            get=get,
        )
    assert not output.exists()


def test_old_output_is_never_overwritten(source, tmp_path):
    output = tmp_path / "already-installed"
    output.mkdir()
    original = output / "keep.json"
    original.write_bytes(b"keep")
    with pytest.raises(ValueError, match="NEW"):
        fetcher.fetch(
            "http://127.0.0.1",
            output,
            expected_ids={"90001", "90002"},
            get=lambda _: pytest.fail("No request expected"),
        )
    assert original.read_bytes() == b"keep"


@pytest.mark.parametrize("target_exists", [True, False])
def test_output_symlinks_are_rejected_before_request(tmp_path, target_exists):
    target = tmp_path / "protected"
    if target_exists:
        target.mkdir()
    output = tmp_path / "linked-output"
    output.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="NEW"):
        fetcher.fetch(
            "http://127.0.0.1",
            output,
            expected_ids={"90001"},
            get=lambda _: pytest.fail("No request expected"),
        )
    assert output.is_symlink()
    assert target.exists() == target_exists


def test_remote_unreviewed_data_and_non_https_urls_are_rejected(source, tmp_path):
    with pytest.raises(ValueError, match="HTTPS"):
        fetcher.fetch("http://example.test", tmp_path / "one", expected_ids={"90001"})
    with pytest.raises(ValueError, match="loopback"):
        fetcher.fetch(
            "https://example.test",
            tmp_path / "two",
            expected_ids={"90001"},
            allow_unreviewed_local=True,
        )
    with pytest.raises(ValueError, match="Redistribution"):
        fetcher.fetch(
            "http://127.0.0.1",
            tmp_path / "three",
            expected_ids={"90001", "90002"},
            get=bridge(local_client()),
        )


def test_wrapper_preserves_original_frontend_and_uses_downloaded_data(
    source, tmp_path, monkeypatch
):
    project = tmp_path / "clone"
    (project / "frontend/assets/data").mkdir(parents=True)
    write(project / "data/regions/catalog.json", json.loads(source.read_text()))
    old = project / "frontend/assets/data/municipality_calendar.json"
    old.write_bytes(b"old local data")
    (project / "frontend/pubspec.lock").write_bytes(b"keep lockfile")
    monkeypatch.setattr(wrapper, "ROOT", project)
    original_fetch = fetcher.fetch
    monkeypatch.setattr(
        wrapper,
        "fetch",
        lambda *a, **kw: original_fetch(*a, **kw, get=bridge(local_client())),
    )
    target, manifest = wrapper.prepare_workspace(
        "http://127.0.0.1", tmp_path / "workspace", allow_unreviewed_local=True
    )
    assert old.read_bytes() == b"old local data"
    assert (target / "pubspec.lock").read_bytes() == b"keep lockfile"
    assert not (target / "assets/data/municipality_calendar.json").exists()
    assert (target / "assets/data/municipality_90001_0_calendar.json").exists()
    assert manifest["redistribution_status"] == "unreviewed_local_only"


@pytest.mark.parametrize("step", ["rewrite", "retrieve", "decide", "classify"])
def test_stale_ui_version_stops_search_before_paid_operations(
    source, monkeypatch, step
):
    from app.routers import search_router

    async def must_not_call(_):
        pytest.fail("No model operation is allowed with stale UI data")

    monkeypatch.setattr(search_router, "_run_step", must_not_call)
    response = local_client().post(
        "/api/search/" + step,
        json={
            "query": "試験",
            "rewritten_query": "試験",
            "municipality_id": "90001",
            "district_id": "same-area",
            "ui_dataset_version": "0" * 64,
        },
    )
    assert response.status_code == 409


@pytest.mark.parametrize("with_version", [True, False])
def test_matching_version_and_legacy_requests_keep_search_contract(
    source, monkeypatch, with_version
):
    from app.routers import search_router

    async def no_model(_):
        return "試験"

    monkeypatch.setattr(search_router, "_run_step", no_model)
    body = {"query": "試験", "municipality_id": "90001", "district_id": "same-area"}
    if with_version:
        body["ui_dataset_version"] = build_snapshot(source)[0]["dataset_version"]
    response = local_client().post("/api/search/rewrite", json=body)
    assert response.status_code == 200 and response.json()["rewritten_query"] == "試験"


def test_bulky_projection_omits_unknown_private_fields():
    from app.services.frontend_data_service import project_bulky

    result = project_bulky(
        {
            "category_code": "bulky",
            "private_field": "secret",
            "config": {
                "municipality_id": "90001",
                "private_field": "secret",
                "source_urls": ["https://example.test/guide"],
                "steps": [
                    {
                        "step_number": 1,
                        "title": "申込",
                        "description": "公式案内を確認",
                        "private_field": "secret",
                    }
                ],
            },
        }
    )
    assert "secret" not in json.dumps(result)
    assert result["config"]["source_urls"] == ["https://example.test/guide"]


def test_workspace_cannot_recursively_copy_into_source_frontend(
    source, tmp_path, monkeypatch
):
    project = tmp_path / "source-project"
    (project / "frontend").mkdir(parents=True)
    monkeypatch.setattr(wrapper, "ROOT", project)
    with pytest.raises(ValueError, match="outside the source"):
        wrapper.prepare_workspace("http://127.0.0.1", project / "frontend/nested")
    assert not (project / "frontend/nested").exists()
