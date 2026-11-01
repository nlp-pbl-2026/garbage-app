"""Resolve collection areas independently of administrative districts and PDFs."""
from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
from datetime import date, time
from urllib.parse import quote

from .. import config


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


class UnsupportedMunicipalityError(RegionResolutionError):
    """The catalog does not register this municipality."""


class RegionalDataError(RuntimeError):
    """A registered municipality has missing or invalid local configuration."""


def data_path(relative: str) -> Path:
    candidates = [Path(__file__).resolve().parents[level] / relative for level in (3, 2)]
    return next((path for path in candidates if path.exists()), candidates[0])


@dataclass(frozen=True)
class CategoryDefinition:
    name: str
    collection_type_id: str | None = None
    cutoff: time | None = None
    answer_note: str = ""


@dataclass(frozen=True)
class RuleProfile:
    categories: dict[str, CategoryDefinition]
    items_path: Path
    embedding_index_path: Path
    calendar_path: Path
    classification_rules: str = ""
    size_question: str = "指定ごみ袋に入る大きさですか？"
    knowledge_title: str = ""
    knowledge_base_id: str = ""
    index_profile_id: str = ""


def matsuyama_profile(profile_id: str, root: Path | None = None) -> RuleProfile:
    """Compatibility adapter for the existing, unchanged Matsuyama datasets."""
    if profile_id not in ("matsuyama_hojo", "nakajima"):
        raise ValueError(f"Unknown Matsuyama rule profile: {profile_id}")
    root = root or data_path("data/regions/matsuyama")
    island = profile_id == "nakajima"
    categories = {}
    for code, (identifier, label) in CATEGORY_DEFINITIONS.items():
        if not island and code in ("缶", "びん"):
            continue
        scheduled = code != "禁止" and (code != "粗大" or island)
        note = ("松山市のごみ集積場所には出せません。" if code == "禁止" else
                "粗大ごみは戸別収集の申し込みが必要です。" if code == "粗大" and not island else "")
        categories[code] = CategoryDefinition(
            label, identifier if scheduled else None,
            time(7 if code == "可燃" else 8) if scheduled else None, note,
        )
    return RuleProfile(
        categories, root / "common/knowledge/items.csv",
        root / "common/knowledge/item_embeddings.npz",
        root / "generated/calendar-2026.json",
        size_question=("中島地域の45L以下の透明袋に入る大きさですか？" if island
                       else "松山市の指定ごみ袋に入る大きさですか？"),
        knowledge_title="松山市ごみ分別辞典", index_profile_id="matsuyama_hojo",
    )


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
    municipality_name: str = ""
    profile: RuleProfile | None = None

    @property
    def rules(self) -> RuleProfile:
        if self.profile is not None:
            return self.profile
        if self.municipality_id == "38201":
            return matsuyama_profile(self.rule_profile_id)
        raise RegionalDataError("自治体の分別設定がありません。")

    @property
    def municipality_label(self) -> str:
        return self.municipality_name or ("松山市" if self.municipality_id == "38201" else self.municipality_id)

    @property
    def category_names(self) -> dict[str, str]:
        return {code: definition.name for code, definition in self.rules.categories.items()}

    @property
    def category_codes(self) -> tuple[str, ...]:
        return tuple(self.rules.categories)

    @property
    def is_nakajima(self) -> bool:
        return self.municipality_id == "38201" and self.rule_profile_id == "nakajima"

    def asset_path(self, name: str) -> Path:
        # Existing environment variables only override Matsuyama, never another city.
        overrides = {"items_path": config.KNOWLEDGE_ITEMS_PATH,
                     "embedding_index_path": config.EMBEDDING_INDEX_PATH,
                     "calendar_path": config.CALENDAR_BUNDLE_PATH}
        if self.municipality_id == "38201" and overrides[name]:
            return Path(overrides[name])
        return getattr(self.rules, name)

    @property
    def evidence_prefix(self) -> str:
        parts = (self.municipality_id, self.rule_profile_id, self.version)
        return "regional://" + "/".join(quote(part, safe="") for part in parts) + "/"


class RegionRegistry:
    def __init__(self, path: Path | None = None):
        default = data_path("data/regions/matsuyama/registry.json")
        self.path = path or Path(os.getenv("REGION_REGISTRY_PATH", str(default)))
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(self.data, dict) or self.data.get("schema_version", 1) != 1:
            raise ValueError("Unsupported registry format")
        if not isinstance(self.data["version"], str) or not self.data["version"]:
            raise ValueError("Dataset version is required")
        if self.data["municipality_id"] != "38201" and not self.data.get("municipality_name"):
            raise ValueError("Municipality name is required")
        if date.fromisoformat(self.data["valid_from"]) > date.fromisoformat(self.data["valid_to"]):
            raise ValueError("Invalid dataset validity")
        self.profiles = self._load_profiles()
        areas = self.data["collection_areas"]
        self.areas = {a["id"]: a for a in areas}
        self.calendars = {c["id"]: c for c in self.data["calendars"]}
        if not areas or len(areas) != len(self.areas):
            raise ValueError("Duplicate collection area ID")
        if len(self.calendars) != len(self.data["calendars"]):
            raise ValueError("Duplicate calendar ID")
        for area in areas:
            if "display_name" in area and (not isinstance(area["display_name"], str) or not area["display_name"].strip()):
                raise ValueError("Invalid collection area display name")
            if area.get("municipality_id", self.data["municipality_id"]) != self.data["municipality_id"]:
                raise ValueError("Collection area municipality mismatch")
            calendar = self.calendars[area["calendar_id"]]
            if calendar["rule_profile_id"] != area["rule_profile_id"]:
                raise ValueError("Collection area/calendar profile mismatch")
            if area["rule_profile_id"] not in self.profiles:
                raise ValueError("Missing rule profile")

    def _load_profiles(self) -> dict[str, RuleProfile]:
        raw_profiles = self.data.get("rule_profiles")
        if raw_profiles is None and self.data["municipality_id"] == "38201":
            return {key: matsuyama_profile(key, self.path.parent)
                    for key in ("matsuyama_hojo", "nakajima")}
        if not isinstance(raw_profiles, dict) or not raw_profiles:
            raise ValueError("Explicit rule profiles are required")
        profiles = {}
        for key, raw in raw_profiles.items():
            if (not isinstance(key, str) or not key or not isinstance(raw, dict)
                    or not isinstance(raw.get("categories"), dict)):
                raise ValueError("Invalid rule profile")
            categories = {}
            for code, definition in raw["categories"].items():
                if not isinstance(definition, dict):
                    raise ValueError("Invalid category definition")
                identifier = definition.get("collection_type_id")
                cutoff = definition.get("cutoff")
                if identifier and (not cutoff or len(cutoff) != 5):
                    raise ValueError("Scheduled categories require an HH:MM cutoff")
                if not isinstance(code, str) or not isinstance(definition["name"], str):
                    raise ValueError("Category codes and names must be strings")
                if identifier is not None and (not isinstance(identifier, str) or not identifier):
                    raise ValueError("Invalid collection type ID")
                if not isinstance(definition.get("answer_note", ""), str):
                    raise ValueError("Category answer notes must be text")
                categories[code] = CategoryDefinition(
                    definition["name"], identifier, time.fromisoformat(cutoff) if cutoff else None,
                    definition.get("answer_note", ""),
                )
            if not categories or any(not code or not definition.name for code, definition in categories.items()):
                raise ValueError("Category codes and names are required")
            def asset(field):
                relative = Path(raw[field])
                if relative.is_absolute():
                    raise ValueError("Dataset asset paths must be relative")
                path = (self.path.parent / relative).resolve()
                if not path.is_relative_to(self.path.parent.resolve()):
                    raise ValueError("Dataset assets must be inside the municipality directory")
                return path
            if not isinstance(raw["classification_rules"], str):
                raise ValueError("Classification rules must be text")
            for field in ("size_question", "knowledge_title", "knowledge_base_id", "index_profile_id"):
                if field in raw and not isinstance(raw[field], str):
                    raise ValueError(f"{field} must be text")
            profiles[key] = RuleProfile(
                categories, asset("items_path"), asset("embedding_index_path"), asset("calendar_path"),
                classification_rules=raw["classification_rules"],
                size_question=raw.get("size_question", "指定ごみ袋に入る大きさですか？"),
                knowledge_title=raw.get("knowledge_title", ""),
                knowledge_base_id=raw.get("knowledge_base_id", ""),
                index_profile_id=raw.get("index_profile_id", key),
            )
        return profiles

    def candidates(self, district_id: str) -> tuple[str, ...]:
        # Ambiguous legacy IDs are intentionally absent from the current IDs.
        if district_id in self.areas:
            return (district_id,)
        return tuple(self.data.get("legacy_district_candidates", {}).get(district_id, []))

    def resolve(self, municipality_id: str, district_id: str) -> RegionContext:
        if municipality_id != self.data["municipality_id"]:
            raise UnsupportedMunicipalityError("指定された自治体は未対応です。")
        candidates = self.candidates(district_id)
        if len(candidates) > 1:
            raise RegionResolutionError("収集地区をもう一度選択してください。", candidates)
        if not candidates:
            raise RegionResolutionError("指定された収集地区は未対応です。")
        area = self.areas[candidates[0]]
        return RegionContext(municipality_id, area["id"], area.get("display_name", area["name"]),
                             area["calendar_id"], area["rule_profile_id"],
                             self.data["version"], self.data["valid_from"], self.data["valid_to"],
                             self.data.get("municipality_name", ""), self.profiles[area["rule_profile_id"]])


class MunicipalityCatalog:
    """Load only the explicitly registered municipality; no default-city fallback."""
    def __init__(self, path: Path | None = None):
        self.path = path or Path(os.getenv("MUNICIPALITY_CATALOG_PATH", str(data_path("data/regions/catalog.json"))))
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("schema_version", 1) != 1
                    or not isinstance(data["municipalities"], list)):
                raise ValueError("Unsupported catalog format")
            entries = data["municipalities"]
            for entry in entries:
                if not isinstance(entry["id"], str) or not entry["id"]:
                    raise ValueError("Municipality ID is required")
                registry_path = Path(entry["registry_path"])
                within_catalog = (self.path.parent / registry_path).resolve().is_relative_to(self.path.parent.resolve())
                if registry_path.is_absolute() or not within_catalog:
                    raise ValueError("Registry must be inside the catalog directory")
            self.entries = {entry["id"]: entry for entry in entries}
            if len(entries) != len(self.entries):
                raise ValueError("Duplicate municipality ID")
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise RegionalDataError("自治体カタログを読み込めません。") from error
        self._registries: dict[str, RegionRegistry] = {}

    def registry(self, municipality_id: str) -> RegionRegistry:
        if municipality_id not in self.entries:
            raise UnsupportedMunicipalityError("指定された自治体は未対応です。")
        if municipality_id not in self._registries:
            path = self.path.parent / self.entries[municipality_id]["registry_path"]
            if municipality_id == "38201" and os.getenv("REGION_REGISTRY_PATH"):
                path = Path(os.environ["REGION_REGISTRY_PATH"])
            try:
                registry = RegionRegistry(path)
                if registry.data["municipality_id"] != municipality_id:
                    raise ValueError("Catalog/registry municipality mismatch")
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise RegionalDataError("自治体の地区台帳・分別設定を読み込めません。") from error
            self._registries[municipality_id] = registry
        return self._registries[municipality_id]

    def resolve(self, municipality_id: str, district_id: str) -> RegionContext:
        return self.registry(municipality_id).resolve(municipality_id, district_id)


@lru_cache(maxsize=1)
def get_registry() -> MunicipalityCatalog:
    return MunicipalityCatalog()
