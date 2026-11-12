// Run in the downloaded workspace. No backend data, model API, or OS plugins.
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
      'downloaded snapshot resolves twenty cities without backend source files',
      () async {
    final manifest = jsonDecode(await rootBundle.loadString(
        'assets/data/frontend_data_manifest.json')) as Map<String, dynamic>;
    expect(manifest['dataset_version'], matches(RegExp(r'^[0-9a-f]{64}$')));
    final data = MunicipalityDataService();
    final cities = await data.municipalities();
    expect(cities.length, 20);
    var areas = 0;
    var addresses = 0;
    for (final city in cities) {
      final id = city['id'] as String;
      final current = await data.getAreas(id);
      areas += current.length;
      for (final area in current) {
        expect(
            await data.verifiedCalendar(area['id'] as String,
                municipalityId: id),
            isNotNull);
      }
      if (await data.addressesFor(id) != null) addresses++;
    }
    expect(areas, 706);
    expect(addresses, 6); // Other fourteen cities must keep manual selection.
  });

  test(
      'downloaded schedules, iCal and notification plans respect verified dates',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final data = MunicipalityDataService();
    for (final city in await data.municipalities()) {
      final id = city['id'] as String;
      final registry = await data.registryFor(id);
      final start = DateTime.parse(registry['valid_from'] as String);
      final end = DateTime.parse(registry['valid_to'] as String);
      final schedules =
          ScheduleService(data: data, municipalityId: id, clock: () => start);
      final profiles = <String>{};
      for (final area in await data.getAreas(id)) {
        if (!profiles.add(area['rule_profile_id'] as String)) continue;
        final district = area['id'] as String;
        final month = await schedules.getMonthlySchedule(
            district, start.year, start.month);
        for (final date in month.keys) {
          expect(!date.isBefore(start) && !date.isAfter(end), isTrue);
        }
        final ical = await IcalExportService(schedules, now: () => start)
            .generateIcalString(district, months: 1);
        expect(
            RegExp('BEGIN:VEVENT').allMatches(ical).length,
            month.values
                .fold<int>(0, (count, entries) => count + entries.length));
        final categories = await data.categories(district, municipalityId: id);
        final planned = await NotificationService.computeScheduleWindow(
          districtId: district,
          municipalityId: id,
          now: start,
          eveningTime: (hour: 20, minute: 0),
          morningTime: (hour: 6, minute: 0),
          eveningEnabledCategories: categories,
          morningEnabledCategories: categories,
          entriesForDate: schedules.getScheduleForDate,
        );
        expect(planned.every((p) => p.scheduledDate.isAfter(start)), isTrue);
        expect(
            await schedules.getScheduleForDate(
                district, end.add(const Duration(days: 1))),
            isEmpty);
      }
    }
  });
}
