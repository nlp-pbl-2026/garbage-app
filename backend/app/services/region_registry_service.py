"""Resolve collection areas independently of administrative districts and PDFs."""
from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path


CATEGORY_DEFINITIONS = {
    "可燃": ("combustible", "可燃ごみ"),
    "プラ": ("plastic_packaging", "プラスチック製容器包装"),
    "紙類": ("paper", "紙類"),
    "金・ガ": ("metal_glass", "金物・ガラス類"),
    "埋立": ("landfill", "埋立ごみ"),
    "水銀": ("mercury", "水銀ごみ"),
    "ペット": ("pet_bottle", "ペットボトル"),
    "粗大": ("bulky", "粗大ごみ"),
    "缶": ("cans", "缶類"),
    "びん": ("bottles", "びん類"),
    "禁止": ("not_collected", "市で収集しないもの"),
}


class RegionResolutionError(ValueError):
    def __init__(self, message: str, candidates: tuple[str, ...] = ()):
        super().__init__(message)
        self.candidates = candidates


@dataclass(frozen=True)
class RegionContext:
    municipality_id: str
    area_id: str
    area_name: str
    calendar_id: str
    rule_profile_id: str
    version: str
    valid_from: str
    valid_to: str

    @property
    def category_codes(self) -> tuple[str, ...]:
        return tuple(code for code in CATEGORY_DEFINITIONS
                     if self.rule_profile_id == "nakajima" or code not in ("缶", "びん"))

    @property
    def is_nakajima(self) -> bool:
        return self.rule_profile_id == "nakajima"


class RegionRegistry:
    def __init__(self, path: Path | None = None):
        default = Path(__file__).resolve().parents[3] / "data/regions/matsuyama/registry.json"
        self.path = path or Path(os.getenv("REGION_REGISTRY_PATH", str(default)))
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        areas = self.data["collection_areas"]
        self.areas = {a["id"]: a for a in areas}
        self.calendars = {c["id"]: c for c in self.data["calendars"]}
        if len(areas) != len(self.areas):
            raise ValueError("Duplicate collection area ID")
        for area in areas:
            calendar = self.calendars[area["calendar_id"]]
            if calendar["rule_profile_id"] != area["rule_profile_id"]:
                raise ValueError("Collection area/calendar profile mismatch")

    def candidates(self, district_id: str) -> tuple[str, ...]:
        # Ambiguous legacy IDs are intentionally absent from the current IDs.
        if district_id in self.areas:
            return (district_id,)
        return tuple(self.data.get("legacy_district_candidates", {}).get(district_id, []))

    def resolve(self, municipality_id: str, district_id: str) -> RegionContext:
        if municipality_id != self.data["municipality_id"]:
            raise RegionResolutionError("現在は松山市のみ対応しています。")
        candidates = self.candidates(district_id)
        if len(candidates) > 1:
            raise RegionResolutionError("収集地区をもう一度選択してください。", candidates)
        if not candidates:
            raise RegionResolutionError("指定された収集地区は未対応です。")
        area = self.areas[candidates[0]]
        return RegionContext(municipality_id, area["id"], area["name"],
                             area["calendar_id"], area["rule_profile_id"],
                             self.data["version"], self.data["valid_from"], self.data["valid_to"])


@lru_cache(maxsize=1)
def get_registry() -> RegionRegistry:
    return RegionRegistry()
