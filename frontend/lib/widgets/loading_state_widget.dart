import 'package:flutter/material.dart';

/// ローディング状態表示用の統一ウィジェット
///
/// AsyncValueパターンのloading状態で使用する。
/// CircularProgressIndicatorとオプションのメッセージを統一的なレイアウトで表示する。
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
/// メッセージ付き:
/// ```dart
/// loading: () => const LoadingStateWidget(message: '地域データを読み込み中...'),
/// ```
class LoadingStateWidget extends StatelessWidget {
  /// 表示するローディングメッセージ（オプション）
  final String? message;

  const LoadingStateWidget({
    super.key,
    this.message,
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
            // ローディングインジケーター
            const CircularProgressIndicator(),
            // メッセージがある場合は表示
            if (message != null) ...[
              const SizedBox(height: 16),
              Text(
                message!,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.grey[600],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
