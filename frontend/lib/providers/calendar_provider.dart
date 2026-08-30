import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/collection_schedule.dart';
import '../services/schedule_service.dart';
import 'region_provider.dart';

/// ScheduleServiceのプロバイダー
final scheduleServiceProvider =
    Provider<ScheduleService>((ref) => ScheduleService());

/// 選択中の日付のStateProvider
///
/// カレンダー画面で選択された日付を保持する。
/// 初期値はnull（未選択状態）。
final selectedDayProvider = StateProvider<DateTime?>((ref) => null);

/// 表示中の月のStateProvider
///
/// カレンダー画面で現在表示中の月を保持する。
/// 初期値は現在の月。
final focusedMonthProvider = StateProvider<DateTime>((ref) => DateTime.now());

/// 月間スケジュールのFutureProvider.family
///
/// 指定月の収集スケジュールを取得する。
/// パラメータとしてDateTimeを受け取り、その年月のスケジュールを返す。
/// regionSettingProviderから地区IDを取得し、ScheduleServiceで月間スケジュールを生成する。
final monthlyScheduleProvider =
    FutureProvider.family<Map<DateTime, List<ScheduleEntry>>, DateTime>(
        (ref, month) async {
  final regionSettingAsync = ref.watch(regionSettingProvider);

  // 地域設定を取得
  final regionSetting = regionSettingAsync.valueOrNull;
  if (regionSetting == null) {
    return {};
  }

  final districtId = regionSetting.districtId;
  final service = ref.watch(scheduleServiceProvider);

  return service.getMonthlySchedule(districtId, month.year, month.month);
});

/// 次回収集予定のFutureProvider
///
/// 今日以降で最も近い収集予定を返す。
/// regionSettingProviderから地区IDを取得し、ScheduleServiceで次回収集日を計算する。
final nextCollectionProvider = FutureProvider<ScheduleEntry?>((ref) async {
  final regionSettingAsync = ref.watch(regionSettingProvider);

  // 地域設定を取得
  final regionSetting = regionSettingAsync.valueOrNull;
  if (regionSetting == null) {
    return null;
  }

  final districtId = regionSetting.districtId;
  final service = ref.watch(scheduleServiceProvider);

  return service.getNextCollection(districtId);
});
