import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/strings.dart';
import '../models/garbage_item.dart';
import '../providers/search_provider.dart';
import '../widgets/popular_items_section.dart';
import '../widgets/region_header.dart';
import '../widgets/search_result_tile.dart';
import 'item_detail_screen.dart';

/// ゴミ品目検索画面
///
/// 検索テキストフィールド（最大50文字）でゴミ品目を検索し、
/// 結果をリスト形式で表示する。
/// 2文字未満の入力では検索を実行せず、結果エリアを空で維持する。
///
/// 要件2.1: 最大50文字まで入力可能な検索テキストフィールド
/// 要件2.2: 2文字以上のキーワードで部分一致検索（最大50件）
/// 要件2.3: 複数品目該当時のメッセージ表示
/// 要件2.4: 各品目にカテゴリ色タグ表示
/// 要件2.5: 複数カテゴリ該当時の補足情報表示
/// 要件2.6: 検索結果なし時のメッセージ表示
/// 要件2.7: 2文字未満時は検索非実行
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  /// 検索テキストフィールドのコントローラー
  late final TextEditingController _searchController;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  /// 検索テキストフィールドの変更を処理する
  void _onSearchChanged(String value) {
    // 50文字制限を適用
    final trimmedValue = value.length > 50 ? value.substring(0, 50) : value;
    ref.read(searchQueryProvider.notifier).state = trimmedValue;
    // クリアボタンの表示/非表示を更新
    setState(() {});
  }

  /// 検索テキストフィールドをクリアする
  void _onClearSearch() {
    _searchController.clear();
    ref.read(searchQueryProvider.notifier).state = '';
    // クリアボタンの表示/非表示を更新
    setState(() {});
  }

  /// 品目タップ時の処理（品目詳細画面へ遷移）
  void _onItemTap(GarbageItem item) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ItemDetailScreen(item: item),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final query = ref.watch(searchQueryProvider);
    final searchResultsAsync = ref.watch(searchResultsProvider);

    return Scaffold(
      appBar: const RegionHeader(),
      body: Column(
        children: [
          // 検索バー
          _buildSearchBar(),
          // 検索結果エリア
          Expanded(
            child: _buildSearchResultsArea(query, searchResultsAsync),
          ),
        ],
      ),
    );
  }

  /// 角丸テキストフィールドの検索バーを構築する
  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: TextField(
        controller: _searchController,
        maxLength: 50,
        onChanged: _onSearchChanged,
        decoration: InputDecoration(
          hintText: AppStrings.searchHint,
          prefixIcon: const Icon(Icons.search, color: Colors.grey),
          suffixIcon: _searchController.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear, color: Colors.grey),
                  onPressed: _onClearSearch,
                )
              : null,
          filled: true,
          fillColor: Colors.grey[100],
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(24),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(24),
            borderSide: BorderSide.none,
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(24),
            borderSide: BorderSide.none,
          ),
          counterText: '', // 文字数カウンターを非表示
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
    );
  }

  /// 検索結果エリアを構築する
  Widget _buildSearchResultsArea(
    String query,
    AsyncValue<List<GarbageItem>> searchResultsAsync,
  ) {
    // 2文字未満の場合は空表示（よく検索される品目スペースを確保）
    if (query.length < 2) {
      return _buildEmptyState();
    }

    return searchResultsAsync.when(
      data: (results) {
        if (results.isEmpty) {
          // 検索結果なし
          return _buildNoResultsMessage();
        }
        // 検索結果あり
        return _buildResultsList(results);
      },
      loading: () => const Center(
        child: CircularProgressIndicator(),
      ),
      error: (error, stack) => Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              AppStrings.dataLoadError,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[600],
              ),
            ),
            const SizedBox(height: 8),
            ElevatedButton(
              onPressed: () => ref.refresh(searchResultsProvider),
              child: const Text(AppStrings.retry),
            ),
          ],
        ),
      ),
    );
  }

  /// 検索結果リストを構築する
  Widget _buildResultsList(List<GarbageItem> results) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 複数品目該当時のメッセージ
        if (results.length > 1)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Text(
              AppStrings.multipleItemsFound,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[700],
              ),
            ),
          ),
        // 検索結果リスト
        Expanded(
          child: ListView.builder(
            itemCount: results.length,
            padding: const EdgeInsets.only(bottom: 16),
            itemBuilder: (context, index) {
              final item = results[index];
              return SearchResultTile(
                item: item,
                onTap: () => _onItemTap(item),
              );
            },
          ),
        ),
      ],
    );
  }

  /// 検索結果なしメッセージを構築する
  Widget _buildNoResultsMessage() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.search_off,
            size: 48,
            color: Colors.grey[400],
          ),
          const SizedBox(height: 12),
          Text(
            AppStrings.noSearchResults,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[600],
            ),
          ),
        ],
      ),
    );
  }

  /// 空の状態（検索前）を構築する
  /// よく検索される品目セクションを表示する
  Widget _buildEmptyState() {
    return const SingleChildScrollView(
      padding: EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(height: 8),
          // よく検索される品目セクション
          PopularItemsSection(),
        ],
      ),
    );
  }
}
