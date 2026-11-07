// Explicit local integration checks against official generated assets, no API.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/official_collection_matcher.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/schedule_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('eight Kamijima areas and every generated date agree with backend data',
      () async {
    final data = MunicipalityDataService();
    final municipality = await data.municipality('38356');
    expect(municipality?['name'], '上島町');

    final areas = await data.getAreas('38356');
    expect(areas.length, 8);
    expect(areas.map((a) => a['rule_profile_id']).toSet(),
        {'main_islands', 'uoshima'});
    final raw = jsonDecode(
      File('assets/data/municipality_38356_0_calendar.json')
          .readAsStringSync(),
    ) as Map<String, dynamic>;
    final service = ScheduleService(data: data, municipalityId: '38356');
    var checked = 0;
    for (final area in areas) {
      final id = area['id'] as String;
      final days = (raw['calendars'] as Map<String, dynamic>)[area['calendar_id']]
          ['days'] as Map<String, dynamic>;
      final categories = await data.categories(id, municipalityId: '38356');
      expect(categories.length, 8);
      for (final category in categories) {
        if (id == '38356-08') {
          expect(category.startTime, '07:00');
          expect(category.cutoffMinutes, 600);
          expect(category.disposalTimeDescription, contains('午前7時から午前10時'));
        } else {
          expect(category.startTime, isNull);
          expect(category.cutoffMinutes, 480);
        }
      }
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
    expect(checked, 1493);

    final names = (await RegionService(data: data).getDistricts('38356'))
        .map((district) => district.name)
        .toList();
    expect(names.length, 8);
    expect(names.any((name) => name.contains('38356-')), isFalse);
    expect(names, contains('魚島地区（魚島クリーンセンター持込）'));
  });

  test('district-specific examples and Uoshima weekday reception are retained',
      () async {
    final schedule = ScheduleService(municipalityId: '38356');
    expect(
      (await schedule.getScheduleForDate('38356-01', DateTime(2026, 4, 1)))
          .map((entry) => entry.category.id)
          .toSet(),
      {'nonburnable'},
    );
    expect(
      (await schedule.getScheduleForDate('38356-02', DateTime(2026, 4, 6)))
          .map((entry) => entry.category.id)
          .toSet(),
      {'nonburnable'},
    );
    expect(
      (await schedule.getScheduleForDate('38356-04', DateTime(2026, 4, 2)))
          .map((entry) => entry.category.id)
          .toSet(),
      {'burnable', 'newspaper'},
    );
    expect(
      (await schedule.getScheduleForDate('38356-06', DateTime(2026, 4, 9)))
          .map((entry) => entry.category.id)
          .toSet(),
      {'burnable', 'newspaper'},
    );
    expect(
      (await schedule.getScheduleForDate('38356-08', DateTime(2026, 4, 6)))
          .map((entry) => entry.category.id)
          .toSet(),
      {
        'burnable',
        'nonburnable',
        'cans',
        'metals_hazardous',
        'newspaper',
        'cardboard',
        'magazines',
        'bulky',
      },
    );
    expect(
      await schedule.getScheduleForDate('38356-08', DateTime(2026, 4, 4)),
      isEmpty,
    );
  });

  test('official town matching keeps ambiguous Ootani choices for confirmation',
      () async {
    final matcher = OfficialCollectionMatcher();
    await matcher.loadChoumeiData();
    GeocodedAddress address(String town) => GeocodedAddress(
          prefecture: '愛媛県',
          city: '上島町',
          town: town,
          fullAddress: '愛媛県上島町$town',
        );

    expect(matcher.matchDistrictCandidates(address('久司浦')).single.collectionAreaId,
        '38356-01');
    expect(matcher.matchDistrictCandidates(address('大谷')).length, 2);
    expect(
      () => matcher.matchDistrict(address('大谷')),
      throwsA(isA<DistrictNotFoundException>()),
    );
    expect(matcher.matchDistrictCandidates(address('不存在')), isEmpty);
  });

  test('bulky guidance and iCal use the selected Kamijima profile', () async {
    final data = MunicipalityDataService();
    for (final profileId in ['main_islands', 'uoshima']) {
      final profile = await data.profile('38356', profileId);
      final config = MunicipalityConfig.fromJson(
        ((profile['bulky_waste'] as Map<String, dynamic>)['config']
            as Map<String, dynamic>),
      );
      expect(config.municipalityName, '上島町');
      expect(config.applicationMethod, ApplicationMethod.none);
      expect(config.informationUrl,
          'https://www.town.kamijima.lg.jp/soshiki/5/665.html');
    }

    final service = ScheduleService(data: data, municipalityId: '38356');
    final ical = await IcalExportService(
      service,
      now: () => DateTime(2026, 4, 1),
    ).generateIcalString('38356-08', months: 1);
    expect(ical, contains('-bulky@garbageapp'));
    expect(ical, contains('午前7時から午前10時'));
    expect(ical, isNot(contains('-not_collected@garbageapp')));
    expect(ical, isNot(contains('-landfill@garbageapp')));
  });
}
