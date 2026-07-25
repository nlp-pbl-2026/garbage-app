import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../models/location.dart';
import '../models/location_error.dart';
import '../services/location_service.dart';
import 'region_provider.dart';

/// 位置情報検出のフェーズ
enum LocationDetectionPhase {
  /// 待機中
  idle,

  /// 権限確認中
  checkingPermission,

  /// GPS取得中
  acquiringLocation,

  /// 逆ジオコーディング中
  geocoding,

  /// マッチング中
  matching,

  /// 成功
  success,

  /// エラー
  error,
}

/// 位置情報検出の状態
///
/// 各フェーズに応じたUI表示の切り替えに使用する。
/// isLoadingゲッターにより、ローディング表示の判定が可能。
class LocationDetectionState {
  final LocationDetectionPhase phase;
  final RegionMatchResult? result;
  final LocationError? error;
  final String? message;

  const LocationDetectionState({
    required this.phase,
    this.result,
    this.error,
    this.message,
  });

  /// 待機状態を生成する
  factory LocationDetectionState.idle() =>
      const LocationDetectionState(phase: LocationDetectionPhase.idle);

  /// ローディング状態を生成する
  factory LocationDetectionState.loading(
          LocationDetectionPhase phase, String message) =>
      LocationDetectionState(phase: phase, message: message);

  /// 成功状態を生成する
  factory LocationDetectionState.success(RegionMatchResult result) =>
      LocationDetectionState(
          phase: LocationDetectionPhase.success, result: result);

  /// エラー状態を生成する
  factory LocationDetectionState.error(LocationError error) =>
      LocationDetectionState(
          phase: LocationDetectionPhase.error, error: error);

  /// ローディング中かどうか
  ///
  /// idle、success、error以外のフェーズではtrueを返す。
  bool get isLoading =>
      phase != LocationDetectionPhase.idle &&
      phase != LocationDetectionPhase.success &&
      phase != LocationDetectionPhase.error;
}

/// 位置情報検出のStateNotifier
///
/// LocationServiceを使用してGPS位置情報の取得から地域マッチングまでの
/// 一連の処理を管理し、各フェーズの状態を通知する。
class LocationDetectionNotifier extends StateNotifier<LocationDetectionState> {
  final LocationService _locationService;

  LocationDetectionNotifier(this._locationService)
      : super(LocationDetectionState.idle());

  /// 地域検出処理を開始する
  ///
  /// 権限確認 → GPS取得 → 逆ジオコーディング → マッチング の順に実行し、
  /// 各ステップでフェーズを更新する。エラー発生時はerror状態に遷移する。
  Future<void> detectRegion() async {
    try {
      // 権限確認フェーズ
      state = LocationDetectionState.loading(
          LocationDetectionPhase.checkingPermission, '権限を確認中...');

      // 位置情報サービスの有効確認
      final serviceEnabled =
          await _locationService.isLocationServiceEnabled();
      if (!serviceEnabled) {
        throw const LocationException(type: LocationErrorType.serviceDisabled);
      }

      // 権限確認・リクエスト
      var permission = await _locationService.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await _locationService.requestPermission();
        if (permission == LocationPermission.denied) {
          throw const LocationException(
              type: LocationErrorType.permissionDenied);
        }
      }
      if (permission == LocationPermission.deniedForever) {
        throw const LocationException(
            type: LocationErrorType.permissionDeniedForever);
      }

      // GPS取得フェーズ
      state = LocationDetectionState.loading(
          LocationDetectionPhase.acquiringLocation, '現在地を取得中...');
      final position = await _locationService.getCurrentPosition();

      // 逆ジオコーディングフェーズ
      state = LocationDetectionState.loading(
          LocationDetectionPhase.geocoding, '住所を特定中...');
      final address = await _locationService.reverseGeocode(
          position.latitude, position.longitude);

      // マッチングフェーズ
      state = LocationDetectionState.loading(
          LocationDetectionPhase.matching, '地域データと照合中...');
      final result = await _locationService.matchRegion(address);

      // 成功
      state = LocationDetectionState.success(result);
    } on LocationException catch (e) {
      state = LocationDetectionState.error(e.toLocationError());
    } catch (e) {
      state = LocationDetectionState.error(
          LocationError.fromType(LocationErrorType.gpsUnavailable));
    }
  }

  /// 状態をリセットする
  void reset() {
    state = LocationDetectionState.idle();
  }
}

// --- Riverpod Provider定義 ---

/// LocationServiceのプロバイダー
///
/// RegionServiceをDIしてLocationServiceを生成する。
final locationServiceProvider = Provider<LocationService>((ref) {
  final regionService = ref.watch(regionServiceProvider);
  return LocationService(regionService);
});

/// 位置情報検出の状態管理プロバイダー
///
/// LocationDetectionNotifierをStateNotifierProviderとして公開し、
/// UI層からの状態監視と操作を可能にする。
final locationDetectionProvider =
    StateNotifierProvider<LocationDetectionNotifier, LocationDetectionState>(
        (ref) {
  final locationService = ref.watch(locationServiceProvider);
  return LocationDetectionNotifier(locationService);
});
