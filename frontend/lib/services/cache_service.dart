import 'package:shared_preferences/shared_preferences.dart';

import '../utils/text_utils.dart';

/// オフラインデータキャッシュの日時管理を行うサービス。
///
/// プロトタイプ段階ではローカルJSONがデフォルトデータソースのため、
/// 実際のデータ同期は行わず、キャッシュ日時管理のみを担当する。
/// SharedPreferencesにデータの最終更新日時を保存し、
/// 30日経過判定によるデータ古い通知の表示ロジックを提供する。
class CacheService {
  /// SharedPreferencesに最終更新日時を保存する際のキー
  static const String _dataLastUpdatedKey = 'data_last_updated';

  /// データの最終更新日時を保存する。
  ///
  /// [dateTime] をISO8601形式の文字列に変換してSharedPreferencesに保存する。
  /// 地域設定完了時に呼び出すことを想定している。
  Future<void> setLastUpdated(DateTime dateTime) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_dataLastUpdatedKey, dateTime.toIso8601String());
  }

  /// 保存済みのデータ最終更新日時を取得する。
  ///
  /// 最終更新日時が保存されていない場合は null を返す。
  Future<DateTime?> getLastUpdated() async {
    final prefs = await SharedPreferences.getInstance();
    final dateString = prefs.getString(_dataLastUpdatedKey);
    if (dateString == null) {
      return null;
    }
    return DateTime.parse(dateString);
  }

  /// キャッシュデータが期限切れかどうかを判定する。
  ///
  /// 保存済みの最終更新日時から30日以上経過している場合は true を返す。
  /// 最終更新日時が未設定の場合も true を返す（データが古い可能性がある）。
  ///
  /// [now] テスト容易性のためオプションで現在日時を指定可能。
  Future<bool> isDataExpired({DateTime? now}) async {
    final lastUpdated = await getLastUpdated();
    if (lastUpdated == null) {
      return true;
    }
    return TextUtils.isCacheExpired(lastUpdated, now: now);
  }
}
