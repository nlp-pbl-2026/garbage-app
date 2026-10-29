import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:garbage_app/repositories/bulky_waste_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('松山市の設定APIが404でも公式案内へフォールバックする', () async {
    final prefs = await SharedPreferences.getInstance();
    final repository = BulkyWasteRepository(
      client:
          MockClient((_) async => http.Response('{"detail":"Not Found"}', 404)),
      prefs: prefs,
      baseUrl: 'https://example.test',
    );

    final result = await repository.getMunicipalityConfig('38201');

    expect(result, isNotNull);
    expect(result!.isBundledFallback, isTrue);
    expect(result.isStale, isTrue);
    expect(result.data.municipalityName, '松山市');
    expect(result.data.collectionFrequency, contains('年6回'));
    expect(result.data.collectionRules, contains('午前8時'));
    expect(result.data.steps, hasLength(5));
    expect(result.data.webFormUrl, contains('city.matsuyama.ehime.jp'));
  });

  test('未対応自治体の404はデータなしとして扱う', () async {
    final prefs = await SharedPreferences.getInstance();
    final repository = BulkyWasteRepository(
      client:
          MockClient((_) async => http.Response('{"detail":"Not Found"}', 404)),
      prefs: prefs,
      baseUrl: 'https://example.test',
    );

    final result = await repository.getMunicipalityConfig('38202');

    expect(result, isNull);
  });

  test('APIが404なら過去のキャッシュより公式案内を優先する', () async {
    SharedPreferences.setMockInitialValues({
      'bulky_waste_config_38201': '''{
        "municipality_id":"38201",
        "municipality_name":"古い松山市データ",
        "collection_frequency":"月1回",
        "reception_hours":"古い受付時間",
        "collection_rules":"処理券を購入",
        "fee_structure_type":"fixed",
        "application_method":"both",
        "web_form_url":null,
        "phone_number":null,
        "steps":[]
      }''',
    });
    final prefs = await SharedPreferences.getInstance();
    final repository = BulkyWasteRepository(
      client:
          MockClient((_) async => http.Response('{"detail":"Not Found"}', 404)),
      prefs: prefs,
      baseUrl: 'https://example.test',
    );

    final result = await repository.getMunicipalityConfig('38201');

    expect(result, isNotNull);
    expect(result!.isBundledFallback, isTrue);
    expect(result.data.municipalityName, '松山市');
    expect(result.data.collectionRules, isNot(contains('処理券')));
  });

  test('APIの設定データを同梱フォールバックより優先する', () async {
    final prefs = await SharedPreferences.getInstance();
    final repository = BulkyWasteRepository(
      client: MockClient(
        (_) async => http.Response(
          '''{
            "municipality_id":"38201",
            "municipality_name":"API松山市",
            "collection_frequency":"API frequency",
            "reception_hours":"API hours",
            "collection_rules":"API rules",
            "fee_structure_type":"fixed",
            "application_method":"web_form",
            "web_form_url":"https://example.test/apply",
            "phone_number":null,
            "steps":[]
          }''',
          200,
          headers: {'content-type': 'application/json'},
        ),
      ),
      prefs: prefs,
      baseUrl: 'https://example.test',
    );

    final result = await repository.getMunicipalityConfig('38201');

    expect(result, isNotNull);
    expect(result!.isBundledFallback, isFalse);
    expect(result.isStale, isFalse);
    expect(result.data.municipalityName, 'API松山市');
  });

  test('従来APIが404ならあいまい検索と同じ品目一覧APIを使う', () async {
    final requestedPaths = <String>[];
    final prefs = await SharedPreferences.getInstance();
    final repository = BulkyWasteRepository(
      client: MockClient((request) async {
        requestedPaths.add(request.url.path);
        if (request.url.path.startsWith('/api/bulky-waste/items/')) {
          return http.Response('{"detail":"Not Found"}', 404);
        }
        return http.Response(
          '''{
            "items":[{
              "id":1,
              "item_name":"ソファ",
              "category":"粗大ごみ",
              "fee_amount":0,
              "size_category":null,
              "size_threshold_cm":null,
              "weight_category":null,
              "weight_threshold_kg":null,
              "notes":"大きさを確認"
            }],
            "total_count":1,
            "municipality_name":"松山市"
          }''',
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
      prefs: prefs,
      baseUrl: 'https://example.test',
    );

    final result = await repository.getItems('38201');

    expect(requestedPaths, [
      '/api/bulky-waste/items/38201',
      '/api/search/items/38201',
    ]);
    expect(result, isNotNull);
    expect(result!.data.items.single.itemName, 'ソファ');
    expect(result.data.items.single.feeAmount, 0);
    expect(result.isStale, isFalse);
  });
}
