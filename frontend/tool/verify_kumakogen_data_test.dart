// Explicit official-asset integration checks; no external API or OS calls.
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
  test('23 named areas share 22 calendars and agree on all 8395 area dates',
      () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38386');
    expect(areas.length, 23);
    expect(areas.map((a) => a['calendar_id']).toSet().length, 22);
    final raw = jsonDecode(
        File('assets/data/municipality_38386_0_calendar.json')
            .readAsStringSync());
    final service = ScheduleService(data: data, municipalityId: '38386');
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days =
          raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      final categories = await data.categories(id, municipalityId: '38386');
      expect(categories.length, 13);
      expect(categories.every((c) => c.cutoffMinutes == 480), isTrue);
      expect(
          categories.any((c) => [
                'bulky',
                'direct_delivery',
                'consult',
                'not_collected'
              ].contains(c.id)),
          isFalse);
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
    expect(checked, 8395);
    final names = (await RegionService(data: data).getDistricts('38386'))
        .map((d) => d.name)
        .toList();
    expect(names.toSet().length, 23);
    expect(
        names.any((n) => RegExp(r'kk-|未確認|カレンダー|\.pdf').hasMatch(n)), isFalse);
    for (final prefix in ['久万：', '美川：', '面河：', '柳谷：']) {
      expect(names.any((n) => n.startsWith(prefix)), isTrue);
    }
    expect(names.where((n) => n.contains('国道沿線')).length, 2);
  });

  test('cross-month cells and PDF precedence preserve resource streams',
      () async {
    final service = ScheduleService(municipalityId: '38386');
    Future<Set<String>> codes(String area, DateTime date) async =>
        (await service.getScheduleForDate(area, date))
            .map((e) => e.category.id)
            .toSet();
    expect(await codes('38386-08', DateTime(2026, 7, 2)),
        containsAll(['plastic_packaging', 'cans']));
    expect(await codes('38386-08', DateTime(2026, 7, 2)),
        isNot(contains('paper')));
    expect(await codes('38386-14', DateTime(2026, 7, 1)), contains('cans'));
    expect(await codes('38386-20', DateTime(2026, 5, 1)), contains('cans'));
    expect(await codes('38386-07', DateTime(2026, 6, 24)), contains('paper'));
    expect(await codes('38386-07', DateTime(2026, 6, 17)),
        isNot(contains('paper')));
    expect(await codes('38386-01', DateTime(2026, 12, 30)),
        isNot(contains('burnable')));
    expect(await codes('38386-01', DateTime(2027, 1, 1)), isEmpty);
  });

  test('notifications and iCal exclude closure, bulky and facility delivery',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    final service = ScheduleService(data: data, municipalityId: '38386');
    final cats = await data.categories('38386-01', municipalityId: '38386');
    final plans = await NotificationService.computeScheduleWindow(
        districtId: '38386-01',
        municipalityId: '38386',
        now: DateTime(2026, 12, 28),
        eveningTime: (hour: 20, minute: 0),
        morningTime: (hour: 7, minute: 0),
        eveningEnabledCategories: cats,
        morningEnabledCategories: cats,
        entriesForDate: service.getScheduleForDate);
    expect(plans, isNotEmpty);
    for (final plan in plans) {
      expect(plan.body, isNot(contains('粗大')));
      expect(plan.body, isNot(contains('直接持ち込み')));
    }
    final ical =
        await IcalExportService(service, now: () => DateTime(2026, 4, 1))
            .generateIcalString('38386-01', months: 12);
    expect(ical, isNot(contains('-bulky@garbageapp')));
    expect(ical, isNot(contains('-direct_delivery@garbageapp')));
    expect(ical, contains('8時'));
    expect(ical, isNot(contains('DTSTART;VALUE=DATE:20270101')));
    expect(ical, isNot(contains('DTSTART;VALUE=DATE:20270401')));
  });

  test(
      'bulky guide refers to current application details without old deadlines',
      () async {
    final profile =
        await MunicipalityDataService().profile('38386', 'citywide');
    final config = MunicipalityConfig.fromJson((profile['bulky_waste']
        as Map<String, dynamic>)['config'] as Map<String, dynamic>);
    expect(config.applicationMethod, ApplicationMethod.guideOnly);
    expect(
        config.informationUrl, 'https://www.kumakogen.jp/soshiki/4/6870.html');
    expect(config.collectionRules, contains('受付期間'));
    expect(config.steps.last.description, contains('過去の募集期限は適用しません'));
  });

  test('GPS without verified station boundaries requires manual selection',
      () async {
    final matcher = OfficialCollectionMatcher();
    await matcher.loadChoumeiData();
    const address = GeocodedAddress(
        prefecture: '愛媛県',
        city: '久万高原町',
        town: '入野',
        fullAddress: '愛媛県久万高原町入野');
    expect(() => matcher.matchDistrictCandidates(address),
        throwsA(isA<DistrictNotFoundException>()));
    expect(() => matcher.matchDistrict(address),
        throwsA(isA<DistrictNotFoundException>()));
  });
}
