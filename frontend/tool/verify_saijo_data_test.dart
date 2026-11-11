// Official-asset integration tests; no network or OS notifications.
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/services/official_collection_matcher.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('39 areas and 25 calendars agree on all 14235 area dates', () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38206');
    expect(areas.length, 39);
    expect(areas.map((a) => a['calendar_id']).toSet().length, 25);
    final raw = jsonDecode(
        File('assets/data/municipality_38206_0_calendar.json')
            .readAsStringSync());
    final service = ScheduleService(data: data, municipalityId: '38206');
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days =
          raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      final categories = await data.categories(id, municipalityId: '38206');
      expect(categories.length, 7);
      expect(categories.every((c) => c.cutoffMinutes == 480), isTrue);
      for (var month = DateTime(2026, 4);
          month.isBefore(DateTime(2027, 4));
          month = DateTime(month.year, month.month + 1)) {
        final actual =
            await service.getMonthlySchedule(id, month.year, month.month);
        for (final day in days.entries) {
          final date = DateTime.parse(day.key);
          if (date.year != month.year || date.month != month.month) continue;
          expect((actual[date] ?? []).map((e) => e.category.id).toSet(),
              (day.value as List).cast<String>().toSet(),
              reason: '$id/${day.key}');
          checked++;
        }
      }
      expect(await service.getMonthlySchedule(id, 2027, 4), isEmpty);
    }
    expect(checked, 14235);
    final names = (await RegionService(data: data).getDistricts('38206'))
        .map((d) => d.name)
        .toList();
    expect(names.toSet().length, 39);
    for (final prefix in ['西条地域：', '東予地域：', '丹原地域：', '小松地域：']) {
      expect(names.any((n) => n.startsWith(prefix)), isTrue);
    }
    expect(
        names.any((n) => RegExp(r'sj-|未確認|カレンダー|\.pdf').hasMatch(n)), isFalse);
    expect(names, contains('丹原地域：徳田（古田新出・田滝を除く）地区'));
    expect(names, contains('東予地域：多賀（三津屋本通りまで）地区'));
  });

  test('as-needed resources never produce dates, notifications or iCal',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    final service = ScheduleService(data: data, municipalityId: '38206');
    for (final id in ['38206-02', '38206-03', '38206-05']) {
      final statuses = await service.collectionStatuses(id);
      for (final code in ['bottles', 'pet_bottles', 'spray_cans']) {
        expect(statuses[code]!.isUnverified, isTrue);
        expect(statuses[code]!.message, contains('随時'));
        expect(await service.getNextCollectionDate(id, code), isNull);
      }
      final cats = await data.categories(id, municipalityId: '38206');
      final plans = await NotificationService.computeScheduleWindow(
          districtId: id,
          municipalityId: '38206',
          now: DateTime(2026, 4, 1),
          eveningTime: (hour: 20, minute: 0),
          morningTime: (hour: 7, minute: 0),
          eveningEnabledCategories: cats,
          morningEnabledCategories: cats,
          entriesForDate: service.getScheduleForDate);
      expect(plans, isNotEmpty);
      for (final plan in plans) {
        expect(plan.body, isNot(contains('ペットボトル')));
        expect(plan.body, isNot(contains('ガラスびん')));
      }
      final ical =
          await IcalExportService(service, now: () => DateTime(2026, 4, 1))
              .generateIcalString(id, months: 12);
      for (final code in [
        'bottles',
        'pet_bottles',
        'spray_cans',
        'bulky',
        'drop_off',
        'direct_delivery'
      ]) {
        expect(ical, isNot(contains('-$code@garbageapp')));
      }
      expect(ical, contains('-burnable@garbageapp'));
      // There is no event to attach this notice to. The collection status,
      // rather than unrelated confirmed events, carries the as-needed notice.
    }
  });

  test('festival closures, multiple streams and year boundary are retained',
      () async {
    final data = MunicipalityDataService();
    final service = ScheduleService(data: data, municipalityId: '38206');
    for (final area in await data.getAreas('38206')) {
      final name = area['name'] as String;
      final id = area['id'] as String;
      if (name.startsWith('西条地域：') || name.startsWith('丹原地域：')) {
        for (final date in [DateTime(2026, 10, 15), DateTime(2026, 10, 16)]) {
          expect(await service.getScheduleForDate(id, date), isEmpty);
        }
      }
      expect(
          await service.getScheduleForDate(id, DateTime(2027, 1, 1)), isEmpty);
    }
    final area = (await data.getAreas('38206'))
        .singleWhere((a) => (a['name'] as String).contains('相之谷地区'));
    final entries = await service.getScheduleForDate(
        area['id'] as String, DateTime(2026, 4, 3));
    expect(entries.map((e) => e.category.id).toSet(), {
      'burnable',
      'non_burnable',
      'dry_batteries',
      'paper',
      'bottles',
      'pet_bottles',
      'spray_cans'
    });
  });

  test('bulky booking uses official telephone/web and tickets, not fixed dates',
      () async {
    final profile =
        await MunicipalityDataService().profile('38206', 'citywide');
    final config = MunicipalityConfig.fromJson((profile['bulky_waste']
        as Map<String, dynamic>)['config'] as Map<String, dynamic>);
    expect(config.applicationMethod, ApplicationMethod.both);
    expect(config.phoneNumber, '0897-66-7453');
    expect(config.webFormUrl, 'https://www.sodai-saijo.jp/');
    expect(config.steps[1].description, contains('1枚300円'));
    expect(config.collectionRules, contains('予約日の朝8時'));
  });

  test('GPS does not guess Saijo collection boundaries', () async {
    final matcher = OfficialCollectionMatcher();
    await matcher.loadChoumeiData();
    const address = GeocodedAddress(
        prefecture: '愛媛県', city: '西条市', town: '大町', fullAddress: '愛媛県西条市大町');
    expect(() => matcher.matchDistrictCandidates(address),
        throwsA(isA<DistrictNotFoundException>()));
  });
}
