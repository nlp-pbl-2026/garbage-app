import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart';
import 'package:http/http.dart' as http;

import '../models/location.dart';
import '../models/location_error.dart';
import 'region_service.dart';

/// 位置情報サービス
///
/// GPS位置情報取得、逆ジオコーディング、地域マッチングの3つの責務を持つ。
/// テスト容易性のため、各機能を個別のメソッドに分離している。
class LocationService {
  final RegionService _regionService;

  LocationService(this._regionService);

  /// 位置情報権限の状態を確認する
  Future<LocationPermission> checkPermission() async {
    return await Geolocator.checkPermission();
  }

  /// 位置情報権限をリクエストする
  Future<LocationPermission> requestPermission() async {
    return await Geolocator.requestPermission();
  }

  /// 位置情報サービスが有効かどうかを確認する
  Future<bool> isLocationServiceEnabled() async {
    return await Geolocator.isLocationServiceEnabled();
  }

  /// 現在位置を取得する（タイムアウト: 10秒）
  ///
  /// タイムアウト時は LocationException(type: gpsTimeout) をスローする。
  /// GPS信号取得不可時は LocationException(type: gpsUnavailable) をスローする。
  Future<GeoPosition> getCurrentPosition() async {
    try {
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      ).timeout(const Duration(seconds: 10));
      return GeoPosition(
          latitude: position.latitude, longitude: position.longitude);
    } on TimeoutException {
      throw const LocationException(type: LocationErrorType.gpsTimeout);
    } catch (e) {
      throw const LocationException(type: LocationErrorType.gpsUnavailable);
    }
  }

  /// 緯度・経度から住所情報を取得する（タイムアウト: 5秒）
  ///
  /// Web環境ではNominatim APIを使用し、ネイティブ環境ではgeocodingパッケージを使用する。
  /// タイムアウト時は LocationException(type: geocodingTimeout) をスローする。
  /// 日本国外の住所の場合は LocationException(type: outsideJapan) をスローする。
  /// 住所情報が不完全な場合は LocationException(type: addressIncomplete) をスローする。
  Future<GeoAddress> reverseGeocode(double latitude, double longitude) async {
    if (kIsWeb) {
      return _reverseGeocodeWeb(latitude, longitude);
    } else {
      return _reverseGeocodeNative(latitude, longitude);
    }
  }

  /// Web環境用の逆ジオコーディング（Nominatim API使用）
  Future<GeoAddress> _reverseGeocodeWeb(double latitude, double longitude) async {
    try {
      debugPrint('[LocationService] Web逆ジオコーディング開始: lat=$latitude, lng=$longitude');
      final url = Uri.parse(
        'https://nominatim.openstreetmap.org/reverse?lat=$latitude&lon=$longitude&format=json&accept-language=ja',
      );
      final response = await http.get(
        url,
        headers: {'User-Agent': 'EhimeGarbageApp/1.0'},
      ).timeout(const Duration(seconds: 5));

      debugPrint('[LocationService] Nominatim応答: status=${response.statusCode}');
      debugPrint('[LocationService] Nominatim body: ${response.body.substring(0, response.body.length > 500 ? 500 : response.body.length)}');

      if (response.statusCode != 200) {
        throw const LocationException(type: LocationErrorType.geocodingFailed);
      }

      final data = json.decode(response.body) as Map<String, dynamic>;
      final addressData = data['address'] as Map<String, dynamic>?;

      if (addressData == null) {
        debugPrint('[LocationService] addressDataがnull');
        throw const LocationException(type: LocationErrorType.geocodingFailed);
      }

      // 国判定
      final country = addressData['country'] as String? ?? '';
      final countryCode = addressData['country_code'] as String? ?? '';
      debugPrint('[LocationService] country=$country, countryCode=$countryCode');
      debugPrint('[LocationService] addressData全体: $addressData');
      if (countryCode != 'jp' && country != '日本' && country != 'Japan') {
        throw const LocationException(type: LocationErrorType.outsideJapan);
      }

      // 都道府県（state/province）と市区町村（city/town/village）を取得
      final prefecture = addressData['state'] as String?
          ?? addressData['province'] as String?
          ?? addressData['state_district'] as String?;
      final city = addressData['city'] as String?
          ?? addressData['town'] as String?
          ?? addressData['village'] as String?
          ?? addressData['county'] as String?;

      debugPrint('[LocationService] prefecture=$prefecture, city=$city');

      if (prefecture == null || city == null) {
        throw const LocationException(type: LocationErrorType.addressIncomplete);
      }

      return GeoAddress(
        country: country,
        administrativeArea: prefecture,
        locality: city,
      );
    } on TimeoutException {
      throw const LocationException(type: LocationErrorType.geocodingTimeout);
    } on LocationException {
      rethrow;
    } catch (e) {
      debugPrint('[LocationService] Web逆ジオコーディング未知のエラー: $e');
      throw const LocationException(type: LocationErrorType.geocodingFailed);
    }
  }

  /// ネイティブ環境用の逆ジオコーディング（geocodingパッケージ使用）
  Future<GeoAddress> _reverseGeocodeNative(double latitude, double longitude) async {
    try {
      final placemarks = await placemarkFromCoordinates(latitude, longitude)
          .timeout(const Duration(seconds: 5));
      if (placemarks.isEmpty) {
        throw const LocationException(type: LocationErrorType.geocodingFailed);
      }
      final placemark = placemarks.first;

      // 日本国外判定
      final country = placemark.country ?? '';
      if (country != '日本' && country != 'Japan' && country != 'JP') {
        throw const LocationException(type: LocationErrorType.outsideJapan);
      }

      final address = GeoAddress(
        country: placemark.country,
        administrativeArea: placemark.administrativeArea,
        locality: placemark.locality,
      );

      // 住所情報不完全チェック
      if (address.administrativeArea == null || address.locality == null) {
        throw const LocationException(
            type: LocationErrorType.addressIncomplete);
      }

      return address;
    } on TimeoutException {
      throw const LocationException(type: LocationErrorType.geocodingTimeout);
    } on LocationException {
      rethrow;
    } catch (e) {
      throw const LocationException(type: LocationErrorType.geocodingFailed);
    }
  }

  /// 逆ジオコーディング結果とアプリ内データをマッチングする
  ///
  /// 都道府県は完全一致、市区町村は前方一致で比較する。
  /// マッチ失敗時は LocationException をスローする。
  Future<RegionMatchResult> matchRegion(GeoAddress address) async {
    // 都道府県マッチング（完全一致）
    final prefectures = await _regionService.getPrefectures();
    final matchedPrefecture = prefectures
        .where((p) => p.name == address.administrativeArea)
        .toList();
    if (matchedPrefecture.isEmpty) {
      throw LocationException(
        type: LocationErrorType.prefectureNotFound,
        detail: address.administrativeArea,
      );
    }

    // 市区町村マッチング（前方一致）
    final municipalities =
        await _regionService.getMunicipalities(matchedPrefecture.first.id);
    final matchedMunicipality = municipalities
        .where((m) =>
            address.locality!.startsWith(m.name) ||
            m.name.startsWith(address.locality!))
        .toList();
    if (matchedMunicipality.isEmpty) {
      throw LocationException(
        type: LocationErrorType.municipalityNotFound,
        detail: address.locality,
      );
    }

    return RegionMatchResult(
      prefecture: matchedPrefecture.first,
      municipality: matchedMunicipality.first,
    );
  }

  /// GPS取得からマッチングまでの一連の処理を実行する
  ///
  /// 権限確認 → GPS取得 → 逆ジオコーディング → マッチング の順に実行する。
  /// 各ステップのエラーは LocationException として伝播する。
  Future<RegionMatchResult> detectRegion() async {
    // 1. 位置情報サービスの確認
    final serviceEnabled = await isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw const LocationException(type: LocationErrorType.serviceDisabled);
    }

    // 2. 権限確認・リクエスト
    var permission = await checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await requestPermission();
      if (permission == LocationPermission.denied) {
        throw const LocationException(
            type: LocationErrorType.permissionDenied);
      }
    }
    if (permission == LocationPermission.deniedForever) {
      throw const LocationException(
          type: LocationErrorType.permissionDeniedForever);
    }

    // 3. GPS取得
    final position = await getCurrentPosition();

    // 4. 逆ジオコーディング
    final address =
        await reverseGeocode(position.latitude, position.longitude);

    // 5. マッチング
    return await matchRegion(address);
  }
}
