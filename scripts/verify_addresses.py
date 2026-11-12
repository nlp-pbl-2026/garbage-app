import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "frontend/assets/data/municipality_addresses.json").read_text(encoding="utf-8"))

# Nominatimが返した 'neighbourhood: 二番町四丁目' を想定
# AddressNormalizerが全角→半角変換するので、CSVの'二番町４丁目'と一致するはず
target = "二番町４丁目"
matches = [e for e in data["entries"] if e["town"] == target]
print(f"「{target}」の一致: {matches}")

# 全角数字を含む町名サンプル
samples = [e["town"] for e in data["entries"] if any(c in e["town"] for c in "１２３４５６７８９０")]
print(f"全角数字を含む町名サンプル（先頭5件）: {samples[:5]}")
print(f"全体エントリ数: {len(data['entries'])}")
print(f"バージョン: {data['version']}")
