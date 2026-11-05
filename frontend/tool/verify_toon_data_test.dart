// Explicit local integration checks against official generated assets, no API.
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
  test('32 areas and all 11680 dates agree with the backend source', () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38215');
    expect(areas.length, 32);
    final raw = jsonDecode(
        File('assets/data/municipality_38215_0_calendar.json')
            .readAsStringSync());
    final service = ScheduleService(data: data, municipalityId: '38215');
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days =
          raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      final cats = await data.categories(id, municipalityId: '38215');
      expect(cats.length,
          11); // 10 dated streams + unverified mercury instruments.
      for (final cat in cats) {
        final knownTime = area['rule_profile_id'] == 'kawauchi' ||
            ['burnable', 'paper'].contains(cat.id);
        expect(cat.cutoffMinutes, knownTime ? 480 : isNull);
      }
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
      final status =
          (await service.collectionStatuses(id))['mercury_instruments']!;
      expect(status.status, 'unverified');
      expect(status.message, contains('未確認'));
    }
    expect(checked, 11680);
    final names = (await RegionService(data: data).getDistricts('38215'))
        .map((d) => d.name)
        .toList();
    expect(names.toSet().length, 32);
    expect(names.any((n) => RegExp('tn-|未確認|カレンダー').hasMatch(n)), isFalse);
    expect(names.where((n) => n.contains('西岡')).length, 2);
    expect(names.where((n) => n.contains('田窪（')).length, 3);
  });

  test(
      'final Sunday labels, adjacent hidden text and stacked collection survive extraction',
      () async {
    final s = ScheduleService(municipalityId: '38215');
    expect(
        (await s.getScheduleForDate('38215-04', DateTime(2026, 4, 26)))
            .map((e) => e.category.id)
            .toSet(),
        {
          'batteries',
          'pet_bottles',
          'plastic_packaging',
          'non_burnable',
          'bulky'
        });
    expect(
        (await s.getScheduleForDate('38215-31', DateTime(2026, 7, 3)))
            .map((e) => e.category.id),
        contains('burnable'));
    expect(
        await s.getScheduleForDate('38215-31', DateTime(2026, 7, 4)), isEmpty);
  });

  test(
      'unknown times suppress morning only, mercury instruments never notify/export',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    for (final id in ['38215-01', '38215-30']) {
      final service = ScheduleService(data: data, municipalityId: '38215');
      final cats = await data.categories(id, municipalityId: '38215');
      var mornings = 0;
      var eveningsWithUnknownTime = 0;
      for (var now = DateTime(2026, 4, 1);
          now.isBefore(DateTime(2027, 4, 1));
          now = now.add(const Duration(days: 6))) {
        final plans = await NotificationService.computeScheduleWindow(
            districtId: id,
            municipalityId: '38215',
            now: now,
            eveningTime: (hour: 20, minute: 0),
            morningTime: (hour: 7, minute: 0),
            eveningEnabledCategories: cats,
            morningEnabledCategories: cats,
            entriesForDate: service.getScheduleForDate);
        for (final plan in plans) {
          expect(plan.body, isNot(contains('水銀使用の計測器')));
          if (!plan.isEvening) {
            mornings++;
            expect(plan.body, isNot(contains('地域で確認')));
          } else if (plan.body.contains('地域で確認')) {
            eveningsWithUnknownTime++;
          }
        }
      }
      expect(mornings, greaterThan(0));
      expect(eveningsWithUnknownTime, id == '38215-01' ? greaterThan(0) : 0);
      final ical =
          await IcalExportService(service, now: () => DateTime(2026, 4, 1))
              .generateIcalString(id, months: 12);
      expect(ical, isNot(contains('-mercury_instruments@garbageapp')));
      expect(
          ical,
          contains(
              '-bulky@garbageapp')); // Regular collection, not reservation.
      expect(ical, contains('午前6時〜8時'));
      expect(ical.contains('地域で確認'), id == '38215-01');
      expect(ical, isNot(contains('0時まで')));
    }
  });

  test('GPS returns all ambiguous town choices and never chooses a weekday',
      () async {
    final matcher = OfficialCollectionMatcher();
    await matcher.loadChoumeiData();
    GeocodedAddress addr(String town) => GeocodedAddress(
        prefecture: '愛媛県', city: '東温市', town: town, fullAddress: '愛媛県東温市$town');
    for (final entry in {'西岡': 2, '田窪': 3, '野田': 2}.entries) {
      expect(
          matcher.matchDistrictCandidates(addr(entry.key)).length, entry.value);
      expect(() => matcher.matchDistrict(addr(entry.key)),
          throwsA(isA<DistrictNotFoundException>()));
    }
    expect(matcher.matchDistrictCandidates(addr('不存在')), isEmpty);
    expect(matcher.matchDistrictCandidates(addr('河之内')).single.collectionAreaId,
        '38215-30');
  });

  test(
      'bulky guides are station collection, not application or facility carry-in',
      () async {
    final data = MunicipalityDataService();
    for (final key in ['shigenobu', 'kawauchi']) {
      final p = await data.profile('38215', key);
      final config = MunicipalityConfig.fromJson((p['bulky_waste']
          as Map<String, dynamic>)['config'] as Map<String, dynamic>);
      expect(config.applicationMethod, ApplicationMethod.none);
      expect(config.steps.first.description, contains('大人2人'));
      expect(config.steps.last.description, contains('粗大ごみを受け入れません'));
      expect(
          config.informationUrl, startsWith('https://www.city.toon.ehime.jp/'));
    }
  });
}
