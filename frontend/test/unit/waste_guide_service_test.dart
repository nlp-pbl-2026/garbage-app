import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/services/waste_guide_service.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  final region = RegionSetting(
    prefectureId: '38',
    prefectureName: '愛媛県',
    municipalityId: '38201',
    municipalityName: '松山市',
    districtId: '38201-08',
    districtName: '清水',
  );

  http.Response jsonResponse(Object body, [int status = 200]) => http.Response(
        jsonEncode(body),
        status,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );

  test('classify runs the real three-stage pipeline in order', () async {
    final paths = <String>[];
    final stages = <SearchPipelineStage>[];
    Map<String, dynamic>? decisionBody;
    final client = MockClient((request) async {
      paths.add(request.url.path);
      switch (request.url.path) {
        case '/api/search/rewrite':
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body['municipality_id'], '38201');
          return jsonResponse({'rewritten_query': 'ペットボトル'});
        case '/api/search/retrieve':
          return jsonResponse({
            'documents': [
              {
                'title': '松山市ごみ分別資料',
                'snippet': 'ペットボトルの出し方',
                'score': 0.91,
              },
            ],
          });
        case '/api/search/decide':
          decisionBody = jsonDecode(request.body) as Map<String, dynamic>;
          return jsonResponse({
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
            'request_id': 'request-1',
          });
      }
      throw StateError('unexpected path: ${request.url.path}');
    });
    final service = WasteGuideService(client: client, baseUrl: 'http://test');

    final result = await service.classify(
      query: 'これは何ごみ？',
      region: region,
      onStageChanged: stages.add,
    );

    expect(paths, [
      '/api/search/rewrite',
      '/api/search/retrieve',
      '/api/search/decide',
    ]);
    expect(stages, SearchPipelineStage.values.skip(1).toList());
    expect(result.classification?.categoryCode, 'ペット');
    expect(result.nextCollection?.date, '2026-09-02');
    expect((decisionBody?['documents'] as List).single['score'], 0.91);
  });

  test('classify sends clarification through both AI stages', () async {
    final captured = <String, Map<String, dynamic>>{};
    final client = MockClient((request) async {
      captured[request.url.path] =
          jsonDecode(request.body) as Map<String, dynamic>;
      if (request.url.path.endsWith('/rewrite')) {
        return jsonResponse({'rewritten_query': '容器 紙'});
      }
      if (request.url.path.endsWith('/retrieve')) {
        return jsonResponse({'documents': []});
      }
      return jsonResponse({
        'status': 'needs_clarification',
        'answer': null,
        'follow_up_question': '汚れていますか？',
        'rewritten_query': '容器 紙',
        'classification': null,
        'next_collection': null,
        'sources': [],
        'request_id': 'request-2',
      });
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
    expect(
      (captured['/api/search/rewrite']?['clarifications'] as List)
          .single['answer'],
      '紙です',
    );
    expect(
      (captured['/api/search/decide']?['clarifications'] as List)
          .single['answer'],
      '紙です',
    );
  });

  test('classify exposes backend detail from any stage', () async {
    final client = MockClient(
        (_) async => jsonResponse({'detail': '現在は清水地区のみ対応しています。'}, 422));
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
