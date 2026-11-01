// Explicit official-data integration check. Not discovered by `flutter test`.
// Generate the locally supplied assets first; no network/Bedrock/OS plugins.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/garbage_item.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('all 23 calendars with category-level verification are readable by Flutter, with 08:00 cutoffs', () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38204');
    expect(areas.length, 23);
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
    expect(checked, 8395);
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
  test('Go/Chuo uses only confirmed non-paper dates from PDF 13', () async {
    final data = MunicipalityDataService();
    final schedule = ScheduleService(data: data, municipalityId: '38204', clock: () => DateTime(2026, 4, 1));
    const id = '38204-13-go';
    final statuses = await schedule.collectionStatuses(id);
    expect(statuses.entries.where((entry) => entry.value.isUnverified).map((entry) => entry.key).toSet(),
        {'cardboard', 'newspaper', 'magazines', 'paper_packaging'});
    final raw = jsonDecode(File('assets/data/municipality_38204_0_calendar.json').readAsStringSync());
    final partial = raw['calendars']['yh-13-go'];
    final tuesday = raw['calendars']['yh-13-tu']['days'] as Map<String, dynamic>;
    final friday = raw['calendars']['yh-13-fr']['days'] as Map<String, dynamic>;
    final papers = statuses.entries.where((e) => e.value.isUnverified).map((e) => e.key).toSet();
    for (final day in (partial['days'] as Map<String, dynamic>).entries) {
      final nonPaper = (tuesday[day.key] as List).cast<String>().where((code) => !papers.contains(code)).toSet();
      expect((day.value as List).toSet(), nonPaper);
      expect((friday[day.key] as List).cast<String>().where((code) => !papers.contains(code)).toSet(), nonPaper);
    }
    final ical = await IcalExportService(schedule, now: () => DateTime(2026, 4, 1)).generateIcalString(id, months: 12);
    for (final paper in papers) {
      expect(await schedule.getNextCollectionDate(id, paper), isNull);
      expect(ical, isNot(contains('-$paper@garbageapp')));
    }
    expect(ical, contains('-burnable@garbageapp'));
  });

  test('all Yawatahama selection labels are unique place names without calendar details', () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38204');
    final districts = await RegionService(data: data).getDistricts('38204');
    final names = districts.map((district) => district.name).toList();
    expect(names.toSet().length, 23);
    expect(names.any((name) => RegExp(r'^\d+[（(：:]').hasMatch(name)), isFalse);
    expect(names.any((name) => name.contains('紙類') || name.contains('未確認')), isFalse);
    expect((await data.area('38204-13-go', municipalityId: '38204'))!['name'], '郷・中央（郷一木地区・旧道沿い）');
    expect((await data.area('38204-15-th', municipalityId: '38204'))!['name'], '日土町（神明・今出）');
    expect((await data.area('38204-10', municipalityId: '38204'))!['name'], '日土町（神明・今出・田之窪を除く）');
    expect((await data.registryFor('38204')).containsKey('coverage_notice'), isFalse);
    for (final area in areas) {
      expect(area['calendar_id'], isNotNull);
      expect(area['official_calendar_number'], isNotNull);
    }
  });

}
