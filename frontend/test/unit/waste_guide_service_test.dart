import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/services/waste_guide_service.dart';

void main() {
  final region = RegionSetting(
    prefectureId: '38',
    prefectureName: '愛媛県',
    municipalityId: '38201',
    municipalityName: '松山市',
    districtId: '38201-08',
    districtName: '清水',
  );

  test('classify parses an answered response and sends region context',
      () async {
    Map<String, dynamic>? capturedBody;
    final client = MockClient((request) async {
      capturedBody = jsonDecode(request.body) as Map<String, dynamic>;
      return http.Response(
        jsonEncode({
          'status': 'answered',
          'answer': 'ペットボトルです。',
          'follow_up_question': null,
          'rewritten_query': 'ペットボトル',
          'classification': {
            'item_name': 'ペットボトル',
            'category_code': 'ペット',
            'category_name': 'ペットボトル',
            'disposal_instructions': 'すすいで出してください。',
            'confidence': 0.98,
          },
          'next_collection': {
            'date': '2026-09-02',
            'display_date': '2026年9月2日（水）',
            'collection_type': 'ペットボトル',
          },
          'sources': [],
        }),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final service = WasteGuideService(client: client, baseUrl: 'http://test');

    final result = await service.classify(query: 'これは何ごみ？', region: region);

    expect(result.status, 'answered');
    expect(result.classification?.categoryCode, 'ペット');
    expect(result.nextCollection?.date, '2026-09-02');
    expect(capturedBody?['municipality_id'], '38201');
    expect(capturedBody?['district_id'], '38201-08');
  });

  test('classify sends a single clarification exchange', () async {
    Map<String, dynamic>? capturedBody;
    final client = MockClient((request) async {
      capturedBody = jsonDecode(request.body) as Map<String, dynamic>;
      return http.Response(
        jsonEncode({
          'status': 'needs_clarification',
          'answer': null,
          'follow_up_question': '素材は何ですか？',
          'rewritten_query': '容器 素材不明',
          'classification': null,
          'next_collection': null,
          'sources': [],
        }),
        200,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });
    final service = WasteGuideService(client: client, baseUrl: 'http://test');

    final result = await service.classify(
      query: 'この容器',
      region: region,
      clarifications: const [
        {'question': '素材は何ですか？', 'answer': '紙です'},
      ],
    );

    expect(result.needsClarification, isTrue);
    expect((capturedBody?['clarifications'] as List).single['answer'], '紙です');
  });

  test('classify exposes backend detail on an error response', () async {
    final client = MockClient((_) async {
      return http.Response(
        jsonEncode({'detail': '現在は清水地区のみ対応しています。'}),
        422,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });
    final service = WasteGuideService(client: client, baseUrl: 'http://test');

    expect(
      () => service.classify(query: '傘', region: region),
      throwsA(
        isA<WasteGuideException>().having(
          (error) => error.message,
          'message',
          '現在は清水地区のみ対応しています。',
        ),
      ),
    );
  });
}
