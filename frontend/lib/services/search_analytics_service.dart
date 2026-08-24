import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/app_config.dart';
import 'waste_guide_service.dart';

class SearchLogEntry {
  final String query;
  final String rewrittenQuery;
  final String status;
  final String? categoryName;
  final double? confidence;
  final double durationMs;
  final String createdAt;

  const SearchLogEntry({
    required this.query,
    required this.rewrittenQuery,
    required this.status,
    required this.categoryName,
    required this.confidence,
    required this.durationMs,
    required this.createdAt,
  });

  factory SearchLogEntry.fromJson(Map<String, dynamic> json) => SearchLogEntry(
        query: json['query'] as String? ?? '',
        rewrittenQuery: json['rewritten_query'] as String? ?? '',
        status: json['status'] as String? ?? '',
        categoryName: json['category_name'] as String?,
        confidence: (json['confidence'] as num?)?.toDouble(),
        durationMs: (json['duration_ms'] as num?)?.toDouble() ?? 0,
        createdAt: json['created_at'] as String? ?? '',
      );
}

class SearchAnalytics {
  final int totalSearches;
  final int answeredCount;
  final int clarificationCount;
  final int unableCount;
  final double? averageConfidence;
  final double? averageDurationMs;
  final Map<String, int> categories;
  final List<SearchLogEntry> recent;

  const SearchAnalytics({
    required this.totalSearches,
    required this.answeredCount,
    required this.clarificationCount,
    required this.unableCount,
    required this.averageConfidence,
    required this.averageDurationMs,
    required this.categories,
    required this.recent,
  });

  factory SearchAnalytics.fromJson(Map<String, dynamic> json) =>
      SearchAnalytics(
        totalSearches: json['total_searches'] as int? ?? 0,
        answeredCount: json['answered_count'] as int? ?? 0,
        clarificationCount: json['clarification_count'] as int? ?? 0,
        unableCount: json['unable_count'] as int? ?? 0,
        averageConfidence: (json['average_confidence'] as num?)?.toDouble(),
        averageDurationMs: (json['average_duration_ms'] as num?)?.toDouble(),
        categories: (json['categories'] as Map<String, dynamic>? ?? const {})
            .map((key, value) => MapEntry(key, (value as num).toInt())),
        recent: (json['recent'] as List<dynamic>? ?? const [])
            .map(
                (item) => SearchLogEntry.fromJson(item as Map<String, dynamic>))
            .toList(),
      );
}

class SearchAnalyticsService {
  final http.Client _client;
  final String _baseUrl;

  SearchAnalyticsService({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? AppConfig.apiBaseUrl;

  Future<SearchAnalytics> fetch(String key) async {
    final response = await _client.get(
      Uri.parse('$_baseUrl/api/search/analytics'),
      headers: {'X-Analytics-Key': key},
    ).timeout(const Duration(seconds: 15));
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode != 200 || decoded is! Map<String, dynamic>) {
      final detail = decoded is Map<String, dynamic> ? decoded['detail'] : null;
      throw WasteGuideException(detail is String ? detail : '分析ログを取得できません。');
    }
    return SearchAnalytics.fromJson(decoded);
  }
}
