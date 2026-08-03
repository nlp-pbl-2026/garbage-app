import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../providers/image_input_provider.dart';
import '../widgets/region_header.dart';
import 'realtime_camera_screen.dart';
import 'region_selection_screen.dart';

/// 画像入力画面
///
/// カメラ撮影またはギャラリーから画像を取得し、プレビュー確認後に
/// バックエンドへアップロードする。状態に応じてUIを切り替える。
///
/// - 初期状態: カメラボタン + ギャラリーボタン表示
/// - カメラ非搭載時: カメラボタンを非活性に
/// - プレビュー状態: 画像表示 + 送信ボタン + やり直しボタン
/// - アップロード中: ローディングインジケーター + 送信ボタン非活性
/// - 成功状態: 成功メッセージ表示 → 自動リセット（2秒後）
/// - エラー状態: エラーメッセージ + 再送信ボタン
class ImageInputScreen extends ConsumerStatefulWidget {
  const ImageInputScreen({super.key});

  @override
  ConsumerState<ImageInputScreen> createState() => _ImageInputScreenState();
}

class _ImageInputScreenState extends ConsumerState<ImageInputScreen> {
  Timer? _resetTimer;

  @override
  void dispose() {
    _resetTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(imageInputProvider);

    // 成功状態になったら2秒後に自動リセット
    ref.listen<ImageInputState>(imageInputProvider, (previous, next) {
      if (next.status == ImageInputStatus.success) {
        _resetTimer?.cancel();
        _resetTimer = Timer(const Duration(seconds: 2), () {
          if (mounted) {
            ref.read(imageInputProvider.notifier).reset();
          }
        });
      }
    });

    return Scaffold(
      appBar: RegionHeader(
        onEditPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => RegionSelectionScreen(
                onRegionSelected: () {
                  Navigator.of(context).pop();
                },
              ),
            ),
          );
        },
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: _buildBody(state),
        ),
      ),
    );
  }

  /// 状態に応じたボディを構築する
  Widget _buildBody(ImageInputState state) {
    switch (state.status) {
      case ImageInputStatus.initial:
        return _buildInitialState(state);
      case ImageInputStatus.previewing:
        return _buildPreviewState(state);
      case ImageInputStatus.uploading:
        return _buildUploadingState(state);
      case ImageInputStatus.success:
        return _buildSuccessState();
      case ImageInputStatus.error:
        return _buildErrorState(state);
    }
  }

  /// 初期状態：カメラボタン + ギャラリーボタン
  Widget _buildInitialState(ImageInputState state) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.image_outlined,
            size: 80,
            color: Colors.grey[400],
          ),
          const SizedBox(height: 24),
          Text(
            '画像を選択してください',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w500,
              color: Colors.grey[700],
            ),
          ),
          const SizedBox(height: 48),
          // カメラボタン
          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton.icon(
              onPressed: state.isCameraAvailable
                  ? () =>
                      ref.read(imageInputProvider.notifier).pickFromCamera()
                  : null,
              icon: const Icon(Icons.camera_alt),
              label: const Text('カメラで撮影'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                disabledBackgroundColor: Colors.grey[300],
                disabledForegroundColor: Colors.grey[500],
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                textStyle: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          // ギャラリーボタン
          SizedBox(
            width: double.infinity,
            height: 56,
            child: OutlinedButton.icon(
              onPressed: () =>
                  ref.read(imageInputProvider.notifier).pickFromGallery(),
              icon: const Icon(Icons.photo_library),
              label: const Text('ギャラリーから選択'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.primary,
                side: const BorderSide(color: AppColors.primary),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                textStyle: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          // リアルタイムカメラボタン
          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton.icon(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => const RealtimeCameraScreen(),
                  ),
                );
              },
              icon: const Icon(Icons.videocam),
              label: const Text('リアルタイムカメラ'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.deepOrange,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                textStyle: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          if (!state.isCameraAvailable) ...[
            const SizedBox(height: 12),
            Text(
              'このデバイスにはカメラがありません',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey[500],
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// プレビュー状態：画像表示 + 送信ボタン + やり直しボタン
  Widget _buildPreviewState(ImageInputState state) {
    return Column(
      children: [
        // 画像プレビュー
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.file(
              File(state.selectedImage!.path),
              fit: BoxFit.contain,
              width: double.infinity,
            ),
          ),
        ),
        const SizedBox(height: 24),
        // 送信ボタン
        SizedBox(
          width: double.infinity,
          height: 52,
          child: ElevatedButton.icon(
            onPressed: () =>
                ref.read(imageInputProvider.notifier).uploadImage(),
            icon: const Icon(Icons.upload),
            label: const Text('送信'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              textStyle: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        // やり直しボタン
        SizedBox(
          width: double.infinity,
          height: 52,
          child: OutlinedButton.icon(
            onPressed: () => ref.read(imageInputProvider.notifier).reset(),
            icon: const Icon(Icons.refresh),
            label: const Text('やり直し'),
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.grey[700],
              side: BorderSide(color: Colors.grey[400]!),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              textStyle: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ],
    );
  }

  /// アップロード中：ローディングインジケーター + 送信ボタン非活性
  Widget _buildUploadingState(ImageInputState state) {
    return Column(
      children: [
        // 画像プレビュー（薄暗く）
        Expanded(
          child: Stack(
            alignment: Alignment.center,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Opacity(
                  opacity: 0.5,
                  child: Image.file(
                    File(state.selectedImage!.path),
                    fit: BoxFit.contain,
                    width: double.infinity,
                  ),
                ),
              ),
              const CircularProgressIndicator(
                color: AppColors.primary,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Text(
          'アップロード中...',
          style: TextStyle(
            fontSize: 14,
            color: Colors.grey[600],
          ),
        ),
        const SizedBox(height: 24),
        // 送信ボタン（非活性）
        SizedBox(
          width: double.infinity,
          height: 52,
          child: ElevatedButton.icon(
            onPressed: null,
            icon: const Icon(Icons.upload),
            label: const Text('送信'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              disabledBackgroundColor: Colors.grey[300],
              disabledForegroundColor: Colors.grey[500],
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              textStyle: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
      ],
    );
  }

  /// 成功状態：成功メッセージ表示
  Widget _buildSuccessState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.check_circle,
            size: 80,
            color: AppColors.primary,
          ),
          const SizedBox(height: 24),
          const Text(
            'アップロードが完了しました',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            '画像が正常に送信されました',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[600],
            ),
          ),
        ],
      ),
    );
  }

  /// エラー状態：エラーメッセージ + 再送信ボタン
  Widget _buildErrorState(ImageInputState state) {
    final hasImage = state.selectedImage != null;

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.error_outline,
            size: 64,
            color: AppColors.error,
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.red[50],
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.error.withValues(alpha: 0.3)),
            ),
            child: Text(
              state.errorMessage ?? 'エラーが発生しました',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 14,
                color: AppColors.error,
              ),
            ),
          ),
          const SizedBox(height: 32),
          if (hasImage) ...[
            // 再送信ボタン（画像がある場合＝アップロード失敗時）
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton.icon(
                onPressed: () =>
                    ref.read(imageInputProvider.notifier).uploadImage(),
                icon: const Icon(Icons.refresh),
                label: const Text('再送信'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  textStyle: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],
          // やり直しボタン（初期状態に戻す）
          SizedBox(
            width: double.infinity,
            height: 52,
            child: OutlinedButton.icon(
              onPressed: () => ref.read(imageInputProvider.notifier).reset(),
              icon: const Icon(Icons.arrow_back),
              label: const Text('やり直し'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.grey[700],
                side: BorderSide(color: Colors.grey[400]!),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                textStyle: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
