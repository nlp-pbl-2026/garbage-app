import '../helpers/municipality_assets.dart';
import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/multi_region_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/providers/settings_provider.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/notification_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _Bundle extends CachingAssetBundle {
  @override
  Future<ByteData> load(String key) async =>
      ByteData.sublistView(Uint8List.fromList(
          utf8.encode(jsonEncode(key.endsWith('municipality_catalog.json')
              ? matsuyamaCatalog()
              : {
                  'municipality_id': '38201',
                  'version': 'test-v1',
                  'collection_areas': [
                    {
                      'id': '38201-08',
                      'name': '清水',
                      'calendar_id': 'c',
                      'rule_profile_id': 'matsuyama_hojo'
                    },
                  ],
                  'legacy_district_candidates': {
                    'old-ambiguous': ['38201-08', 'other']
                  },
                }))));
}

class _Notifications extends NotificationService {
  final updated = <String>[];
  @override
  Future<void> updateDistrict(String districtId,
          {String municipalityId = '38201'}) async =>
      updated.add(districtId);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('removing active region does not activate an ambiguous legacy district', () async {
    final valid = RegionSetting(prefectureId: '38', prefectureName: '愛媛県',
      municipalityId: '38201', municipalityName: '松山市',
      districtId: '38201-08', districtName: '清水');
    final ambiguous = RegionSetting(prefectureId: '38', prefectureName: '愛媛県',
      municipalityId: '38201', municipalityName: '松山市',
      districtId: 'old-ambiguous', districtName: '旧地区');
    SharedPreferences.setMockInitialValues({
      'multi_region_migrated': true,
      'region_setting': jsonEncode(valid.toJson()),
      'saved_regions': jsonEncode([
        SavedRegion(id: 'home', label: '自宅', setting: valid, isActive: true).toJson(),
        SavedRegion(id: 'work', label: '職場', setting: ambiguous, isActive: false).toJson(),
      ]),
    });
    final data = MunicipalityDataService(bundle: _Bundle());
    final notifications = _Notifications();
    final container = ProviderContainer(overrides: [
      municipalityDataProvider.overrideWithValue(data),
      regionServiceProvider.overrideWithValue(RegionService(data: data)),
      notificationServiceProvider.overrideWithValue(notifications),
    ]);
    addTearDown(container.dispose);
    await container.read(regionSettingProvider.notifier).loadSetting();
    await container.read(multiRegionProvider.notifier).loadRegions();
    await container.read(multiRegionProvider.notifier).removeRegion('home');
    expect(container.read(regionSettingProvider).valueOrNull, isNull);
    expect((await SharedPreferences.getInstance()).getString('region_setting'), isNull);
    expect(notifications.updated.last, '');
    expect(container.read(multiRegionProvider).valueOrNull!.single.setting.districtId,
      'old-ambiguous');
    expect(container.read(multiRegionProvider).valueOrNull!.single.isActive, isFalse);
    expect(await container.read(multiRegionServiceProvider).getActiveRegion(), isNull);
  });

  test('removing active region skips an ambiguous legacy district', () async {
    RegionSetting setting(String id) => RegionSetting(prefectureId: '38', prefectureName: '愛媛県',
      municipalityId: '38201', municipalityName: '松山市', districtId: id, districtName: id);
    SharedPreferences.setMockInitialValues({
      'multi_region_migrated': true,
      'region_setting': jsonEncode(setting('38201-08').toJson()),
      'saved_regions': jsonEncode([
        SavedRegion(id: 'home', label: '自宅', setting: setting('38201-08'), isActive: true).toJson(),
        SavedRegion(id: 'old', label: '旧地区', setting: setting('old-ambiguous'), isActive: false).toJson(),
        SavedRegion(id: 'valid', label: '別地区', setting: setting('38201-08'), isActive: false).toJson(),
      ]),
    });
    final data = MunicipalityDataService(bundle: _Bundle());
    final notifications = _Notifications();
    final container = ProviderContainer(overrides: [
      municipalityDataProvider.overrideWithValue(data),
      regionServiceProvider.overrideWithValue(RegionService(data: data)),
      notificationServiceProvider.overrideWithValue(notifications),
    ]);
    addTearDown(container.dispose);
    await container.read(multiRegionProvider.notifier).loadRegions();
    await container.read(multiRegionProvider.notifier).removeRegion('home');
    expect((await container.read(multiRegionServiceProvider).getActiveRegion())?.id, 'valid');
    expect(container.read(regionSettingProvider).valueOrNull?.districtId, '38201-08');
    expect(notifications.updated.last, '38201-08');
  });
}
