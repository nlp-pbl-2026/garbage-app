import 'dart:math';

import 'gps_detection.dart';

/// 逆ジオコーディング結果のキャッシュエントリ
///
/// 座標、住所データ、挿入時刻を保持し、
/// Haversine公式による他の座標との距離計算を提供する。
class GeocodingCacheEntry {
  /// キャッシュした座標の緯度
  final double latitude;

  /// キャッシュした座標の経度
  final double longitude;

  /// 逆ジオコーディングで得られた住所データ
  final GeocodedAddress address;

  /// キャッシュに挿入された時刻
  final DateTime insertedAt;

  const GeocodingCacheEntry({
    required this.latitude,
    required this.longitude,
    required this.address,
    required this.insertedAt,
  });

  /// 地球の平均半径（メートル）
  static const double _earthRadiusMeters = 6371000.0;

  /// Haversine公式による2点間の距離（メートル）を計算する。
  ///
  /// [lat] 比較対象の緯度（度数法）
  /// [lng] 比較対象の経度（度数法）
  /// 戻り値: 2点間の大圏距離（メートル）
  double distanceTo(double lat, double lng) {
    final lat1Rad = _toRadians(latitude);
    final lat2Rad = _toRadians(lat);
    final deltaLat = _toRadians(lat - latitude);
    final deltaLng = _toRadians(lng - longitude);

    final a = sin(deltaLat / 2) * sin(deltaLat / 2) +
        cos(lat1Rad) * cos(lat2Rad) * sin(deltaLng / 2) * sin(deltaLng / 2);
    final c = 2 * atan2(sqrt(a), sqrt(1 - a));

    return _earthRadiusMeters * c;
  }

  static double _toRadians(double degrees) => degrees * pi / 180.0;

  @override
  String toString() =>
      'GeocodingCacheEntry(lat: $latitude, lng: $longitude, '
      'address: $address, insertedAt: $insertedAt)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GeocodingCacheEntry &&
          runtimeType == other.runtimeType &&
          latitude == other.latitude &&
          longitude == other.longitude &&
          address == other.address &&
          insertedAt == other.insertedAt;

  @override
  int get hashCode => Object.hash(latitude, longitude, address, insertedAt);
}
