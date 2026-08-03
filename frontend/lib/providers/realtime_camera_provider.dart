import 'package:camera/camera.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:permission_handler/permission_handler.dart';

import '../services/camera_service.dart';

/// リアルタイムカメラ画面の状態ステータス
enum RealtimeCameraStatus {
  /// 初期化中（権限確認・カメラ準備）
  loading,

  /// カメラプレビュー表示中
  previewing,

  /// 権限拒否（通常）
  permissionDenied,

  /// 権限永久拒否（「今後表示しない」で拒否）
  permissionPermanentlyDenied,

  /// エラー発生
  error,

  /// デバイスにカメラなし
  noCameraAvailable,
}

/// リアルタイムカメラ画面の状態
class RealtimeCameraState {
  final RealtimeCameraStatus status;
  final CameraController? controller;
  final String? errorMessage;

  const RealtimeCameraState({
    this.status = RealtimeCameraStatus.loading,
    this.controller,
    this.errorMessage,
  });

  RealtimeCameraState copyWith({
    RealtimeCameraStatus? status,
    CameraController? controller,
    String? errorMessage,
  }) {
    return RealtimeCameraState(
      status: status ?? this.status,
      controller: controller ?? this.controller,
      errorMessage: errorMessage,
    );
  }
}

/// カメラ状態を管理するStateNotifier
///
/// 権限チェック → 初期化 → プレビュー → エラーの状態遷移を制御する。
/// CameraService を介してカメラリソースを管理し、
/// ライフサイクルイベントに応じてリソースの解放・再取得を行う。
class RealtimeCameraNotifier extends StateNotifier<RealtimeCameraState> {
  final CameraService _cameraService;

  RealtimeCameraNotifier({
    required CameraService cameraService,
  })  : _cameraService = cameraService,
        super(const RealtimeCameraState());

  /// 権限確認 → カメラ初期化 → previewing 遷移
  ///
  /// 1. カメラ権限の状態を確認し、未許可ならリクエスト
  /// 2. 権限が許可されたらカメラを初期化
  /// 3. 正常に初期化できたら previewing 状態へ遷移
  Future<void> initialize() async {
    state = const RealtimeCameraState(status: RealtimeCameraStatus.loading);

    try {
      // 権限確認
      final permissionStatus = await Permission.camera.status;

      if (permissionStatus.isGranted) {
        await _initializeCamera();
        return;
      }

      if (permissionStatus.isPermanentlyDenied) {
        state = const RealtimeCameraState(
          status: RealtimeCameraStatus.permissionPermanentlyDenied,
        );
        return;
      }

      // 権限リクエスト
      final result = await Permission.camera.request();

      if (result.isGranted) {
        await _initializeCamera();
      } else if (result.isPermanentlyDenied) {
        state = const RealtimeCameraState(
          status: RealtimeCameraStatus.permissionPermanentlyDenied,
        );
      } else {
        state = const RealtimeCameraState(
          status: RealtimeCameraStatus.permissionDenied,
        );
      }
    } catch (e) {
      state = RealtimeCameraState(
        status: RealtimeCameraStatus.error,
        errorMessage: 'カメラの起動に失敗しました: ${e.toString()}',
      );
    }
  }

  /// カメラを初期化する内部メソッド
  Future<void> _initializeCamera() async {
    try {
      final cameras = await _cameraService.getAvailableCameras();

      if (cameras.isEmpty) {
        state = const RealtimeCameraState(
          status: RealtimeCameraStatus.noCameraAvailable,
        );
        return;
      }

      // 背面カメラを優先的に選択
      final backCamera = cameras.firstWhere(
        (camera) => camera.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );

      final controller = _cameraService.createController(
        backCamera,
        ResolutionPreset.high,
      );

      await _cameraService.initializeController(controller);

      // mounted チェック（dispose 後に状態を更新しない）
      if (!mounted) {
        _cameraService.disposeController(controller);
        return;
      }

      state = RealtimeCameraState(
        status: RealtimeCameraStatus.previewing,
        controller: controller,
      );
    } on CameraException catch (e) {
      if (!mounted) return;
      state = RealtimeCameraState(
        status: RealtimeCameraStatus.error,
        errorMessage: 'カメラエラー: ${e.description ?? e.toString()}',
      );
    } catch (e) {
      if (!mounted) return;
      state = RealtimeCameraState(
        status: RealtimeCameraStatus.error,
        errorMessage: 'カメラの起動に失敗しました: ${e.toString()}',
      );
    }
  }

  /// エラー時の再初期化
  ///
  /// 現在の状態に関わらず、既存のコントローラーを破棄して
  /// initialize() を再実行する。
  Future<void> retry() async {
    await _disposeCurrentController();
    await initialize();
  }

  /// アプリライフサイクル変更時の処理
  ///
  /// - resumed: カメラを再初期化
  /// - paused/inactive/detached/hidden: リソースを解放
  void onLifecycleChanged(AppLifecycleState lifecycleState) {
    switch (lifecycleState) {
      case AppLifecycleState.resumed:
        _handleResumed();
        break;
      case AppLifecycleState.paused:
      case AppLifecycleState.inactive:
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
        _handleNonResumed();
        break;
    }
  }

  /// アプリがフォアグラウンドに復帰した時の処理
  void _handleResumed() {
    // previewing 状態でなければ再初期化を試みる
    if (state.status != RealtimeCameraStatus.previewing) {
      initialize();
    }
  }

  /// アプリがバックグラウンドに移行した時の処理
  void _handleNonResumed() {
    if (state.status == RealtimeCameraStatus.previewing &&
        state.controller != null) {
      _cameraService.disposeController(state.controller!);
      state = const RealtimeCameraState(status: RealtimeCameraStatus.loading);
    }
  }

  /// 現在のコントローラーを破棄する
  Future<void> _disposeCurrentController() async {
    if (state.controller != null) {
      _cameraService.disposeController(state.controller!);
    }
  }

  /// リソースを完全に解放する
  @override
  void dispose() {
    if (state.controller != null) {
      _cameraService.disposeController(state.controller!);
    }
    super.dispose();
  }
}

/// リアルタイムカメラ状態管理プロバイダー
final realtimeCameraProvider =
    StateNotifierProvider<RealtimeCameraNotifier, RealtimeCameraState>((ref) {
  return RealtimeCameraNotifier(
    cameraService: ref.watch(cameraServiceProvider),
  );
});
