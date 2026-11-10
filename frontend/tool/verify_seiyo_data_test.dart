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

  test('seventeen Seiyo areas and all generated dates match backend data',
      () async {
    final data = MunicipalityDataService();
    final municipality = await data.municipality('38214');
    expect(municipality?['name'], '西予市');

    final areas = await data.getAreas('38214');
    expect(areas.length, 17);
    expect(areas.map((a) => a['rule_profile_id']).toSet(),
        {'cutoff_0700', 'cutoff_0800'});
    final raw = jsonDecode(
      File('assets/data/municipality_38214_0_calendar.json')
          .readAsStringSync(),
    ) as Map<String, dynamic>;
    final service = ScheduleService(data: data, municipalityId: '38214');
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
    expect(checked, 3052);

    final names = (await RegionService(data: data).getDistricts('38214'))
        .map((district) => district.name)
        .toList();
    expect(names.length, 17);
    expect(names.any((name) => name.contains('38214-')), isFalse);
    expect(names, contains('明浜：俵津・渡江・狩浜・高山・宮野浦・田之浜'));
    expect(names, contains('城川：土居・高川'));
  });

  test('cutoffs, closures and operational first weeks are retained',
      () async {
    final data = MunicipalityDataService();
    final early = await data.categories('38214-03', municipalityId: '38214');
    final normal = await data.categories('38214-01', municipalityId: '38214');
    expect(early.where((category) => category.cutoffMinutes != null)
        .every((category) => category.cutoffMinutes == 420), isTrue);
    expect(normal.where((category) => category.cutoffMinutes != null)
        .every((category) => category.cutoffMinutes == 480), isTrue);

    final service = ScheduleService(data: data, municipalityId: '38214');
    expect(await service.getScheduleForDate('38214-01', DateTime(2027, 1, 2)),
        isEmpty);
    expect(
      (await service.getScheduleForDate('38214-01', DateTime(2027, 1, 9)))
          .map((entry) => entry.category.id)
          .toSet(),
      {'pet'},
    );
    expect(
      (await service.getScheduleForDate('38214-03', DateTime(2027, 1, 8)))
          .map((entry) => entry.category.id)
          .toSet(),
      {'bottles', 'burnable'},
    );
    expect(await service.getScheduleForDate('38214-12', DateTime(2026, 8, 15)),
        isEmpty);
  });

  test('bulky guidance and iCal use Seiyo data only', () async {
    final data = MunicipalityDataService();
    for (final profileId in ['cutoff_0700', 'cutoff_0800']) {
      final profile = await data.profile('38214', profileId);
      final config = MunicipalityConfig.fromJson(
        ((profile['bulky_waste'] as Map<String, dynamic>)['config']
            as Map<String, dynamic>),
      );
      expect(config.municipalityName, '西予市');
      expect(config.applicationMethod, ApplicationMethod.guideOnly);
      expect(config.informationUrl,
          'https://www.city.seiyo.ehime.jp/kakuka/seikatsu_fukushi/kankyo_eisei/gomi/calenda/index.html');
    }

    final ical = await IcalExportService(
      ScheduleService(data: data, municipalityId: '38214'),
      now: () => DateTime(2026, 4, 1),
    ).generateIcalString('38214-01', months: 1);
    expect(ical, contains('-burnable@garbageapp'));
    expect(ical, contains('-landfill@garbageapp'));
    expect(ical, isNot(contains('-bulky@garbageapp')));
    expect(ical, isNot(contains('-not_collected@garbageapp')));
  });
}
