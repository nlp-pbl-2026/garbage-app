from datetime import date

from app.services.calendar_service import CalendarService


def test_returns_next_shimizu_collection_date():
    service = CalendarService()

    result = service.next_collection("可燃", from_date=date(2026, 8, 24))

    assert result is not None
    assert result.date == date(2026, 8, 25)
    assert result.collection_type == "可燃ごみ"
    assert result.display_date == "2026年8月25日（火）"


def test_returns_none_for_non_calendar_category():
    service = CalendarService()

    assert service.next_collection("禁止", from_date=date(2026, 8, 24)) is None
    assert service.next_collection("粗大", from_date=date(2026, 8, 24)) is None

