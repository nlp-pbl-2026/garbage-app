"""Unit tests for language middleware Accept-Language parsing."""

import sys
import os

# Ensure backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.middleware.language_resolver import resolve_language, SUPPORTED_LANGUAGES


class TestResolveLanguage:
    """Tests for resolve_language function."""

    # --- Missing/empty header → fallback to 'ja' ---

    def test_none_header_returns_ja(self):
        assert resolve_language(None) == "ja"

    def test_empty_string_returns_ja(self):
        assert resolve_language("") == "ja"

    def test_whitespace_only_returns_ja(self):
        assert resolve_language("   ") == "ja"

    # --- Simple supported language tags ---

    def test_simple_ja(self):
        assert resolve_language("ja") == "ja"

    def test_simple_en(self):
        assert resolve_language("en") == "en"

    def test_simple_pt(self):
        assert resolve_language("pt") == "pt"

    def test_simple_zh(self):
        assert resolve_language("zh") == "zh"

    def test_simple_vi(self):
        assert resolve_language("vi") == "vi"

    # --- Regional variants → base language ---

    def test_pt_br_returns_pt(self):
        assert resolve_language("pt-BR") == "pt"

    def test_zh_cn_returns_zh(self):
        assert resolve_language("zh-CN") == "zh"

    def test_en_us_returns_en(self):
        assert resolve_language("en-US") == "en"

    def test_zh_tw_returns_zh(self):
        assert resolve_language("zh-TW") == "zh"

    def test_en_gb_returns_en(self):
        assert resolve_language("en-GB") == "en"

    def test_vi_vn_returns_vi(self):
        assert resolve_language("vi-VN") == "vi"

    # --- Unsupported languages → fallback to 'ja' ---

    def test_unsupported_language_returns_ja(self):
        assert resolve_language("fr") == "ja"

    def test_unsupported_with_region_returns_ja(self):
        assert resolve_language("de-DE") == "ja"

    def test_multiple_unsupported_returns_ja(self):
        assert resolve_language("fr, de, it") == "ja"

    # --- Q-factor weighting ---

    def test_highest_q_factor_wins(self):
        # en has q=0.5, pt has q=0.9 → pt wins
        assert resolve_language("en;q=0.5, pt;q=0.9") == "pt"

    def test_default_q_is_1(self):
        # pt has implicit q=1.0, en has q=0.8 → pt wins
        assert resolve_language("pt, en;q=0.8") == "pt"

    def test_explicit_q1_equal_to_default(self):
        assert resolve_language("en;q=1.0") == "en"

    def test_q0_means_rejected(self):
        # en is explicitly rejected (q=0), fallback to ja
        assert resolve_language("en;q=0") == "ja"

    def test_mixed_supported_and_unsupported_with_q(self):
        # fr (unsupported) has highest q, en is next → en
        assert resolve_language("fr;q=1.0, en;q=0.9, de;q=0.8") == "en"

    def test_complex_q_factor_ordering(self):
        # zh has q=0.7, vi has q=0.9, en has q=0.5 → vi wins
        assert resolve_language("zh;q=0.7, vi;q=0.9, en;q=0.5") == "vi"

    def test_regional_with_q_factor(self):
        # pt-BR;q=0.8 → pt, en-US;q=0.5 → en; pt wins
        assert resolve_language("pt-BR;q=0.8, en-US;q=0.5") == "pt"

    # --- Malformed entries ---

    def test_malformed_entries_skipped(self):
        # First entry is malformed, second is valid
        assert resolve_language(";;;, en") == "en"

    def test_completely_malformed_returns_ja(self):
        assert resolve_language(";;;///!!!") == "ja"

    def test_invalid_q_value_skipped_as_malformed(self):
        # Invalid q value → entire entry treated as malformed, skip it
        assert resolve_language("en;q=abc") == "ja"

    def test_invalid_q_value_with_valid_fallback(self):
        # Invalid q entry is skipped, valid entry is used
        assert resolve_language("en;q=abc, pt") == "pt"

    # --- Case insensitivity ---

    def test_uppercase_tag_matches(self):
        assert resolve_language("EN") == "en"

    def test_mixed_case_regional_matches(self):
        assert resolve_language("Pt-Br") == "pt"

    # --- Wildcard handling ---

    def test_wildcard_alone_returns_ja(self):
        assert resolve_language("*") == "ja"

    def test_wildcard_with_low_q_after_supported(self):
        # en is preferred, wildcard is fallback
        assert resolve_language("en;q=0.9, *;q=0.1") == "en"

    # --- Whitespace tolerance ---

    def test_spaces_around_tags(self):
        assert resolve_language(" en , pt ;q=0.5 ") == "en"

    def test_spaces_around_q_value(self):
        assert resolve_language("vi ; q = 0.8") == "vi"

    # --- Real-world browser headers ---

    def test_chrome_header(self):
        # Typical Chrome header for English user
        header = "en-US,en;q=0.9,ja;q=0.8"
        assert resolve_language(header) == "en"

    def test_firefox_portuguese_header(self):
        # Typical Firefox header for Portuguese (Brazil) user
        header = "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3"
        assert resolve_language(header) == "pt"

    def test_no_supported_in_browser_header(self):
        # User with only unsupported languages
        header = "fr-FR,fr;q=0.9,de;q=0.8,it;q=0.7"
        assert resolve_language(header) == "ja"
