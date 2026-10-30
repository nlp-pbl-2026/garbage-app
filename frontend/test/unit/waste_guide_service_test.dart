import 'dart:convert';
import 'dart:typed_data';

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

  test('classify supports image-only input and omits image from retrieval',
      () async {
    final captured = <String, Map<String, dynamic>>{};
    final client = MockClient((request) async {
      captured[request.url.path] =
          jsonDecode(request.body) as Map<String, dynamic>;
      if (request.url.path.endsWith('/rewrite')) {
        return jsonResponse({'rewritten_query': '木製のいす'});
      }
      if (request.url.path.endsWith('/retrieve')) {
        return jsonResponse({'documents': []});
      }
      return jsonResponse({
        'status': 'unable_to_determine',
        'answer': '分類を確定できませんでした。',
        'follow_up_question': null,
        'rewritten_query': '木製のいす',
        'classification': null,
        'next_collection': null,
        'sources': [],
        'request_id': 'request-image-only',
      });
    });
    final service = WasteGuideService(client: client, baseUrl: 'http://test');
    final image = SearchImageInput(
      bytes: Uint8List.fromList([1, 2, 3]),
      mediaType: 'image/jpeg',
      fileName: 'chair.jpg',
    );

    await service.classify(query: '', region: region, image: image);

    expect(captured['/api/search/rewrite']?['query'], '');
    expect(
      captured['/api/search/rewrite']?['image'],
      {'media_type': 'image/jpeg', 'data_base64': 'AQID'},
    );
    expect(captured['/api/search/retrieve']!.containsKey('image'), isFalse);
    expect(
      captured['/api/search/decide']?['image'],
      {'media_type': 'image/jpeg', 'data_base64': 'AQID'},
    );
  });

  test('classify supports combined image and text input', () async {
    Map<String, dynamic>? rewriteBody;
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/rewrite')) {
        rewriteBody = jsonDecode(request.body) as Map<String, dynamic>;
        return jsonResponse({'rewritten_query': '汚れたプラスチック容器'});
      }
      if (request.url.path.endsWith('/retrieve')) {
        return jsonResponse({'documents': []});
      }
      return jsonResponse({
        'status': 'needs_clarification',
        'answer': null,
        'follow_up_question': '汚れは取り除けますか？',
        'rewritten_query': '汚れたプラスチック容器',
        'classification': null,
        'next_collection': null,
        'sources': [],
        'request_id': 'request-image-text',
      });
    });
    final service = WasteGuideService(client: client, baseUrl: 'http://test');

    await service.classify(
      query: '汚れています',
      region: region,
      image: SearchImageInput(
        bytes: Uint8List.fromList([4, 5, 6]),
        mediaType: 'image/png',
        fileName: 'container.png',
      ),
    );

    expect(rewriteBody?['query'], '汚れています');
    expect(rewriteBody?['image']['media_type'], 'image/png');
    expect(rewriteBody?['image']['data_base64'], 'BAUG');
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
