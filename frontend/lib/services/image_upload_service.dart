import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

/// 画像アップロードレスポンス
class ImageUploadResponse {
  final String imageId;
  final String filename;

  const ImageUploadResponse({
    required this.imageId,
    required this.filename,
  });

  factory ImageUploadResponse.fromJson(Map<String, dynamic> json) {
    return ImageUploadResponse(
      imageId: json['id'] as String,
      filename: json['filename'] as String,
    );
  }
}

/// 画像アップロード時の例外
class ImageUploadException implements Exception {
  final String message;
  final int? statusCode;

  const ImageUploadException(this.message, {this.statusCode});

  @override
  String toString() => 'ImageUploadException: $message (statusCode: $statusCode)';
}

/// 画像アップロードサービス
///
/// 画像ファイルをバックエンドの `/api/images/upload` エンドポイントに
/// マルチパートPOSTリクエストで送信する。
class ImageUploadService {
  final http.Client _client;
  final String _baseUrl;

  /// [ImageUploadService] を生成する。
  ///
  /// [client] を省略した場合はデフォルトの [http.Client] を使用する。
  /// テスト時にはモックを注入できる。
  /// [baseUrl] はAPIのベースURL（末尾スラッシュなし）。
  ImageUploadService({
    http.Client? client,
    String baseUrl = 'http://localhost:8000',
  })  : _client = client ?? http.Client(),
        _baseUrl = baseUrl;

  /// 画像ファイルをアップロードする。
  ///
  /// [imageFile] アップロードする画像ファイル（XFile）
  /// [authToken] 認証トークン（Bearer トークン）
  ///
  /// アップロードに成功した場合は [ImageUploadResponse] を返す。
  /// ネットワークエラーやサーバーエラーの場合は [ImageUploadException] をスローする。
  Future<ImageUploadResponse> upload(XFile imageFile, String authToken) async {
    final uri = Uri.parse('$_baseUrl/api/images/upload');

    try {
      final request = http.MultipartRequest('POST', uri);

      // 認証ヘッダーを設定
      request.headers['Authorization'] = 'Bearer $authToken';

      // マルチパートファイルを追加
      request.files.add(
        await http.MultipartFile.fromPath(
          'file',
          imageFile.path,
          filename: imageFile.name,
        ),
      );

      // リクエストを送信
      final streamedResponse = await _client.send(request);
      final response = await http.Response.fromStream(streamedResponse);

      // レスポンスのステータスコードをチェック
      if (response.statusCode == 201) {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        return ImageUploadResponse.fromJson(body);
      }

      // クライアントエラー（4xx）
      if (response.statusCode >= 400 && response.statusCode < 500) {
        final detail = _extractErrorDetail(response.body);
        throw ImageUploadException(
          detail,
          statusCode: response.statusCode,
        );
      }

      // サーバーエラー（5xx）
      throw ImageUploadException(
        'サーバーエラーが発生しました。しばらくしてから再試行してください',
        statusCode: response.statusCode,
      );
    } on ImageUploadException {
      rethrow;
    } on SocketException {
      throw const ImageUploadException(
        'アップロードに失敗しました。ネットワーク接続を確認してください',
      );
    } on http.ClientException {
      throw const ImageUploadException(
        'アップロードに失敗しました。ネットワーク接続を確認してください',
      );
    } catch (e) {
      throw ImageUploadException(
        'アップロードに失敗しました。ネットワーク接続を確認してください',
      );
    }
  }

  /// レスポンスボディからエラー詳細を抽出する。
  String _extractErrorDetail(String body) {
    try {
      final json = jsonDecode(body) as Map<String, dynamic>;
      return json['detail'] as String? ?? 'リクエストエラーが発生しました';
    } catch (_) {
      return 'リクエストエラーが発生しました';
    }
  }
}
