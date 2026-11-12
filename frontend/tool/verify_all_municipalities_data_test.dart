// Requires installed official data; no network, model inference or OS plugins.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/models/garbage_item.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

String streamId(String city, String code) => city == '38201'
    ? GarbageCategoryExtension.fromString(code).toJsonString()
    : code;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final catalog = jsonDecode(
      File('assets/data/municipality_catalog.json').readAsStringSync());
  final cities =
      (catalog['municipalities'] as List).cast<Map<String, dynamic>>();

  test('twenty selectable cities retain the backend area IDs and profiles',
      () async {
    final data = MunicipalityDataService();
    final selected = await RegionService(data: data).getMunicipalities('38');
    expect(selected.length, 20);
    expect(
        selected.map((c) => c.id).toSet(), cities.map((c) => c['id']).toSet());
    var areas = 0;
    for (final city in cities) {
      final id = city['id'] as String;
      final backend =
          jsonDecode(File('../data/regions/catalog.json').readAsStringSync());
      final entry =
          (backend['municipalities'] as List).singleWhere((c) => c['id'] == id);
      final registry = jsonDecode(
          File('../data/regions/${entry['registry_path']}').readAsStringSync());
      final actual = await data.getAreas(id);
      expect(actual.map((a) => a['id']).toSet(),
          (registry['collection_areas'] as List).map((a) => a['id']).toSet());
      areas += actual.length;
      if (city['addresses_asset'] != null) {
        expect((await data.addressesFor(id))!['municipality_id'], id);
      }
    }
    expect(areas, 706);
  });

  for (final city in cities) {
    final id = city['id'] as String;
    test(
        '$id all calendar dates agree; expiry, notifications and iCal stay local',
        () async {
      tz_data.initializeTimeZones();
      tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
      final data = MunicipalityDataService();
      final registry = await data.registryFor(id);
      final start = DateTime.parse(registry['valid_from'] as String);
      final end = DateTime.parse(registry['valid_to'] as String);
      final schedule =
          ScheduleService(data: data, municipalityId: id, clock: () => start);
      final coveredProfiles = <String>{};
      for (final area in await data.getAreas(id)) {
        final areaId = area['id'] as String;
        final pid = area['rule_profile_id'] as String;
        final record =
            (await data.verifiedCalendar(areaId, municipalityId: id))!;
        final bundle = await data.calendarFor(id, pid);
        final days = record['days'] as Map<String, dynamic>;
        // Both clients must consume byte-equivalent common data, not separate rules.
        final backendCatalog =
            jsonDecode(File('../data/regions/catalog.json').readAsStringSync());
        final backendCity = (backendCatalog['municipalities'] as List)
            .singleWhere((c) => c['id'] == id);
        final backendBase = '../data/regions/${backendCity['registry_path']}'
            .replaceFirst(RegExp(r'/registry\.json$'), '');
        final sourcePath = id == '38201'
            ? 'generated/calendar-2026.json'
            : jsonDecode(File('$backendBase/registry.json').readAsStringSync())[
                'rule_profiles'][pid]['calendar_path'];
        expect(bundle,
            jsonDecode(File('$backendBase/$sourcePath').readAsStringSync()));
        for (var month = DateTime(start.year, start.month);
            !month.isAfter(end);
            month = DateTime(month.year, month.month + 1)) {
          final actual = await schedule.getMonthlySchedule(
              areaId, month.year, month.month);
          final expected = <DateTime, Set<String>>{};
          for (final entry in days.entries) {
            final day = DateTime.parse(entry.key);
            if (day.year != month.year || day.month != month.month) continue;
            final codes = (entry.value as List).cast<String>();
            if (codes.isNotEmpty) {
              expected[day] = codes.map((c) => streamId(id, c)).toSet();
            }
          }
          expect({
            for (final d in actual.entries)
              d.key: d.value.map((e) => e.category.id).toSet()
          }, expected, reason: '$id/$areaId/${month.year}-${month.month}');
        }
        expect(
            await schedule.getScheduleForDate(
                areaId, end.add(const Duration(days: 1))),
            isEmpty);
        if (!coveredProfiles.add(pid)) continue;
        final config = await data.profile(id, pid);
        if (config['bulky_waste'] != null) {
          final guide = MunicipalityConfig.fromJson((config['bulky_waste']
              as Map<String, dynamic>)['config'] as Map<String, dynamic>);
          expect(guide.municipalityId, id);
          expect(guide.collectionRules, isNotEmpty);
        } else {
          // Matsuyama keeps its existing repository-backed guide.
          expect(id, '38201');
        }
        final cats = await data.categories(areaId, municipalityId: id);
        final ical = await IcalExportService(schedule, now: () => start)
            .generateIcalString(areaId, months: 16);
        final events = ical.split('BEGIN:VEVENT').skip(1);
        for (final event in events) {
          final raw = RegExp(r'DTSTART;VALUE=DATE:(\d{8})')
              .firstMatch(event)!
              .group(1)!;
          final iso =
              '${raw.substring(0, 4)}-${raw.substring(4, 6)}-${raw.substring(6)}';
          final date = DateTime.parse(iso);
          expect(!date.isBefore(start) && !date.isAfter(end), isTrue);
          final allowed =
              (days[iso] as List).cast<String>().map((c) => streamId(id, c));
          expect(allowed.any((c) => event.contains('-$c@garbageapp')), isTrue);
        }
        final after = ScheduleService(
            data: data,
            municipalityId: id,
            clock: () => end.add(const Duration(days: 1)));
        final afterIcal = await IcalExportService(after,
                now: () => DateTime(end.year, end.month + 1))
            .generateIcalString(areaId);
        expect(afterIcal, isNot(contains('BEGIN:VEVENT')));
        final plans = await NotificationService.computeScheduleWindow(
          districtId: areaId,
          municipalityId: id,
          now: start,
          eveningTime: (hour: 20, minute: 0),
          morningTime: (hour: 6, minute: 0),
          eveningEnabledCategories: cats,
          morningEnabledCategories: cats,
          entriesForDate: schedule.getScheduleForDate,
        );
        for (final plan in plans) {
          final payload = jsonDecode(plan.payload) as Map<String, dynamic>;
          expect(payload['municipality_id'], id);
          expect(payload['district_id'], areaId);
          final iso = (payload['date'] as String).substring(0, 10);
          expect(days[iso], isNotNull);
          expect((days[iso] as List).isNotEmpty, isTrue);
        }
      }
      expect(coveredProfiles, (city['profiles'] as Map).keys.toSet());
    }, timeout: const Timeout(Duration(minutes: 3)));
  }
}
