import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:geocoding/geocoding.dart';
import 'package:http/http.dart' as http;

import '../models/gps_detection.dart';
import 'abstract_reverse_geocoder.dart';

/// 逆ジオコーディングサービス。
///
/// GPS座標（緯度・経度）から日本語住所情報への変換を担当する。
/// ネイティブ環境では `geocoding` パッケージのプラットフォームAPIを使用し、
/// Web環境ではNominatim API（OpenStreetMap）をHTTP経由で使用する。
class ReverseGeocodingService extends AbstractReverseGeocoder {
  /// GPS座標から住所情報を取得する。
  ///
  /// [latitude] と [longitude] で指定された座標を日本語住所に変換し、
  /// [GeocodedAddress] として返す。
  ///
  /// Web環境ではNominatim APIを使用し、ネイティブ環境ではgeocodingパッケージを使用する。
  /// 変換に失敗した場合は [GeocodingFailedException] をスローする。
  @override
  Future<GeocodedAddress> getAddressFromCoordinates(
    double latitude,
    double longitude,
  ) async {
    if (kIsWeb) {
      return _getAddressFromCoordinatesWeb(latitude, longitude);
    } else {
      return _getAddressFromCoordinatesNative(latitude, longitude);
    }
  }

  /// Web環境用の逆ジオコーディング（Nominatim API使用）
  Future<GeocodedAddress> _getAddressFromCoordinatesWeb(
    double latitude,
    double longitude,
  ) async {
    try {
      debugPrint('[ReverseGeocodingService] Web逆ジオコーディング開始: lat=$latitude, lng=$longitude');
      final url = Uri.parse(
        'https://nominatim.openstreetmap.org/reverse?lat=$latitude&lon=$longitude&format=json&accept-language=ja&addressdetails=1',
      );
      final response = await http.get(
        url,
        headers: {'User-Agent': 'EhimeGarbageApp/1.0'},
      ).timeout(const Duration(seconds: 5));

      debugPrint('[ReverseGeocodingService] Nominatim応答: status=${response.statusCode}');

      if (response.statusCode != 200) {
        throw GeocodingFailedException();
      }

      final data = json.decode(response.body) as Map<String, dynamic>;
      final addressData = data['address'] as Map<String, dynamic>?;

      if (addressData == null) {
        debugPrint('[ReverseGeocodingService] addressDataがnull');
        throw GeocodingFailedException();
      }

      debugPrint('[ReverseGeocodingService] addressData: $addressData');

      // 都道府県（state/province）
      final prefecture = addressData['state'] as String?
          ?? addressData['province'] as String?
          ?? addressData['state_district'] as String?
          ?? '';

      // 市区町村（city/town/village）
      final city = addressData['city'] as String?
          ?? addressData['town'] as String?
          ?? addressData['village'] as String?
          ?? '';

      // 町名（suburb/neighbourhood/quarter）
      final town = addressData['suburb'] as String?
          ?? addressData['neighbourhood'] as String?
          ?? addressData['quarter'] as String?
          ?? '';

      // 丁目等
      final subTown = addressData['road'] as String?;

      debugPrint('[ReverseGeocodingService] prefecture=$prefecture, city=$city, town=$town');

      if (prefecture.isEmpty || city.isEmpty || town.isEmpty) {
        // townが空でもcityがあれば使えるケースがある
        if (prefecture.isEmpty || city.isEmpty) {
          throw GeocodingFailedException();
        }
      }

      final fullAddress = '$prefecture$city$town${subTown ?? ''}';

      return GeocodedAddress(
        prefecture: prefecture,
        city: city,
        town: town.isNotEmpty ? town : city, // townが空の場合はcityをフォールバック
        subTown: subTown,
        fullAddress: fullAddress,
      );
    } on TimeoutException {
      throw GeocodingFailedException();
    } on GeocodingFailedException {
      rethrow;
    } catch (e) {
      debugPrint('[ReverseGeocodingService] Web逆ジオコーディングエラー: $e');
      throw GeocodingFailedException();
    }
  }

  /// ネイティブ環境用の逆ジオコーディング（geocodingパッケージ使用）
  Future<GeocodedAddress> _getAddressFromCoordinatesNative(
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
