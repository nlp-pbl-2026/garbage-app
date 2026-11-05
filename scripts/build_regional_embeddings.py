#!/usr/bin/env python3
"""Explicit, paid Titan generation for a single verified regional CSV.

Call only after budget approval. A local checkpoint keyed by the exact embedding
text/model/dimensions avoids paying again after interruption or metadata changes.
This does not create/modify AWS resources, nor update any other city's files.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
from threading import Event, Lock
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_item_embeddings", ROOT / "backend/build_item_embeddings.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MODEL = "amazon.titan-embed-text-v2:0"
DIMENSIONS = 1024
# Conservative budget reserve, 10x the documented USD 0.00002 / 1,000 input tokens.
RESERVE_PER_1000 = .0002


def build(
    source,
    output,
    municipality,
    profile,
    checkpoint,
    *,
    max_calls=900,
    budget=1.0,
    workers=1,
):
    import boto3
    from botocore.config import Config
    import numpy as np
    rows = module.load_items(source)
    if not rows or len(rows) > max_calls or len({row['item_id'] for row in rows}) != len(rows):
        raise ValueError("Invalid item count or duplicate item IDs")
    if not 1 <= workers <= 8:
        raise ValueError("workers must be between 1 and 8")
    records = [json.loads(line) for line in checkpoint.read_text(encoding='utf-8').splitlines()] if checkpoint.exists() else []
    cache = {r['key']: r['vector'] for r in records if 'vector' in r}
    call_count = sum(r.get('calls', 0) for r in records)
    reserve = sum(r.get('reserved_usd', 0) for r in records)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    row_keys = []
    unique_documents = {}
    for row in rows:
        document = module.build_document(row)
        key = hashlib.sha256(f'{MODEL}/{DIMENSIONS}/{document}'.encode()).hexdigest()
        row_keys.append(key)
        unique_documents.setdefault(key, document)
    missing = [(key, document) for key, document in unique_documents.items() if key not in cache]
    if missing:
        minimum_cost = min(
            (len(document.encode('utf-8')) + 128) / 1000 * RESERVE_PER_1000
            for _, document in missing
        )
        if call_count >= max_calls or reserve + minimum_cost > budget:
            raise RuntimeError("Approved call/budget limit reached")
        client = boto3.client(
            'bedrock-runtime',
            region_name='ap-northeast-1',
            config=Config(
                retries={'total_max_attempts': 1},
                connect_timeout=10,
                read_timeout=45,
                max_pool_connections=max(10, workers * 2),
            ),
        )
        lock = Lock()
        stop = Event()

        def embed(entry):
            nonlocal call_count, reserve
            key, document = entry
            cost = (len(document.encode('utf-8')) + 128) / 1000 * RESERVE_PER_1000
            for attempt in range(3):
                if stop.is_set():
                    raise RuntimeError("Embedding generation stopped after another request failed")
                with lock:
                    if call_count >= max_calls or reserve + cost > budget:
                        raise RuntimeError("Approved call/budget limit reached")
                    reservation = {'key': key, 'calls': 1, 'reserved_usd': cost}
                    with checkpoint.open('a', encoding='utf-8') as stream:
                        stream.write(json.dumps(reservation) + '\n')
                    call_count += 1
                    reserve += cost
                try:
                    response = client.invoke_model(modelId=MODEL, body=json.dumps({
                        'inputText': document, 'dimensions': DIMENSIONS, 'normalize': True}))
                    body = json.loads(response['body'].read())
                    vector = body['embedding']
                    array = np.asarray(vector, dtype=np.float32)
                    if array.shape != (DIMENSIONS,) or not np.isfinite(array).all() or np.linalg.norm(array) == 0:
                        raise ValueError('Invalid Titan vector')
                    with lock:
                        cache[key] = vector
                        with checkpoint.open('a', encoding='utf-8') as stream:
                            stream.write(json.dumps({'key': key, 'vector': vector,
                                'input_tokens': body.get('inputTextTokenCount')}) + '\n')
                    return
                except Exception:
                    if attempt == 2:
                        stop.set()
                        raise
                    time.sleep(2 ** attempt)

        completed = len(unique_documents) - len(missing)
        print(
            f'{completed}/{len(unique_documents)} unique documents already cached; '
            f'{call_count} paid attempts; budget reserve ${reserve:.5f}',
            flush=True,
        )
        executor = ThreadPoolExecutor(max_workers=workers)
        futures = []
        try:
            futures = [executor.submit(embed, entry) for entry in missing]
            for future in as_completed(futures):
                future.result()
                completed += 1
                if completed % 50 == 0 or completed == len(unique_documents):
                    with lock:
                        print(
                            f'{completed}/{len(unique_documents)} unique documents; '
                            f'{call_count} paid attempts; budget reserve ${reserve:.5f}',
                            flush=True,
                        )
        except Exception:
            stop.set()
            for future in futures:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True)
    vectors = [cache[key] for key in row_keys]
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
    (output.parent / 'index_manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8'
    )
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
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    build(args.source, args.output, args.municipality, args.profile, args.checkpoint,
          max_calls=args.max_calls, budget=args.budget_usd, workers=args.workers)
