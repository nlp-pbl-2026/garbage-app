/// アプリケーション設定
///
/// API接続先やタイムアウト値など、環境に依存する設定を一元管理する。
/// 本番環境では環境変数やビルド構成で切り替えることを想定。
class AppConfig {
  // プライベートコンストラクタ（インスタンス化防止）
  AppConfig._();

  /// バックエンド API のベース URL
  ///
  /// 開発環境: http://localhost:8000
  /// 本番環境: TODO 環境変数やDartのdefineで切り替え
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  /// アップロードタイムアウト（秒）
  static const int uploadTimeoutSeconds = 30;
}
