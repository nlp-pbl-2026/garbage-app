import '../models/gps_detection.dart';

/// 位置情報サービスの抽象インターフェース。
///
/// GPS座標取得、位置情報権限の確認・リクエスト、
/// 位置情報サービスの有効状態確認を定義する。
/// テスト時にモック実装を注入可能にするためのDI基盤。
abstract class AbstractLocationService {
  /// 位置情報の権限状態を確認する。
  Future<LocationPermissionStatus> checkPermission();

  /// 位置情報の権限をリクエストする。
  ///
  /// OSの権限ダイアログを表示し、ユーザーの選択結果を返す。
  Future<LocationPermissionStatus> requestPermission();

  /// 端末の位置情報サービスが有効かチェックする。
  Future<bool> isLocationServiceEnabled();

  /// GPS座標を取得する。
  ///
  /// Throws:
  /// - [LocationServiceDisabledException] 位置情報サービスが無効な場合
  /// - [LocationPermissionDeniedException] 権限が拒否されている場合
  /// - [LocationTimeoutException] タイムアウトした場合
  /// - [LocationInaccurateException] 精度が不十分な場合
  Future<GpsCoordinate> getCurrentPosition();
}
