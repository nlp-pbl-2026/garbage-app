// GPS地区自動判定機能のデータモデルと例外クラス

/// GPS判定エラー種別（UI分岐制御用）
enum GpsDetectionErrorType {
  permissionDenied, // 権限拒否 → 「設定を開く」ボタン表示
  serviceDisabled, // サービス無効 → 「設定を開く」ボタン表示
  timeout, // タイムアウト → 「再試行」ボタン表示
  inaccurate, // 精度不足 → 「再試行」ボタン表示
  geocodingFailed, // ジオコーディング失敗
  outOfArea, // エリア外
  districtNotFound, // 地区未特定
  unknown, // 予期しないエラー
}

/// 候補リスト表示用データモデル（地区番号、地区名、町名）
class DistrictCandidate {
  final int districtNumber;
  final String districtName;
  final String townName;

  const DistrictCandidate({
    required this.districtNumber,
    required this.districtName,
    required this.townName,
  });

  @override
  String toString() =>
      'DistrictCandidate(districtNumber: $districtNumber, districtName: $districtName, townName: $townName)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DistrictCandidate &&
          runtimeType == other.runtimeType &&
          districtNumber == other.districtNumber &&
          districtName == other.districtName &&
          townName == other.townName;

  @override
  int get hashCode => Object.hash(districtNumber, districtName, townName);
}

/// GPS座標データモデル
class GpsCoordinate {
  final double latitude;
  final double longitude;
  final double accuracy; // 水平精度（メートル）

  const GpsCoordinate({
    required this.latitude,
    required this.longitude,
    required this.accuracy,
  });

  /// 精度が500メートル以内であれば有効とみなす
  bool get isAccurate => accuracy <= 500.0;

  @override
  String toString() =>
      'GpsCoordinate(lat: $latitude, lng: $longitude, accuracy: $accuracy)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GpsCoordinate &&
          runtimeType == other.runtimeType &&
          latitude == other.latitude &&
          longitude == other.longitude &&
          accuracy == other.accuracy;

  @override
  int get hashCode => Object.hash(latitude, longitude, accuracy);
}

/// 逆ジオコーディング結果の住所データモデル
class GeocodedAddress {
  final String prefecture; // 都道府県名（例: "愛媛県"）
  final String city; // 市区町村名（例: "松山市"）
  final String town; // 町名（例: "道後湯之町"）
  final String? subTown; // 丁目等（例: "１丁目"）
  final String fullAddress; // 完全住所文字列

  const GeocodedAddress({
    required this.prefecture,
    required this.city,
    required this.town,
    this.subTown,
    required this.fullAddress,
  });

  @override
  String toString() =>
      'GeocodedAddress(prefecture: $prefecture, city: $city, town: $town, subTown: $subTown)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is GeocodedAddress &&
          runtimeType == other.runtimeType &&
          prefecture == other.prefecture &&
          city == other.city &&
          town == other.town &&
          subTown == other.subTown &&
          fullAddress == other.fullAddress;

  @override
  int get hashCode =>
      Object.hash(prefecture, city, town, subTown, fullAddress);
}

/// 地区マッチング結果データモデル
class DistrictMatchResult {
  final int districtNumber; // 地区番号（1〜84）
  final String districtName; // 地区名（例: "道後"）
  final String matchedTown; // マッチした町名

  const DistrictMatchResult({
    required this.districtNumber,
    required this.districtName,
    required this.matchedTown,
  });

  @override
  String toString() =>
      'DistrictMatchResult(districtNumber: $districtNumber, districtName: $districtName, matchedTown: $matchedTown)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is DistrictMatchResult &&
          runtimeType == other.runtimeType &&
          districtNumber == other.districtNumber &&
          districtName == other.districtName &&
          matchedTown == other.matchedTown;

  @override
  int get hashCode =>
      Object.hash(districtNumber, districtName, matchedTown);
}

/// choumei.csv の1行分のデータモデル
class ChoumeiEntry {
  final int districtNumber; // 地区番号
  final String districtName; // 地区名
  final String townCode; // 町コード
  final String townName; // 町名（マッチングキー）
  final String oldCityName; // 旧市町村名

  const ChoumeiEntry({
    required this.districtNumber,
    required this.districtName,
    required this.townCode,
    required this.townName,
    required this.oldCityName,
  });

  @override
  String toString() =>
      'ChoumeiEntry(districtNumber: $districtNumber, districtName: $districtName, townName: $townName)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ChoumeiEntry &&
          runtimeType == other.runtimeType &&
          districtNumber == other.districtNumber &&
          districtName == other.districtName &&
          townCode == other.townCode &&
          townName == other.townName &&
          oldCityName == other.oldCityName;

  @override
  int get hashCode =>
      Object.hash(districtNumber, districtName, townCode, townName, oldCityName);
}

/// 位置情報権限の状態
enum LocationPermissionStatus {
  granted, // 許可済み
  denied, // 拒否
  deniedForever, // 永久拒否（設定から変更必要）
  serviceDisabled, // 位置情報サービス無効
}

/// GPS地区判定の例外基底クラス
sealed class GpsDetectionException implements Exception {
  String get userMessage;
}

/// 位置情報権限が拒否された場合の例外
class LocationPermissionDeniedException extends GpsDetectionException {
  @override
  String get userMessage =>
      '位置情報が許可されていません。設定アプリから権限を有効にしてください。';
}

/// 端末の位置情報サービスが無効な場合の例外
class LocationServiceDisabledException extends GpsDetectionException {
  @override
  String get userMessage =>
      '位置情報サービスが無効です。端末の設定で有効にしてください。';
}

/// GPS座標取得がタイムアウトした場合の例外
class LocationTimeoutException extends GpsDetectionException {
  @override
  String get userMessage =>
      '位置情報の取得がタイムアウトしました。再試行するか、手動で地域を選択してください。';
}

/// GPS座標の精度が不十分な場合の例外
class LocationInaccurateException extends GpsDetectionException {
  @override
  String get userMessage =>
      '位置情報の精度が不十分です。屋外で再試行するか、手動で地域を選択してください。';
}

/// 逆ジオコーディングが失敗した場合の例外
class GeocodingFailedException extends GpsDetectionException {
  @override
  String get userMessage =>
      '住所の取得に失敗しました。手動で地域を選択してください。';
}

/// 対応エリア外（松山市外）の場合の例外
class OutOfAreaException extends GpsDetectionException {
  @override
  String get userMessage =>
      '現在地は対応エリア外です。手動で地域を選択してください。';
}

/// 地区を特定できなかった場合の例外
class DistrictNotFoundException extends GpsDetectionException {
  @override
  String get userMessage =>
      '現在地の地区を特定できませんでした。手動で地域を選択してください。';
}
