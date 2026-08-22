import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../constants/app_config.dart';
import '../models/region.dart';

/// RAGクエリサービス
///
/// バックエンドの POST /api/rag/query エンドポイントに
/// ユーザーの質問と地域情報を送信し、AI回答を取得する。
class RagService {
  final http.Client _client;
  final String _baseUrl;

  /// [RagService] を生成する。
  ///
  /// [client] を省略した場合はデフォルトの [http.Client] を使用する。
  /// テスト時にはモックを注入できる。
  /// [baseUrl] を省略した場合は [AppConfig.apiBaseUrl] を使用する。
  RagService({
    http.Client? client,
    String? baseUrl,
  })  : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? AppConfig.apiBaseUrl;

  /// ユーザーメッセージを送信し、RAG回答テキストを返す。
  ///
  /// [query] ユーザーの質問テキスト
  /// [region] 現在選択中の地域設定（nullの場合は地域情報なしで送信）
  ///
  /// 正常時は回答テキストを返す。
  /// エラー時は日本語のエラーメッセージを返す（例外はスローしない）。
  Future<String> sendMessage(String query, {RegionSetting? region}) async {
    final uri = Uri.parse('$_baseUrl/api/rag/query');

    final body = <String, dynamic>{
      'query': query,
    };

    if (region != null) {
      body['municipality_id'] = region.municipalityId;
      body['municipality_name'] = region.municipalityName;
      body['district_id'] = region.districtId;
      body['district_name'] = region.districtName;
    }

    try {
      final response = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: json.encode(body),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body) as Map<String, dynamic>;
        return data['answer'] as String? ?? 'AIからの応答がありませんでした。';
      } else if (response.statusCode == 422) {
        return '質問を入力してください。';
      } else if (response.statusCode == 504) {
        return 'リクエストがタイムアウトしました。しばらくしてからお試しください。';
      } else if (response.statusCode == 503) {
        return 'AIサービスに接続できません。しばらくしてからお試しください。';
      } else {
        return 'エラーが発生しました（${response.statusCode}）。しばらくしてからお試しください。';
      }
    } on SocketException {
      return '通信エラーが発生しました。インターネット接続を確認してください。';
    } on http.ClientException {
      return '通信エラーが発生しました。インターネット接続を確認してください。';
    } catch (e) {
      return '通信エラーが発生しました。インターネット接続を確認してください。';
    }
  }
}
