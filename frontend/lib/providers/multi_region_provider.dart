import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/region.dart';
import '../services/multi_region_service.dart';
import '../services/notification_service.dart';
import 'region_provider.dart';
import 'settings_provider.dart';

/// MultiRegionServiceのプロバイダー
final multiRegionServiceProvider = Provider<MultiRegionService>((ref) {
  return MultiRegionService();
});

/// 複数地区管理のStateNotifierProvider
///
/// SavedRegionリストを管理し、地区の追加・削除・切り替えを提供する。
/// アクティブ地区が変更された場合、regionSettingProviderと通知スケジュールも更新する。
final multiRegionProvider =
    StateNotifierProvider<MultiRegionNotifier, AsyncValue<List<SavedRegion>>>(
  (ref) {
    final service = ref.watch(multiRegionServiceProvider);
    final notificationService = ref.watch(notificationServiceProvider);
    return MultiRegionNotifier(ref, service, notificationService);
  },
);

/// 複数地区管理のStateNotifier
class MultiRegionNotifier
    extends StateNotifier<AsyncValue<List<SavedRegion>>> {
  final Ref _ref;
  final MultiRegionService _service;
  final NotificationService _notificationService;

  MultiRegionNotifier(this._ref, this._service, this._notificationService)
      : super(const AsyncValue.loading()) {
    loadRegions();
  }

  /// 保存済み地区リストを読み込む
  Future<void> loadRegions() async {
    state = const AsyncValue.loading();
    try {
      final regions = await _service.getSavedRegions();
      state = AsyncValue.data(regions);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// 新しい地区を追加する
  ///
  /// [label] ユーザーが付けるラベル
  /// [setting] 追加する地域設定
  ///
  /// 追加後に地区リストを再読み込みする。
  /// 最初の地区の場合はregionSettingProviderも更新する。
  Future<void> addRegion(String label, RegionSetting setting) async {
    try {
      final newRegion = await _service.addRegion(label, setting);
      if (newRegion.isActive) {
        await _applyActiveRegion(newRegion.setting);
      }
      await loadRegions();
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// 地区を削除する
  ///
  /// [id] 削除する地区のID
  ///
  /// アクティブ地区が削除された場合、新しいアクティブ地区で
  /// regionSettingProviderと通知スケジュールを更新する。
  Future<void> removeRegion(String id) async {
    try {
      final currentRegions = state.valueOrNull ?? [];
      final removedRegion = currentRegions.where((r) => r.id == id).firstOrNull;
      final wasActive = removedRegion?.isActive ?? false;

      await _service.removeRegion(id);
      await loadRegions();

      // アクティブ地区が削除された場合、新しいアクティブ地区を適用
      if (wasActive) {
        final activeRegion = await _service.getActiveRegion();
        if (activeRegion != null) {
          await _applyActiveRegion(activeRegion.setting);
        }
      }
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// アクティブな地区を切り替える
  ///
  /// [id] アクティブに設定する地区のID
  ///
  /// regionSettingProviderを更新し、通知スケジュールを再計算する。
  Future<void> setActiveRegion(String id) async {
    try {
      final activeRegion = await _service.setActiveRegion(id);
      if (activeRegion != null) {
        await _applyActiveRegion(activeRegion.setting);
      }
      await loadRegions();
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// アクティブ地区の設定をregionSettingProviderと通知に反映する
  Future<void> _applyActiveRegion(RegionSetting setting) async {
    // regionSettingProviderを更新
    await _ref.read(regionSettingProvider.notifier).saveSetting(setting);

    // 通知スケジュールを再計算
    await _notificationService.refreshNotifications();
  }
}
