import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/garbage_item.dart';
import 'locale_provider.dart';
import '../services/garbage_service.dart';

/// GarbageServiceのプロバイダー
///
/// アプリ全体で単一のGarbageServiceインスタンスを提供する。
final garbageServiceProvider = Provider<GarbageService>((ref) {
  return GarbageService();
});

/// 検索クエリのStateProvider
///
/// ユーザーが入力した検索文字列を管理する。
/// 初期値は空文字列。
final searchQueryProvider = StateProvider<String>((ref) => '');

/// 検索結果のFutureProvider（autoDispose）
///
/// searchQueryProviderの値を監視し、2文字以上の場合に検索を実行する。
/// 2文字未満の場合は空リストを返す。
/// autoDisposeにより、参照されなくなった際にリソースを解放する。
///
/// 非日本語ロケール選択時はデュアル言語検索を有効にし、
/// ローカライズされたフィールドと日本語フィールドの両方で検索する（要件7.6, 7.7）。
final searchResultsProvider =
    FutureProvider.autoDispose<List<GarbageItem>>((ref) async {
  final query = ref.watch(searchQueryProvider);

  // 2文字未満なら空リストを返す
  if (query.length < 2) {
    return [];
  }

  final locale = ref.watch(localeProvider);
  final isDualLanguage = locale.languageCode != 'ja';

  final garbageService = ref.read(garbageServiceProvider);
  return garbageService.searchItems(query, isDualLanguage: isDualLanguage);
});

/// よく検索される品目のFutureProvider
///
/// GarbageService.getPopularItems()を呼び出し、
/// 事前定義されたよく検索される品目を取得する。
final popularItemsProvider = FutureProvider<List<GarbageItem>>((ref) async {
  final garbageService = ref.read(garbageServiceProvider);
  return garbageService.getPopularItems();
});
