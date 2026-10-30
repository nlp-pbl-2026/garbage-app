"""Shared, explicitly dated official calendars; never infer recurrence."""

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import config
from .region_registry_service import CATEGORY_DEFINITIONS, RegionContext, get_registry


CATEGORY_TO_COLLECTION_TYPE = {
    "可燃": "combustible",
    "埋立": "landfill",
    "金・ガ": "metal_glass",
    "紙類": "paper",
    "ペット": "pet_bottle",
    "プラ": "plastic_packaging",
    "水銀": "mercury",
    "缶": "cans",
    "びん": "bottles",
    "粗大": "bulky",
}

# 松山市「ごみ分別はやわかり帳」の分類別搬出期限。
CATEGORY_COLLECTION_CUTOFF_HOURS = {
    "可燃": 7,
    "埋立": 8,
    "金・ガ": 8,
    "紙類": 8,
    "ペット": 8,
    "プラ": 8,
    "水銀": 8,
    "缶": 8,
    "びん": 8,
    "粗大": 8,
}


@dataclass(frozen=True)
class CollectionDate:
    date: date
    collection_type: str

    @property
    def display_date(self) -> str:
        weekdays = "月火水木金土日"
        return (
            f"{self.date.year}年{self.date.month}月{self.date.day}日"
            f"（{weekdays[self.date.weekday()]}）"
        )


class CalendarService:
    """CSVを一度だけ読み込み、分類コードから次の収集日を返す。"""

    def __init__(self, calendar_path: Path | None = None, *, region: RegionContext | None = None,
                 bundle: dict | None = None):
        self.region = region or get_registry().resolve("38201", "38201-08")
        self.version = self.region.version
        self.availability = "available"
        self._valid_from = date.fromisoformat(self.region.valid_from)
        self._valid_to = date.fromisoformat(self.region.valid_to)
        self._dates: dict[str, list[CollectionDate]] = {}
        # Explicit CSV injection remains available for legacy integrations/tests.
        if calendar_path is not None and calendar_path.suffix == ".csv":
            self._calendar_path = calendar_path
            self._dates = self._load_dates()
            return
        relative = Path("data/regions/matsuyama/generated/calendar-2026.json")
        candidates = [Path(__file__).resolve().parents[level] / relative for level in (3, 2)]
        default = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
        self._calendar_path = calendar_path or Path(config.CALENDAR_BUNDLE_PATH or default)
        if bundle is None:
            if not self._calendar_path.exists():
                self.availability = "missing_data"
                return
            bundle = json.loads(self._calendar_path.read_text(encoding="utf-8"))
        record = bundle.get("calendars", {}).get(self.region.calendar_id)
        if (bundle.get("version") != self.region.version or not record
                or record.get("verification_status") != "checked"
                or bundle.get("valid_from") != self.region.valid_from
                or bundle.get("valid_to") != self.region.valid_to):
            self.availability = "unverified_data"
            return
        for raw_date, categories in record["days"].items():
            parsed = date.fromisoformat(raw_date)
            if not self._valid_from <= parsed <= self._valid_to:
                raise ValueError("Calendar date outside its official validity")
            for category_id in categories:
                label = next((label for _, (identifier, label) in CATEGORY_DEFINITIONS.items()
                              if identifier == category_id), None)
                if label is None:
                    raise ValueError(f"Unknown collection category: {category_id}")
                self._dates.setdefault(category_id, []).append(CollectionDate(parsed, label))
        for entries in self._dates.values():
            entries.sort(key=lambda entry: entry.date)

    def _load_dates(self) -> dict[str, list[CollectionDate]]:
        dates: dict[str, list[CollectionDate]] = {}
        with self._calendar_path.open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                collection_type_id = row.get("collection_type_id", "")
                raw_dates = row.get("collection_dates", "")
                if not collection_type_id or not raw_dates:
                    continue
                bucket = dates.setdefault(collection_type_id, [])
                for raw_date in raw_dates.split("|"):
                    parsed = date.fromisoformat(raw_date)
                    if all(existing.date != parsed for existing in bucket):
                        bucket.append(
                            CollectionDate(
                                date=parsed,
                                collection_type=row["collection_type"],
                            )
                        )
        for bucket in dates.values():
            bucket.sort(key=lambda item: item.date)
        return dates

    def next_collection(
        self,
        category_code: str,
        *,
        from_date: date | None = None,
        at: datetime | None = None,
        cutoff_hour: int | None = None,
    ) -> CollectionDate | None:
        collection_type_id = CATEGORY_TO_COLLECTION_TYPE.get(category_code)
        if collection_type_id is None or self.availability != "available":
            return None
        if category_code == "粗大" and not self.region.is_nakajima:
            return None
        target_date = from_date or datetime.now(ZoneInfo(config.TIMEZONE)).date()
        if at is not None:
            local_now = at.astimezone(ZoneInfo(config.TIMEZONE))
            target_date = local_now.date()
            effective_cutoff = cutoff_hour if cutoff_hour is not None else CATEGORY_COLLECTION_CUTOFF_HOURS[category_code]
            collection_cutoff = time(hour=effective_cutoff)
            if local_now.time() >= collection_cutoff:
                target_date += timedelta(days=1)
        if not self._valid_from <= target_date <= self._valid_to:
            return None
        return next(
            (
                item
                for item in self._dates.get(collection_type_id, [])
                if item.date >= target_date
            ),
            None,
        )
