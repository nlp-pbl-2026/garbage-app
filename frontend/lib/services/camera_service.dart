import 'package:camera/camera.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// カメラ制御サービス
///
/// Flutter `camera` パッケージの [CameraController] の生成・初期化・破棄を
/// 抽象化するラッパーサービス。テスト時にモックを注入可能にするため、
/// Riverpod Provider 経由で提供する。
class CameraService {
  /// 利用可能なカメラ一覧を取得する。
  ///
  /// デバイスに搭載されているすべてのカメラの [CameraDescription] リストを返す。
  /// カメラが見つからない場合は空リストを返す。
  Future<List<CameraDescription>> getAvailableCameras() async {
    return await availableCameras();
  }

  /// [CameraController] を生成する。
  ///
  /// 指定された [camera] と [preset] に基づいてコントローラーを作成する。
  /// 生成後は [initializeController] を呼び出して初期化する必要がある。
  CameraController createController(
    CameraDescription camera,
    ResolutionPreset preset,
  ) {
    return CameraController(camera, preset);
  }

  /// [CameraController] を初期化する。
  ///
  /// コントローラーの初期化処理を実行し、カメラプレビューの準備を完了する。
  /// 初期化に失敗した場合は [CameraException] がスローされる。
  Future<void> initializeController(CameraController controller) async {
    await controller.initialize();
  }

  /// カメラプレビューを一時停止する。
  ///
  /// アプリがバックグラウンドに移行した際などに呼び出し、
  /// カメラリソースの消費を抑える。
  Future<void> pausePreview(CameraController controller) async {
    if (controller.value.isInitialized) {
      await controller.pausePreview();
    }
  }

  /// カメラプレビューを再開する。
  ///
  /// アプリがフォアグラウンドに復帰した際などに呼び出し、
  /// カメラプレビューの表示を再開する。
  Future<void> resumePreview(CameraController controller) async {
    if (controller.value.isInitialized) {
      await controller.resumePreview();
    }
  }

  /// [CameraController] を破棄してリソースを解放する。
  ///
  /// 画面破棄時やカメラ使用終了時に呼び出し、
  /// カメラリソースを完全に解放する。
  void disposeController(CameraController controller) {
    controller.dispose();
  }
}

/// CameraService プロバイダー
///
/// テスト時に `overrideWithValue` でモックを注入可能。
final cameraServiceProvider = Provider<CameraService>(
  (ref) => CameraService(),
);
