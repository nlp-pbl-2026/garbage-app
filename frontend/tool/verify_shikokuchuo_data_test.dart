// Explicit local integration checks against generated official assets, no API.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/schedule_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('twenty Shikokuchuo areas and generated dates match backend data',
      () async {
    final data = MunicipalityDataService();
    final municipality = await data.municipality('38213');
    expect(municipality?['name'], '四国中央市');

    final areas = await data.getAreas('38213');
    expect(areas.length, 20);
    expect(areas.map((a) => a['rule_profile_id']).toSet(),
        {'standard_0730', 'early_0700', 'mishima_0730'});
    final raw = jsonDecode(
      File('assets/data/municipality_38213_0_calendar.json')
          .readAsStringSync(),
    ) as Map<String, dynamic>;
    final service = ScheduleService(data: data, municipalityId: '38213');
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days = (raw['calendars'] as Map<String, dynamic>)[area['calendar_id']]
          ['days'] as Map<String, dynamic>;
      for (var month = DateTime(2026, 4);
          month.isBefore(DateTime(2027, 4));
          month = DateTime(month.year, month.month + 1)) {
        final actual =
            await service.getMonthlySchedule(id, month.year, month.month);
        for (final day in days.entries) {
          final date = DateTime.parse(day.key);
          if (date.year != month.year || date.month != month.month) continue;
          expect(
            (actual[date] ?? []).map((e) => e.category.id).toSet(),
            (day.value as List).cast<String>().toSet(),
            reason: '$id/${day.key}',
          );
          checked++;
        }
      }
      expect(await service.getMonthlySchedule(id, 2027, 4), isEmpty);
    }
    expect(checked, 3107);

    final names = (await RegionService(data: data).getDistricts('38213'))
        .map((district) => district.name)
        .toList();
    expect(names.length, 20);
    expect(names.any((name) => name.contains('38213-')), isFalse);
    expect(names, contains('川之江1・朝7時：天生津・宝洞山・石ノ口・切山'));
  });

  test('cutoffs, closures and Mishima festival collection are retained',
      () async {
    final data = MunicipalityDataService();
    final early = await data.categories('38213-02', municipalityId: '38213');
    final normal = await data.categories('38213-01', municipalityId: '38213');
    expect(early.every((category) => category.cutoffMinutes == 420), isTrue);
    expect(normal.every((category) => category.cutoffMinutes == 450), isTrue);

    final service = ScheduleService(data: data, municipalityId: '38213');
    expect(await service.getScheduleForDate('38213-01', DateTime(2026, 5, 2)),
        isEmpty);
    expect(
      (await service.getScheduleForDate('38213-10', DateTime(2026, 10, 14)))
          .map((entry) => entry.category.id)
          .toSet(),
      {'magazines', 'misc_paper'},
    );
    expect(
      (await service.getScheduleForDate('38213-10', DateTime(2026, 10, 15)))
          .map((entry) => entry.category.id)
          .toSet(),
      {'burnable'},
    );
    expect(await service.getScheduleForDate('38213-10', DateTime(2026, 10, 22)),
        isEmpty);
  });

  test('bulky guidance and iCal use Shikokuchuo data only', () async {
    final data = MunicipalityDataService();
    for (final profileId in
        ['standard_0730', 'early_0700', 'mishima_0730']) {
      final profile = await data.profile('38213', profileId);
      final config = MunicipalityConfig.fromJson(
        ((profile['bulky_waste'] as Map<String, dynamic>)['config']
            as Map<String, dynamic>),
      );
      expect(config.municipalityName, '四国中央市');
      expect(config.applicationMethod, ApplicationMethod.phone);
      expect(config.informationUrl,
          'https://www.city.shikokuchuo.ehime.jp/soshiki/15/1924.html');
    }

    final ical = await IcalExportService(
      ScheduleService(data: data, municipalityId: '38213'),
      now: () => DateTime(2026, 4, 1),
    ).generateIcalString('38213-01', months: 1);
    expect(ical, contains('-burnable@garbageapp'));
    expect(ical, contains('-misc_paper@garbageapp'));
    expect(ical, isNot(contains('-bulky@garbageapp')));
    expect(ical, isNot(contains('-not_collected@garbageapp')));
  });
}
