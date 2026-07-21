import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/region.dart';
import '../services/region_service.dart';

/// RegionServiceのプロバイダー
final regionServiceProvider = Provider<RegionService>((ref) => RegionService());

/// 地域設定の状態管理プロバイダー
///
/// SharedPreferencesから地域設定を読み込み・保存する。
/// AsyncValueで非同期状態（ローディング・データ・エラー）を管理する。
final regionSettingProvider =
    StateNotifierProvider<RegionSettingNotifier, AsyncValue<RegionSetting?>>(
  (ref) {
    final service = ref.watch(regionServiceProvider);
    return RegionSettingNotifier(service);
  },
);

/// 都道府県一覧を取得するプロバイダー
final prefecturesProvider = FutureProvider<List<Prefecture>>((ref) {
  final service = ref.watch(regionServiceProvider);
  return service.getPrefectures();
});

/// 指定された都道府県IDに属する市区町村一覧を取得するプロバイダー
final municipalitiesProvider =
    FutureProvider.family<List<Municipality>, String>((ref, prefectureId) {
  final service = ref.watch(regionServiceProvider);
  return service.getMunicipalities(prefectureId);
});

/// 指定された市区町村IDに属する地区一覧を取得するプロバイダー
final districtsProvider =
    FutureProvider.family<List<District>, String>((ref, municipalityId) {
  final service = ref.watch(regionServiceProvider);
  return service.getDistricts(municipalityId);
});

/// 地域設定のStateNotifier
///
/// 地域設定の読み込み・保存・バリデーションを管理する。
class RegionSettingNotifier extends StateNotifier<AsyncValue<RegionSetting?>> {
  final RegionService _service;

  RegionSettingNotifier(this._service) : super(const AsyncValue.loading()) {
    loadSetting();
  }

  /// SharedPreferencesから地域設定を読み込む
  Future<void> loadSetting() async {
    state = const AsyncValue.loading();
    try {
      final setting = await _service.getRegionSetting();
      state = AsyncValue.data(setting);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// 地域設定を保存し、状態を更新する
  Future<void> saveSetting(RegionSetting setting) async {
    try {
      await _service.saveRegionSetting(setting);
      state = AsyncValue.data(setting);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// 地域選択のバリデーションを実行する
  ///
  /// 都道府県・市区町村・地区がすべて選択されている場合にのみ有効と判定する。
  RegionValidationResult validate({
    String? prefectureId,
    String? municipalityId,
    String? districtId,
  }) {
    return RegionValidationResult.validate(
      prefectureId: prefectureId,
      municipalityId: municipalityId,
      districtId: districtId,
    );
  }
}

/// 地域選択バリデーション結果
class RegionValidationResult {
  final bool isValid;
  final String? prefectureError;
  final String? municipalityError;
  final String? districtError;

  const RegionValidationResult._({
    required this.isValid,
    this.prefectureError,
    this.municipalityError,
    this.districtError,
  });

  /// すべて有効な場合のコンストラクタ
  const RegionValidationResult.valid()
      : isValid = true,
        prefectureError = null,
        municipalityError = null,
        districtError = null;

  /// バリデーションを実行し結果を返す
  ///
  /// 都道府県・市区町村・地区のいずれかがnullの場合はエラーメッセージを設定する。
  /// すべてが非nullの場合のみisValid=trueとなる。
  factory RegionValidationResult.validate({
    String? prefectureId,
    String? municipalityId,
    String? districtId,
  }) {
    final prefError = prefectureId == null ? '都道府県を選択してください' : null;
    final muniError = municipalityId == null ? '市区町村を選択してください' : null;
    final distError = districtId == null ? '地区を選択してください' : null;

    return RegionValidationResult._(
      isValid:
          prefectureId != null && municipalityId != null && districtId != null,
      prefectureError: prefError,
      municipalityError: muniError,
      districtError: distError,
    );
  }
}
