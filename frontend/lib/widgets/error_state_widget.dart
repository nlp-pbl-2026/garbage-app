import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';

/// エラー状態表示用の統一ウィジェット
///
/// AsyncValueパターンのerror状態で使用する。
/// エラーメッセージと再試行ボタンを統一的なレイアウトで表示する。
///
/// 使用例:
/// ```dart
/// someProvider.when(
///   data: (data) => DataWidget(data),
///   loading: () => const LoadingStateWidget(),
///   error: (error, stack) => ErrorStateWidget(
///     message: AppLocalizations.of(context).dataLoadError,
///     onRetry: () => ref.refresh(someProvider),
///   ),
/// );
/// ```
///
/// 要件1.6: データ取得失敗時のエラーメッセージと再試行ボタン
/// 要件10.4: ネットワーク接続復旧後のデータ同期失敗時の再試行
/// 要件10.5: オフライン状態でキャッシュデータがない場合のメッセージ表示
class ErrorStateWidget extends StatelessWidget {
  /// 表示するエラーメッセージ
  final String message;

  /// 再試行ボタン押下時のコールバック
  final VoidCallback onRetry;

  /// エラーアイコン（デフォルト: error_outline）
  final IconData icon;

  const ErrorStateWidget({
    super.key,
    required this.message,
    required this.onRetry,
    this.icon = Icons.error_outline,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            // エラーアイコン
            Icon(
              icon,
              size: 48,
              color: Colors.red[300],
            ),
            const SizedBox(height: 16),
            // エラーメッセージ
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[700],
              ),
            ),
            const SizedBox(height: 16),
            // 再試行ボタン
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 18),
              label: Text(AppLocalizations.of(context).retry),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 12,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
