// Explicit official-data integration check. Not discovered by `flutter test`.
// Generate the locally supplied assets first; no network/Bedrock/OS plugins.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/garbage_item.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('all 22 official calendars are readable by Flutter, with 08:00 cutoffs', () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38204');
    expect(areas.length, 22);
    final raw = jsonDecode(File('assets/data/municipality_38204_0_calendar.json').readAsStringSync());
    final schedule = ScheduleService(data: data, municipalityId: '38204', clock: () => DateTime(2026, 4, 1));
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days = raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      final categories = await data.categories(id, municipalityId: '38204');
      expect(categories.every((category) => category.cutoffMinutes == 480), isTrue);
      for (var month = DateTime(2026, 4); month.isBefore(DateTime(2027, 4)); month = DateTime(month.year, month.month + 1)) {
        final actual = await schedule.getMonthlySchedule(id, month.year, month.month);
        for (final entry in days.entries) {
          final date = DateTime.parse(entry.key);
          if (date.year != month.year || date.month != month.month) continue;
          expect((actual[date] ?? []).map((e) => e.category.toJsonString()).toSet(),
              (entry.value as List).cast<String>().toSet(), reason: '$id / ${entry.key}');
          checked++;
        }
      }
      expect(await schedule.getMonthlySchedule(id, 2027, 4), isEmpty);
    }
    expect(checked, 8030);
  });

  test('Oshima shared paper stream, iCal and notification planning agree', () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    const id = '38204-19';
    final categories = await data.categories(id, municipalityId: '38204');
    expect(categories.where((c) => c.toJsonString() == 'paper_all').length, 1);
    final schedule = ScheduleService(data: data, municipalityId: '38204', clock: () => DateTime(2026, 11, 1));
    final ical = await IcalExportService(schedule, now: () => DateTime(2026, 11, 1)).generateIcalString(id, months: 1);
    final month = await schedule.getMonthlySchedule(id, 2026, 11);
    expect('BEGIN:VEVENT'.allMatches(ical).length, month.values.fold<int>(0, (n, e) => n + e.length));
    expect(ical, contains('8時まで'));
    expect(ical, isNot(contains('7時まで')));
    final planned = await NotificationService.computeScheduleWindow(
      districtId: id, now: DateTime(2026, 11, 1),
      eveningTime: (hour: 20, minute: 0), morningTime: (hour: 7, minute: 0),
      eveningEnabledCategories: categories, morningEnabledCategories: categories,
      entriesForDate: schedule.getScheduleForDate,
    );
    expect(planned, isNotEmpty);
    expect(planned.every((n) => n.scheduledDate.hour == (n.isEvening ? 20 : 7)), isTrue);
    final afterCutoff = await NotificationService.computeScheduleWindow(
      districtId: id, now: DateTime(2026, 11, 1),
      eveningTime: (hour: 20, minute: 0), morningTime: (hour: 8, minute: 0),
      eveningEnabledCategories: [], morningEnabledCategories: categories,
      entriesForDate: schedule.getScheduleForDate,
    );
    expect(afterCutoff, isEmpty);
  });
}
