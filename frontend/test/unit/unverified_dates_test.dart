import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;
import '../helpers/municipality_assets.dart';

Map<String, String> fixtures() {
  final files = multiMunicipalityAssets();
  final calendar = jsonDecode(files['90001-calendar']!);
  calendar['calendars']['same-calendar']['days'] = {
    '2026-11-02': ['burnable'],
    '2026-11-04': ['burnable']
  };
  calendar['calendars']['same-calendar']['unverified_dates'] = {
    'burnable': {
      '2026-11-03': {
        'message': '公式資料が一致しません',
        'source_url': 'https://example.test/calendar'
      }
    }
  };
  files['90001-calendar'] = jsonEncode(calendar);
  return files;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('uncertain next day does not erase later verified events or mix cities',
      () async {
    final data =
        MunicipalityDataService(bundle: MunicipalityBundle(fixtures()));
    final schedule = ScheduleService(
        data: data,
        municipalityId: '90001',
        clock: () => DateTime(2026, 11, 2, 9));
    expect(
        await schedule.getNextCollectionDate('same-area', 'burnable'), isNull);
    expect(
        (await schedule.collectionStatuses('same-area'))['burnable']!
            .isUnverified,
        isTrue);
    final month = await schedule.getMonthlySchedule('same-area', 2026, 11);
    expect(month.keys.toSet(), {DateTime(2026, 11, 2), DateTime(2026, 11, 4)});
    final later = ScheduleService(
        data: data,
        municipalityId: '90001',
        clock: () => DateTime(2026, 11, 3, 9));
    expect(await later.getNextCollectionDate('same-area', 'burnable'),
        DateTime(2026, 11, 4));
    final other = ScheduleService(
        data: data,
        municipalityId: '90002',
        clock: () => DateTime(2026, 11, 2, 9));
    expect(await other.getNextCollectionDate('same-area', 'burnable'),
        DateTime(2026, 11, 3));
    final day = await schedule.collectionStatuses('same-area',
        fromDate: DateTime(2026, 11, 3), toDate: DateTime(2026, 11, 3));
    expect(day['burnable']!.message, contains('2026-11-03'));
    final known = await schedule.collectionStatuses('same-area',
        fromDate: DateTime(2026, 11, 4), toDate: DateTime(2026, 11, 4));
    expect(known['burnable']!.isUnverified, isFalse);
  });
  test('notification and iCal keep known dates but omit the unknown day',
      () async {
    final data =
        MunicipalityDataService(bundle: MunicipalityBundle(fixtures()));
    final schedule = ScheduleService(
        data: data,
        municipalityId: '90001',
        clock: () => DateTime(2026, 11, 1));
    final ical =
        await IcalExportService(schedule, now: () => DateTime(2026, 11, 1))
            .generateIcalString('same-area', months: 1);
    expect(ical, contains('20261102'));
    expect(ical, contains('20261104'));
    expect(ical, isNot(contains('20261103')));
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final cats = await data.categories('same-area', municipalityId: '90001');
    final plans = await NotificationService.computeScheduleWindow(
        districtId: 'same-area',
        municipalityId: '90001',
        now: DateTime(2026, 11, 1),
        eveningTime: (hour: 20, minute: 0),
        morningTime: (hour: 7, minute: 0),
        eveningEnabledCategories: cats,
        morningEnabledCategories: cats,
        entriesForDate: schedule.getScheduleForDate);
    expect(plans, isNotEmpty);
    expect(plans.every((p) => !p.payload.startsWith('2026-11-03')), isTrue);
  });
  test('a verified event overlapping an unknown date is rejected', () async {
    final files = fixtures();
    final cal = jsonDecode(files['90001-calendar']!);
    cal['calendars']['same-calendar']['days']['2026-11-03'] = ['burnable'];
    files['90001-calendar'] = jsonEncode(cal);
    final data = MunicipalityDataService(bundle: MunicipalityBundle(files));
    expect(await data.verifiedCalendar('same-area', municipalityId: '90001'),
        isNull);
  });
}
