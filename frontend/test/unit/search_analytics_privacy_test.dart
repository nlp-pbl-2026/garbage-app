import 'package:flutter_test/flutter_test.dart';
import 'package:garbage_app/services/search_analytics_service.dart';

void main() {
  test('metrics and redacted recent entries retain the existing wire contract',
      () {
    final summary = SearchAnalytics.fromJson({
      'total_searches': 1,
      'answered_count': 1,
      'clarification_count': 0,
      'average_confidence': 0.9,
      'average_duration_ms': 100,
      'categories': {'可燃ごみ': 1},
      'recent': [
        {
          'query': '（入力文は保存していません）',
          'rewritten_query': '',
          'text_retained': false,
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
    expect(summary.recent.single.query, '（入力文は保存していません）');
    expect(summary.recent.single.rewrittenQuery, isEmpty);
  });
}
