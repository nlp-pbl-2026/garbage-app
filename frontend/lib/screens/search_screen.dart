import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/strings.dart';
import '../models/garbage_item.dart';
import '../providers/search_provider.dart';
import '../services/search_history_service.dart';
import '../widgets/popular_items_section.dart';
import '../widgets/region_header.dart';
import '../widgets/search_result_tile.dart';
import 'item_detail_screen.dart';
import 'region_selection_screen.dart';

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
  final SearchHistoryService _historyService = SearchHistoryService();
  List<String> _searchHistory = [];

  /// 検索履歴保存用デバウンスタイマー
  Timer? _historyDebounceTimer;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final history = await _historyService.getHistory();
    if (mounted) {
      setState(() {
        _searchHistory = history;
      });
    }
  }

  @override
  void dispose() {
    _historyDebounceTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  /// 検索テキストフィールドの変更を処理する
  void _onSearchChanged(String value) {
    // 50文字制限を適用
    final trimmedValue = value.length > 50 ? value.substring(0, 50) : value;
    ref.read(searchQueryProvider.notifier).state = trimmedValue;

    // デバウンス: 入力停止から1秒後に履歴保存（入力途中の文字列は保存しない）
    _historyDebounceTimer?.cancel();
    if (trimmedValue.trim().length >= 2) {
      _historyDebounceTimer = Timer(const Duration(seconds: 1), () {
        _historyService.addHistory(trimmedValue.trim()).then((_) => _loadHistory());
      });
    }

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
      appBar: RegionHeader(
        onEditPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => RegionSelectionScreen(
                onRegionSelected: () {
                  Navigator.of(context).pop();
                },
              ),
            ),
          );
        },
      ),
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
        // 検索結果リスト + よく検索されるもの
        Expanded(
          child: ListView(
            padding: const EdgeInsets.only(bottom: 16),
            children: [
              ...results.map((item) => SearchResultTile(
                    item: item,
                    onTap: () => _onItemTap(item),
                  )),
              const SizedBox(height: 24),
              // よく検索されるものを常に表示
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: PopularItemsSection(
                  onItemSelected: (name) {
                    _searchController.text = name;
                    setState(() {});
                  },
                ),
              ),
            ],
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
  /// 検索ヒント、カテゴリクイック検索、検索履歴、よく検索される品目を表示する
  Widget _buildEmptyState() {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 16),
          // 検索ヒントセクション
          _buildSearchHint(),
          const SizedBox(height: 24),
          // カテゴリ別クイック検索
          _buildCategoryQuickSearch(),
          const SizedBox(height: 24),
          // 検索履歴セクション
          if (_searchHistory.isNotEmpty) _buildHistorySection(),
          // よく検索される品目セクション
          PopularItemsSection(
            onItemSelected: (name) {
              _searchController.text = name;
              setState(() {});
            },
          ),
        ],
      ),
    );
  }

  /// 検索ヒントカードを構築する
  Widget _buildSearchHint() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.green.shade50, Colors.teal.shade50],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(Icons.lightbulb_outline, color: Colors.green.shade700, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '捨て方がわからないものを検索',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Colors.green.shade900,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '品目名を入力すると分別方法がわかります',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.green.shade700,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// カテゴリ別クイック検索を構築する
  Widget _buildCategoryQuickSearch() {
    final categories = [
      ('可燃ごみ', Icons.local_fire_department, Colors.pink.shade400),
      ('資源ごみ', Icons.recycling, Colors.green.shade600),
      ('プラスチック', Icons.shopping_bag_outlined, Colors.orange.shade600),
      ('ペットボトル', Icons.water_drop_outlined, Colors.blue.shade600),
      ('危険ごみ', Icons.warning_amber, Colors.red.shade600),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'カテゴリから探す',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: Colors.black87,
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 80,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: categories.length,
            separatorBuilder: (_, __) => const SizedBox(width: 12),
            itemBuilder: (context, index) {
              final (label, icon, color) = categories[index];
              return GestureDetector(
                onTap: () {
                  _searchController.text = label;
                  _onSearchChanged(label);
                },
                child: Container(
                  width: 80,
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: color.withOpacity(0.3)),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(icon, color: color, size: 28),
                      const SizedBox(height: 4),
                      Text(
                        label,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: color,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  /// 検索履歴セクションを構築する
  Widget _buildHistorySection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              '検索履歴',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Colors.black87,
              ),
            ),
            TextButton(
              onPressed: () async {
                await _historyService.clearHistory();
                _loadHistory();
              },
              child: Text(
                'すべて削除',
                style: TextStyle(fontSize: 12, color: Colors.grey[600]),
              ),
            ),
          ],
        ),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: _searchHistory.take(10).map((keyword) {
            return GestureDetector(
              onTap: () {
                _searchController.text = keyword;
                _onSearchChanged(keyword);
              },
              child: Chip(
                label: Text(keyword, style: const TextStyle(fontSize: 13)),
                deleteIcon: const Icon(Icons.close, size: 16),
                onDeleted: () async {
                  await _historyService.removeHistory(keyword);
                  _loadHistory();
                },
                backgroundColor: Colors.grey[100],
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            );
          }).toList(),
        ),
        const SizedBox(height: 16),
      ],
    );
  }
}
