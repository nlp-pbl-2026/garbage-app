// Explicit official-data integration check; not discovered by flutter test.
// Generate the reviewed local assets first. No network/Bedrock/OS calls.
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
  test('all 16 Iyo areas consume the same 5840 backend dates and 08:30 cutoffs',
      () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38210');
    expect(areas.length, 16);
    final raw = jsonDecode(
        File('assets/data/municipality_38210_0_calendar.json')
            .readAsStringSync());
    final schedule = ScheduleService(
        data: data, municipalityId: '38210', clock: () => DateTime(2026, 4, 1));
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days =
          raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      final categories = await data.categories(id, municipalityId: '38210');
      expect(categories.length, 9);
      expect(categories.every((category) => category.cutoffMinutes == 510),
          isTrue);
      for (var month = DateTime(2026, 4);
          month.isBefore(DateTime(2027, 4));
          month = DateTime(month.year, month.month + 1)) {
        final actual =
            await schedule.getMonthlySchedule(id, month.year, month.month);
        for (final entry in days.entries) {
          final date = DateTime.parse(entry.key);
          if (date.year != month.year || date.month != month.month) continue;
          expect(
              (actual[date] ?? [])
                  .map((e) => e.category.toJsonString())
                  .toSet(),
              (entry.value as List).cast<String>().toSet(),
              reason: '$id / ${entry.key}');
          checked++;
        }
      }
      expect(await schedule.getMonthlySchedule(id, 2027, 4), isEmpty);
    }
    expect(checked, 5840);
    final names = (await RegionService(data: data).getDistricts('38210'))
        .map((d) => d.name)
        .toList();
    expect(names.toSet().length, 16);
    expect(
        names.any((name) =>
            name.contains('紙類') || name.contains('未確認') || name.contains('火曜')),
        isFalse);
  });

  test('unverified streams stay out of next dates, iCal and notifications',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    const id = '38210-iyo-hiraoka';
    final schedule = ScheduleService(
        data: data,
        municipalityId: '38210',
        clock: () => DateTime(2026, 11, 1));
    final statuses = await schedule.collectionStatuses(id);
    final unknown = statuses.entries
        .where((e) => e.value.isUnverified)
        .map((e) => e.key)
        .toSet();
    expect(unknown,
        {'bottles', 'pet_bottles', 'non_burnable', 'hazardous', 'paper'});
    final ical =
        await IcalExportService(schedule, now: () => DateTime(2026, 11, 1))
            .generateIcalString(id, months: 1);
    for (final code in unknown) {
      expect(await schedule.getNextCollectionDate(id, code), isNull);
      expect(ical, isNot(contains('-$code@garbageapp')));
    }
    expect(ical, contains('8時30分まで'));
    expect(ical, contains('-burnable@garbageapp'));
    final categories = await data.categories(id, municipalityId: '38210');
    final notifications = await NotificationService.computeScheduleWindow(
      districtId: id,
      now: DateTime(2026, 11, 1),
      eveningTime: (hour: 20, minute: 0),
      morningTime: (hour: 8, minute: 29),
      eveningEnabledCategories: categories,
      morningEnabledCategories: categories,
      entriesForDate: schedule.getScheduleForDate,
    );
    expect(notifications, isNotEmpty);
    for (final entry in notifications) {
      for (final code in unknown) {
        expect(
            entry.body,
            isNot(contains(categories
                .firstWhere((c) => c.toJsonString() == code)
                .displayName)));
      }
    }
    final afterCutoff = await NotificationService.computeScheduleWindow(
      districtId: id,
      now: DateTime(2026, 11, 1),
      eveningTime: (hour: 20, minute: 0),
      morningTime: (hour: 8, minute: 30),
      eveningEnabledCategories: [],
      morningEnabledCategories: categories,
      entriesForDate: schedule.getScheduleForDate,
    );
    expect(afterCutoff, isEmpty);
  });

  test('Nakayama shared August cell does not create a fifth Monday paper date',
      () async {
    final schedule = ScheduleService(
        data: MunicipalityDataService(), municipalityId: '38210');
    final fourth = await schedule.getScheduleForDate(
        '38210-nakayama-sare', DateTime(2026, 8, 24));
    final fifth = await schedule.getScheduleForDate(
        '38210-nakayama-sare', DateTime(2026, 8, 31));
    expect(fourth.map((e) => e.category.toJsonString()), contains('paper'));
    expect(
        fifth.map((e) => e.category.toJsonString()), isNot(contains('paper')));
  });
}
