import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// 検索履歴サービス
///
/// 検索キーワードの履歴をSharedPreferencesに保存・取得・削除する。
/// 最大50件まで保持し、古いエントリから削除する。
class SearchHistoryService {
  static const String _historyKey = 'search_history';
  static const int _maxHistoryCount = 50;

  /// 検索履歴を取得する（新しい順）
  Future<List<String>> getHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonString = prefs.getString(_historyKey);
    if (jsonString == null) return [];

    try {
      final list = json.decode(jsonString) as List<dynamic>;
      return list.cast<String>();
    } catch (_) {
      return [];
    }
  }

  /// 検索キーワードを履歴に追加する
  ///
  /// 同じキーワードが既に存在する場合は先頭に移動する。
  /// 最大件数を超えた場合は末尾（最も古い）を削除する。
  Future<void> addHistory(String keyword) async {
    if (keyword.trim().length < 2) return;

    final prefs = await SharedPreferences.getInstance();
    final history = await getHistory();

    // 既存の同一キーワードを削除
    history.remove(keyword.trim());

    // 先頭に追加
    history.insert(0, keyword.trim());

    // 最大件数制限
    if (history.length > _maxHistoryCount) {
      history.removeRange(_maxHistoryCount, history.length);
    }

    await prefs.setString(_historyKey, json.encode(history));
  }

  /// 特定のキーワードを履歴から削除する
  Future<void> removeHistory(String keyword) async {
    final prefs = await SharedPreferences.getInstance();
    final history = await getHistory();
    history.remove(keyword);
    await prefs.setString(_historyKey, json.encode(history));
  }

  /// 履歴を全て削除する
  Future<void> clearHistory() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_historyKey);
  }
}
