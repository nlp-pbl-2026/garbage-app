import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/app_config.dart';

/// Gemini API を使ったチャットサービス
///
/// ゴミ分別に特化したシステムプロンプトを使い、
/// ユーザーの質問に対してAI応答を返す。
class GeminiService {
  GeminiService();

  static const String _baseUrl =
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent';

  static const String _systemPrompt =
      'あなたは愛媛県のゴミ出しアプリのAIアシスタントです。ゴミの分別方法、収集日、出し方、アプリの使い方など、ユーザーの質問に日本語で簡潔に回答してください。わからない場合は「お住まいの市役所にお問い合わせください」と案内してください。';

  /// ユーザーメッセージを送信し、AIの応答テキストを返す
  ///
  /// エラー時は日本語のエラーメッセージを返す。
  Future<String> sendMessage(String userMessage) async {
    final url = Uri.parse('$_baseUrl?key=${AppConfig.geminiApiKey}');

    final body = jsonEncode({
      'contents': [
        {
          'role': 'user',
          'parts': [
            {'text': userMessage}
          ]
        }
      ],
      'systemInstruction': {
        'parts': [
          {'text': _systemPrompt}
        ]
      }
    });

    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: body,
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final candidates = data['candidates'] as List<dynamic>?;
        if (candidates != null && candidates.isNotEmpty) {
          final content =
              candidates[0]['content'] as Map<String, dynamic>?;
          final parts = content?['parts'] as List<dynamic>?;
          if (parts != null && parts.isNotEmpty) {
            return parts[0]['text'] as String? ?? 'AIからの応答がありませんでした。';
          }
        }
        return 'AIからの応答を解析できませんでした。';
      } else if (response.statusCode == 429) {
        return 'リクエストが多すぎます。少し時間を置いてからもう一度お試しください。';
      } else {
        return 'エラーが発生しました（${response.statusCode}）。しばらくしてからお試しください。';
      }
    } catch (e) {
      return '通信エラーが発生しました。インターネット接続を確認してください。';
    }
  }
}
