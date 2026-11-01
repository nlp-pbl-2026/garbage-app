#!/usr/bin/env python3
"""Explicit, paid Titan generation for a single verified regional CSV.

Call only after budget approval. A local checkpoint keyed by the exact embedding
text/model/dimensions avoids paying again after interruption or metadata changes.
This does not create/modify AWS resources, nor update any other city's files.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_item_embeddings", ROOT / "backend/build_item_embeddings.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MODEL = "amazon.titan-embed-text-v2:0"
DIMENSIONS = 1024
# Conservative budget reserve, 10x the documented USD 0.00002 / 1,000 input tokens.
RESERVE_PER_1000 = .0002


def build(source, output, municipality, profile, checkpoint, *, max_calls=900, budget=1.0):
    import boto3
    from botocore.config import Config
    import numpy as np
    rows = module.load_items(source)
    if not rows or len(rows) > max_calls or len({row['item_id'] for row in rows}) != len(rows):
        raise ValueError("Invalid item count or duplicate item IDs")
    records = [json.loads(line) for line in checkpoint.read_text().splitlines()] if checkpoint.exists() else []
    cache = {r['key']: r['vector'] for r in records if 'vector' in r}
    call_count = sum(r.get('calls', 0) for r in records)
    reserve = sum(r.get('reserved_usd', 0) for r in records)
    client = None
    vectors = []
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    for position, row in enumerate(rows, 1):
        document = module.build_document(row)
        key = hashlib.sha256(f'{MODEL}/{DIMENSIONS}/{document}'.encode()).hexdigest()
        if key not in cache:
            upper_tokens = len(document.encode('utf-8')) + 128
            cost = upper_tokens / 1000 * RESERVE_PER_1000
            for attempt in range(3):
                if call_count >= max_calls or reserve + cost > budget:
                    raise RuntimeError("Approved call/budget limit reached")
                # Reserve before the request, including failed/retried calls.
                reservation = {'key': key, 'calls': 1, 'reserved_usd': cost}
                with checkpoint.open('a') as stream:
                    stream.write(json.dumps(reservation) + '\n')
                call_count += 1
                reserve += cost
                if client is None:
                    client = boto3.client('bedrock-runtime', region_name='ap-northeast-1',
                        config=Config(retries={'total_max_attempts': 1}, connect_timeout=10, read_timeout=45))
                try:
                    response = client.invoke_model(modelId=MODEL, body=json.dumps({
                        'inputText': document, 'dimensions': DIMENSIONS, 'normalize': True}))
                    body = json.loads(response['body'].read())
                    vector = body['embedding']
                    array = np.asarray(vector, dtype=np.float32)
                    if array.shape != (DIMENSIONS,) or not np.isfinite(array).all() or np.linalg.norm(array) == 0:
                        raise ValueError('Invalid Titan vector')
                    cache[key] = vector
                    with checkpoint.open('a') as stream:
                        stream.write(json.dumps({'key': key, 'vector': vector,
                            'input_tokens': body.get('inputTextTokenCount')}) + '\n')
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
        vectors.append(cache[key])
        if position % 50 == 0 or position == len(rows):
            print(f'{position}/{len(rows)} records; {call_count} paid attempts; budget reserve ${reserve:.5f}', flush=True)
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, vectors=matrix, item_ids=np.array([r['item_id'] for r in rows]),
                        model_id=np.array(MODEL), dimensions=np.array(DIMENSIONS))
    manifest = {'schema_version': 1, 'municipality_id': municipality, 'profile_id': profile,
        'item_count': len(rows), 'model_id': MODEL, 'dimensions': DIMENSIONS,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'index_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'verification': 'csv_ids_model_dimensions_finite_normalized_checked',
        'embedding_text': 'backend/build_item_embeddings.py:build_document',
        'generation_calls': call_count, 'generation_budget_reserve_usd': reserve}
    (output.parent / 'index_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Wrote {output} and verification manifest')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--municipality', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--max-calls', type=int, default=900)
    parser.add_argument('--budget-usd', type=float, default=1)
    args = parser.parse_args()
    build(args.source, args.output, args.municipality, args.profile, args.checkpoint,
          max_calls=args.max_calls, budget=args.budget_usd)
