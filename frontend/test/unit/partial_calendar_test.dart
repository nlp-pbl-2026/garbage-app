import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/waste_guide_result.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;
import '../helpers/municipality_assets.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('known dates survive while unverified dates cannot become iCal or notifications', () async {
    final data = MunicipalityDataService(bundle: MunicipalityBundle(partialMunicipalityAssets()));
    final schedule = ScheduleService(data: data, municipalityId: '90001', clock: () => DateTime(2026, 11, 1));
    final states = await schedule.collectionStatuses('same-area');
    expect(states['burnable']!.status, 'checked');
    expect(states.values.where((s) => s.isUnverified).length, 4);
    expect((await schedule.getNextCollection('same-area'))!.date, DateTime(2026, 11, 2));
    expect(await schedule.getNextCollectionDate('same-area', 'paper_a'), isNull);
    expect(await schedule.getScheduleForDate('same-area', DateTime(2026, 11, 3)), isEmpty);
    final ical = await IcalExportService(schedule, now: () => DateTime(2026, 11, 1)).generateIcalString('same-area', months: 1);
    expect(ical, contains('burnable@garbageapp'));
    expect(ical, isNot(contains('paper_a')));
    expect(ical, isNot(contains('20261103')));
    tz_data.initializeTimeZones(); tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final categories = await data.categories('same-area', municipalityId: '90001');
    final planned = await NotificationService.computeScheduleWindow(districtId: 'same-area', now: DateTime(2026, 11, 1),
      eveningTime: (hour: 20, minute: 0), morningTime: (hour: 7, minute: 0),
      eveningEnabledCategories: categories, morningEnabledCategories: categories, entriesForDate: schedule.getScheduleForDate);
    expect(planned, isNotEmpty);
    expect(planned.every((entry) => !entry.body.contains('未確認')), isTrue);
    expect(planned.every((entry) => !entry.payload.startsWith('2026-11-03')), isTrue);
  });

  test('partial verification requires explicit states for every collection stream', () async {
    final files = partialMunicipalityAssets();
    final calendar = jsonDecode(files['90001-calendar']!);
    (calendar['calendars']['same-calendar']['collection_type_verification'] as Map).remove('burnable');
    files['90001-calendar'] = jsonEncode(calendar);
    final data = MunicipalityDataService(bundle: MunicipalityBundle(files));
    expect(await data.verifiedCalendar('same-area', municipalityId: '90001'), isNull);
    final schedule = ScheduleService(data: data, municipalityId: '90001');
    expect(await schedule.getMonthlySchedule('same-area', 2026, 11), isEmpty);
  });

  test('API unknown status and no upcoming collection remain distinct', () {
    final base = {'status': 'answered', 'rewritten_query': '試験紙', 'next_collection': null};
    final unknown = WasteGuideResult.fromJson({...base, 'collection_status': {'status': 'unverified', 'message': '未確認', 'source_url': 'https://example.test/calendar.pdf'}});
    final empty = WasteGuideResult.fromJson({...base, 'collection_status': {'status': 'no_upcoming_collection'}});
    expect(unknown.collectionStatus!.isUnverified, isTrue);
    expect(empty.collectionStatus!.isUnverified, isFalse);
    expect(unknown.nextCollection, isNull);
    expect(WasteGuideResult.fromJson(base).collectionStatus, isNull); // Old API compatibility.
  });
}
