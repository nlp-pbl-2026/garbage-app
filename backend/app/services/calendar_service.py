"""Shared, explicitly dated official calendars; never infer recurrence."""

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import config
from .region_registry_service import RegionContext, get_registry


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


@dataclass(frozen=True)
class CollectionStatus:
    status: str
    message: str | None = None
    source_url: str | None = None


class CalendarService:
    """確認済みの年度別日付を読み込み、分類コードから次の収集日を返す。"""

    def __init__(self, calendar_path: Path | None = None, *, region: RegionContext | None = None,
                 bundle: dict | None = None):
        self.region = region or get_registry().resolve("38201", "38201-08")
        self.version = self.region.version
        self.availability = "available"
        self._valid_from = date.fromisoformat(self.region.valid_from)
        self._valid_to = date.fromisoformat(self.region.valid_to)
        self._dates: dict[str, list[CollectionDate]] = {}
        self._verification: dict[str, dict] = {}
        # Explicit CSV injection remains available for legacy integrations/tests.
        if calendar_path is not None and calendar_path.suffix == ".csv":
            self._calendar_path = calendar_path
            self._dates = self._load_dates()
            return
        self._calendar_path = calendar_path or self.region.asset_path("calendar_path")
        if bundle is None:
            if not self._calendar_path.exists():
                self.availability = "missing_data"
                return
            bundle = json.loads(self._calendar_path.read_text(encoding="utf-8"))
        if not isinstance(bundle, dict) or not isinstance(bundle.get("calendars"), dict):
            raise ValueError("Invalid calendar bundle")
        record = bundle["calendars"].get(self.region.calendar_id)
        if (bundle.get("version") != self.region.version or not isinstance(record, dict)
                or (bundle.get("municipality_id") != self.region.municipality_id
                    and not (self.region.municipality_id == "38201" and "municipality_id" not in bundle))
                or record.get("verification_status") not in {"checked", "partially_checked"}
                or bundle.get("valid_from") != self.region.valid_from
                or bundle.get("valid_to") != self.region.valid_to):
            self.availability = "unverified_data"
            return
        streams = {definition.collection_type_id for definition in self.region.rules.categories.values()
                   if definition.collection_type_id}
        verification = record.get("collection_type_verification")
        if verification is not None or record["verification_status"] == "partially_checked":
            if (not isinstance(verification, dict) or set(verification) != streams
                    or any(not isinstance(info, dict) or info.get("status") not in {"checked", "unverified"}
                           for info in verification.values())):
                raise ValueError("Invalid collection type verification")
            unverified = [info for info in verification.values() if info["status"] == "unverified"]
            if (bool(unverified) != (record["verification_status"] == "partially_checked")
                    or len(unverified) == len(streams)
                    or any(not info.get("message") or not info.get("source_url") for info in unverified)):
                raise ValueError("Inconsistent partial calendar verification")
            self._verification = verification
            if unverified:
                self.availability = "partially_available"
        if not isinstance(record.get("days"), dict):
            raise ValueError("Invalid calendar days")
        for raw_date, categories in record["days"].items():
            if not isinstance(categories, list) or any(not isinstance(value, str) for value in categories):
                raise ValueError("Invalid calendar collection types")
            parsed = date.fromisoformat(raw_date)
            if not self._valid_from <= parsed <= self._valid_to:
                raise ValueError("Calendar date outside its official validity")
            for category_id in categories:
                if self._verification.get(category_id, {}).get("status") == "unverified":
                    raise ValueError("Unverified collection type must not contain scheduled dates")
                label = next((definition.name for definition in self.region.rules.categories.values()
                              if definition.collection_type_id == category_id), None)
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
        definition = self.region.rules.categories.get(category_code)
        collection_type_id = definition.collection_type_id if definition else None
        if (collection_type_id is None or self.availability not in {"available", "partially_available"}
                or self._verification.get(collection_type_id, {}).get("status") == "unverified"):
            return None
        target_date = from_date or datetime.now(ZoneInfo(config.TIMEZONE)).date()
        if at is not None:
            local_now = at.astimezone(ZoneInfo(config.TIMEZONE))
            target_date = local_now.date()
            collection_cutoff = time(hour=cutoff_hour) if cutoff_hour is not None else definition.cutoff
            if collection_cutoff is None:
                return None
            if local_now.time() >= collection_cutoff:
                target_date += timedelta(days=1)
        if not self._valid_from <= target_date <= self._valid_to:
            return None
        result = next(
            (
                item
                for item in self._dates.get(collection_type_id, [])
                if item.date >= target_date
            ),
            None,
        )
        return CollectionDate(result.date, definition.name) if result else None

    def collection_status(self, category_code: str, next_collection: CollectionDate | None = None) -> CollectionStatus:
        definition = self.region.rules.categories.get(category_code)
        if definition is None or definition.collection_type_id is None:
            return CollectionStatus("not_scheduled")
        if self.availability not in {"available", "partially_available"}:
            return CollectionStatus(self.availability)
        info = self._verification.get(definition.collection_type_id, {})
        if info.get("status") == "unverified":
            return CollectionStatus("unverified", info["message"], info["source_url"])
        return CollectionStatus("scheduled" if next_collection else "no_upcoming_collection")
