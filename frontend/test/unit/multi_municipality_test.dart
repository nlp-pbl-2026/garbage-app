import 'dart:convert';
import 'package:flutter/material.dart' show Color, FlutterError;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/garbage_item.dart';
import 'package:garbage_app/models/garbage_category.dart';
import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/models/notification_timing_type.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/services/ical_export_service.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/notification_customization_service.dart';
import 'package:garbage_app/services/notification_navigation_handler.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/services/official_collection_matcher.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:garbage_app/services/schedule_service.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;
import '../helpers/municipality_assets.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Map<String, String> files;
  late MunicipalityDataService data;
  setUp(() {
    files = multiMunicipalityAssets();
    data = MunicipalityDataService(bundle: MunicipalityBundle(files));
    SharedPreferences.setMockInitialValues({});
  });
  ScheduleService schedule(String city, {DateTime? now}) => ScheduleService(
      municipalityId: city,
      data: data,
      clock: () => now ?? DateTime(2026, 11, 1));

  test('selection uses only catalog cities and municipality-scoped area IDs',
      () async {
    final service = RegionService(data: data);
    expect((await service.getMunicipalities('38')).map((m) => m.id),
        ['90001', '90002']);
    expect(await service.getDistricts('38201'), isEmpty);
    expect((await service.getDistricts('90002')).single.name, '試験町B地区');
    expect(await data.area('same-area', municipalityId: 'unknown'), isNull);
  });

  test(
      'saved region is validated within its own city without overwriting unknown settings',
      () async {
    final setting = RegionSetting(
        prefectureId: '38',
        prefectureName: '愛媛県',
        municipalityId: '90002',
        municipalityName: '試験町B',
        districtId: 'same-area',
        districtName: '試験町B地区');
    final service = RegionService(data: data);
    await service.saveRegionSetting(setting);
    expect((await service.getRegionSetting())?.municipalityId, '90002');
    final unknown = {...setting.toJson(), 'municipalityId': 'unknown'};
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('region_setting', jsonEncode(unknown));
    expect(await service.getRegionSetting(), isNull);
    expect(jsonDecode(prefs.getString('region_setting')!), unknown);
  });

  test(
      'stream names, colors and identities are regional even when IDs match Matsuyama',
      () async {
    final a =
        (await data.categories('same-area', municipalityId: '90001')).single;
    final b =
        (await data.categories('same-area', municipalityId: '90002')).single;
    expect(a.id, 'burnable');
    expect(a, isNot(GarbageCategory.burnable));
    expect(a, isNot(b));
    expect(CategoryColors.getLabel(a), '試験市A回収物');
    expect(CategoryColors.getColor(a), const Color(0xff112233));
    expect(CategoryColors.getLabel(b), '試験町B回収物');
  });

  test(
      'calendars share district IDs safely, respect minute cutoffs and validity',
      () async {
    expect((await schedule('90001').getNextCollection('same-area'))?.date,
        DateTime(2026, 11, 2));
    expect((await schedule('90002').getNextCollection('same-area'))?.date,
        DateTime(2026, 11, 3));
    expect(
        await schedule('90001', now: DateTime(2026, 11, 2, 8, 29))
            .getNextCollectionDate('same-area', 'burnable'),
        DateTime(2026, 11, 2));
    expect(
        await schedule('90001', now: DateTime(2026, 11, 2, 8, 30))
            .getNextCollection('same-area'),
        isNull);
    expect(await schedule('90002').getMonthlySchedule('same-area', 2027, 1),
        isEmpty);
  });

  for (final field in ['municipality_id', 'version', 'valid_to']) {
    test('calendar $field mismatch never supplies another city’s dates',
        () async {
      final calendar =
          jsonDecode(files['90002-calendar']!) as Map<String, dynamic>;
      calendar[field] = 'wrong';
      files['90002-calendar'] = jsonEncode(calendar);
      expect(await schedule('90002').getMonthlySchedule('same-area', 2026, 11),
          isEmpty);
    });
  }

  test(
      'unverified and unknown streams are not silently treated as Matsuyama categories',
      () async {
    final calendar =
        jsonDecode(files['90002-calendar']!) as Map<String, dynamic>;
    calendar['calendars']['same-calendar']['verification_status'] = 'pending';
    files['90002-calendar'] = jsonEncode(calendar);
    expect(await schedule('90002').getMonthlySchedule('same-area', 2026, 11),
        isEmpty);
    calendar['calendars']['same-calendar']['verification_status'] = 'checked';
    calendar['calendars']['same-calendar']['days']['2026-11-03'] = ['paper'];
    data = MunicipalityDataService(
        bundle: MunicipalityBundle(
            {...files, '90002-calendar': jsonEncode(calendar)}));
    expect(() => schedule('90002').getMonthlySchedule('same-area', 2026, 11),
        throwsFormatException);
  });

  test('missing registry or profile fails without a default city', () async {
    files.remove('90002-registry');
    expect(() => data.getAreas('90002'), throwsA(isA<FlutterError>()));
    final catalog = jsonDecode(files['assets/data/municipality_catalog.json']!);
    catalog['municipalities'][1]['profiles'] = {};
    files = multiMunicipalityAssets()
      ..['assets/data/municipality_catalog.json'] = jsonEncode(catalog);
    data = MunicipalityDataService(bundle: MunicipalityBundle(files));
    expect(() => data.categories('same-area', municipalityId: '90002'),
        throwsStateError);
  });

  test(
      'notification preferences isolate municipality/profile and retain legacy Matsuyama fallback',
      () async {
    final a =
        (await data.categories('same-area', municipalityId: '90001')).single;
    final b =
        (await data.categories('same-area', municipalityId: '90002')).single;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('notification_category_burnable_morning', false);
    await prefs.setBool('notification_category_recyclable_evening', false);
    final service = NotificationCustomizationService(prefs);
    expect(
        await service.getEnabledCategories(NotificationTimingType.morning,
            categories: [a, b]),
        [a, b]);
    await service.saveSetting(a, NotificationTimingType.morning, false);
    expect(
        await service.getEnabledCategories(NotificationTimingType.morning,
            categories: [a, b]),
        [b]);
    expect(
        await service.getEnabledCategories(NotificationTimingType.evening,
            categories: [GarbageCategory.paper]),
        isEmpty);
  });

  test(
      'iCal and notifications use the selected city’s names, minute deadline and payload',
      () async {
    tz_data.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Tokyo'));
    final categories =
        await data.categories('same-area', municipalityId: '90001');
    final service = schedule('90001');
    final ical =
        await IcalExportService(service, now: () => DateTime(2026, 11, 1))
            .generateIcalString('same-area', months: 1);
    expect(ical, contains('SUMMARY:試験市A回収物の日'));
    expect(ical, contains('8時30分まで'));
    expect(ical, contains('UID:90001-same-area-20261102-burnable@garbageapp'));
    expect(ical, isNot(contains('試験町B')));
    Future<List<PlannedNotification>> plan(int minute) =>
        NotificationService.computeScheduleWindow(
            districtId: 'same-area',
            municipalityId: '90001',
            now: DateTime(2026, 11, 1),
            eveningTime: (hour: 20, minute: 0),
            morningTime: (hour: 8, minute: minute),
            eveningEnabledCategories: categories,
            morningEnabledCategories: categories,
            entriesForDate: service.getScheduleForDate);
    final planned = await plan(29);
    expect(planned.length, 2);
    expect(planned.last.body, contains('試験市A回収物'));
    expect(jsonDecode(planned.last.payload)['municipality_id'], '90001');
    expect((await plan(30)).where((n) => !n.isEvening), isEmpty);
  });

  test(
      'old-city notification taps cannot select a date in a different municipality',
      () {
    final dates = <DateTime?>[];
    final handler = NotificationNavigationHandler(
        onNavigateToCollectionDay: dates.add,
        isCurrentRegion: (city, district) =>
            city == '90002' && district == 'same-area');
    void tap(String payload) => handler.onNotificationResponse(
        NotificationResponse(
            notificationResponseType:
                NotificationResponseType.selectedNotification,
            payload: payload));
    tap(jsonEncode({
      'date': '2026-11-02',
      'municipality_id': '90001',
      'district_id': 'same-area'
    }));
    tap('2026-11-02T00:00:00.000');
    expect(dates, isEmpty);
    tap(jsonEncode({
      'date': '2026-11-03',
      'municipality_id': '90002',
      'district_id': 'same-area'
    }));
    expect(dates, [DateTime(2026, 11, 3)]);
  });

  test(
      'official address matching scopes identical towns to the actual municipality',
      () async {
    final matcher = OfficialCollectionMatcher(data: data);
    await matcher.loadChoumeiData();
    final result = matcher.matchDistrict(const GeocodedAddress(
        prefecture: '愛媛県', city: '試験町B', town: '同名町', fullAddress: '試験町B同名町'));
    expect(result.region?.municipalityId, '90002');
    expect(result.region?.districtId, 'same-area');
    expect(
        () => matcher.matchDistrict(const GeocodedAddress(
            prefecture: '愛媛県',
            city: '松山市',
            town: '同名町',
            fullAddress: '松山市同名町')),
        throwsA(isA<OutOfAreaException>()));
  });

  test('municipality without an address table remains manual selection',
      () async {
    final catalog = jsonDecode(files['assets/data/municipality_catalog.json']!);
    catalog['municipalities'][1].remove('addresses_asset');
    files['assets/data/municipality_catalog.json'] = jsonEncode(catalog);
    final matcher = OfficialCollectionMatcher(data: data);
    await matcher.loadChoumeiData();
    expect(
        () => matcher.matchDistrict(const GeocodedAddress(
            prefecture: '愛媛県',
            city: '試験町B',
            town: '同名町',
            fullAddress: '試験町B同名町')),
        throwsA(isA<DistrictNotFoundException>()));
  });
  test('an invalid address table does not prevent matching another city', () async {
    final addresses = jsonDecode(files['90002-addresses']!);
    addresses['version'] = 'wrong-version';
    files['90002-addresses'] = jsonEncode(addresses);
    final matcher = OfficialCollectionMatcher(data: data);
    await matcher.loadChoumeiData();
    expect(matcher.matchDistrict(const GeocodedAddress(prefecture: '愛媛県', city: '試験市A',
        town: '同名町', fullAddress: '試験市A同名町')).region?.municipalityId, '90001');
    expect(() => matcher.matchDistrict(const GeocodedAddress(prefecture: '愛媛県', city: '試験町B',
        town: '同名町', fullAddress: '試験町B同名町')), throwsA(isA<DistrictNotFoundException>()));
  });

}
