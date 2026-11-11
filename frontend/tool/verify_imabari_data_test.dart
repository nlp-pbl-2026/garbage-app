// Explicit official-asset checks; no paid APIs, GPS or OS notifications.
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
  test('233 address selections share 44 calendars on all 85045 area dates',
      () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38202');
    final raw = jsonDecode(
        File('assets/data/municipality_38202_0_calendar.json')
            .readAsStringSync());
    expect(areas.length, 233);
    expect(areas.map((a) => a['calendar_id']).toSet().length, 44);
    final schedule = ScheduleService(data: data, municipalityId: '38202');
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days =
          raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      for (var month = DateTime(2026, 4);
          month.isBefore(DateTime(2027, 4));
          month = DateTime(month.year, month.month + 1)) {
        final actual =
            await schedule.getMonthlySchedule(id, month.year, month.month);
        for (final day in days.entries) {
          final date = DateTime.parse(day.key);
          if (date.month != month.month || date.year != month.year) continue;
          expect((actual[date] ?? []).map((e) => e.category.id).toSet(),
              (day.value as List).cast<String>().toSet(),
              reason: '$id/${day.key}');
          checked++;
        }
      }
      expect(await schedule.getMonthlySchedule(id, 2027, 4), isEmpty);
    }
    expect(checked, 85045);
  });

  test('address conditions and island names survive without internal numbers',
      () async {
    final data = MunicipalityDataService();
    final districts = await RegionService(data: data).getDistricts('38202');
    final names = districts.map((d) => d.name).toList();
    expect(names.toSet().length, 233);
    expect(
        names,
        containsAll(
            ['離島：馬島', '離島：来島・小島', '離島：宮窪町・鵜島', '関前：岡村', '関前：大下', '関前：小大下']));
    expect(names.any((n) => n.contains('国道196') && n.contains('山側')), isTrue);
    expect(names.any((n) => n.contains('枝堀町') && n.contains('枝番')), isTrue);
    expect(names.any((n) => n.contains('吉海町') && n.contains('津島除く')), isTrue);
    expect(names.any((n) => RegExp(r'im-|\.pdf|未確認|カレンダー番号').hasMatch(n)),
        isFalse);
    expect(await data.addressesFor('38202'), isNull);
  });

  test(
      'special holiday shifts, split cells and regional paper dates are retained',
      () async {
    final schedule = ScheduleService(municipalityId: '38202');
    expect(
        await schedule.getScheduleForDate('38202-a012', DateTime(2026, 4, 29)),
        isEmpty);
    expect(
        (await schedule.getScheduleForDate('38202-a012', DateTime(2026, 4, 30)))
            .map((e) => e.category.id)
            .toSet(),
        {'burnable', 'non_burnable'});
    expect(
        (await schedule.getScheduleForDate('38202-a210', DateTime(2026, 5, 5)))
            .map((e) => e.category.id)
            .toSet(),
        {'plastics', 'resources'});
    expect(
        await schedule.getScheduleForDate('38202-a210', DateTime(2026, 5, 6)),
        isEmpty);
    expect(
        await schedule.getScheduleForDate('38202-a119', DateTime(2027, 1, 1)),
        isEmpty);
    expect(
        (await schedule.getScheduleForDate('38202-a119', DateTime(2026, 4, 2)))
            .map((e) => e.category.id),
        contains('paper'));
    expect(
        (await schedule.getScheduleForDate('38202-a118', DateTime(2026, 4, 3)))
            .map((e) => e.category.id),
        contains('paper'));
  });

  test(
      'unknown ship deadline has no morning alarm and remains in iCal guidance',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    for (final id in ['38202-a012', '38202-a060']) {
      final schedule = ScheduleService(data: data, municipalityId: '38202');
      final cats = await data.categories(id, municipalityId: '38202');
      expect(cats.every((c) => c.cutoffMinutes == null), isTrue);
      final plans = await NotificationService.computeScheduleWindow(
          districtId: id,
          municipalityId: '38202',
          now: DateTime(2026, 3, 31),
          eveningTime: (hour: 20, minute: 0),
          morningTime: (hour: 6, minute: 0),
          eveningEnabledCategories: cats,
          morningEnabledCategories: cats,
          entriesForDate: schedule.getScheduleForDate);
      expect(plans, isNotEmpty);
      expect(plans.every((p) => p.scheduledDate.hour == 20), isTrue);
      expect(plans.every((p) => p.body.contains('出航時刻')), isTrue);
      final ical =
          await IcalExportService(schedule, now: () => DateTime(2026, 4, 1))
              .generateIcalString(id, months: 12);
      expect(ical, contains('出航時刻'));
      expect(ical, isNot(contains('-bulky@garbageapp')));
    }
  });

  test('bulky calendars and official application methods follow the region',
      () async {
    final data = MunicipalityDataService();
    for (final profile in [
      'mainland',
      'hatohama_islands',
      'ushima',
      'sekizen'
    ]) {
      final raw = await data.profile('38202', profile);
      final config = MunicipalityConfig.fromJson((raw['bulky_waste']
          as Map<String, dynamic>)['config'] as Map<String, dynamic>);
      expect(
          config.applicationMethod,
          profile == 'sekizen'
              ? ApplicationMethod.guideOnly
              : ApplicationMethod.phone);
      expect(
          config.phoneNumber,
          profile == 'sekizen'
              ? '0897-88-2111'
              : profile == 'ushima'
                  ? '0897-86-2500'
                  : '0898-47-5300');
      final area = (await data.getAreas('38202'))
          .firstWhere((a) => a['rule_profile_id'] == profile);
      final id = area['id'] as String;
      final ical = await IcalExportService(
          ScheduleService(data: data, municipalityId: '38202'),
          now: () => DateTime(2026, 4, 1)).generateIcalString(id, months: 12);
      expect(ical.contains('-bulky@garbageapp'), profile == 'sekizen');
    }
  });

  test('GPS does not assume address or collection-station boundaries',
      () async {
    final matcher = OfficialCollectionMatcher();
    await matcher.loadChoumeiData();
    const address = GeocodedAddress(
        prefecture: '愛媛県', city: '今治市', town: '枝堀町', fullAddress: '愛媛県今治市枝堀町');
    expect(() => matcher.matchDistrictCandidates(address),
        throwsA(isA<DistrictNotFoundException>()));
  });
}
