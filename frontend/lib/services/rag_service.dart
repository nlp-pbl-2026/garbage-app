import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../constants/app_config.dart';
import '../models/region.dart';

/// RAGクエリの結果タイプ
enum RagErrorType {
  none,
  noResponse,
  validationError,
  timeout,
  serviceUnavailable,
  genericError,
  networkError,
}

/// RAGクエリの結果
class RagResult {
  final String? answer;
  final RagErrorType errorType;
  final int? statusCode;

  const RagResult.success(this.answer)
    : errorType = RagErrorType.none,
      statusCode = null;

  const RagResult.error(this.errorType, {this.statusCode}) : answer = null;
}

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
  RagService({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = baseUrl ?? AppConfig.apiBaseUrl;

  /// ユーザーメッセージを送信し、RAG回答を返す。
  ///
  /// [query] ユーザーの質問テキスト
  /// [region] 現在選択中の地域設定（nullの場合は地域情報なしで送信）
  ///
  /// 正常時は [RagResult.success] を返す。
  /// エラー時は [RagResult.error] を返す（例外はスローしない）。
  Future<RagResult> sendMessage(String query, {RegionSetting? region}) async {
    final uri = Uri.parse('$_baseUrl/api/rag/query');

    final body = <String, dynamic>{'query': query};

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
        final answer = data['answer'] as String?;
        if (answer == null || answer.isEmpty) {
          return const RagResult.error(RagErrorType.noResponse);
        }
        return RagResult.success(answer);
      } else if (response.statusCode == 422) {
        return const RagResult.error(
          RagErrorType.validationError,
          statusCode: 422,
        );
      } else if (response.statusCode == 504) {
        return const RagResult.error(RagErrorType.timeout, statusCode: 504);
      } else if (response.statusCode == 503) {
        return const RagResult.error(
          RagErrorType.serviceUnavailable,
          statusCode: 503,
        );
      } else {
        return RagResult.error(
          RagErrorType.genericError,
          statusCode: response.statusCode,
        );
      }
    } on SocketException {
      return const RagResult.error(RagErrorType.networkError);
    } on http.ClientException {
      return const RagResult.error(RagErrorType.networkError);
    } catch (e) {
      return const RagResult.error(RagErrorType.networkError);
    }
  }
}
