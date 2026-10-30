import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/garbage_item.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:timezone/timezone.dart' as tz;
import 'package:timezone/data/latest_all.dart' as tz_data;

class MemoryAssetBundle extends CachingAssetBundle {
  MemoryAssetBundle(this.files);
  final Map<String, String> files;

  @override
  Future<ByteData> load(String key) async {
    final bytes = Uint8List.fromList(utf8.encode(files[key]!));
    return ByteData.sublistView(bytes);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final registry = jsonEncode({
    'version': 'test-v1', 'valid_from': '2026-04-01', 'valid_to': '2027-03-31',
    'collection_areas': [
      {'id': '38201-08', 'name': '清水', 'calendar_id': 'shared', 'rule_profile_id': 'matsuyama_hojo'},
      {'id': '38201-11', 'name': '試験', 'calendar_id': 'shared', 'rule_profile_id': 'matsuyama_hojo'},
    ],
    'legacy_district_candidates': {'old-ambiguous': ['38201-08', '38201-11']},
  });
  final calendar = jsonEncode({
    'version': 'test-v1', 'valid_from': '2026-04-01', 'valid_to': '2027-03-31',
    'calendars': {'shared': {
      'verification_status': 'checked',
      'days': {
        '2026-10-30': ['combustible', 'paper'],
        '2026-11-06': ['combustible'],
        '2027-03-31': ['mercury'],
      },
    }},
  });

  MunicipalityDataService data() => MunicipalityDataService(bundle: MemoryAssetBundle({
    'assets/data/municipality_registry.json': registry,
    'assets/data/municipality_calendar.json': calendar,
  }));

  test('shared calendar, same-day categories, and 7/8 o’clock cutoff', () async {
    final service = ScheduleService(data: data(),
        clock: () => DateTime(2026, 10, 30, 7, 30));
    final today = await service.getScheduleForDate('38201-08', DateTime(2026, 10, 30));
    expect(today.map((entry) => entry.category),
        containsAll([GarbageCategory.burnable, GarbageCategory.paper]));
    expect((await service.getNextCollection('38201-08'))?.category, GarbageCategory.paper);
    expect((await service.getNextCollection('38201-11'))?.date, DateTime(2026, 10, 30));
    expect(await service.getNextCollectionDate('38201-08', 'burnable'), DateTime(2026, 11, 6));
    expect(await service.getNextCollectionDate('38201-08', 'paper'), DateTime(2026, 10, 30));
  });

  test('ambiguous legacy ID never selects a calendar', () async {
    expect(await data().area('old-ambiguous'), isNull);
    expect(await ScheduleService(data: data()).getMonthlySchedule('old-ambiguous', 2026, 10), isEmpty);
  });

  test('no extrapolation beyond the official fiscal year', () async {
    final service = ScheduleService(data: data(), clock: () => DateTime(2027, 4, 1, 6));
    expect(await service.getNextCollection('38201-08'), isNull);
    expect(await service.getMonthlySchedule('38201-08', 2027, 4), isEmpty);
  });

  test('iCal and notifications use the same explicit collection entries', () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final schedule = ScheduleService(data: data(),
        clock: () => DateTime(2026, 10, 29, 12));
    final ical = await IcalExportService(schedule,
        now: () => DateTime(2026, 10, 29, 12)).generateIcalString('38201-08', months: 1);
    expect(ical, contains('DTSTART;VALUE=DATE:20261030'));
    expect(ical, contains('UID:38201-08-20261030-burnable@garbageapp'));
    expect(ical, contains('UID:38201-08-20261030-paper@garbageapp'));
    expect(ical, contains('可燃ごみの収集日です。7時まで'));
    expect(ical, contains('紙類の収集日です。8時まで'));
    final notifications = await NotificationService.computeScheduleWindow(
      districtId: '38201-08', now: DateTime(2026, 10, 29, 12),
      eveningTime: (hour: 20, minute: 0), morningTime: (hour: 7, minute: 0),
      eveningEnabledCategories: [GarbageCategory.burnable, GarbageCategory.paper],
      morningEnabledCategories: [GarbageCategory.burnable, GarbageCategory.paper],
      entriesForDate: schedule.getScheduleForDate,
    );
    expect(notifications.where((entry) => entry.payload.startsWith('2026-10-30')).length, 2);
    final morning = notifications.singleWhere((entry) => !entry.isEvening);
    expect(morning.body, contains('紙類'));
    expect(morning.body, isNot(contains('可燃')));
  });
}
