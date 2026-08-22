import 'package:flutter/foundation.dart';

/// ローカリゼーションフォールバック使用時のデバッグログユーティリティ
///
/// デバッグ/ステージングビルドでフォールバック翻訳が使用された場合に
/// コンソールへ警告ログを出力する。プロダクションビルドではログ出力しない。
///
/// [fieldName] - フォールバックが発生したフィールド名（例: "name", "disposalMethod"）
/// [itemId] - 対象のアイテムID
/// [targetLanguage] - 翻訳が見つからなかった対象言語コード
void logFallbackUsage(String fieldName, String itemId, String targetLanguage) {
  if (kDebugMode) {
    debugPrint(
      '[i18n FALLBACK] Missing translation: field=$fieldName, '
      'itemId=$itemId, language=$targetLanguage',
    );
  }
}
