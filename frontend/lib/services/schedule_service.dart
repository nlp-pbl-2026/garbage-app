import '../models/collection_schedule.dart';
import '../models/garbage_item.dart';
import 'municipality_data_service.dart';
import '../utils/japan_time.dart';

/// Reads explicit FY2026 official dates from the same generated source as the API.
class ScheduleService {
  ScheduleService({MunicipalityDataService? data, DateTime Function()? clock})
      : _data = data ?? MunicipalityDataService(),
        _clock = clock ?? (() => japanWallTime(DateTime.now()));

  final MunicipalityDataService _data;
  final DateTime Function() _clock;

  Future<Map<DateTime, List<ScheduleEntry>>> getMonthlySchedule(
      String districtId, int year, int month) async {
    final record = await _data.verifiedCalendar(districtId);
    if (record == null) return {};
    final days = record['days'] as Map<String, dynamic>;
    final result = <DateTime, List<ScheduleEntry>>{};
    for (final day in days.entries) {
      final date = DateTime.parse(day.key);
      if (date.year != year || date.month != month) continue;
      for (final code in (day.value as List).cast<String>()) {
        final category = GarbageCategoryExtension.fromString(code);
        (result[date] ??= []).add(ScheduleEntry(
          districtId: districtId, category: category, date: date,
        ));
      }
    }
    return result;
  }

  Future<List<ScheduleEntry>> getScheduleForDate(String districtId, DateTime date) async {
    final month = await getMonthlySchedule(districtId, date.year, date.month);
    return month[DateTime(date.year, date.month, date.day)] ?? [];
  }

  bool _notPast(ScheduleEntry entry, DateTime now) {
    final date = DateTime(entry.date.year, entry.date.month, entry.date.day);
    final today = DateTime(now.year, now.month, now.day);
    if (date.isAfter(today)) return true;
    if (date.isBefore(today)) return false;
    final hour = entry.category == GarbageCategory.burnable ? 7 : 8;
    return now.hour < hour;
  }

  Future<List<ScheduleEntry>> _upcoming(String districtId) async {
    final now = _clock();
    final bundle = await _data.calendar;
    final end = DateTime.parse(bundle['valid_to'] as String);
    if (now.isAfter(end.add(const Duration(days: 1)))) return [];
    final entries = <ScheduleEntry>[];
    for (var month = DateTime(now.year, now.month); !month.isAfter(end);
        month = DateTime(month.year, month.month + 1)) {
      final schedule = await getMonthlySchedule(districtId, month.year, month.month);
      for (final day in schedule.values) {
        entries.addAll(day.where((entry) => _notPast(entry, now)));
      }
    }
    entries.sort((a, b) => a.date.compareTo(b.date));
    return entries;
  }

  Future<ScheduleEntry?> getNextCollection(String districtId) async {
    final entries = await _upcoming(districtId);
    return entries.isEmpty ? null : entries.first;
  }

  Future<DateTime?> getNextCollectionDate(String districtId, String categoryId) async {
    final category = _category(categoryId);
    if (category == null) return null;
    for (final entry in await _upcoming(districtId)) {
      if (entry.category == category) return entry.date;
    }
    return null;
  }

  Future<List<DateTime>> getUpcomingCollectionDates(String districtId,
      String categoryId, {int count = 10}) async {
    final category = _category(categoryId);
    if (category == null || count <= 0) return [];
    final dates = <DateTime>[];
    for (final entry in await _upcoming(districtId)) {
      if (entry.category == category && !dates.contains(entry.date)) {
        dates.add(entry.date);
        if (dates.length >= count) break;
      }
    }
    return dates;
  }

  GarbageCategory? _category(String value) {
    try {
      return GarbageCategoryExtension.fromString(value);
    } on ArgumentError {
      return null;
    }
  }
}
