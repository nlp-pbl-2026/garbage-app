import 'package:garbage_app/models/gps_detection.dart';

/// バックグラウンド位置変化監視の状態
///
/// sealed class hierarchyにより、状態遷移を型安全に管理する。
/// - Idle: 監視停止中
/// - Active: 監視中（定期チェック実行中）
/// - Prompting: ユーザーに再検出提案を表示中
/// - Cooldown: 提案後のクールダウン期間中
sealed class BackgroundMonitorState {
  const BackgroundMonitorState();
}

/// 監視停止中の状態
class BackgroundMonitorIdle extends BackgroundMonitorState {
  const BackgroundMonitorIdle();

  @override
  String toString() => 'BackgroundMonitorIdle()';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is BackgroundMonitorIdle && runtimeType == other.runtimeType;

  @override
  int get hashCode => runtimeType.hashCode;
}

/// 監視中の状態（定期的に位置チェックを実行）
class BackgroundMonitorActive extends BackgroundMonitorState {
  /// 最後にチェックした座標（初回チェック前はnull）
  final GpsCoordinate? lastCheckedCoordinate;

  /// 最後にチェックした時刻（初回チェック前はnull）
  final DateTime? lastCheckTime;

  const BackgroundMonitorActive({
    this.lastCheckedCoordinate,
    this.lastCheckTime,
  });

  @override
  String toString() =>
      'BackgroundMonitorActive(lastCheckedCoordinate: $lastCheckedCoordinate, '
      'lastCheckTime: $lastCheckTime)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is BackgroundMonitorActive &&
          runtimeType == other.runtimeType &&
          lastCheckedCoordinate == other.lastCheckedCoordinate &&
          lastCheckTime == other.lastCheckTime;

  @override
  int get hashCode => Object.hash(lastCheckedCoordinate, lastCheckTime);
}

/// ユーザーに地域設定更新を提案中の状態
class BackgroundMonitorPrompting extends BackgroundMonitorState {
  /// 基準座標からの距離（km）
  final double distanceKm;

  const BackgroundMonitorPrompting({
    required this.distanceKm,
  });

  @override
  String toString() =>
      'BackgroundMonitorPrompting(distanceKm: $distanceKm)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is BackgroundMonitorPrompting &&
          runtimeType == other.runtimeType &&
          distanceKm == other.distanceKm;

  @override
  int get hashCode => distanceKm.hashCode;
}

/// 提案後のクールダウン期間中の状態（24時間）
class BackgroundMonitorCooldown extends BackgroundMonitorState {
  /// クールダウン終了時刻
  final DateTime cooldownUntil;

  const BackgroundMonitorCooldown({
    required this.cooldownUntil,
  });

  @override
  String toString() =>
      'BackgroundMonitorCooldown(cooldownUntil: $cooldownUntil)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is BackgroundMonitorCooldown &&
          runtimeType == other.runtimeType &&
          cooldownUntil == other.cooldownUntil;

  @override
  int get hashCode => cooldownUntil.hashCode;
}
