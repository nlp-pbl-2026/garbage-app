import '../models/gps_detection.dart';

/// 逆ジオコーディングサービスの抽象インターフェース。
///
/// GPS座標（緯度・経度）から住所情報への変換を定義する。
/// テスト時にモック実装を注入可能にするためのDI基盤。
abstract class AbstractReverseGeocoder {
  /// GPS座標から住所情報を取得する。
  ///
  /// [latitude] と [longitude] で指定された座標を住所に変換し、
  /// [GeocodedAddress] として返す。
  ///
  /// Throws:
  /// - [GeocodingFailedException] 住所変換に失敗した場合
  Future<GeocodedAddress> getAddressFromCoordinates(
    double latitude,
    double longitude,
  );
}
