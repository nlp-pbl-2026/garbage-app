"""Paid generation is replaced with a local fake; resume and budget are verified."""
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import boto3
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('build_regional_embeddings', ROOT / 'scripts/build_regional_embeddings.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_resume_reuses_exact_embedding_text_but_reverifies_changed_csv_metadata(tmp_path, monkeypatch):
    calls = []
    class Runtime:
        def invoke_model(self, **kwargs):
            calls.append(kwargs)
            return {'body': io.BytesIO(json.dumps({'embedding': [1., 0.], 'inputTextTokenCount': 3}).encode())}
    monkeypatch.setattr(boto3, 'client', lambda *a, **k: Runtime())
    monkeypatch.setattr(builder, 'DIMENSIONS', 2)
    source, output, checkpoint = tmp_path/'items.csv', tmp_path/'index.npz', tmp_path/'checkpoint.jsonl'
    source.write_text('item_id,item,category,note\na,試験品,burn,出し方\n')
    builder.build(source, output, '90001', 'test', checkpoint, max_calls=3, budget=1)
    assert len(calls) == 1
    source.write_text('item_id,item,category,note\na,試験品,carry,出し方\n')
    builder.build(source, output, '90001', 'test', checkpoint, max_calls=3, budget=1)
    assert len(calls) == 1
    manifest = json.loads((tmp_path/'index_manifest.json').read_text())
    assert manifest['municipality_id'] == '90001'
    assert manifest['source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    with np.load(output) as index:
        assert index['item_ids'].tolist() == ['a']
        assert index['vectors'].shape == (1, 2)


def test_budget_limit_is_checked_before_any_aws_client_is_created(tmp_path, monkeypatch):
    monkeypatch.setattr(boto3, 'client', lambda *a, **k: pytest.fail('Unexpected AWS client'))
    source = tmp_path/'items.csv'
    source.write_text('item_id,item,note\na,試験品,出し方\n')
    with pytest.raises(RuntimeError, match='budget'):
        builder.build(source, tmp_path/'index.npz', '90001', 'test', tmp_path/'checkpoint.jsonl', budget=0)
    assert not (tmp_path/'index.npz').exists()


def test_shared_disposal_text_is_evidence_but_does_not_bias_item_embeddings():
    from app.services.item_search_service import ItemMatch
    row = {"item": "試験いす", "note": "木製は可燃", "disposal_instructions": "指定袋で収集日までに搬出"}
    document = builder.module.build_document(row)
    assert document == "試験いす。木製は可燃"
    match = ItemMatch(item_id="test", item=row["item"], category="burn", category_display="可燃",
        note=row["note"], score=1, disposal_instructions=row["disposal_instructions"])
    assert "指定袋で収集日までに搬出" in match.evidence_text
    assert "品目固有条件を優先" in match.evidence_text
