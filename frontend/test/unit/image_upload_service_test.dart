import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker/image_picker.dart';
import 'package:garbage_app/services/image_upload_service.dart';

void main() {
  late File testImageFile;

  setUpAll(() {
    // テスト用の一時的な画像ファイルを作成
    testImageFile = File('test_upload_image.jpg');
    testImageFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]); // JPEG header
  });

  tearDownAll(() {
    if (testImageFile.existsSync()) {
      testImageFile.deleteSync();
    }
  });

  group('ImageUploadService.upload', () {
    test('アップロード成功時にImageUploadResponseを返す', () async {
      final mockClient = MockClient.streaming((request, bodyStream) async {
        expect(request.method, equals('POST'));
        expect(request.url.path, equals('/api/images/upload'));
        expect(request.headers['authorization'], equals('Bearer test-token'));

        // Consume the stream to avoid errors
        await bodyStream.drain<void>();

        return http.StreamedResponse(
          Stream.value(utf8.encode(jsonEncode({
            'id': 'image-123',
            'filename': 'photo.jpg',
          }))),
          201,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ImageUploadService(
        client: mockClient,
        baseUrl: 'http://localhost:8000',
      );

      final result = await service.upload(
        XFile(testImageFile.path),
        'test-token',
      );

      expect(result.imageId, equals('image-123'));
      expect(result.filename, equals('photo.jpg'));
    });

    test('サーバーエラー（5xx）時にImageUploadExceptionをスローする', () async {
      final mockClient = MockClient.streaming((request, bodyStream) async {
        await bodyStream.drain<void>();
        return http.StreamedResponse(
          Stream.value(utf8.encode(jsonEncode({'detail': 'Internal Server Error'}))),
          500,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ImageUploadService(
        client: mockClient,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () => service.upload(XFile(testImageFile.path), 'token'),
        throwsA(isA<ImageUploadException>().having(
          (e) => e.message,
          'message',
          'サーバーエラーが発生しました。しばらくしてから再試行してください',
        ).having(
          (e) => e.statusCode,
          'statusCode',
          500,
        )),
      );
    });

    test('クライアントエラー（400）時にサーバーのdetailメッセージを含む例外をスローする', () async {
      final mockClient = MockClient.streaming((request, bodyStream) async {
        await bodyStream.drain<void>();
        return http.StreamedResponse(
          Stream.value(utf8.encode(jsonEncode({'detail': 'サポートされていない画像形式です'}))),
          400,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ImageUploadService(
        client: mockClient,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () => service.upload(XFile(testImageFile.path), 'token'),
        throwsA(isA<ImageUploadException>().having(
          (e) => e.message,
          'message',
          'サポートされていない画像形式です',
        ).having(
          (e) => e.statusCode,
          'statusCode',
          400,
        )),
      );
    });

    test('認証エラー（401）時に例外をスローする', () async {
      final mockClient = MockClient.streaming((request, bodyStream) async {
        await bodyStream.drain<void>();
        return http.StreamedResponse(
          Stream.value(utf8.encode(jsonEncode({'detail': '認証が必要です'}))),
          401,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ImageUploadService(
        client: mockClient,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () => service.upload(XFile(testImageFile.path), 'token'),
        throwsA(isA<ImageUploadException>().having(
          (e) => e.statusCode,
          'statusCode',
          401,
        )),
      );
    });

    test('ネットワークエラー時にImageUploadExceptionをスローする', () async {
      final mockClient = MockClient.streaming((request, bodyStream) async {
        throw const SocketException('Connection refused');
      });

      final service = ImageUploadService(
        client: mockClient,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () => service.upload(XFile(testImageFile.path), 'token'),
        throwsA(isA<ImageUploadException>().having(
          (e) => e.message,
          'message',
          'アップロードに失敗しました。ネットワーク接続を確認してください',
        ).having(
          (e) => e.statusCode,
          'statusCode',
          isNull,
        )),
      );
    });

    test('ClientException時にネットワークエラーメッセージをスローする', () async {
      final mockClient = MockClient.streaming((request, bodyStream) async {
        throw http.ClientException('Connection reset');
      });

      final service = ImageUploadService(
        client: mockClient,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () => service.upload(XFile(testImageFile.path), 'token'),
        throwsA(isA<ImageUploadException>().having(
          (e) => e.message,
          'message',
          'アップロードに失敗しました。ネットワーク接続を確認してください',
        )),
      );
    });

    test('レスポンスボディがJSONでない場合もエラーを適切にハンドリングする', () async {
      final mockClient = MockClient.streaming((request, bodyStream) async {
        await bodyStream.drain<void>();
        return http.StreamedResponse(
          Stream.value(utf8.encode('Bad Gateway')),
          502,
        );
      });

      final service = ImageUploadService(
        client: mockClient,
        baseUrl: 'http://localhost:8000',
      );

      expect(
        () => service.upload(XFile(testImageFile.path), 'token'),
        throwsA(isA<ImageUploadException>().having(
          (e) => e.statusCode,
          'statusCode',
          502,
        )),
      );
    });
  });

  group('ImageUploadResponse.fromJson', () {
    test('正しいJSONからインスタンスを生成する', () {
      final json = {'id': 'abc-123', 'filename': 'image.png'};

      final response = ImageUploadResponse.fromJson(json);

      expect(response.imageId, equals('abc-123'));
      expect(response.filename, equals('image.png'));
    });
  });

  group('ImageUploadService コンストラクタ', () {
    test('カスタムbaseUrlを設定できる', () {
      final service = ImageUploadService(
        baseUrl: 'https://api.example.com',
      );

      expect(service, isNotNull);
    });

    test('デフォルトのbaseUrlはlocalhost:8000', () {
      final service = ImageUploadService();

      expect(service, isNotNull);
    });
  });
}
