import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/region.dart';

/// 地域データの読み込みと地域設定の永続化を管理するサービス。
///
/// assets/data/ 配下のJSONファイルから都道府県・市区町村・地区データを読み込み、
/// SharedPreferencesを使用して選択された地域設定を保存・復元する。
class RegionService {
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
  /// assets/data/municipalities.json からデータを読み込み、
  /// [prefectureId] でフィルタリングした結果を返す。
  Future<List<Municipality>> getMunicipalities(String prefectureId) async {
    final jsonString =
        await rootBundle.loadString('assets/data/municipalities.json');
    final List<dynamic> jsonList = json.decode(jsonString) as List<dynamic>;
    final allMunicipalities = jsonList
        .map((item) => Municipality.fromJson(item as Map<String, dynamic>))
        .toList();
    return allMunicipalities
        .where((m) => m.prefectureId == prefectureId)
        .toList();
  }

  /// 指定された市区町村IDに属する地区一覧を取得する。
  ///
  /// assets/data/districts.json からデータを読み込み、
  /// [municipalityId] でフィルタリングした結果を返す。
  Future<List<District>> getDistricts(String municipalityId) async {
    final jsonString =
        await rootBundle.loadString('assets/data/districts.json');
    final List<dynamic> jsonList = json.decode(jsonString) as List<dynamic>;
    final allDistricts = jsonList
        .map((item) => District.fromJson(item as Map<String, dynamic>))
        .toList();
    return allDistricts
        .where((d) => d.municipalityId == municipalityId)
        .toList();
  }

  /// 地域設定をSharedPreferencesに保存する。
  ///
  /// [setting] をJSON文字列にシリアライズして保存する。
  Future<void> saveRegionSetting(RegionSetting setting) async {
    final prefs = await SharedPreferences.getInstance();
    final jsonString = json.encode(setting.toJson());
    await prefs.setString(_regionSettingKey, jsonString);
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
    return RegionSetting.fromJson(jsonMap);
  }
}
