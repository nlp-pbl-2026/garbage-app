import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:garbage_app/models/region.dart';
import 'package:garbage_app/services/rag_service.dart';

void main() {
  RegionSetting createTestRegion() {
    return RegionSetting(
      prefectureId: '38',
      prefectureName: '愛媛県',
      municipalityId: '38201',
      municipalityName: '松山市',
      districtId: '38201-08',
      districtName: '清水',
    );
  }

  group('RagService.sendMessage', () {
    group('リクエストボディ構築', () {
      test('RegionSettingありの場合、地域情報がリクエストに含まれる', () async {
        Map<String, dynamic>? capturedBody;

        final mockClient = MockClient((request) async {
          capturedBody = jsonDecode(request.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({'answer': '回答テスト', 'sources': []}),
            200,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final region = createTestRegion();
        await service.sendMessage('テスト質問', region: region);

        expect(capturedBody, isNotNull);
        expect(capturedBody!['query'], equals('テスト質問'));
        expect(capturedBody!['municipality_id'], equals('38201'));
        expect(capturedBody!['municipality_name'], equals('松山市'));
        expect(capturedBody!['district_id'], equals('38201-08'));
        expect(capturedBody!['district_name'], equals('清水'));
      });

      test('RegionSettingなしの場合、queryのみがリクエストに含まれる', () async {
        Map<String, dynamic>? capturedBody;

        final mockClient = MockClient((request) async {
          capturedBody = jsonDecode(request.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({'answer': '回答テスト', 'sources': []}),
            200,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        await service.sendMessage('テスト質問');

        expect(capturedBody, isNotNull);
        expect(capturedBody!['query'], equals('テスト質問'));
        expect(capturedBody!.containsKey('municipality_id'), isFalse);
        expect(capturedBody!.containsKey('municipality_name'), isFalse);
        expect(capturedBody!.containsKey('district_id'), isFalse);
        expect(capturedBody!.containsKey('district_name'), isFalse);
      });

      test('リクエストURLが正しい', () async {
        Uri? capturedUri;

        final mockClient = MockClient((request) async {
          capturedUri = request.url;
          return http.Response(
            jsonEncode({'answer': '回答', 'sources': []}),
            200,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://myserver:9000',
        );

        await service.sendMessage('テスト');

        expect(capturedUri, isNotNull);
        expect(capturedUri!.toString(), equals('http://myserver:9000/api/rag/query'));
      });

      test('Content-Typeがapplication/jsonである', () async {
        String? capturedContentType;

        final mockClient = MockClient((request) async {
          capturedContentType = request.headers['content-type'];
          return http.Response(
            jsonEncode({'answer': '回答', 'sources': []}),
            200,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        await service.sendMessage('テスト');

        expect(capturedContentType, equals('application/json'));
      });
    });

    group('正常レスポンス', () {
      test('200レスポンスからanswerを取得する', () async {
        final mockClient = MockClient((request) async {
          return http.Response(
            jsonEncode({
              'answer': 'プラスチック製の植木鉢は可燃ごみです。',
              'sources': [
                {'title': 'ゴミ品目一覧', 'uri': 's3://bucket/items.csv', 'snippet': 'テキスト'}
              ],
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final result = await service.sendMessage('植木鉢は何ゴミ？');

        expect(result, equals('プラスチック製の植木鉢は可燃ごみです。'));
      });

      test('answerがnullの場合にフォールバックメッセージを返す', () async {
        final mockClient = MockClient((request) async {
          return http.Response(
            jsonEncode({'answer': null, 'sources': []}),
            200,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final result = await service.sendMessage('テスト');

        expect(result, contains('応答がありませんでした'));
      });
    });

    group('エラーハンドリング', () {
      test('422レスポンスで入力エラーメッセージを返す', () async {
        final mockClient = MockClient((request) async {
          return http.Response(
            jsonEncode({'detail': 'Validation error'}),
            422,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final result = await service.sendMessage('');

        expect(result, contains('質問を入力してください'));
      });

      test('503レスポンスで接続エラーメッセージを返す', () async {
        final mockClient = MockClient((request) async {
          return http.Response(
            jsonEncode({'detail': 'AI service unavailable'}),
            503,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final result = await service.sendMessage('テスト');

        expect(result, contains('接続できません'));
      });

      test('504レスポンスでタイムアウトメッセージを返す', () async {
        final mockClient = MockClient((request) async {
          return http.Response(
            jsonEncode({'detail': 'Timeout'}),
            504,
            headers: {'content-type': 'application/json'},
          );
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final result = await service.sendMessage('テスト');

        expect(result, contains('タイムアウト'));
      });

      test('SocketException時にネットワークエラーメッセージを返す', () async {
        final mockClient = MockClient((request) async {
          throw const SocketException('Connection refused');
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final result = await service.sendMessage('テスト');

        expect(result, contains('通信エラー'));
        expect(result, contains('インターネット接続'));
      });

      test('ClientException時にネットワークエラーメッセージを返す', () async {
        final mockClient = MockClient((request) async {
          throw http.ClientException('Connection closed');
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final result = await service.sendMessage('テスト');

        expect(result, contains('通信エラー'));
      });

      test('未知のステータスコードで汎用エラーメッセージを返す', () async {
        final mockClient = MockClient((request) async {
          return http.Response('Internal Server Error', 500);
        });

        final service = RagService(
          client: mockClient,
          baseUrl: 'http://test:8000',
        );

        final result = await service.sendMessage('テスト');

        expect(result, contains('エラーが発生しました'));
        expect(result, contains('500'));
      });
    });
  });
}
