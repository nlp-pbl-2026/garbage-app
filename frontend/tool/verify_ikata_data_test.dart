// Explicit integration with generated official assets. No API or OS calls.
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/models/garbage_item.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('all eight Ikata groups consume the same 2920 reviewed backend dates',
      () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38442');
    expect(areas.length, 8);
    final raw = jsonDecode(
        File('assets/data/municipality_38442_0_calendar.json')
            .readAsStringSync());
    final service = ScheduleService(
        data: data, municipalityId: '38442', clock: () => DateTime(2026, 4, 1));
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days =
          raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      final categories = await data.categories(id, municipalityId: '38442');
      expect(categories.length, 9);
      expect(categories.every((c) => c.cutoffMinutes == 480), isTrue);
      expect(categories.map((c) => c.toJsonString()),
          containsAll(['styrofoam', 'paper_textiles']));
      for (var month = DateTime(2026, 4);
          month.isBefore(DateTime(2027, 4));
          month = DateTime(month.year, month.month + 1)) {
        final actual =
            await service.getMonthlySchedule(id, month.year, month.month);
        for (final day in days.entries) {
          final date = DateTime.parse(day.key);
          if (date.year != month.year || date.month != month.month) continue;
          expect(
              (actual[date] ?? [])
                  .map((e) => e.category.toJsonString())
                  .toSet(),
              (day.value as List).cast<String>().toSet(),
              reason: '$id / ${day.key}');
          checked++;
        }
      }
      expect(await service.getMonthlySchedule(id, 2027, 4), isEmpty);
    }
    expect(checked, 2920);
    final names = (await RegionService(data: data).getDistricts('38442'))
        .map((d) => d.name)
        .toList();
    expect(names.toSet().length, 8);
    expect(names.any((n) => RegExp('曜|未確認|A-|B-|C-|毎月').hasMatch(n)), isFalse);
    expect(names.where((n) => n.contains('高浦')).length, 2);
    expect(names.any((n) => n.startsWith('瀬戸地域') && n.contains('高浦')), isTrue);
    expect(names.any((n) => n.startsWith('三崎地域') && n.contains('高浦')), isTrue);
  });

  test(
      'year-end closures, weekend collections, cutoff and profile-specific paper days',
      () async {
    final data = MunicipalityDataService();
    final service = ScheduleService(
        data: data,
        municipalityId: '38442',
        clock: () => DateTime(2026, 11, 2, 7, 59));
    expect(await service.getNextCollectionDate('38442-01', 'burnable'),
        DateTime(2026, 11, 2));
    final later = ScheduleService(
        data: data,
        municipalityId: '38442',
        clock: () => DateTime(2026, 11, 2, 8));
    expect(await later.getNextCollectionDate('38442-01', 'burnable'),
        DateTime(2026, 11, 5));
    expect(
        (await service.getScheduleForDate('38442-03', DateTime(2026, 4, 4)))
            .single
            .category
            .toJsonString(),
        'burnable');
    expect(
        (await service.getScheduleForDate('38442-05', DateTime(2026, 4, 13)))
            .single
            .category
            .toJsonString(),
        'paper_textiles');
    expect(
        (await service.getScheduleForDate('38442-07', DateTime(2026, 4, 20)))
            .single
            .category
            .toJsonString(),
        'paper_textiles');
    for (final area in await data.getAreas('38442')) {
      for (final day in [1, 2, 3]) {
        expect(
            await service.getScheduleForDate(
                area['id'] as String, DateTime(2027, 1, day)),
            isEmpty);
      }
    }
  });

  test(
      'notifications and full-year iCal contain nine regular streams, never application-only bulky waste',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    final service = ScheduleService(
        data: data, municipalityId: '38442', clock: () => DateTime(2026, 4, 1));
    for (final area in await data.getAreas('38442')) {
      final id = area['id'] as String;
      final categories = await data.categories(id, municipalityId: '38442');
      final ical =
          await IcalExportService(service, now: () => DateTime(2026, 4, 1))
              .generateIcalString(id, months: 12);
      expect(ical, contains('8時まで'));
      expect(ical, isNot(contains('-bulky@garbageapp')));
      expect(ical, isNot(contains('-not_collected@garbageapp')));
      expect(ical, isNot(contains('DTSTART;VALUE=DATE:20270101')));
      final observed = <String>{};
      for (var now = DateTime(2026, 4, 1);
          now.isBefore(DateTime(2027, 4, 1));
          now = now.add(const Duration(days: 7))) {
        final plans = await NotificationService.computeScheduleWindow(
            districtId: id,
            municipalityId: '38442',
            now: now,
            eveningTime: (hour: 20, minute: 0),
            morningTime: (hour: 7, minute: 59),
            eveningEnabledCategories: categories,
            morningEnabledCategories: categories,
            entriesForDate: service.getScheduleForDate);
        for (final plan in plans) {
          expect(plan.body, isNot(contains('粗大ごみ')));
          expect(plan.body, isNot(contains('排出禁止')));
          for (final category in categories) {
            if (plan.body.contains(category.displayName!)) {
              observed.add(category.id);
            }
          }
        }
      }
      expect(observed, categories.map((c) => c.id).toSet());
      final after = await NotificationService.computeScheduleWindow(
          districtId: id,
          municipalityId: '38442',
          now: DateTime(2026, 11, 1),
          eveningTime: (hour: 20, minute: 0),
          morningTime: (hour: 8, minute: 0),
          eveningEnabledCategories: [],
          morningEnabledCategories: categories,
          entriesForDate: service.getScheduleForDate);
      expect(after, isEmpty);
    }
  });

  test(
      'three regional bulky guides preserve application and carry-in conditions',
      () async {
    final data = MunicipalityDataService();
    for (final profile in ['ikata', 'seto', 'misaki']) {
      final raw = (await data.profile('38442', profile))['bulky_waste']
          as Map<String, dynamic>;
      final config =
          MunicipalityConfig.fromJson(raw['config'] as Map<String, dynamic>);
      expect(config.municipalityId, '38442');
      expect(config.informationUrl,
          startsWith('https://www.town.ikata.ehime.jp/'));
      expect(config.collectionFrequency, contains('申込制'));
      expect(config.collectionRules, contains('記載がありません'));
      expect(config.steps.last.description, contains('可燃ごみ・禁止品は搬入できません'));
      expect(raw['category_code'], 'bulky');
    }
  });
}
