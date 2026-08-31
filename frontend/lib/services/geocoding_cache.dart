import '../models/geocoding_cache_entry.dart';
import '../models/gps_detection.dart';

/// セッション内逆ジオコーディング結果キャッシュ
///
/// 同一座標近傍（50m以内）からのリクエスト時にAPI呼び出しを省略するための
/// メモリ内キャッシュ。FIFO方式で最大100件を保持する。
class GeocodingCache {
  /// キャッシュの最大エントリ数
  static const int maxEntries = 100;

  /// キャッシュヒットとみなす半径（メートル）
  static const double hitRadiusMeters = 50.0;

  final List<GeocodingCacheEntry> _entries = [];

  /// キャッシュからヒットを検索（50m以内で最近傍）
  ///
  /// 指定された座標から50m以内にあるキャッシュエントリを探し、
  /// 最も距離が近いエントリの住所を返す。
  /// 該当エントリがない場合はnullを返す。
  GeocodedAddress? get(double latitude, double longitude) {
    GeocodingCacheEntry? nearest;
    double nearestDistance = double.infinity;

    for (final entry in _entries) {
      final distance = entry.distanceTo(latitude, longitude);
      if (distance <= hitRadiusMeters && distance < nearestDistance) {
        nearest = entry;
        nearestDistance = distance;
      }
    }

    return nearest?.address;
  }

  /// キャッシュに追加（FIFO、上限100件）
  ///
  /// 上限に達している場合は、挿入時刻が最も古いエントリを1件削除してから
  /// 新しいエントリを追加する。
  void put(double latitude, double longitude, GeocodedAddress address) {
    if (_entries.length >= maxEntries) {
      // 挿入時刻が最も古いエントリを削除（FIFO）
      int oldestIndex = 0;
      DateTime oldestTime = _entries[0].insertedAt;
      for (int i = 1; i < _entries.length; i++) {
        if (_entries[i].insertedAt.isBefore(oldestTime)) {
          oldestTime = _entries[i].insertedAt;
          oldestIndex = i;
        }
      }
      _entries.removeAt(oldestIndex);
    }

    _entries.add(
      GeocodingCacheEntry(
        latitude: latitude,
        longitude: longitude,
        address: address,
        insertedAt: DateTime.now(),
      ),
    );
  }

  /// キャッシュクリア
  void clear() {
    _entries.clear();
  }

  /// 現在のエントリ数
  int get length => _entries.length;
}
