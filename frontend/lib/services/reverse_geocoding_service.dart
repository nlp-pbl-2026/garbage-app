import 'package:geocoding/geocoding.dart';

import '../models/gps_detection.dart';
import 'abstract_reverse_geocoder.dart';

/// 逆ジオコーディングサービス。
///
/// GPS座標（緯度・経度）から日本語住所情報への変換を担当する。
/// `geocoding` パッケージのプラットフォームネイティブAPIを使用し、
/// 外部APIサーバーへの依存なしに住所変換を行う。
class ReverseGeocodingService extends AbstractReverseGeocoder {
  /// GPS座標から住所情報を取得する。
  ///
  /// [latitude] と [longitude] で指定された座標を日本語住所に変換し、
  /// [GeocodedAddress] として返す。
  ///
  /// 変換に失敗した場合は [GeocodingFailedException] をスローする。
  @override
  Future<GeocodedAddress> getAddressFromCoordinates(
    double latitude,
    double longitude,
  ) async {
    try {
      final placemarks = await placemarkFromCoordinates(latitude, longitude);

      if (placemarks.isEmpty) {
        throw GeocodingFailedException();
      }

      final placemark = placemarks.first;

      final prefecture = placemark.administrativeArea ?? '';
      final city = placemark.locality ?? '';
      final town = placemark.subLocality ?? '';
      final subTown = placemark.thoroughfare;

      if (prefecture.isEmpty || city.isEmpty || town.isEmpty) {
        throw GeocodingFailedException();
      }

      final fullAddress = '$prefecture$city$town${subTown ?? ''}';

      return GeocodedAddress(
        prefecture: prefecture,
        city: city,
        town: town,
        subTown: subTown,
        fullAddress: fullAddress,
      );
    } on GeocodingFailedException {
      rethrow;
    } catch (_) {
      throw GeocodingFailedException();
    }
  }
}
