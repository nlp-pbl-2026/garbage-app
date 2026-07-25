/// 位置情報エラー関連のモデル
///
/// GPS取得、逆ジオコーディング、地域マッチングの各段階で発生する
/// エラーの種別、ユーザーメッセージ、対応アクションを定義する。

/// 位置情報エラーの種別
enum LocationErrorType {
  /// 位置情報サービスが無効
  serviceDisabled,

  /// 権限拒否
  permissionDenied,

  /// 権限永続的拒否
  permissionDeniedForever,

  /// GPS取得タイムアウト（10秒超過）
  gpsTimeout,

  /// GPS信号取得不可
  gpsUnavailable,

  /// 逆ジオコーディングタイムアウト（5秒超過）
  geocodingTimeout,

  /// 逆ジオコーディング失敗
  geocodingFailed,

  /// 日本国外
  outsideJapan,

  /// 住所情報不完全（都道府県名or市区町村名なし）
  addressIncomplete,

  /// 都道府県マッチ失敗
  prefectureNotFound,

  /// 市区町村マッチ失敗
  municipalityNotFound,
}

/// 位置情報エラー
///
/// エラー種別に応じたユーザーメッセージ、再試行可否、設定画面遷移ボタン表示を保持する。
class LocationError {
  final LocationErrorType type;

  /// ユーザーに表示するメッセージ
  final String userMessage;

  /// 再試行可能かどうか
  final bool canRetry;

  /// 設定画面への遷移ボタンを表示するか
  final bool showSettings;

  const LocationError({
    required this.type,
    required this.userMessage,
    required this.canRetry,
    this.showSettings = false,
  });

  /// エラー種別からLocationErrorインスタンスを生成する
  ///
  /// [type] エラー種別
  /// [detail] 追加情報（都道府県名や市区町村名など、メッセージに埋め込む値）
  factory LocationError.fromType(LocationErrorType type, {String? detail}) {
    switch (type) {
      case LocationErrorType.serviceDisabled:
        return LocationError(
          type: type,
          userMessage: '端末の位置情報サービスが無効です。設定画面から位置情報サービスを有効にしてください',
          canRetry: false,
          showSettings: true,
        );
      case LocationErrorType.permissionDenied:
        return LocationError(
          type: type,
          userMessage: '位置情報の権限が必要です。端末の設定画面から位置情報を許可してください',
          canRetry: false,
          showSettings: true,
        );
      case LocationErrorType.permissionDeniedForever:
        return LocationError(
          type: type,
          userMessage: '位置情報の権限が無効です。端末の設定画面から位置情報を許可してください',
          canRetry: false,
          showSettings: true,
        );
      case LocationErrorType.gpsTimeout:
        return LocationError(
          type: type,
          userMessage: '位置情報の取得に失敗しました。電波状況の良い場所で再度お試しください',
          canRetry: true,
        );
      case LocationErrorType.gpsUnavailable:
        return LocationError(
          type: type,
          userMessage: '位置情報を取得できませんでした。手動で地域を選択してください',
          canRetry: false,
        );
      case LocationErrorType.geocodingTimeout:
        return LocationError(
          type: type,
          userMessage: '住所の特定に失敗しました。再度お試しいただくか、手動で選択してください',
          canRetry: true,
        );
      case LocationErrorType.geocodingFailed:
        return LocationError(
          type: type,
          userMessage: '住所情報を特定できませんでした。手動で地域を選択してください',
          canRetry: false,
        );
      case LocationErrorType.outsideJapan:
        return LocationError(
          type: type,
          userMessage: '愛媛県内の位置情報を検出できませんでした。手動で地域を選択してください',
          canRetry: false,
        );
      case LocationErrorType.addressIncomplete:
        return LocationError(
          type: type,
          userMessage: '住所情報を特定できませんでした。手動で地域を選択してください',
          canRetry: false,
        );
      case LocationErrorType.prefectureNotFound:
        return LocationError(
          type: type,
          userMessage: '検出された地域（${detail ?? "不明"}）はアプリの対応地域外です。手動で地域を選択してください',
          canRetry: false,
        );
      case LocationErrorType.municipalityNotFound:
        return LocationError(
          type: type,
          userMessage: '検出された市区町村（${detail ?? "不明"}）はアプリの対応地域外です。手動で地域を選択してください',
          canRetry: false,
        );
    }
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is LocationError &&
          runtimeType == other.runtimeType &&
          type == other.type &&
          userMessage == other.userMessage &&
          canRetry == other.canRetry &&
          showSettings == other.showSettings;

  @override
  int get hashCode =>
      type.hashCode ^
      userMessage.hashCode ^
      canRetry.hashCode ^
      showSettings.hashCode;

  @override
  String toString() =>
      'LocationError(type: $type, userMessage: $userMessage, '
      'canRetry: $canRetry, showSettings: $showSettings)';
}

/// 位置情報関連の例外
///
/// LocationServiceの各メソッドがエラー時にスローする例外クラス。
/// LocationDetectionNotifierがキャッチしてLocationErrorに変換する。
class LocationException implements Exception {
  /// エラー種別
  final LocationErrorType type;

  /// 追加情報（都道府県名や市区町村名など）
  final String? detail;

  const LocationException({
    required this.type,
    this.detail,
  });

  /// この例外に対応するLocationErrorを生成する
  LocationError toLocationError() => LocationError.fromType(type, detail: detail);

  @override
  String toString() => 'LocationException(type: $type, detail: $detail)';
}
