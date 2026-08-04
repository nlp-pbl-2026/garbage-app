import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:permission_handler/permission_handler.dart';

import '../providers/realtime_camera_provider.dart';
import '../widgets/classification_overlay.dart';

/// リアルタイムカメラプレビュー画面
///
/// WidgetsBindingObserver でアプリライフサイクルを監視し、
/// Notifier に状態変更を通知する。状態に応じた UI を描画する。
///
/// 要件1.1: カメラプレビュー表示
/// 要件1.2: 全画面プレビュー
/// 要件1.3: ローディングインジケーター
/// 要件2.4: 権限拒否メッセージ + 設定誘導
/// 要件2.5: 永久拒否メッセージ + 設定誘導
/// 要件4.3: 戻るボタン表示
/// 要件4.4: 戻るボタンで前画面へ戻る
/// 要件6.1: エラーメッセージ表示
/// 要件6.2: カメラ利用不可メッセージ
/// 要件6.3: エラーメッセージ + 再試行ボタン
class RealtimeCameraScreen extends ConsumerStatefulWidget {
  const RealtimeCameraScreen({super.key});

  @override
  ConsumerState<RealtimeCameraScreen> createState() =>
      _RealtimeCameraScreenState();
}

class _RealtimeCameraScreenState extends ConsumerState<RealtimeCameraScreen>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // カメラ初期化を開始
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(realtimeCameraProvider.notifier).initialize();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    ref.read(realtimeCameraProvider.notifier).onLifecycleChanged(state);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(realtimeCameraProvider);

    return Scaffold(
      backgroundColor: Colors.black,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: _buildBody(state),
    );
  }

  /// 状態に応じたボディを構築する
  Widget _buildBody(RealtimeCameraState state) {
    switch (state.status) {
      case RealtimeCameraStatus.loading:
        return _buildLoading();
      case RealtimeCameraStatus.previewing:
        return _buildPreviewing(state);
      case RealtimeCameraStatus.permissionDenied:
        return _buildPermissionDenied();
      case RealtimeCameraStatus.permissionPermanentlyDenied:
        return _buildPermissionPermanentlyDenied();
      case RealtimeCameraStatus.noCameraAvailable:
        return _buildNoCameraAvailable();
      case RealtimeCameraStatus.error:
        return _buildError(state);
    }
  }

  /// loading → CircularProgressIndicator (centered)
  Widget _buildLoading() {
    return const Center(
      child: CircularProgressIndicator(
        color: Colors.white,
      ),
    );
  }

  /// previewing → CameraPreview (full screen) + ClassificationOverlay (Stack overlay)
  Widget _buildPreviewing(RealtimeCameraState state) {
    return Stack(
      fit: StackFit.expand,
      children: [
        CameraPreview(state.controller!),
        const ClassificationOverlay(),
      ],
    );
  }

  /// permissionDenied → メッセージ「カメラのアクセス許可が必要です」 + 「設定を開く」ボタン
  Widget _buildPermissionDenied() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.camera_alt_outlined,
              size: 64,
              color: Colors.white54,
            ),
            const SizedBox(height: 24),
            const Text(
              'カメラのアクセス許可が必要です',
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w500,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () => openAppSettings(),
              child: const Text('設定を開く'),
            ),
          ],
        ),
      ),
    );
  }

  /// permissionPermanentlyDenied → メッセージ「デバイスの設定からカメラの権限を許可してください」 + 「設定を開く」ボタン
  Widget _buildPermissionPermanentlyDenied() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.settings_outlined,
              size: 64,
              color: Colors.white54,
            ),
            const SizedBox(height: 24),
            const Text(
              'デバイスの設定からカメラの権限を許可してください',
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w500,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () => openAppSettings(),
              child: const Text('設定を開く'),
            ),
          ],
        ),
      ),
    );
  }

  /// noCameraAvailable → メッセージ「このデバイスにはカメラがありません」
  Widget _buildNoCameraAvailable() {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.no_photography_outlined,
              size: 64,
              color: Colors.white54,
            ),
            SizedBox(height: 24),
            Text(
              'このデバイスにはカメラがありません',
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w500,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  /// error → エラーメッセージ + 「再試行」ボタン
  Widget _buildError(RealtimeCameraState state) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: Colors.redAccent,
            ),
            const SizedBox(height: 24),
            Text(
              state.errorMessage ?? 'エラーが発生しました',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            ElevatedButton(
              onPressed: () =>
                  ref.read(realtimeCameraProvider.notifier).retry(),
              child: const Text('再試行'),
            ),
          ],
        ),
      ),
    );
  }
}
