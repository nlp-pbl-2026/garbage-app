import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../constants/app_config.dart';
import '../models/region.dart';
import '../models/waste_guide_result.dart';

class WasteGuideException implements Exception {
  final String message;

  const WasteGuideException(this.message);

  @override
  String toString() => message;
}

class WasteGuideService {
  final http.Client _client;
  final String _baseUrl;

  WasteGuideService({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? AppConfig.apiBaseUrl;

  Future<WasteGuideResult> classify({
    required String query,
    required RegionSetting region,
    List<Map<String, String>> clarifications = const [],
  }) async {
    final uri = Uri.parse('$_baseUrl/api/search/classify');
    late final http.Response response;
    try {
      response = await _client
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'query': query,
              'municipality_id': region.municipalityId,
              'municipality_name': region.municipalityName,
              'district_id': region.districtId,
              'district_name': region.districtName,
              'clarifications': clarifications,
            }),
          )
          .timeout(const Duration(seconds: 70));
    } on SocketException {
      throw const WasteGuideException('バックエンドに接続できません。起動状態を確認してください。');
    } on http.ClientException {
      throw const WasteGuideException('通信に失敗しました。接続状態を確認してください。');
    } on TimeoutException {
      throw const WasteGuideException('検索がタイムアウトしました。もう一度お試しください。');
    }

    late final Map<String, dynamic> decoded;
    try {
      decoded =
          jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    } on Object {
      throw const WasteGuideException('サーバーから不正な応答を受信しました。');
    }

    if (response.statusCode != 200) {
      final detail = decoded['detail'];
      throw WasteGuideException(
        detail is String && detail.isNotEmpty
            ? detail
            : '検索に失敗しました。もう一度お試しください。',
      );
    }

    try {
      return WasteGuideResult.fromJson(decoded);
    } on Object {
      throw const WasteGuideException('サーバーから不正な応答を受信しました。');
    }
  }
}
