"""清水地区の公式カレンダーから次回収集日を決定する。"""

import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import config


CATEGORY_TO_COLLECTION_TYPE = {
    "可燃": "combustible",
    "埋立": "landfill",
    "金・ガ": "metal_glass",
    "紙類": "paper",
    "ペット": "pet_bottle",
    "プラ": "plastic_packaging",
    "水銀": "mercury",
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

    def __init__(self, calendar_path: Path | None = None):
        configured_path = Path(config.CALENDAR_PATH) if config.CALENDAR_PATH else None
        self._calendar_path = calendar_path or configured_path or (
            Path(__file__).resolve().parents[3]
            / "data/regions/matsuyama/shimizu/calendar/2026.csv"
        )
        self._dates = self._load_dates()

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
        if collection_type_id is None:
            return None
        target_date = from_date or date.today()
        if at is not None:
            local_now = at.astimezone(ZoneInfo(config.TIMEZONE))
            target_date = local_now.date()
            effective_cutoff = cutoff_hour
            if effective_cutoff is None:
                effective_cutoff = config.COLLECTION_CUTOFF_HOUR
            if effective_cutoff is None:
                effective_cutoff = CATEGORY_COLLECTION_CUTOFF_HOURS.get(
                    category_code, 8
                )
            collection_cutoff = time(hour=effective_cutoff)
            if local_now.time() >= collection_cutoff:
                target_date += timedelta(days=1)
        return next(
            (
                item
                for item in self._dates.get(collection_type_id, [])
                if item.date >= target_date
            ),
            None,
        )
