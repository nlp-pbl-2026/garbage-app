import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/bulky_waste.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/providers/bulky_waste_provider.dart';
import 'package:garbage_app/providers/municipality_provider.dart';
import 'package:garbage_app/providers/region_provider.dart';
import 'package:garbage_app/repositories/bulky_waste_repository.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/region_service.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../helpers/municipality_assets.dart';

MunicipalityConfig config(String city) => MunicipalityConfig(municipalityId: city,
    municipalityName: '試験町B', collectionFrequency: '試験用の収集方式', receptionHours: '公式案内参照',
    collectionRules: '試験町Bの窓口へ確認', feeStructureType: FeeStructureType.fixed,
    applicationMethod: ApplicationMethod.phone, phoneNumber: '000-0000', steps: []);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late SharedPreferences prefs;
  late Map<String, String> files;
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    files = multiMunicipalityAssets();
    await prefs.setString('region_setting', jsonEncode(RegionSetting(prefectureId: '38', prefectureName: '愛媛県',
        municipalityId: '90002', municipalityName: '試験町B', districtId: 'same-area', districtName: '試験町B地区').toJson()));
  });

  Future<ProviderContainer> container(http.Client client) async {
    final data = MunicipalityDataService(bundle: MunicipalityBundle(files));
    final result = ProviderContainer(overrides: [
      municipalityDataProvider.overrideWithValue(data),
      regionServiceProvider.overrideWithValue(RegionService(data: data)),
      sharedPreferencesProvider.overrideWithValue(prefs), httpClientProvider.overrideWithValue(client),
    ]);
    addTearDown(result.dispose);
    await result.read(regionSettingProvider.notifier).loadSetting();
    return result;
  }

  test('a profile named nakajima in another city never receives Matsuyama’s guide or category', () async {
    final paths = <String>[];
    final scope = await container(MockClient((request) async {
      paths.add(request.url.path);
      return http.Response('{}', 404);
    }));
    expect(await scope.read(municipalityConfigProvider.future), isNull);
    expect(await scope.read(bulkyWasteItemsProvider(const BulkyWasteQuery(
        municipalityId: '90002', districtId: 'same-area')).future), isNull);
    expect(paths.any((path) => path.contains('38201')), isFalse);
    expect(paths.any((path) => path.contains('/api/search/items/')), isFalse);
  });

  test('explicit guide and category metadata select the city’s catalog without guessing', () async {
    final catalog = jsonDecode(files['assets/data/municipality_catalog.json']!);
    catalog['municipalities'][1]['profiles']['nakajima']['bulky_waste'] = {
      'category_code': 'carry', 'config': config('90002').toJson(),
    };
    files['assets/data/municipality_catalog.json'] = jsonEncode(catalog);
    final scope = await container(MockClient((request) async {
      expect(request.url.path, '/api/search/items/90002');
      expect(request.url.queryParameters['category'], 'carry');
      expect(request.url.queryParameters['district_id'], 'same-area');
      return http.Response(jsonEncode({'items': [], 'total_count': 0, 'municipality_name': '試験町B'}), 200,
          headers: {'content-type': 'application/json; charset=utf-8'});
    }));
    final guide = await scope.read(municipalityConfigProvider.future);
    expect(guide?.data.collectionRules, '試験町Bの窓口へ確認');
    expect(guide?.data.applicationMethod, ApplicationMethod.phone);
    expect((await scope.read(bulkyWasteItemsProvider(const BulkyWasteQuery(
        municipalityId: '90002', districtId: 'same-area')).future))?.data.municipalityName, '試験町B');
  });

  test('mismatched API configuration is neither shown nor cached for another city', () async {
    final repository = BulkyWasteRepository(prefs: prefs, client: MockClient((_) async =>
        http.Response(jsonEncode(config('38201').toJson()), 200)));
    expect(await repository.getMunicipalityConfig('90002'), isNull);
    expect(prefs.getString('bulky_waste_config_90002'), isNull);
  });
}
