import 'dart:async';

import 'package:geolocator/geolocator.dart' hide LocationServiceDisabledException;

import '../models/gps_detection.dart';
import 'abstract_location_service.dart';

/// Geolocator の静的メソッドをラップするクラス。
///
/// テスト時にモック実装を注入可能にするためのDI基盤。
/// デフォルトでは実際の Geolocator 静的メソッドを呼び出す。
class GeolocatorWrapper {
  /// 位置情報の権限状態を確認する。
  Future<LocationPermission> checkPermission() => Geolocator.checkPermission();

  /// 位置情報の権限をリクエストする。
  Future<LocationPermission> requestPermission() =>
      Geolocator.requestPermission();

  /// 端末の位置情報サービスが有効かチェックする。
  Future<bool> isLocationServiceEnabled() =>
      Geolocator.isLocationServiceEnabled();

  /// 現在位置を取得する。
  Future<Position> getCurrentPosition({
    LocationAccuracy desiredAccuracy = LocationAccuracy.best,
    Duration? timeLimit,
  }) =>
      Geolocator.getCurrentPosition(
        desiredAccuracy: desiredAccuracy,
        timeLimit: timeLimit,
      );

  /// 端末のアプリ設定画面を起動する。
  Future<bool> openAppSettings() => Geolocator.openAppSettings();
}

/// GPS位置情報取得サービス。
///
/// 端末のGPS座標取得、位置情報権限の確認・リクエスト、
/// 位置情報サービスの有効状態確認を担当する。
/// [GeolocatorWrapper] をラップし、アプリ固有の例外に変換する。
class GpsLocationService extends AbstractLocationService {
  /// GPS取得のタイムアウト時間（秒）
  static const Duration _timeout = Duration(seconds: 5);

  /// Geolocator ラッパー（テスト時にモック注入可能）
  final GeolocatorWrapper _geolocator;

  /// コンストラクタ。
  ///
  /// [geolocator] を省略した場合、デフォルトの [GeolocatorWrapper] を使用する。
  GpsLocationService({GeolocatorWrapper? geolocator})
      : _geolocator = geolocator ?? GeolocatorWrapper();

  /// 位置情報の権限状態を確認する。
  ///
  /// geolocator の checkPermission をラップし、
  /// アプリ固有の [LocationPermissionStatus] に変換して返す。
  @override
  Future<LocationPermissionStatus> checkPermission() async {
    final permission = await _geolocator.checkPermission();
    return _mapPermission(permission);
  }

  /// 位置情報の権限をリクエストする。
  ///
  /// OSの権限ダイアログを表示し、ユーザーの選択結果を
  /// [LocationPermissionStatus] として返す。
  @override
  Future<LocationPermissionStatus> requestPermission() async {
    final permission = await _geolocator.requestPermission();
    return _mapPermission(permission);
  }

  /// 端末の位置情報サービスが有効かチェックする。
  ///
  /// 有効な場合は true、無効な場合は false を返す。
  @override
  Future<bool> isLocationServiceEnabled() async {
    return await _geolocator.isLocationServiceEnabled();
  }

  /// GPS座標を取得する。
  ///
  /// タイムアウト5秒以内に精度500m以内の座標を取得できた場合に
  /// [GpsCoordinate] を返す。
  ///
  /// Throws:
  /// - [LocationServiceDisabledException] 位置情報サービスが無効な場合
  /// - [LocationPermissionDeniedException] 権限が拒否されている場合
  /// - [LocationTimeoutException] 5秒以内に座標を取得できなかった場合
  /// - [LocationInaccurateException] 精度が500mを超えた場合
  @override
  Future<GpsCoordinate> getCurrentPosition() async {
    // 位置情報サービスの有効状態を確認
    final serviceEnabled = await isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw LocationServiceDisabledException();
    }

    // 権限状態を確認
    var permission = await checkPermission();
    if (permission == LocationPermissionStatus.denied) {
      permission = await requestPermission();
    }

    if (permission == LocationPermissionStatus.denied ||
        permission == LocationPermissionStatus.deniedForever) {
      throw LocationPermissionDeniedException();
    }

    // GPS座標を取得（タイムアウト付き）
    final Position position;
    try {
      position = await _geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: _timeout,
      );
    } on TimeoutException {
      throw LocationTimeoutException();
    } on LocationServiceDisabledException {
      throw LocationServiceDisabledException();
    }

    // 精度バリデーション
    final coordinate = GpsCoordinate(
      latitude: position.latitude,
      longitude: position.longitude,
      accuracy: position.accuracy,
    );

    if (!coordinate.isAccurate) {
      throw LocationInaccurateException();
    }

    return coordinate;
  }

  /// geolocator の LocationPermission をアプリ固有の
  /// [LocationPermissionStatus] にマッピングする。
  LocationPermissionStatus _mapPermission(LocationPermission permission) {
    switch (permission) {
      case LocationPermission.always:
      case LocationPermission.whileInUse:
        return LocationPermissionStatus.granted;
      case LocationPermission.denied:
      case LocationPermission.unableToDetermine:
        return LocationPermissionStatus.denied;
      case LocationPermission.deniedForever:
        return LocationPermissionStatus.deniedForever;
    }
  }
}
