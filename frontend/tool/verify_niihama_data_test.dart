// Explicit local checks against generated official assets. No API or OS calls.
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
  test('all 15 groups consume exactly the same 5475 backend calendar dates',
      () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38205');
    expect(areas.length, 15);
    final raw = jsonDecode(
        File('assets/data/municipality_38205_0_calendar.json')
            .readAsStringSync());
    final service = ScheduleService(
        data: data, municipalityId: '38205', clock: () => DateTime(2026, 4, 1));
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days =
          raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      final cats = await data.categories(id, municipalityId: '38205');
      expect(cats.length, 8);
      expect(
          cats.every((c) => c.cutoffMinutes == (id == '38205-15' ? 540 : 450)),
          isTrue);
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
              reason: '$id / ${day.key}');
          checked++;
        }
      }
      expect(await service.getMonthlySchedule(id, 2027, 4), isEmpty);
    }
    expect(checked, 5475);
    final names = (await RegionService(data: data).getDistricts('38205'))
        .map((d) => d.name)
        .toList();
    expect(names.toSet().length, 15);
    expect(names.any((n) => RegExp('タイプ|曜|未確認').hasMatch(n)), isFalse);
    expect(names.where((n) => n.contains('宮西町')).length, 2);
    expect(names.any((n) => n.startsWith('市街地：') && n.contains('宮西町')), isTrue);
    expect(names.any((n) => n.startsWith('大島：') && n.contains('宮西町')), isTrue);
  });

  test('multiple streams, regional cutoff and facility-only days stay distinct',
      () async {
    final data = MunicipalityDataService();
    final service = ScheduleService(
        data: data,
        municipalityId: '38205',
        clock: () => DateTime(2026, 4, 2, 8));
    expect(
        (await service.getScheduleForDate('38205-13', DateTime(2026, 4, 4)))
            .map((e) => e.category.id)
            .toSet(),
        {'bottles_cans', 'paper', 'pet_bottles'});
    expect(
        (await service.getScheduleForDate('38205-13', DateTime(2026, 4, 15)))
            .map((e) => e.category.id)
            .toSet(),
        {'non_burnable', 'textiles'});
    expect(await service.getScheduleForDate('38205-01', DateTime(2026, 4, 12)),
        isEmpty);
    expect(await service.getScheduleForDate('38205-01', DateTime(2026, 4, 30)),
        isEmpty);
    expect(await service.getNextCollectionDate('38205-15', 'burnable'),
        DateTime(2026, 4, 2));
    final late = ScheduleService(
        data: data,
        municipalityId: '38205',
        clock: () => DateTime(2026, 4, 2, 9));
    expect(await late.getNextCollectionDate('38205-15', 'burnable'),
        DateTime(2026, 4, 6));
  });

  test(
      'iCal and notification plans exclude bulky, carry-in, holidays and closed dates',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    final service = ScheduleService(
        data: data, municipalityId: '38205', clock: () => DateTime(2026, 4, 1));
    for (final area in await data.getAreas('38205')) {
      final id = area['id'] as String;
      final cats = await data.categories(id, municipalityId: '38205');
      final ical =
          await IcalExportService(service, now: () => DateTime(2026, 4, 1))
              .generateIcalString(id, months: 12);
      expect(ical, contains(id == '38205-15' ? '9時まで' : '7時30分まで'));
      for (final code in [
        'bulky',
        'self_delivery',
        'not_collected',
        'consultation'
      ]) {
        expect(ical, isNot(contains('-$code@garbageapp')));
      }
      expect(ical, isNot(contains('DTSTART;VALUE=DATE:20270101')));
      final seen = <String>{};
      for (var now = DateTime(2026, 4, 1);
          now.isBefore(DateTime(2027, 4, 1));
          now = now.add(const Duration(days: 7))) {
        final plans = await NotificationService.computeScheduleWindow(
            districtId: id,
            municipalityId: '38205',
            now: now,
            eveningTime: (hour: 20, minute: 0),
            morningTime: (hour: 7, minute: 0),
            eveningEnabledCategories: cats,
            morningEnabledCategories: cats,
            entriesForDate: service.getScheduleForDate);
        for (final plan in plans) {
          expect(plan.body, isNot(contains('大型ごみ')));
          for (final cat in cats) {
            if (plan.body.contains(cat.displayName!)) seen.add(cat.id);
          }
        }
      }
      expect(seen, cats.map((c) => c.id).toSet());
      final after = await NotificationService.computeScheduleWindow(
          districtId: id,
          municipalityId: '38205',
          now: DateTime(2026, 11, 1),
          eveningTime: (hour: 20, minute: 0),
          morningTime: (hour: 9, minute: 0),
          eveningEnabledCategories: [],
          morningEnabledCategories: cats,
          entriesForDate: service.getScheduleForDate);
      expect(after, isEmpty);
    }
  });

  test(
      'official town candidates preserve road sides, chome ranges and same-named island',
      () async {
    final matcher = OfficialCollectionMatcher();
    await matcher.loadChoumeiData();
    GeocodedAddress addr(String town) => GeocodedAddress(
        prefecture: '愛媛県',
        city: '新居浜市',
        town: town,
        fullAddress: '愛媛県新居浜市$town');
    for (final town in ['萩生', '宮西町', '新須賀町', '宇高町']) {
      final choices = matcher.matchDistrictCandidates(addr(town));
      expect(choices.length, 2, reason: town);
      expect(choices.every((c) => c.region!.municipalityId == '38205'), isTrue);
      expect(() => matcher.matchDistrict(addr(town)),
          throwsA(isA<DistrictNotFoundException>()));
    }
    expect(matcher.matchDistrictCandidates(addr('不存在町')), isEmpty);
    expect(matcher.matchDistrictCandidates(addr('別子山')).single.collectionAreaId,
        '38205-15');
  });

  test('three guides retain official fee, appointment and carry-in conditions',
      () async {
    final data = MunicipalityDataService();
    for (final key in ['mainland', 'oshima', 'besshiyama']) {
      final p = await data.profile('38205', key);
      final config = MunicipalityConfig.fromJson((p['bulky_waste']
          as Map<String, dynamic>)['config'] as Map<String, dynamic>);
      expect(config.feeStructureType, FeeStructureType.fixed);
      expect(config.collectionFrequency, contains('200円'));
      expect(config.phoneNumber, '0897-31-5300');
      expect(config.applicationMethod, ApplicationMethod.both);
      expect(config.steps.last.description, contains('50kgまで500円'));
      expect(
          config.informationUrl, startsWith('https://www.city.niihama.lg.jp/'));
    }
  });
}
