import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/region.dart';
import 'municipality_data_service.dart';

/// 地域データの読み込みと地域設定の永続化を管理するサービス。
///
/// assets/data/ 配下のJSONファイルから都道府県・市区町村・地区データを読み込み、
/// SharedPreferencesを使用して選択された地域設定を保存・復元する。
class RegionService {
  RegionService({MunicipalityDataService? data}) : _data = data ?? MunicipalityDataService();
  final MunicipalityDataService _data;
  /// SharedPreferencesに地域設定を保存する際のキー
  static const String _regionSettingKey = 'region_setting';

  /// 都道府県一覧を取得する。
  ///
  /// assets/data/prefectures.json からデータを読み込み、
  /// List<Prefecture> として返す。
  Future<List<Prefecture>> getPrefectures() async {
    final jsonString = await rootBundle.loadString('assets/data/prefectures.json');
    final List<dynamic> jsonList = json.decode(jsonString) as List<dynamic>;
    return jsonList
        .map((item) => Prefecture.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// 指定された都道府県IDに属する市区町村一覧を取得する。
  ///
  /// 同梱カタログに登録された自治体から、
  /// [prefectureId] でフィルタリングした結果を返す。
  Future<List<Municipality>> getMunicipalities(String prefectureId) async {
    return (await _data.municipalities())
        .where((entry) => entry['prefecture_id'] == prefectureId)
        .map((entry) => Municipality(
            id: entry['id'] as String,
            prefectureId: prefectureId,
            name: entry['name'] as String))
        .toList();
  }

  /// 指定された市区町村IDに属する地区一覧を取得する。
  ///
  /// 選択した自治体の収集地区台帳から、
  /// [municipalityId] でフィルタリングした結果を返す。
  Future<List<District>> getDistricts(String municipalityId) async {
    return (await _data.getAreas(municipalityId))
        .map((entry) => District(
              id: entry['id'] as String,
              municipalityId: municipalityId,
              name: entry['name'] as String,
            ))
        .toList();
  }

  Future<String?> getCoverageNotice(String municipalityId) async {
    if (await _data.municipality(municipalityId) == null) return null;
    return (await _data.registryFor(municipalityId))['coverage_notice'] as String?;
  }

  /// 地域設定をSharedPreferencesに保存する。
  ///
  /// [setting] をJSON文字列にシリアライズして保存する。
  Future<void> saveRegionSetting(RegionSetting setting) async {
    final prefs = await SharedPreferences.getInstance();
    final jsonString = json.encode(setting.toJson());
    await prefs.setString(_regionSettingKey, jsonString);
  }

  Future<void> clearRegionSetting() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_regionSettingKey);
  }

  /// SharedPreferencesから保存済みの地域設定を取得する。
  ///
  /// 地域設定が保存されていない場合は null を返す。
  Future<RegionSetting?> getRegionSetting() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonString = prefs.getString(_regionSettingKey);
    if (jsonString == null) {
      return null;
    }
    final Map<String, dynamic> jsonMap =
        json.decode(jsonString) as Map<String, dynamic>;
    final old = RegionSetting.fromJson(jsonMap);
    final area =
        await _data.area(old.districtId, municipalityId: old.municipalityId);
    if (area == null) {
      return null; // Ambiguous/unknown legacy ID requires selection.
    }
    if (area['id'] == old.districtId && area['name'] == old.districtName) {
      return old;
    }
    final migrated = RegionSetting(
      prefectureId: old.prefectureId, prefectureName: old.prefectureName,
      municipalityId: old.municipalityId, municipalityName: old.municipalityName,
      districtId: area['id'] as String, districtName: area['name'] as String,
    );
    await saveRegionSetting(migrated);
    return migrated;
  }
}
