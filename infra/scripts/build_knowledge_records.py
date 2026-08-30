"""CSV原本をBedrock向けの1レコード1文書へ変換する。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = (
    PROJECT_ROOT / "data/regions/matsuyama/common/knowledge"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "infra/generated/knowledge_records"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def clean_output(output_dir: Path) -> None:
    """既知の生成ファイルだけを消し、指定外のファイルには触れない。"""

    if not output_dir.exists():
        return
    for path in output_dir.rglob("*.txt"):
        path.unlink()
    for path in sorted(output_dir.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def write_document(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(line for line in lines if line) + "\n", encoding="utf-8")


def build_item_documents(source_dir: Path, output_dir: Path) -> int:
    count = 0
    for row in read_csv(source_dir / "items.csv"):
        item_id = row.get("item_id", "").strip()
        item = row.get("item", "").strip()
        if not item_id or not item:
            continue
        write_document(
            output_dir / "items" / f"{item_id}.txt",
            [
                "松山市 家庭ごみ分別辞典",
                f"品目: {item}",
                f"読み: {row.get('reading', '').strip()}" if row.get("reading") else "",
                f"分類コード: {row.get('category', '').strip()}",
                f"分類: {row.get('category_display', '').strip()}",
                f"出し方・注意: {row.get('note', '').strip()}" if row.get("note") else "",
                f"検索情報: {row.get('search_text', '').strip()}",
                f"出典ページ: {row.get('source_printed_page', '').strip()}" if row.get("source_printed_page") else "",
            ],
        )
        count += 1
    return count


def build_rule_documents(source_dir: Path, output_dir: Path) -> int:
    count = 0
    for source_name in ("category_rules.csv", "general_rules.csv"):
        for index, row in enumerate(read_csv(source_dir / source_name), start=1):
            record_id = (
                row.get("rule_id")
                or row.get("record_id")
                or f"{Path(source_name).stem}_{index:04d}"
            )
            lines = ["松山市 家庭ごみ分別ルール"]
            lines.extend(
                f"{key}: {value.strip()}"
                for key, value in row.items()
                if value and value.strip()
            )
            write_document(output_dir / "rules" / f"{record_id}.txt", lines)
            count += 1
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean_output(args.output_dir)
    item_count = build_item_documents(args.source_dir, args.output_dir)
    rule_count = build_rule_documents(args.source_dir, args.output_dir)
    manifest = {
        "source": str(args.source_dir.relative_to(PROJECT_ROOT)),
        "item_documents": item_count,
        "rule_documents": rule_count,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
