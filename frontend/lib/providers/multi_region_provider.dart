export 'municipality_provider.dart' show municipalityDataProvider;
import 'municipality_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/region.dart';
import '../services/multi_region_service.dart';
import '../services/municipality_data_service.dart';
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
    final municipalityData = ref.watch(municipalityDataProvider);
    return MultiRegionNotifier(ref, service, notificationService, municipalityData);
  },
);

/// 複数地区管理のStateNotifier
class MultiRegionNotifier extends StateNotifier<AsyncValue<List<SavedRegion>>> {
  final Ref _ref;
  final MultiRegionService _service;
  final NotificationService _notificationService;
  final MunicipalityDataService _municipalityData;

  MultiRegionNotifier(this._ref, this._service, this._notificationService, this._municipalityData)
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
  Future<SavedRegion?> addRegion(String label, RegionSetting setting) async {
    try {
      final newRegion = await _service.addRegion(label, setting);
      if (newRegion.isActive) {
        await _applyActiveRegion(newRegion.setting);
      }
      await loadRegions();
      return newRegion;
    } catch (e, st) {
      state = AsyncValue.error(e, st);
      return null;
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
        SavedRegion? fallback;
        for (final candidate in await _service.getSavedRegions()) {
          if (await _municipalityData.area(candidate.setting.districtId,
                  municipalityId: candidate.setting.municipalityId) !=
              null) {
            fallback = candidate;
            break;
          }
        }
        if (fallback != null) {
          await setActiveRegion(fallback.id);
        } else {
          await _service.clearActiveRegion();
          await loadRegions();
          await _ref.read(regionSettingProvider.notifier).clearSetting();
          await _notificationService.updateDistrict('');
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
      final saved = (await _service.getSavedRegions())
          .where((region) => region.id == id)
          .firstOrNull;
      final area = saved == null
          ? null
          : await _municipalityData.area(saved.setting.districtId,
              municipalityId: saved.setting.municipalityId);
      if (saved == null || area == null) {
        throw StateError('保存された収集地区を再選択してください。');
      }
      if (area['id'] != saved.setting.districtId) {
        await _service.replaceRegionSetting(id, RegionSetting(
          prefectureId: saved.setting.prefectureId,
          prefectureName: saved.setting.prefectureName,
          municipalityId: saved.setting.municipalityId,
          municipalityName: saved.setting.municipalityName,
          districtId: area['id'] as String,
          districtName: area['name'] as String,
        ));
      }
      final activeRegion = await _service.setActiveRegion(id);
      if (activeRegion != null) {
        await _applyActiveRegion(activeRegion.setting);
      }
      await loadRegions();
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> replaceRegionSetting(String id, RegionSetting setting) async {
    final updated = await _service.replaceRegionSetting(id, setting);
    if (updated?.isActive == true) await _applyActiveRegion(setting);
    await loadRegions();
  }

  /// アクティブ地区の設定をregionSettingProviderと通知に反映する
  Future<void> _applyActiveRegion(RegionSetting setting) async {
    // regionSettingProviderを更新
    await _ref.read(regionSettingProvider.notifier).saveSetting(setting);

    // 通知側にも新しいDistrict_IDを反映し、通知スケジュールを再計算する（要件 1.6, 3.7）
    await _notificationService.updateDistrict(setting.districtId,
        municipalityId: setting.municipalityId);
  }
}
