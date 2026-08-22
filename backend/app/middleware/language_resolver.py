"""Accept-Language ヘッダー解析ロジック（純粋関数）

RFC 9110 準拠の Accept-Language ヘッダーパースを行い、
サポート言語の中から最適な言語を決定する。

このモジュールは外部依存なし（標準ライブラリのみ使用）。
"""

from __future__ import annotations

import re

SUPPORTED_LANGUAGES = ["ja", "en", "pt", "zh", "vi"]

# Pattern to match a language tag with optional q-factor
# Examples: "en", "en-US", "pt-BR;q=0.8", "zh-CN;q=0.5", "*;q=0.1"
_LANG_TAG_RE = re.compile(
    r"^\s*"
    r"([a-zA-Z]{1,8}(?:-[a-zA-Z0-9]{1,8})*|\*)"  # language tag or wildcard
    r"\s*(?:;\s*q\s*=\s*([01](?:\.\d{0,3})?))?"   # optional q-factor
    r"\s*$"
)


def resolve_language(accept_language: str | None) -> str:
    """RFC 9110 準拠の Accept-Language 解析。

    q-factor 重み付けで最優先のサポート言語を返す。
    サポート言語にマッチしない場合は 'ja' にフォールバックする。

    Args:
        accept_language: Accept-Language ヘッダーの値。None or 空文字の場合は 'ja' を返す。

    Returns:
        解決された言語コード（SUPPORTED_LANGUAGES のいずれか）
    """
    if not accept_language or not accept_language.strip():
        return "ja"

    # Parse each comma-separated language tag
    parsed: list[tuple[str, float]] = []
    for tag_str in accept_language.split(","):
        match = _LANG_TAG_RE.match(tag_str)
        if not match:
            # Malformed entry — skip
            continue

        lang_tag = match.group(1).lower()
        q_str = match.group(2)

        # Parse q-factor, default to 1.0
        if q_str is not None:
            try:
                q_value = float(q_str)
            except ValueError:
                q_value = 1.0
            # Clamp to valid range [0, 1]
            q_value = max(0.0, min(1.0, q_value))
        else:
            q_value = 1.0

        # Skip tags with q=0 (explicitly rejected)
        if q_value == 0.0:
            continue

        parsed.append((lang_tag, q_value))

    if not parsed:
        return "ja"

    # Sort by q-factor descending, then by order of appearance (stable sort)
    parsed.sort(key=lambda x: x[1], reverse=True)

    # Try to match each tag (in priority order) to a supported language
    for lang_tag, _ in parsed:
        if lang_tag == "*":
            # Wildcard matches the default language
            return "ja"

        # Extract base language code (handle regional variants like pt-BR → pt)
        base_lang = lang_tag.split("-")[0]

        if base_lang in SUPPORTED_LANGUAGES:
            return base_lang

    # No supported language found
    return "ja"
