import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// メモデータの永続化・バリデーションを担当するサービスクラス
///
/// SharedPreferencesを使用してJSON形式でメモデータを保存・取得・削除する。
/// 日付をキー、メモテキストを値として管理し、アプリ起動時にキャッシュを初期化する。
class MemoService {
  /// SharedPreferencesに保存する際のストレージキー
  static const String _storageKey = 'calendar_memos';

  /// メモテキストの最大文字数
  static const int maxMemoLength = 200;

  final SharedPreferences _prefs;

  /// メモデータのインメモリキャッシュ（日付キー → メモテキスト）
  Map<String, String> _cache = {};

  MemoService(this._prefs);

  /// キャッシュを初期化する（SharedPreferencesから読み込み）
  ///
  /// アプリ起動時に呼び出し、保存済みメモデータをメモリに読み込む。
  /// 読み込みまたはデシリアライズに失敗した場合は空のMapで初期化する。
  Future<void> init() async {
    try {
      final jsonString = _prefs.getString(_storageKey);
      if (jsonString != null) {
        _cache = _deserialize(jsonString);
      } else {
        _cache = {};
      }
    } catch (_) {
      // SharedPreferences読み込み失敗時は空のMapで初期化
      _cache = {};
    }
  }

  /// 指定日付のメモを取得する
  ///
  /// [date] 対象日付
  /// 返り値: メモテキスト。未登録の場合はnull。
  String? getMemo(DateTime date) {
    final key = _dateToKey(date);
    return _cache[key];
  }

  /// 指定月に存在するメモの日付セットを取得する
  ///
  /// [year] 年、[month] 月を指定し、その月にメモが存在する日付のSetを返す。
  Set<DateTime> getMemoDatesForMonth(int year, int month) {
    final Set<DateTime> dates = {};
    for (final key in _cache.keys) {
      final parts = key.split('-');
      if (parts.length == 3) {
        final keyYear = int.tryParse(parts[0]);
        final keyMonth = int.tryParse(parts[1]);
        final keyDay = int.tryParse(parts[2]);
        if (keyYear == year && keyMonth == month && keyDay != null) {
          dates.add(DateTime(keyYear!, keyMonth!, keyDay));
        }
      }
    }
    return dates;
  }

  /// メモを保存する
  ///
  /// [date] 対象日付、[text] メモテキスト。
  /// バリデーション失敗時はfalseを返す。
  /// SharedPreferences書き込み失敗時もfalseを返す。
  Future<bool> saveMemo(DateTime date, String text) async {
    final trimmedText = text.trim();
    if (!isValidMemoText(trimmedText)) {
      return false;
    }

    final key = _dateToKey(date);
    _cache[key] = trimmedText;

    try {
      final jsonString = _serialize(_cache);
      final result = await _prefs.setString(_storageKey, jsonString);
      if (!result) {
        // 書き込み失敗時はキャッシュをロールバック
        _cache.remove(key);
        return false;
      }
      return true;
    } catch (_) {
      // SharedPreferences書き込み失敗時はキャッシュをロールバック
      _cache.remove(key);
      return false;
    }
  }

  /// メモを削除する
  ///
  /// [date] 対象日付。
  /// メモが存在しない場合は何もしない。
  /// SharedPreferences書き込み失敗時はキャッシュをロールバックする。
  Future<void> deleteMemo(DateTime date) async {
    final key = _dateToKey(date);
    final previousValue = _cache[key];

    if (previousValue == null) {
      return;
    }

    _cache.remove(key);

    try {
      final jsonString = _serialize(_cache);
      final result = await _prefs.setString(_storageKey, jsonString);
      if (!result) {
        // 書き込み失敗時はキャッシュをロールバック
        _cache[key] = previousValue;
      }
    } catch (_) {
      // SharedPreferences書き込み失敗時はキャッシュをロールバック
      _cache[key] = previousValue;
    }
  }

  /// 日付をストレージキー文字列に変換する（yyyy-MM-dd形式）
  String _dateToKey(DateTime date) {
    final year = date.year.toString().padLeft(4, '0');
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');
    return '$year-$month-$day';
  }

  /// 全メモデータをJSON文字列にシリアライズする
  String _serialize(Map<String, String> memos) {
    return json.encode(memos);
  }

  /// JSON文字列から全メモデータをデシリアライズする
  ///
  /// パースに失敗した場合は空のMapを返す。
  /// 不正なエントリ（値がString以外）はスキップする。
  Map<String, String> _deserialize(String jsonString) {
    try {
      final decoded = json.decode(jsonString);
      if (decoded is! Map<String, dynamic>) {
        return {};
      }
      final Map<String, String> result = {};
      for (final entry in decoded.entries) {
        if (entry.value is String) {
          // 日付キー形式のバリデーション
          final parts = entry.key.split('-');
          if (parts.length == 3 &&
              int.tryParse(parts[0]) != null &&
              int.tryParse(parts[1]) != null &&
              int.tryParse(parts[2]) != null) {
            result[entry.key] = entry.value as String;
          }
        }
      }
      return result;
    } catch (_) {
      // JSONデシリアライズ失敗時は空のMapを返す
      return {};
    }
  }

  /// テキストのバリデーション
  ///
  /// 以下の条件を満たす場合にtrueを返す：
  /// - 空文字列でない（trim後）
  /// - 200文字以下
  bool isValidMemoText(String text) {
    if (text.trim().isEmpty) {
      return false;
    }
    if (text.length > maxMemoLength) {
      return false;
    }
    return true;
  }
}
