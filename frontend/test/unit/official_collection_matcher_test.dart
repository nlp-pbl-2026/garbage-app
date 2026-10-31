import '../helpers/municipality_assets.dart';
import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/gps_detection.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/official_collection_matcher.dart';

class MemoryAssetBundle extends CachingAssetBundle {
  MemoryAssetBundle(this.files);
  final Map<String, String> files;
  @override
  Future<ByteData> load(String key) async =>
      ByteData.sublistView(Uint8List.fromList(utf8.encode(files[key]!)));
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final data = MunicipalityDataService(
      bundle: MemoryAssetBundle(withMatsuyamaCatalog({
    'assets/data/municipality_registry.json': jsonEncode({
      'municipality_id': '38201',
      'version': 'test-v1',
      'collection_areas': [
        {'id': '38201-08', 'name': '清水'},
        {'id': '38201-ca-test', 'name': '試験地区'},
      ],
    }),
    'assets/data/municipality_addresses.json': jsonEncode({
      'municipality_id': '38201',
      'version': 'test-v1',
      'entries': [
        {'town': '清水町', 'lookup_town': '清水町', 'area_id': '38201-08'},
        {'town': '分割町(1)', 'lookup_town': '分割町', 'area_id': '38201-08'},
        {'town': '分割町(2)', 'lookup_town': '分割町', 'area_id': '38201-ca-test'},
      ],
    }),
  })));

  GeocodedAddress address(String town, {String city = '松山市'}) => GeocodedAddress(
    prefecture: '愛媛県', city: city, town: town, fullAddress: '$city$town');

  test('uses an exact official town with confirmation-ready area ID', () async {
    final matcher = OfficialCollectionMatcher(data: data);
    await matcher.loadChoumeiData();
    final result = matcher.matchDistrict(address('清水町'));
    expect(result.collectionAreaId, '38201-08');
  });

  test('split town remains multiple candidates', () async {
    final matcher = OfficialCollectionMatcher(data: data);
    await matcher.loadChoumeiData();
    expect(() => matcher.matchDistrict(address('分割町')), throwsA(isA<DistrictNotFoundException>()));
    expect(matcher.matchDistrictCandidates(address('分割町'))
        .map((item) => item.collectionAreaId).toSet(), {'38201-08', '38201-ca-test'});
  });

  test('unknown town and city are not guessed', () async {
    final matcher = OfficialCollectionMatcher(data: data);
    await matcher.loadChoumeiData();
    expect(() => matcher.matchDistrict(address('未知町')), throwsA(isA<DistrictNotFoundException>()));
    expect(() => matcher.matchDistrict(address('清水町', city: '今治市')),
        throwsA(isA<OutOfAreaException>()));
  });
}
