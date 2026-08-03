import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;
import 'package:garbage_app/models/gps_detection.dart';

/// ローカルGeoJSONポリゴンデータによる地区判定サービス
///
/// アプリバンドル内のGeoJSONファイルからポリゴンデータを読み込み、
/// Ray-castingアルゴリズムでPoint-in-Polygon判定を行う。
/// オフライン環境でもGPS座標から地区を特定できる。
class GeoJsonResolver {
  /// GeoJSONアセットのパス
  static const String _assetPath = 'assets/data/matsuyama_districts.geojson';

  /// 読み込み済みポリゴンデータ
  final List<_DistrictPolygon> _polygons = [];

  /// ポリゴンデータの読み込み状態
  bool get isLoaded => _polygons.isNotEmpty;

  /// アプリ起動時に非同期でポリゴンデータをロード
  ///
  /// rootBundleからGeoJSONファイルを読み込み、各FeatureのPolygon座標を
  /// メモリ上にパースする。UIスレッドをブロックしない。
  Future<void> loadPolygons() async {
    if (_polygons.isNotEmpty) return;

    try {
      final jsonString = await rootBundle.loadString(_assetPath);
      final geojson = json.decode(jsonString) as Map<String, dynamic>;
      final features = geojson['features'] as List<dynamic>;

      for (final feature in features) {
        final properties = feature['properties'] as Map<String, dynamic>;
        final geometry = feature['geometry'] as Map<String, dynamic>;
        final type = geometry['type'] as String;

        if (type != 'Polygon') continue;

        final districtNumber = properties['district_number'] as int;
        final districtName = properties['district_name'] as String;
        final coordinates = geometry['coordinates'] as List<dynamic>;

        // GeoJSON Polygon: coordinates[0] は外環リング [[lng, lat], ...]
        final outerRing = coordinates[0] as List<dynamic>;
        final points = outerRing.map((coord) {
          final c = coord as List<dynamic>;
          return _Point(
            longitude: (c[0] as num).toDouble(),
            latitude: (c[1] as num).toDouble(),
          );
        }).toList();

        _polygons.add(_DistrictPolygon(
          districtNumber: districtNumber,
          districtName: districtName,
          points: points,
        ));
      }
    } catch (_) {
      // ロード失敗時は空のままにする（isLoaded == false）
      // 呼び出し元（GPS_Detection_Provider）がフォールバックを処理する
    }
  }

  /// 座標からどの地区ポリゴンに含まれるか判定
  ///
  /// Ray-castingアルゴリズムで各ポリゴンに対してPoint-in-Polygon判定を行い、
  /// 該当する地区の[DistrictMatchResult]を返す。
  /// 200ms以内に結果を返す。該当なしの場合はnullを返す。
  /// [isLoaded]がfalseの場合もnullを返す（呼び出し元がフォールバックを処理）。
  DistrictMatchResult? resolveDistrict(double latitude, double longitude) {
    if (!isLoaded) return null;

    for (final polygon in _polygons) {
      if (_isPointInPolygon(latitude, longitude, polygon.points)) {
        return DistrictMatchResult(
          districtNumber: polygon.districtNumber,
          districtName: polygon.districtName,
          matchedTown: polygon.districtName, // ポリゴン判定では地区名を町名として使用
        );
      }
    }

    return null;
  }

  /// Ray-casting アルゴリズムによるPoint-in-Polygon判定
  ///
  /// 点から右方向に半直線を引き、ポリゴンの辺との交差回数を数える。
  /// 交差回数が奇数ならポリゴン内部、偶数ならポリゴン外部。
  bool _isPointInPolygon(
    double latitude,
    double longitude,
    List<_Point> polygon,
  ) {
    bool inside = false;
    final int n = polygon.length;

    for (int i = 0, j = n - 1; i < n; j = i++) {
      final double yi = polygon[i].latitude;
      final double xi = polygon[i].longitude;
      final double yj = polygon[j].latitude;
      final double xj = polygon[j].longitude;

      // 辺が点のY座標をまたいでいるか判定
      if ((yi > latitude) != (yj > latitude)) {
        // 半直線との交差X座標を計算
        final double intersectX =
            (xj - xi) * (latitude - yi) / (yj - yi) + xi;
        if (longitude < intersectX) {
          inside = !inside;
        }
      }
    }

    return inside;
  }
}

/// ポリゴンの頂点（緯度・経度）
class _Point {
  final double latitude;
  final double longitude;

  const _Point({required this.latitude, required this.longitude});
}

/// 地区ポリゴンデータ（内部用）
class _DistrictPolygon {
  final int districtNumber;
  final String districtName;
  final List<_Point> points;

  const _DistrictPolygon({
    required this.districtNumber,
    required this.districtName,
    required this.points,
  });
}
