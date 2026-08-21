/// テキストユーティリティおよびキャッシュ判定ロジック
class TextUtils {
  /// キャッシュデータが期限切れ（30日以上経過）かどうかを判定する。
  ///
  /// [lastUpdated] データの最終更新日時
  /// [now] 現在日時（テスト容易性のためオプション、デフォルトはDateTime.now()）
  ///
  /// 最終更新日から30日以上経過している場合は true を返す。
  static bool isCacheExpired(DateTime lastUpdated, {DateTime? now}) {
    final currentTime = now ?? DateTime.now();
    final difference = currentTime.difference(lastUpdated);
    return difference.inDays >= 30;
  }
}
