// Explicit local checks against generated official assets. No API or OS calls.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/schedule_service.dart';

const assigned = <String, ({String name, int areas})>{
  '38207': (name: '大洲市', areas: 29),
  '38402': (name: '砥部町', areas: 7),
  '38506': (name: '愛南町', areas: 8),
  '38488': (name: '鬼北町', areas: 8),
  '38484': (name: '松野町', areas: 11),
  '38422': (name: '内子町', areas: 26),
  '38401': (name: '松前町', areas: 2),
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('all assigned municipalities and geographical area names are selectable',
      () async {
    final data = MunicipalityDataService();
    final municipalities = {
      for (final entry in await data.municipalities())
        entry['id'] as String: entry['name'] as String
    };
    for (final entry in assigned.entries) {
      expect(municipalities[entry.key], entry.value.name);
      final areas = await data.getAreas(entry.key);
      expect(areas.length, entry.value.areas, reason: entry.value.name);
      expect(areas.map((area) => area['id']).toSet().length, areas.length);
      expect(areas.every((area) => (area['name'] as String).trim().isNotEmpty),
          isTrue);
      expect(
          areas.every((area) =>
              !RegExp(r'calendar|\.pdf|未確認').hasMatch(area['name'] as String)),
          isTrue,
          reason: '${entry.value.name} must expose place names, not internals');
      final regionNames =
          (await RegionService(data: data).getDistricts(entry.key))
              .map((region) => region.name)
              .toList();
      expect(regionNames, areas.map((area) => area['name']).toList());
    }
  });

  test('calendar, iCal and category streams use each selected municipality',
      () async {
    final data = MunicipalityDataService();
    for (final entry in assigned.entries) {
      final municipalityId = entry.key;
      final registry = await data.registryFor(municipalityId);
      final area = (await data.getAreas(municipalityId)).first;
      final areaId = area['id'] as String;
      final profileId = area['rule_profile_id'] as String;
      final raw = await data.calendarFor(municipalityId, profileId);
      expect(raw['municipality_id'], municipalityId);
      expect(raw['version'], registry['version']);
      final calendar = (raw['calendars']
          as Map<String, dynamic>)[area['calendar_id']] as Map<String, dynamic>;
      expect(calendar['verification_status'], 'checked');
      final days = (calendar['days'] as Map<String, dynamic>);
      expect(days, isNotEmpty);
      final validFrom = DateTime.parse(registry['valid_from'] as String);
      final service = ScheduleService(
          data: data, municipalityId: municipalityId, clock: () => validFrom);
      final month = await service.getMonthlySchedule(
          areaId, validFrom.year, validFrom.month);
      expect(month, isNotEmpty, reason: entry.value.name);
      final categories =
          await data.categories(areaId, municipalityId: municipalityId);
      expect(categories, isNotEmpty);
      final iCal = await IcalExportService(service, now: () => validFrom)
          .generateIcalString(areaId, months: 12);
      expect(iCal, contains('BEGIN:VCALENDAR'));
      expect(iCal, contains('BEGIN:VEVENT'));
      expect(iCal, isNot(contains('null@garbageapp')));
      final validTo = DateTime.parse(registry['valid_to'] as String);
      final outside = DateTime(validTo.year, validTo.month + 1, 1);
      expect(
          await service.getMonthlySchedule(areaId, outside.year, outside.month),
          isEmpty,
          reason:
              '${entry.value.name} must not repeat beyond official validity');
    }
  });

  test('all assigned municipalities expose their own bulky-waste guidance',
      () async {
    final data = MunicipalityDataService();
    for (final entry in assigned.entries) {
      final area = (await data.getAreas(entry.key)).first;
      final profile =
          await data.profile(entry.key, area['rule_profile_id'] as String);
      final bulky = profile['bulky_waste'] as Map<String, dynamic>;
      expect(bulky['category_code'], isNotEmpty);
      final config =
          MunicipalityConfig.fromJson(bulky['config'] as Map<String, dynamic>);
      expect(config.municipalityId, entry.key);
      expect(config.municipalityName, entry.value.name);
      expect(config.informationUrl, startsWith('https://'));
      expect(config.steps, isNotEmpty);
    }
  });

  test('generated catalog and registry assets are committed metadata', () {
    final catalog = jsonDecode(
        File('assets/data/municipality_catalog.json').readAsStringSync());
    final ids = (catalog['municipalities'] as List)
        .map((entry) => entry['id'] as String)
        .toSet();
    expect(ids.containsAll(assigned.keys), isTrue);
    for (final id in assigned.keys) {
      expect(File('assets/data/municipality_${id}_registry.json').existsSync(),
          isTrue);
    }
  });
}
