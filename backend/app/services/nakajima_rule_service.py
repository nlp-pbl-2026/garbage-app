"""Translate shared item candidates into FY2026 Nakajima evidence.

The shared vectors identify possible items.  Mainland classification notes are
never used as Nakajima evidence.  The common category relationship comes from
Matsuyama's March 2026 waste plan; collection instructions come from the
FY2026 Nakajima calendar and the city's Nakajima household-waste page.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .item_search_service import ItemMatch
from .region_registry_service import CATEGORY_DEFINITIONS


PLAN_URL = (
    "https://www.city.matsuyama.ehime.jp/kurashi/gomi/kanren/"
    "gomikeikaku.files/R8ippaikeikaku_honpenn.pdf"
)
CALENDAR_URL = (
    "https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/"
    "gomicalender/r8gomicaletikubetu.files/2026nakajimaoura.pdf"
)
RULES_URL = (
    "https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/"
    "kateigomi_nakajima.html"
)

# The plan describes Nakajima as splitting the mainland metal/glass category.
# Excluded items and blank classifications need their own item-level grounds.
COMMON_CATEGORIES = frozenset({"可燃", "プラ", "紙類", "ペット", "埋立", "水銀", "粗大"})

# These mainland notes can change the classification or collection eligibility.
# They must be reviewed for Nakajima rather than inherited from the dictionary.
CONDITIONAL_NOTE = re.compile(
    r"[「『][^」』]+[」』]|袋に入らない|場合|ものは|P\.?\s*\d+|"
    r"申込|申し込|申し込み|戸別|電話|持ち込|引き取|収集しな|出せな|処理できな"
)
CONTAINER_NAME = re.compile(r"缶|びん|ビン|瓶")
MIXED_CONTAINER = re.compile(r"缶.*(?:びん|ビン|瓶)|(?:びん|ビン|瓶).*缶")
BEVERAGE_FOOD_CAN = re.compile(r"缶詰|飲料缶|(?:お茶|ジュース|ビール|コーヒー)の缶")
BEVERAGE_FOOD_BOTTLE = re.compile(
    r"(?:ビール|ワイン|ラムネ|牛乳|しょうゆ|醤油|みりん|料理酒|"
    r"ドレッシング|飲料|食料品|調味料).*(?:びん|ビン|瓶|ガラス製)"
)
METAL_GLASS_EXCEPTION = re.compile(
    r"スプレー缶|カセットボンベ|一斗缶|(?:びん|ビン|瓶)の(?:ふた|キャップ)|"
    r"(?:びん|ビン|瓶).*キャップ.*金属"
)

# These instructions are limited to what the island's official material says.
# The candidate's mainland note is deliberately absent.
ISLAND_INSTRUCTIONS = {
    "可燃": "中島地域の可燃ごみは、45L以下の白色半透明袋で午前7時までに出します。",
    "プラ": "中島地域のプラスチック製容器包装は、汚れを取り除き、45L以下の無色透明袋で午前8時までに出します。",
    "紙類": "中島地域の紙類は、紙の種類ごとに分け、十文字にひもをかけて午前8時までに出します。",
    "ペット": "中島地域ではPETマークのあるボトルをペットボトルとして、キャップとラベルを外し、軽くすすいで午前8時までに出します。",
    "埋立": "中島地域の埋立ごみは、地区別カレンダーの収集日に午前8時までに出します。",
    "水銀": "中島地域の水銀ごみは、45L以下の無色透明袋で午前8時までに出します。",
    "粗大": "中島地域の粗大ごみは、地区別カレンダーの収集日に集積場所へ午前8時までに出します。小さなものは45L以下の無色透明袋に入れます。",
    "金・ガ": "中島地域の金物・ガラス類は、45L以下の無色透明袋で午前8時までに出します。刃物や割れガラスは安全に包んで表示します。袋に入らないものは粗大ごみです。",
    "缶": "中島地域の缶類は、中身を残さず軽くすすぎ、45L以下の無色透明袋で午前8時までに出します。",
    "びん": "中島地域のびん類は、キャップを外して軽くすすぎ、45L以下の無色透明袋で午前8時までに出します。",
}


def _norm(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace(" ", "").replace("　", "")


@dataclass(frozen=True)
class IslandRuleResult:
    category: str | None
    status: str
    reason: str


def resolve_shared_item(match: ItemMatch) -> IslandRuleResult:
    """Apply only the official common-category relationship and clear split rules.

    A conditional mainland note is a review flag, not Nakajima evidence.  An
    ambiguous can/bottle name is never converted by its spelling alone.
    """

    name = _norm(match.item)
    note = _norm(match.note)
    if not name or not match.category or match.category == "禁止":
        return IslandRuleResult(None, "unverified", "個別の中島地域の根拠が必要")
    # The dictionary's four PET rows mention sorting detached caps into a
    # different category; that does not make the bottle's own category vary.
    if (match.category == "ペット" and "ペットボトル" in name
            and "キャップ" in note and "ボトルはすすいで出す" in note
            and "場合" not in note):
        return IslandRuleResult("ペット", "common_rule", "基本計画で共通のペットボトル区分")
    if CONDITIONAL_NOTE.search(note):
        return IslandRuleResult(None, "conditional", "品目の条件を公式資料と照合する必要あり")

    if match.category in COMMON_CATEGORIES:
        return IslandRuleResult(match.category, "common_rule", "基本計画で共通の分別区分")

    if match.category != "金・ガ":
        return IslandRuleResult(None, "unverified", "中島地域の区分を確認できない")
    if MIXED_CONTAINER.search(name):
        return IslandRuleResult(None, "conditional", "缶とびんの用途・材質を確認する必要あり")
    if METAL_GLASS_EXCEPTION.search(name):
        return IslandRuleResult("金・ガ", "split_rule", "中島カレンダーの金物・ガラス類の例")
    if BEVERAGE_FOOD_CAN.search(name):
        return IslandRuleResult("缶", "split_rule", "中島カレンダーの飲料缶・缶詰の例")
    if BEVERAGE_FOOD_BOTTLE.search(name):
        return IslandRuleResult("びん", "split_rule", "中島カレンダーの飲料・食料品用びんの例")
    if CONTAINER_NAME.search(name):
        return IslandRuleResult(None, "conditional", "中身の用途・材質を確認する必要あり")
    return IslandRuleResult("金・ガ", "split_rule", "基本計画で残る金物・ガラス類")


def evidence_text(match: ItemMatch, rule: IslandRuleResult) -> str:
    if rule.category is None:
        raise ValueError("Unverified candidate cannot become classification evidence")
    label = CATEGORY_DEFINITIONS[rule.category][1]
    instructions = ISLAND_INSTRUCTIONS[rule.category]
    if rule.category == "金・ガ" and ("スプレー缶" in match.item or "カセットボンベ" in match.item):
        instructions += "スプレー缶・カセットボンベは必ず使い切って出します。"
    return (
        f"品目: {match.item}\n"
        f"分類: {label} ({rule.category})\n"
        "根拠の範囲: 品目名は共通索引の検索候補です。中島地域の個別品目表への掲載を示すものではありません。\n"
        f"中島地域の分類根拠: {rule.reason}。\n"
        f"出し方・条件: {instructions}\n"
        f"出典: {PLAN_URL} / {CALENDAR_URL} / {RULES_URL}"
    )
