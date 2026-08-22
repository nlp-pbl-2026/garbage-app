import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/app_config.dart';

/// Gemini API を使ったチャットサービス
///
/// ゴミ分別に特化したシステムプロンプトを使い、
/// ユーザーの質問に対してAI応答を返す。
/// 言語コードに応じてシステムプロンプトをパラメタライズし、
/// ユーザーの選択言語で応答を生成する。
class GeminiService {
  GeminiService();

  static const String _baseUrl =
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent';

  /// 言語コードに応じた応答指示
  static const Map<String, String> _languageInstructions = {
    'ja': 'ユーザーの質問に日本語で簡潔に回答してください。',
    'en': 'Please respond to user questions concisely in English.',
    'pt':
        'Por favor, responda às perguntas do usuário de forma concisa em português.',
    'zh': '请用中文简洁地回答用户的问题。',
    'vi':
        'Vui lòng trả lời câu hỏi của người dùng một cách ngắn gọn bằng tiếng Việt.',
  };

  /// 言語コードに応じたシステムプロンプトを動的に生成する
  ///
  /// 1. ベースコンテキスト（愛媛県ゴミ出しアプリのAIアシスタント）
  /// 2. 言語固有の応答指示
  /// 3. 日本語のゴミカテゴリ用語を括弧で併記する指示（日本語以外の場合）
  /// 4. わからない場合の案内
  String buildSystemPrompt(String languageCode) {
    final languageInstruction =
        _languageInstructions[languageCode] ?? _languageInstructions['ja']!;

    final buffer = StringBuffer();
    buffer.writeln('あなたは愛媛県のゴミ出しアプリのAIアシスタントです。');
    buffer.writeln(languageInstruction);

    // 日本語以外の場合、ゴミカテゴリ名に日本語の元用語を括弧で併記する指示を追加
    if (languageCode != 'ja') {
      buffer.writeln(
          'ゴミカテゴリ名（可燃ごみ、資源ごみ、プラスチック製容器包装、ペットボトル、粗大ごみ等）を言及する際は、翻訳語の後に括弧で日本語の元の用語を併記してください。');
    }

    buffer.write('わからない場合は地元の市役所への問い合わせを案内してください。');

    return buffer.toString();
  }

  /// ユーザーメッセージを送信し、AIの応答テキストを返す
  ///
  /// [languageCode] に基づいてシステムプロンプトをパラメタライズする。
  /// エラー時はnullを返す（呼び出し側でARBの`aiErrorMessage`を表示する想定）。
  Future<String?> sendMessage(
    String userMessage, {
    required String languageCode,
  }) async {
    final url = Uri.parse('$_baseUrl?key=${AppConfig.geminiApiKey}');
    final systemPrompt = buildSystemPrompt(languageCode);

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
          {'text': systemPrompt}
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
          final content = candidates[0]['content'] as Map<String, dynamic>?;
          final parts = content?['parts'] as List<dynamic>?;
          if (parts != null && parts.isNotEmpty) {
            return parts[0]['text'] as String?;
          }
        }
        return null;
      } else {
        return null;
      }
    } catch (e) {
      return null;
    }
  }
}
