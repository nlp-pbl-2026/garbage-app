import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../constants/app_config.dart';
import '../models/bulky_waste.dart';

/// API + キャッシュフォールバックの結果ラッパー
///
/// データ本体と、キャッシュから返されたかどうかの [isStale] フラグを保持する。
/// [isStale] が true の場合、表示されているデータは以前の取得結果であり、
/// 最新情報を反映していない可能性がある。
class CachedResult<T> {
  final T data;

  /// true の場合、キャッシュから取得したデータであることを示す
  final bool isStale;

  const CachedResult({required this.data, required this.isStale});

  @override
  String toString() => 'CachedResult(data: $data, isStale: $isStale)';
}

/// 品目一覧のソート基準
enum SortBy {
  /// 品目名（五十音順）
  name,

  /// 手数料
  fee,
}

/// ソート順序
enum SortOrder {
  /// 昇順
  asc,

  /// 降順
  desc,
}

/// 品目一覧レスポンス
///
/// 品目リストと付帯情報（件数・自治体名）を保持する。
class BulkyWasteItemList {
  final List<BulkyWasteItem> items;
  final int totalCount;
  final String municipalityName;

  const BulkyWasteItemList({
    required this.items,
    required this.totalCount,
    required this.municipalityName,
  });

  factory BulkyWasteItemList.fromJson(Map<String, dynamic> json) {
    return BulkyWasteItemList(
      items: (json['items'] as List<dynamic>)
          .map((e) => BulkyWasteItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      totalCount: json['total_count'] as int,
      municipalityName: json['municipality_name'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'items': items.map((e) => e.toJson()).toList(),
      'total_count': totalCount,
      'municipality_name': municipalityName,
    };
  }
}

/// 粗大ごみデータリポジトリ
///
/// バックエンドAPIからデータを取得し、SharedPreferencesにキャッシュする。
/// API呼び出しが失敗した場合はキャッシュからデータを返す（フォールバック）。
/// キャッシュデータを返す際には [CachedResult.isStale] が true になる。
class BulkyWasteRepository {
  final http.Client _client;
  final SharedPreferences _prefs;
  final String _baseUrl;

  /// APIリクエストのタイムアウト時間
  static const Duration _timeout = Duration(seconds: 10);

  /// SharedPreferencesキーのプレフィックス
  static const String _configCacheKeyPrefix = 'bulky_waste_config_';
  static const String _itemsCacheKeyPrefix = 'bulky_waste_items_';
  static const String _configTimestampKeyPrefix =
      'bulky_waste_config_timestamp_';

  /// [BulkyWasteRepository] を生成する。
  ///
  /// [client] HTTP クライアント（テスト時にモック注入可能）
  /// [prefs] SharedPreferences インスタンス
  /// [baseUrl] APIベースURL（省略時は [AppConfig.apiBaseUrl]）
  BulkyWasteRepository({
    required http.Client client,
    required SharedPreferences prefs,
    String? baseUrl,
  })  : _client = client,
        _prefs = prefs,
        _baseUrl = baseUrl ?? AppConfig.apiBaseUrl;

  /// 現在の言語コードをSharedPreferencesから取得する。
  /// 保存されていない場合は日本語('ja')をデフォルトとして返す。
  String _getLanguageCode() {
    return _prefs.getString('language_code') ?? 'ja';
  }

  /// Accept-Languageヘッダーを含むリクエストヘッダーを生成する。
  Map<String, String> _buildHeaders() {
    return {'Accept-Language': _getLanguageCode()};
  }

  /// 自治体設定を取得する（API → キャッシュフォールバック）
  ///
  /// API呼び出しが成功した場合はデータをキャッシュに保存し、
  /// [CachedResult.isStale] = false で返す。
  /// API呼び出しが失敗した場合はキャッシュからデータを読み込み、
  /// [CachedResult.isStale] = true で返す。
  /// キャッシュも存在しない場合は null を返す。
  Future<CachedResult<MunicipalityConfig>?> getMunicipalityConfig(
      String municipalityId) async {
    try {
      final uri = Uri.parse('$_baseUrl/api/bulky-waste/config/$municipalityId');
      final response =
          await _client.get(uri, headers: _buildHeaders()).timeout(_timeout);

      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        final config = MunicipalityConfig.fromJson(json);
        await _cacheConfig(municipalityId, config);
        return CachedResult(data: config, isStale: false);
      }

      // 404 の場合はキャッシュフォールバックせず null
      if (response.statusCode == 404) {
        return null;
      }

      // その他のエラーはキャッシュフォールバック
      return _getCachedConfigResult(municipalityId);
    } on TimeoutException {
      return _getCachedConfigResult(municipalityId);
    } catch (_) {
      return _getCachedConfigResult(municipalityId);
    }
  }

  /// 品目一覧を取得する（API → キャッシュフォールバック）
  ///
  /// [search] 検索キーワード（部分一致）
  /// [sortBy] ソート基準（name/fee）
  /// [sortOrder] ソート順序（asc/desc）
  ///
  /// API呼び出しが成功した場合はデータをキャッシュに保存し、
  /// [CachedResult.isStale] = false で返す。
  /// API呼び出しが失敗した場合はキャッシュからデータを読み込み、
  /// [CachedResult.isStale] = true で返す。
  /// キャッシュも存在しない場合は null を返す。
  Future<CachedResult<BulkyWasteItemList>?> getItems(
    String municipalityId, {
    String? search,
    SortBy? sortBy,
    SortOrder? sortOrder,
  }) async {
    try {
      final queryParams = <String, String>{};
      if (search != null && search.isNotEmpty) {
        queryParams['search'] = search;
      }
      if (sortBy != null) {
        queryParams['sort_by'] = sortBy == SortBy.name ? 'name' : 'fee';
      }
      if (sortOrder != null) {
        queryParams['sort_order'] = sortOrder == SortOrder.asc ? 'asc' : 'desc';
      }

      final uri = Uri.parse('$_baseUrl/api/bulky-waste/items/$municipalityId')
          .replace(
              queryParameters: queryParams.isNotEmpty ? queryParams : null);

      final response =
          await _client.get(uri, headers: _buildHeaders()).timeout(_timeout);

      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        final itemList = BulkyWasteItemList.fromJson(json);
        // 検索なしの場合のみキャッシュに保存（ベースデータのみ）
        if (search == null || search.isEmpty) {
          await _cacheItems(municipalityId, itemList);
        }
        return CachedResult(data: itemList, isStale: false);
      }

      if (response.statusCode == 404) {
        return null;
      }

      return _getCachedItemsResult(municipalityId);
    } on TimeoutException {
      return _getCachedItemsResult(municipalityId);
    } catch (_) {
      return _getCachedItemsResult(municipalityId);
    }
  }

  /// 品目詳細を取得する
  ///
  /// 品目詳細はキャッシュフォールバックを使わず、APIから直接取得する。
  /// 取得に失敗した場合は null を返す。
  Future<BulkyWasteItem?> getItemDetail(
      String municipalityId, int itemId) async {
    try {
      final uri =
          Uri.parse('$_baseUrl/api/bulky-waste/items/$municipalityId/$itemId');
      final response =
          await _client.get(uri, headers: _buildHeaders()).timeout(_timeout);

      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        return BulkyWasteItem.fromJson(json);
      }

      return null;
    } on TimeoutException {
      return null;
    } catch (_) {
      return null;
    }
  }

  // ─── キャッシュ操作（プライベート） ────────────────────────────────────

  /// 自治体設定をキャッシュに保存する
  Future<void> _cacheConfig(
      String municipalityId, MunicipalityConfig config) async {
    final key = '$_configCacheKeyPrefix$municipalityId';
    final timestampKey = '$_configTimestampKeyPrefix$municipalityId';
    await _prefs.setString(key, jsonEncode(config.toJson()));
    await _prefs.setInt(timestampKey, DateTime.now().millisecondsSinceEpoch);
  }

  /// キャッシュから自治体設定を読み込み CachedResult で返す
  CachedResult<MunicipalityConfig>? _getCachedConfigResult(
      String municipalityId) {
    final cached = _getCachedConfig(municipalityId);
    if (cached == null) return null;
    return CachedResult(data: cached, isStale: true);
  }

  /// キャッシュから自治体設定を読み込む
  MunicipalityConfig? _getCachedConfig(String municipalityId) {
    final key = '$_configCacheKeyPrefix$municipalityId';
    final jsonString = _prefs.getString(key);
    if (jsonString == null) return null;
    try {
      final json = jsonDecode(jsonString) as Map<String, dynamic>;
      return MunicipalityConfig.fromJson(json);
    } catch (_) {
      return null;
    }
  }

  /// 品目一覧をキャッシュに保存する
  Future<void> _cacheItems(
      String municipalityId, BulkyWasteItemList itemList) async {
    final key = '$_itemsCacheKeyPrefix$municipalityId';
    await _prefs.setString(key, jsonEncode(itemList.toJson()));
  }

  /// キャッシュから品目一覧を読み込み CachedResult で返す
  CachedResult<BulkyWasteItemList>? _getCachedItemsResult(
      String municipalityId) {
    final cached = _getCachedItems(municipalityId);
    if (cached == null) return null;
    return CachedResult(data: cached, isStale: true);
  }

  /// キャッシュから品目一覧を読み込む
  BulkyWasteItemList? _getCachedItems(String municipalityId) {
    final key = '$_itemsCacheKeyPrefix$municipalityId';
    final jsonString = _prefs.getString(key);
    if (jsonString == null) return null;
    try {
      final json = jsonDecode(jsonString) as Map<String, dynamic>;
      return BulkyWasteItemList.fromJson(json);
    } catch (_) {
      return null;
    }
  }
}
