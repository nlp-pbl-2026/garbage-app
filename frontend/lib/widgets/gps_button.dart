import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../constants/colors.dart';
import '../models/location_error.dart';
import '../providers/location_provider.dart';

/// GPS位置情報による地域自動設定ボタンウィジェット
///
/// 「現在地から設定」ボタンを表示し、GPS位置情報を使って
/// 都道府県・市区町村を自動検出する機能を提供する。
///
/// 状態に応じて以下のUIを表示する:
/// - 待機中: GPSアイコン + 「現在地から設定」テキストのOutlinedButton
/// - ローディング中: CircularProgressIndicator + メッセージ（非活性化）
/// - エラー時: エラーメッセージカード（canRetryなら再試行、showSettingsなら設定遷移）
/// - 成功時: 緑色チェックマーク + 「現在地から検出しました」メッセージ（2秒間表示）
///
/// 要件5.1, 5.2, 5.3, 5.5, 7.5
class GpsButton extends ConsumerStatefulWidget {
  const GpsButton({super.key});

  @override
  ConsumerState<GpsButton> createState() => _GpsButtonState();
}

class _GpsButtonState extends ConsumerState<GpsButton> {
  /// 成功メッセージ表示中フラグ
  bool _showSuccessMessage = false;

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(locationDetectionProvider);

    // 成功時に2秒間確認メッセージを表示する
    ref.listen<LocationDetectionState>(locationDetectionProvider,
        (previous, next) {
      if (next.phase == LocationDetectionPhase.success) {
        setState(() {
          _showSuccessMessage = true;
        });
        Future.delayed(const Duration(seconds: 2), () {
          if (mounted) {
            setState(() {
              _showSuccessMessage = false;
            });
          }
        });
      }
    });

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // メインボタン
        _buildButton(state),
        // エラー表示エリア
        if (state.phase == LocationDetectionPhase.error && state.error != null)
          _buildErrorCard(state.error!),
        // 成功メッセージ表示エリア
        if (_showSuccessMessage) _buildSuccessMessage(),
      ],
    );
  }

  /// メインのGPSボタンを構築する
  Widget _buildButton(LocationDetectionState state) {
    final isLoading = state.isLoading;

    return OutlinedButton.icon(
      onPressed: isLoading ? null : _onDetect,
      icon: isLoading
          ? const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppColors.primary,
              ),
            )
          : const Icon(Icons.my_location),
      label: Text(
        isLoading ? (state.message ?? '処理中...') : '現在地から設定',
      ),
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.primary,
        side: const BorderSide(color: AppColors.primary),
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
  }

  /// エラーメッセージカードを構築する
  Widget _buildErrorCard(LocationError error) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.red[50],
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.error.withOpacity(0.3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // エラーメッセージ
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.error_outline,
                  size: 18,
                  color: Colors.red[700],
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    error.userMessage,
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.red[700],
                    ),
                  ),
                ),
              ],
            ),
            // アクションボタン
            if (error.canRetry || error.showSettings)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    // 再試行ボタン
                    if (error.canRetry)
                      TextButton.icon(
                        onPressed: _onRetry,
                        icon: const Icon(Icons.refresh, size: 16),
                        label: const Text('再試行'),
                        style: TextButton.styleFrom(
                          foregroundColor: AppColors.primary,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 4,
                          ),
                        ),
                      ),
                    // 設定を開くボタン
                    if (error.showSettings)
                      TextButton.icon(
                        onPressed: _onOpenSettings,
                        icon: const Icon(Icons.settings, size: 16),
                        label: const Text('設定を開く'),
                        style: TextButton.styleFrom(
                          foregroundColor: AppColors.primary,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 4,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// 成功メッセージを構築する
  Widget _buildSuccessMessage() {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.check_circle,
            size: 18,
            color: AppColors.primary,
          ),
          const SizedBox(width: 6),
          Text(
            '現在地から検出しました',
            style: TextStyle(
              fontSize: 13,
              color: AppColors.primary,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  /// GPS検出を実行する
  void _onDetect() {
    ref.read(locationDetectionProvider.notifier).detectRegion();
  }

  /// リトライ処理
  void _onRetry() {
    ref.read(locationDetectionProvider.notifier).detectRegion();
  }

  /// 設定画面を開く
  void _onOpenSettings() {
    Geolocator.openAppSettings();
  }
}
