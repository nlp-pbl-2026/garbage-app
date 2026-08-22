import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;

import '../models/garbage_item.dart';

/// ゴミ品目の検索・取得を担当するサービスクラス
///
/// ローカルJSONファイルからデータを読み込み、キーワード検索・人気品目取得・
/// ID検索の機能を提供する。初回読み込み後はメモリにキャッシュする。
class GarbageService {
  /// ゴミ品目データのキャッシュ
  List<GarbageItem>? _itemsCache;

  /// 人気品目データのキャッシュ（itemIdとlabelのリスト）
  List<Map<String, dynamic>>? _popularItemsCache;

  /// ゴミ品目データを読み込み、キャッシュする
  ///
  /// キャッシュ済みの場合はキャッシュから返す。
  Future<List<GarbageItem>> _loadItems() async {
    if (_itemsCache != null) {
      return _itemsCache!;
    }

    final jsonString =
        await rootBundle.loadString('assets/data/garbage_items.json');
    final List<dynamic> jsonList = json.decode(jsonString) as List<dynamic>;
    _itemsCache = jsonList
        .map(
          (item) => GarbageItem.fromJson(item as Map<String, dynamic>),
        )
        .toList();
    return _itemsCache!;
  }

  /// 人気品目のJSON定義データを読み込み、キャッシュする
  Future<List<Map<String, dynamic>>> _loadPopularItemsData() async {
    if (_popularItemsCache != null) {
      return _popularItemsCache!;
    }

    final jsonString =
        await rootBundle.loadString('assets/data/popular_items.json');
    final List<dynamic> jsonList = json.decode(jsonString) as List<dynamic>;
    _popularItemsCache =
        jsonList.map((item) => item as Map<String, dynamic>).toList();
    return _popularItemsCache!;
  }

  /// キーワードで品目を検索する
  ///
  /// - [keyword]が2文字未満の場合は空リストを返す
  /// - [keyword]が50文字を超える場合は50文字に切り詰めてから検索する
  /// - [isDualLanguage]がtrueの場合、ローカライズされたフィールドと日本語フィールドの
  ///   両方に対して検索し、重複なしの結合結果を返す（要件7.6, 7.7）
  /// - [isDualLanguage]がfalseの場合、日本語のnameとkeywordsのみに対して検索する
  /// - 結果は最大50件まで返す
  Future<List<GarbageItem>> searchItems(
    String keyword, {
    bool isDualLanguage = false,
  }) async {
    // 2文字未満なら空リストを返す
    if (keyword.length < 2) {
      return [];
    }

    // 50文字超なら50文字に切り詰める
    final searchKeyword =
        keyword.length > 50 ? keyword.substring(0, 50) : keyword;

    final items = await _loadItems();
    final queryLower = searchKeyword.toLowerCase();

    final Set<String> matchedIds = {};
    final List<GarbageItem> results = [];

    for (final item in items) {
      if (matchedIds.contains(item.id)) continue;

      bool matches = false;

      if (isDualLanguage) {
        // ローカライズされたフィールドでマッチング
        if (item.localizedName?.toLowerCase().contains(queryLower) == true) {
          matches = true;
        }
        if (!matches &&
            item.localizedKeywords
                .any((k) => k.toLowerCase().contains(queryLower))) {
          matches = true;
        }
      }

      // 日本語フィールドでマッチング（常に実行）
      if (!matches && item.name.toLowerCase().contains(queryLower)) {
        matches = true;
      }
      if (!matches &&
          item.keywords.any((k) => k.toLowerCase().contains(queryLower))) {
        matches = true;
      }

      if (matches) {
        matchedIds.add(item.id);
        results.add(item);
      }
    }

    // 最大50件まで返す
    if (results.length > 50) {
      return results.sublist(0, 50);
    }
    return results;
  }

  /// よく検索される品目を取得する（5-10件）
  ///
  /// popular_items.jsonを読み込み、itemIdでgarbage_items.jsonのデータと
  /// 紐づけて返す。紐づけできない品目はスキップする。
  Future<List<GarbageItem>> getPopularItems() async {
    final popularData = await _loadPopularItemsData();
    final items = await _loadItems();

    final List<GarbageItem> popularItems = [];

    for (final entry in popularData) {
      final itemId = entry['itemId'] as String;
      // garbage_items.jsonから該当品目を検索
      final matchingItem = items.where((item) => item.id == itemId).toList();
      if (matchingItem.isNotEmpty) {
        popularItems.add(matchingItem.first);
      }
    }

    return popularItems;
  }

  /// 品目IDから詳細を取得する
  ///
  /// 指定したIDの品目が存在しない場合はnullを返す。
  Future<GarbageItem?> getItemById(String itemId) async {
    final items = await _loadItems();

    final matchingItems = items.where((item) => item.id == itemId).toList();
    if (matchingItems.isEmpty) {
      return null;
    }
    return matchingItems.first;
  }
}
