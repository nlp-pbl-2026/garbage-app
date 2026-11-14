import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/search_analytics_service.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'dart:convert';

void main() {
  test('metrics and research text retain the existing wire contract', () {
    final summary = SearchAnalytics.fromJson({
      'total_searches': 1,
      'answered_count': 1,
      'clarification_count': 0,
      'average_confidence': 0.9,
      'average_duration_ms': 100,
      'categories': {'可燃ごみ': 1},
      'recent': [
        {
          'query': 'この缶は何ごみ？',
          'rewritten_query': 'アルミ缶',
          'clarifications': [
            {'question': '材質は何ですか？', 'answer': 'アルミです'}
          ],
          'answer': 'かん類に出してください。',
          'follow_up_question': null,
          'text_retained': true,
          'status': 'answered',
          'category_name': '可燃ごみ',
          'confidence': 0.9,
          'duration_ms': 100,
          'created_at': '2026-11-15T00:00:00Z'
        }
      ]
    });
    expect(summary.totalSearches, 1);
    expect(summary.categories['可燃ごみ'], 1);
    final item = summary.recent.single;
    expect(item.query, 'この缶は何ごみ？');
    expect(item.rewrittenQuery, 'アルミ缶');
    expect(item.clarifications.single.question, '材質は何ですか？');
    expect(item.clarifications.single.answer, 'アルミです');
    expect(item.answer, 'かん類に出してください。');
    expect(item.followUpQuestion, isNull);
    expect(item.confidence, 0.9);
    expect(item.durationMs, 100);
  });

  test('older metrics-only records and pending questions remain readable', () {
    final old = SearchLogEntry.fromJson({
      'query': '（入力文は保存していません）',
      'text_retained': false,
    });
    expect(old.query, '（入力文は保存していません）');
    expect(old.rewrittenQuery, isEmpty);
    expect(old.clarifications, isEmpty);
    expect(old.answer, isNull);
    expect(old.followUpQuestion, isNull);
    final pending = SearchLogEntry.fromJson({
      'query': '容器',
      'follow_up_question': '材質は何ですか？',
    });
    expect(pending.followUpQuestion, '材質は何ですか？');
  });

  test('analytics key is sent only in the protected request header', () async {
    final service = SearchAnalyticsService(
      baseUrl: 'https://example.invalid',
      client: MockClient((request) async {
        expect(request.url.path, '/api/search/analytics');
        expect(request.url.query, isEmpty);
        expect(request.headers['X-Analytics-Key'], 'test-admin-key');
        return http.Response(jsonEncode({'recent': []}), 200);
      }),
    );
    expect((await service.fetch('test-admin-key')).recent, isEmpty);
  });
}
