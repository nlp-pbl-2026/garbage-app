// Explicit checks of locally generated official assets; no cloud or OS calls.
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
      'all twenty municipalities and 123 Uwajima choices retain common calendars',
      () async {
    final data = MunicipalityDataService();
    final cities = await RegionService(data: data).getMunicipalities('38');
    expect(cities.length, 20);
    final areas = await data.getAreas('38203');
    expect(areas.length, 123);
    expect(areas.map((a) => a['calendar_id']).toSet().length, 56);
    final names = areas.map((a) => a['display_name']).toList();
    expect(names.toSet().length, 123);
    expect(names.any((n) => RegExp(r'uw-|\.pdf|カレンダー番号').hasMatch(n as String)),
        isFalse);
    final raw = jsonDecode(
        File('assets/data/municipality_38203_0_calendar.json')
            .readAsStringSync());
    final schedule = ScheduleService(data: data, municipalityId: '38203');
    var checked = 0;
    for (final area in areas) {
      final days =
          raw['calendars'][area['calendar_id']]['days'] as Map<String, dynamic>;
      for (var month = DateTime(2026, 4);
          month.isBefore(DateTime(2027, 4));
          month = DateTime(month.year, month.month + 1)) {
        final actual = await schedule.getMonthlySchedule(
            area['id'] as String, month.year, month.month);
        for (final entry in days.entries) {
          final date = DateTime.parse(entry.key);
          if (date.month != month.month || date.year != month.year) continue;
          expect((actual[date] ?? []).map((e) => e.category.id).toSet(),
              (entry.value as List).toSet(),
              reason: '${area['id']}/${entry.key}');
          checked++;
        }
      }
    }
    expect(checked, 44895);
    expect(await data.addressesFor('38203'), isNull);
  });
  test(
      'unknown date, month-end PET and exact resource transfer have distinct statuses',
      () async {
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38203');
    String id(String name) =>
        areas.firstWhere((a) => a['display_name'] == name)['id'] as String;
    final schedule = ScheduleService(
        data: data,
        municipalityId: '38203',
        clock: () => DateTime(2026, 9, 30, 7));
    final north = id('宇和島地区 → 北宇和島町');
    expect(await schedule.getNextCollectionDate(north, 'burnable'), isNull);
    expect((await schedule.collectionStatuses(north))['burnable']!.isUnverified,
        isTrue);
    final next = ScheduleService(
        data: data,
        municipalityId: '38203',
        clock: () => DateTime(2026, 10, 1, 7));
    expect(await next.getNextCollectionDate(north, 'burnable'), isNotNull);
    for (final name in ['戸島（本浦・美砂子・小内浦・嘉島）', '日振島（喜路・明海・能登）', '高光（平駄場）']) {
      final status = await schedule.collectionStatuses(id('宇和島地区 → $name'));
      expect(status['pet']!.isUnverified, isTrue);
    }
    final horibata = id('宇和島地区 → 堀端町');
    final transfer = ScheduleService(
        data: data,
        municipalityId: '38203',
        clock: () => DateTime(2026, 11, 18, 5));
    expect(await transfer.getNextCollectionDate(horibata, 'paper'),
        DateTime(2026, 11, 19));
    expect(
        (await transfer.getScheduleForDate(horibata, DateTime(2026, 11, 23)))
            .any((e) => e.category.id == 'paper'),
        isFalse);
  });
  test('no unverified/bulky/dropoff iCal events or morning boat-time alarms',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    final areas = await data.getAreas('38203');
    final island =
        areas.firstWhere((a) => (a['name'] as String).contains('戸島（'))['id']
            as String;
    final schedule = ScheduleService(
        data: data, municipalityId: '38203', clock: () => DateTime(2026, 4, 1));
    final ical =
        await IcalExportService(schedule, now: () => DateTime(2026, 4, 1))
            .generateIcalString(island, months: 12);
    for (final code in [
      'pet',
      'bulky',
      'clean_plastics',
      'dropoff',
      'batteries'
    ]) {
      expect(ical, isNot(contains('-$code@garbageapp')));
    }
    final cats = await data.categories(island, municipalityId: '38203');
    final plans = await NotificationService.computeScheduleWindow(
        districtId: island,
        municipalityId: '38203',
        now: DateTime(2026, 3, 31),
        eveningTime: (hour: 20, minute: 0),
        morningTime: (hour: 6, minute: 0),
        eveningEnabledCategories: cats,
        morningEnabledCategories: cats,
        entriesForDate: schedule.getScheduleForDate);
    expect(plans, isNotEmpty);
    expect(plans.every((p) => p.scheduledDate.hour == 20), isTrue);
    for (final pid in ['uwajima', 'yoshida', 'mima', 'tsushima']) {
      final profile = await data.profile('38203', pid);
      final bulky = MunicipalityConfig.fromJson((profile['bulky_waste']
          as Map<String, dynamic>)['config'] as Map<String, dynamic>);
      expect(bulky.applicationMethod, ApplicationMethod.guideOnly);
      expect(bulky.collectionRules, contains('直接搬入'));
    }
  });
}
