import 'dart:async';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/background_monitor_state.dart';
import '../models/gps_detection.dart';
import '../services/abstract_location_service.dart';
import 'gps_detection_provider.dart';

/// バックグラウンド位置変化監視のStateNotifier。
///
/// アプリがフォアグラウンドにある間、定期的にGPS座標を取得し、
/// 基準座標（地区設定時の座標）からの距離変化を検出する。
/// 2km以上の移動が検出され、かつ24時間のクールダウンが経過している場合、
/// ユーザーに地域設定の更新を提案する。
///
/// 呼び出し元がアプリのライフサイクル（フォアグラウンド/バックグラウンド）に
/// 応じてstartMonitoring/stopMonitoringを制御する責務を持つ。
class BackgroundLocationMonitor
    extends StateNotifier<BackgroundMonitorState> {
  /// 再検出提案のトリガー距離（km）
  static const double triggerDistanceKm = 2.0;

  /// 提案後のクールダウン期間（24時間）
  static const Duration cooldownDuration = Duration(hours: 24);

  /// 位置チェックの最小間隔（30分）
  static const Duration minCheckInterval = Duration(minutes: 30);

  /// 位置チェックの最大間隔（60分）
  static const Duration maxCheckInterval = Duration(minutes: 60);

  /// 地球の平均半径（km）
  static const double _earthRadiusKm = 6371.0;

  final AbstractLocationService _locationService;
  final GpsDetectionNotifier _gpsDetectionNotifier;
  final GpsCoordinate _referenceCoordinate;

  Timer? _checkTimer;
  DateTime? _lastPromptTime;

  /// テスト用にクロックを注入できるようにするためのコールバック。
  /// デフォルトはDateTime.now()を返す。
  DateTime Function() clock;

  BackgroundLocationMonitor({
    required AbstractLocationService locationService,
    required GpsDetectionNotifier gpsDetectionNotifier,
    required GpsCoordinate referenceCoordinate,
    DateTime Function()? clock,
  })  : _locationService = locationService,
        _gpsDetectionNotifier = gpsDetectionNotifier,
        _referenceCoordinate = referenceCoordinate,
        clock = clock ?? DateTime.now,
        super(const BackgroundMonitorIdle());

  /// 位置監視を開始する。
  ///
  /// 30〜60分の間隔で定期的にGPS座標を取得し、
  /// 基準座標との距離を計算する。
  /// フォアグラウンド時のみ動作し、呼び出し元がライフサイクル管理を行う。
  void startMonitoring() {
    if (state is BackgroundMonitorActive) return;

    // クールダウン中の場合はActiveに遷移するが、チェック時にクールダウンを考慮する
    state = const BackgroundMonitorActive();

    _scheduleNextCheck();
  }

  /// 位置監視を停止する。
  ///
  /// タイマーをキャンセルし、Idle状態に遷移する。
  void stopMonitoring() {
    _checkTimer?.cancel();
    _checkTimer = null;
    state = const BackgroundMonitorIdle();
  }

  /// ユーザーが「更新する」を選択した場合のハンドラ。
  ///
  /// GPS地区判定フローを開始し、完了後にActive状態に戻る。
  Future<void> acceptUpdate() async {
    await _gpsDetectionNotifier.detectDistrict();
    state = const BackgroundMonitorActive();
    _scheduleNextCheck();
  }

  /// ユーザーが「後で」を選択（または暗黙的にdismiss）した場合のハンドラ。
  ///
  /// 24時間のクールダウンを設定し、監視を継続する。
  void dismissPrompt() {
    final now = clock();
    _lastPromptTime = now;
    state = BackgroundMonitorCooldown(
      cooldownUntil: now.add(cooldownDuration),
    );

    // クールダウン後にActiveに戻すためにタイマーを再スケジュール
    _scheduleNextCheck();
  }

  /// 次の位置チェックをスケジュールする。
  ///
  /// 30〜60分のランダムな間隔でタイマーを設定する。
  void _scheduleNextCheck() {
    _checkTimer?.cancel();
    final interval = _calculateCheckInterval();
    _checkTimer = Timer(interval, _performCheck);
  }

  /// 30〜60分のランダムな間隔を計算する。
  Duration _calculateCheckInterval() {
    final random = Random();
    final minMs = minCheckInterval.inMilliseconds;
    final maxMs = maxCheckInterval.inMilliseconds;
    final intervalMs = minMs + random.nextInt(maxMs - minMs);
    return Duration(milliseconds: intervalMs);
  }

  /// 定期チェックを実行する。
  ///
  /// 現在の位置を取得し、基準座標との距離を計算。
  /// 距離が2km以上でクールダウン期間外であれば、Prompting状態に遷移する。
  Future<void> _performCheck() async {
    try {
      final currentPosition = await _locationService.getCurrentPosition();
      final now = clock();

      final distanceKm = calculateHaversineDistanceKm(
        _referenceCoordinate.latitude,
        _referenceCoordinate.longitude,
        currentPosition.latitude,
        currentPosition.longitude,
      );

      // 状態をActiveに更新（最終チェック情報を記録）
      state = BackgroundMonitorActive(
        lastCheckedCoordinate: currentPosition,
        lastCheckTime: now,
      );

      // 距離が閾値以上かチェック
      if (distanceKm >= triggerDistanceKm) {
        // クールダウン中かチェック
        if (_isInCooldown(now)) {
          // クールダウン中なので次のチェックをスケジュールするのみ
          _scheduleNextCheck();
          return;
        }

        // プロンプト表示条件を満たす
        _lastPromptTime = now;
        state = BackgroundMonitorPrompting(distanceKm: distanceKm);
        // プロンプト表示中はタイマーを停止（ユーザーアクションを待つ）
        return;
      }

      // 距離が閾値未満 → 次のチェックをスケジュール
      _scheduleNextCheck();
    } catch (_) {
      // 位置取得失敗時は静かに次のチェックまで待機（Req 10エラーハンドリング方針）
      _scheduleNextCheck();
    }
  }

  /// 現在がクールダウン期間中かどうか判定する。
  ///
  /// 前回のプロンプトから24時間未満の場合はtrue。
  /// 前回のプロンプトがない（初回）場合はfalse。
  bool _isInCooldown(DateTime now) {
    if (_lastPromptTime == null) return false;
    return now.difference(_lastPromptTime!) < cooldownDuration;
  }

  /// Haversine公式による2点間の距離（km）を計算する。
  ///
  /// [lat1], [lng1]: 1点目の緯度・経度（度数法）
  /// [lat2], [lng2]: 2点目の緯度・経度（度数法）
  /// 戻り値: 2点間の大圏距離（km）
  static double calculateHaversineDistanceKm(
    double lat1,
    double lng1,
    double lat2,
    double lng2,
  ) {
    final lat1Rad = _toRadians(lat1);
    final lat2Rad = _toRadians(lat2);
    final deltaLat = _toRadians(lat2 - lat1);
    final deltaLng = _toRadians(lng2 - lng1);

    final a = sin(deltaLat / 2) * sin(deltaLat / 2) +
        cos(lat1Rad) * cos(lat2Rad) * sin(deltaLng / 2) * sin(deltaLng / 2);
    final c = 2 * atan2(sqrt(a), sqrt(1 - a));

    return _earthRadiusKm * c;
  }

  static double _toRadians(double degrees) => degrees * pi / 180.0;

  @override
  void dispose() {
    _checkTimer?.cancel();
    super.dispose();
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

/// BackgroundLocationMonitorの基準座標プロバイダー。
///
/// 地区が設定された時の座標を保持する。
/// 呼び出し元がこの値を設定した後にbackgroundLocationMonitorProviderを使用する。
final referenceCoordinateProvider = StateProvider<GpsCoordinate?>(
  (ref) => null,
);

/// BackgroundLocationMonitorのStateNotifierProvider。
///
/// referenceCoordinateが設定されている場合のみモニターを生成する。
/// referenceCoordinateがnullの場合はIdle状態のモニターを返す。
final backgroundLocationMonitorProvider = StateNotifierProvider<
    BackgroundLocationMonitor, BackgroundMonitorState>((ref) {
  final locationService = ref.watch(gpsLocationServiceProvider);
  final gpsDetectionNotifier = ref.watch(gpsDetectionProvider.notifier);
  final referenceCoordinate = ref.watch(referenceCoordinateProvider);

  return BackgroundLocationMonitor(
    locationService: locationService,
    gpsDetectionNotifier: gpsDetectionNotifier,
    referenceCoordinate: referenceCoordinate ??
        const GpsCoordinate(latitude: 0, longitude: 0, accuracy: 0),
  );
});
