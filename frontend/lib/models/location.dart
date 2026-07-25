/// 位置情報関連のデータモデル
///
/// GPS位置情報取得、逆ジオコーディング、地域マッチングの結果を保持するクラス群。
/// 既存のregion.dartのPrefecture・Municipalityクラスと連携して使用する。
library;

import 'region.dart';

/// GPS座標
///
/// デバイスのGPSから取得した緯度・経度を保持する。
class GeoPosition {
  final double latitude;
  final double longitude;

  const GeoPosition({required this.latitude, required this.longitude});

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GeoPosition &&
          runtimeType == other.runtimeType &&
          latitude == other.latitude &&
          longitude == other.longitude;

  @override
  int get hashCode => latitude.hashCode ^ longitude.hashCode;

  @override
  String toString() => 'GeoPosition(latitude: $latitude, longitude: $longitude)';
}

/// 逆ジオコーディング結果
///
/// 緯度・経度から逆ジオコーディングで取得した住所情報を保持する。
/// countryは国名、administrativeAreaは都道府県、localityは市区町村を表す。
class GeoAddress {
  final String? country;
  final String? administrativeArea;
  final String? locality;

  const GeoAddress({
    this.country,
    this.administrativeArea,
    this.locality,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GeoAddress &&
          runtimeType == other.runtimeType &&
          country == other.country &&
          administrativeArea == other.administrativeArea &&
          locality == other.locality;

  @override
  int get hashCode =>
      country.hashCode ^ administrativeArea.hashCode ^ locality.hashCode;

  @override
  String toString() =>
      'GeoAddress(country: $country, administrativeArea: $administrativeArea, locality: $locality)';
}

/// 地域マッチング結果
///
/// 逆ジオコーディング結果とアプリ内地域データのマッチングが成功した場合の結果を保持する。
/// prefectureはマッチした都道府県、municipalityはマッチした市区町村を表す。
class RegionMatchResult {
  final Prefecture prefecture;
  final Municipality municipality;

  const RegionMatchResult({
    required this.prefecture,
    required this.municipality,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is RegionMatchResult &&
          runtimeType == other.runtimeType &&
          prefecture == other.prefecture &&
          municipality == other.municipality;

  @override
  int get hashCode => prefecture.hashCode ^ municipality.hashCode;

  @override
  String toString() =>
      'RegionMatchResult(prefecture: $prefecture, municipality: $municipality)';
}
