import '../models/collection_schedule.dart';
import '../models/garbage_item.dart';
import 'municipality_data_service.dart';
import '../utils/japan_time.dart';

/// Reads verified explicit dates for one municipality without extrapolation.
class ScheduleService {
  ScheduleService(
      {MunicipalityDataService? data,
      DateTime Function()? clock,
      this.municipalityId = '38201'})
      : _data = data ?? MunicipalityDataService(),
        _clock = clock ?? (() => japanWallTime(DateTime.now()));

  final String municipalityId;
  final MunicipalityDataService _data;
  final DateTime Function() _clock;

  Future<Map<DateTime, List<ScheduleEntry>>> getMonthlySchedule(
      String districtId, int year, int month) async {
    final record = await _data.verifiedCalendar(districtId,
        municipalityId: municipalityId);
    if (record == null) return {};
    final registry = await _data.registryFor(municipalityId);
    final start = DateTime.parse(registry['valid_from'] as String);
    final end = DateTime.parse(registry['valid_to'] as String);
    final categories =
        await _data.categories(districtId, municipalityId: municipalityId);
    final days = record['days'] as Map<String, dynamic>;
    final result = <DateTime, List<ScheduleEntry>>{};
    for (final day in days.entries) {
      final date = DateTime.parse(day.key);
      if (date.year != year ||
          date.month != month ||
          date.isBefore(start) ||
          date.isAfter(end)) {
        continue;
      }
      for (final code in (day.value as List).cast<String>()) {
        final matches = categories.where((category) =>
            category.toJsonString() == code ||
            (municipalityId == '38201' && _category(code) == category));
        if (matches.length != 1) {
          throw const FormatException('Unknown calendar collection type');
        }
        final category = matches.single;
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
    return now.hour * 60 + now.minute < entry.category.cutoffMinutes;
  }

  Future<List<ScheduleEntry>> _upcoming(String districtId) async {
    final now = _clock();
    if (await _data.area(districtId, municipalityId: municipalityId) == null) {
      return [];
    }
    final bundle = await _data.registryFor(municipalityId);
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

  Future<DateTime?> getNextCollectionDate(
      String districtId, String categoryId) async {
    final category = await _resolveCategory(districtId, categoryId);
    if (category == null) return null;
    for (final entry in await _upcoming(districtId)) {
      if (entry.category == category) return entry.date;
    }
    return null;
  }

  Future<List<DateTime>> getUpcomingCollectionDates(
      String districtId, String categoryId,
      {int count = 10}) async {
    final category = await _resolveCategory(districtId, categoryId);
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

  Future<GarbageCategory?> _resolveCategory(
      String districtId, String id) async {
    final categories =
        await _data.categories(districtId, municipalityId: municipalityId);
    for (final category in categories) {
      if (category.id == id ||
          (municipalityId == '38201' && category == _category(id))) {
        return category;
      }
    }
    return null;
  }

  GarbageCategory? _category(String value) {
    try {
      return GarbageCategoryExtension.fromString(value);
    } on ArgumentError {
      return null;
    }
  }
}
