import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/services/municipality_data_service.dart';
import 'package:garbage_app/services/waste_guide_service.dart';
import '../helpers/municipality_assets.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final version = List.filled(64, 'a').join();
  final region = RegionSetting(
      prefectureId: '38',
      prefectureName: '愛媛県',
      municipalityId: '90001',
      municipalityName: '試験市',
      districtId: 'test-area',
      districtName: '試験地区');

  test('downloaded manifest supplies the snapshot version', () async {
    final data = MunicipalityDataService(
        bundle: MunicipalityBundle({
      'assets/data/frontend_data_manifest.json':
          jsonEncode({'schema_version': 1, 'dataset_version': version}),
    }));
    expect(await data.snapshotVersion(), version);
  });

  test('invalid manifest is not treated as a legacy app', () async {
    final data = MunicipalityDataService(
        bundle: MunicipalityBundle({
      'assets/data/frontend_data_manifest.json':
          jsonEncode({'schema_version': 1, 'dataset_version': 'invalid'}),
    }));
    expect(data.snapshotVersion(), throwsFormatException);
  });

  test('older bundled apps without a manifest remain compatible', () async {
    final data = MunicipalityDataService(bundle: MunicipalityBundle({}));
    expect(await data.snapshotVersion(), isNull);
  });

  test('all three search steps send the same UI version', () async {
    final paths = <String>[];
    final service = WasteGuideService(
        baseUrl: 'http://test',
        dataVersion: () async => version,
        client: MockClient((request) async {
          paths.add(request.url.path);
          expect(jsonDecode(request.body)['ui_dataset_version'], version);
          final Object body = request.url.path.endsWith('rewrite')
              ? {'rewritten_query': '試験品'}
              : request.url.path.endsWith('retrieve')
                  ? {'documents': []}
                  : {
                      'status': 'needs_clarification',
                      'rewritten_query': '試験品',
                      'follow_up_question': '素材は何ですか？',
                      'sources': []
                    };
          return http.Response(jsonEncode(body), 200,
              headers: {'content-type': 'application/json'});
        }));
    expect(
        (await service.classify(query: '試験', region: region))
            .needsClarification,
        isTrue);
    expect(paths.length, 3);
  });

  test('version conflict stops the pipeline before subsequent steps', () async {
    var calls = 0;
    final service = WasteGuideService(
        baseUrl: 'http://test',
        dataVersion: () async => version,
        client: MockClient((request) async {
          calls++;
          return http.Response(
              jsonEncode({'detail': '画面とサーバーのデータ版が異なります。'}), 409,
              headers: {'content-type': 'application/json'});
        }));
    await expectLater(service.classify(query: '試験', region: region),
        throwsA(isA<WasteGuideException>()));
    expect(calls, 1);
  });
}
