import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/region.dart';

/// 複数地区管理サービス
///
/// SharedPreferencesに複数のRegionSettingをJSON配列で保存し、
/// 地区の追加・削除・アクティブ切り替えを管理する。
/// 最大5件まで地区を保存可能。
class MultiRegionService {
  /// SharedPreferencesに保存済み地区リストを保存する際のキー
  static const String _savedRegionsKey = 'saved_regions';

  /// 保存可能な地区の最大数
  static const int maxRegions = 5;

  /// マイグレーション済みフラグのキー
  static const String _migratedKey = 'multi_region_migrated';

  /// 保存済み地区リストを取得する
  ///
  /// 初回呼び出し時にマイグレーションを実行し、
  /// 既存の単一地域設定を「自宅」ラベルで保存する。
  Future<List<SavedRegion>> getSavedRegions() async {
    final prefs = await SharedPreferences.getInstance();

    // マイグレーション確認
    await _migrateIfNeeded(prefs);

    final jsonString = prefs.getString(_savedRegionsKey);
    if (jsonString == null) {
      return [];
    }

    final List<dynamic> jsonList = json.decode(jsonString) as List<dynamic>;
    return jsonList
        .map((item) => SavedRegion.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// 新しい地区を追加する
  ///
  /// [label] ユーザーが付けるラベル（"自宅", "職場"等）
  /// [setting] 追加する地域設定
  ///
  /// 最大5件まで保存可能。5件を超える場合は例外をスローする。
  /// 追加した地区が最初の1件の場合、自動的にアクティブに設定する。
  Future<SavedRegion> addRegion(String label, RegionSetting setting) async {
    final prefs = await SharedPreferences.getInstance();
    final regions = await getSavedRegions();

    if (regions.length >= maxRegions) {
      throw Exception('保存できる地区は最大$maxRegions件までです');
    }

    final id = _generateId();
    final isFirst = regions.isEmpty;
    final newRegion = SavedRegion(
      id: id,
      label: label,
      setting: setting,
      isActive: isFirst,
    );

    regions.add(newRegion);
    await _saveRegions(prefs, regions);

    return newRegion;
  }

  /// 地区を削除する
  ///
  /// [id] 削除する地区のID
  ///
  /// アクティブな地区を削除した場合、残りの先頭地区を自動的にアクティブに設定する。
  Future<void> removeRegion(String id) async {
    final prefs = await SharedPreferences.getInstance();
    final regions = await getSavedRegions();

    final removedIndex = regions.indexWhere((r) => r.id == id);
    if (removedIndex == -1) return;

    final wasActive = regions[removedIndex].isActive;
    regions.removeAt(removedIndex);

    // アクティブだった地区を削除した場合、先頭をアクティブに
    if (wasActive && regions.isNotEmpty) {
      regions[0] = regions[0].copyWith(isActive: true);
    }

    await _saveRegions(prefs, regions);
  }

  /// アクティブな地区を切り替える
  ///
  /// [id] アクティブに設定する地区のID
  ///
  /// 指定したIDの地区をアクティブに設定し、他のすべての地区を非アクティブにする。
  Future<SavedRegion?> setActiveRegion(String id) async {
    final prefs = await SharedPreferences.getInstance();
    final regions = await getSavedRegions();

    SavedRegion? activeRegion;
    final updatedRegions = regions.map((r) {
      if (r.id == id) {
        activeRegion = r.copyWith(isActive: true);
        return activeRegion!;
      }
      return r.copyWith(isActive: false);
    }).toList();

    await _saveRegions(prefs, updatedRegions);
    return activeRegion;
  }

  /// 現在のアクティブ地区を取得する
  ///
  /// アクティブな地区がない場合は null を返す。
  Future<SavedRegion?> getActiveRegion() async {
    final regions = await getSavedRegions();
    try {
      return regions.firstWhere((r) => r.isActive);
    } catch (_) {
      return regions.isNotEmpty ? regions.first : null;
    }
  }

  /// 既存の単一地域設定からマイグレーションする
  ///
  /// 初回のみ実行し、既存のregion_settingを「自宅」ラベルで
  /// 複数地区リストの最初のエントリとして保存する。
  Future<void> _migrateIfNeeded(SharedPreferences prefs) async {
    final migrated = prefs.getBool(_migratedKey) ?? false;
    if (migrated) return;

    final existingJson = prefs.getString('region_setting');
    if (existingJson != null) {
      final setting = RegionSetting.fromJson(
        json.decode(existingJson) as Map<String, dynamic>,
      );
      final savedRegion = SavedRegion(
        id: _generateId(),
        label: '自宅',
        setting: setting,
        isActive: true,
      );
      await _saveRegions(prefs, [savedRegion]);
    }

    await prefs.setBool(_migratedKey, true);
  }

  /// 地区リストをSharedPreferencesに保存する
  Future<void> _saveRegions(
    SharedPreferences prefs,
    List<SavedRegion> regions,
  ) async {
    final jsonList = regions.map((r) => r.toJson()).toList();
    final jsonString = json.encode(jsonList);
    await prefs.setString(_savedRegionsKey, jsonString);
  }

  /// ユニークIDを生成する
  ///
  /// uuidパッケージを使わず、DateTimeベースのシンプルなIDを生成する。
  String _generateId() {
    final now = DateTime.now();
    return '${now.millisecondsSinceEpoch}_${now.microsecond}';
  }
}
