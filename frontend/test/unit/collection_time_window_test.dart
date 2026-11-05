// Synthetic fixtures: no official data, platform plugins or network required.
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;
import '../helpers/municipality_assets.dart';

Map<String, String> assets() {
  final files = multiMunicipalityAssets();
  final catalog = jsonDecode(files['assets/data/municipality_catalog.json']!);
  final cats =
      catalog['municipalities'][0]['profiles']['nakajima']['categories'];
  cats.clear();
  cats['local'] = {
    'name': '地域時刻の収集物',
    'collection_type_id': 'local',
    'cutoff_status': 'unverified',
    'time_note': '搬出時刻は地域で確認してください。'
  };
  cats['known'] = {
    'name': '確認済み収集物',
    'collection_type_id': 'known',
    'start_time': '06:00',
    'cutoff': '08:00',
    'time_note': '当日の午前6時〜8時に出してください。'
  };
  files['assets/data/municipality_catalog.json'] = jsonEncode(catalog);
  final cal = jsonDecode(files['90001-calendar']!);
  cal['calendars']['same-calendar']['days'] = {
    '2026-11-02': ['known', 'local'],
    '2026-11-09': ['known', 'local']
  };
  files['90001-calendar'] = jsonEncode(cal);
  return files;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('unknown cutoff retains dates but next collection skips the current day',
      () async {
    final data = MunicipalityDataService(bundle: MunicipalityBundle(assets()));
    final schedule = ScheduleService(
        data: data,
        municipalityId: '90001',
        clock: () => DateTime(2026, 11, 2, 7));
    final cats = await data.categories('same-area', municipalityId: '90001');
    final local = cats.singleWhere((c) => c.id == 'local');
    expect(local.cutoffMinutes, isNull);
    expect(local.deadlineLabel, contains('地域で確認'));
    expect(cats.singleWhere((c) => c.id == 'known').startTime, '06:00');
    expect(
        (await schedule.getScheduleForDate('same-area', DateTime(2026, 11, 2)))
            .length,
        2);
    expect(await schedule.getNextCollectionDate('same-area', 'local'),
        DateTime(2026, 11, 9));
    expect(await schedule.getNextCollectionDate('same-area', 'known'),
        DateTime(2026, 11, 2));
  });

  test(
      'unknown cutoff has evening notice and all-day iCal, never a morning plan',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService(bundle: MunicipalityBundle(assets()));
    final schedule = ScheduleService(data: data, municipalityId: '90001');
    final cats = await data.categories('same-area', municipalityId: '90001');
    final plans = await NotificationService.computeScheduleWindow(
        districtId: 'same-area',
        municipalityId: '90001',
        now: DateTime(2026, 11, 1, 12),
        eveningTime: (hour: 20, minute: 0),
        morningTime: (hour: 7, minute: 0),
        eveningEnabledCategories: cats,
        morningEnabledCategories: cats,
        entriesForDate: schedule.getScheduleForDate);
    expect(plans.length, 2);
    expect(plans.singleWhere((p) => p.isEvening).body, contains('搬出時刻は地域で確認'));
    expect(plans.singleWhere((p) => !p.isEvening).body,
        isNot(contains('地域時刻の収集物')));
    final ical =
        await IcalExportService(schedule, now: () => DateTime(2026, 11, 1))
            .generateIcalString('same-area', months: 1);
    expect(ical, contains('DTSTART;VALUE=DATE:20261102'));
    expect(ical, contains('搬出時刻は地域で確認'));
    expect(ical, contains('午前6時〜8時'));
    expect(ical, isNot(contains('0時まで')));
  });

  for (final change in [
    {'time_note': ''},
    {'cutoff': '08:00'},
    {'cutoff_status': 'checked'}
  ]) {
    test('invalid explicit unknown cutoff fails closed: $change', () async {
      final files = assets();
      final catalog =
          jsonDecode(files['assets/data/municipality_catalog.json']!);
      catalog['municipalities'][0]['profiles']['nakajima']['categories']
              ['local']
          .addAll(change);
      files['assets/data/municipality_catalog.json'] = jsonEncode(catalog);
      final data = MunicipalityDataService(bundle: MunicipalityBundle(files));
      await expectLater(data.categories('same-area', municipalityId: '90001'),
          throwsFormatException);
    });
  }
}
