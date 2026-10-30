import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/bulky_waste.dart';
import '../../providers/bulky_waste_provider.dart';
import '../../providers/region_provider.dart';
import '../../repositories/bulky_waste_repository.dart';
import '../../screens/fee_display_screen.dart';
import 'external_link_handler.dart';

/// 品目一覧のソートモード
enum ItemSortMode {
  /// 名前順（五十音順）
  name,

  /// 手数料昇順
  feeAsc,

  /// 手数料降順
  feeDesc,
}

/// 粗大ごみ品目一覧ウィジェット
///
/// 品目一覧を検索・ソート可能なリスト形式で表示する。
/// [municipalityId] に基づいてバックエンドAPIから品目データを取得し、
/// ローカルで検索フィルタリングとソートを適用する。
///
/// 要件3.1: 品目一覧を五十音順で表示
/// 要件3.2: 品目名・カテゴリ・手数料を表示
/// 要件3.3: 1文字以上のキーワードで部分一致フィルタリング
/// 要件3.4: 検索結果0件時のメッセージ表示
/// 要件3.5: 有料品目がある場合のソート切替（名前順/手数料昇順/手数料降順）
/// 要件3.6: API失敗時のエラーメッセージ+リトライ
class ItemListView extends ConsumerStatefulWidget {
  /// 対象の自治体ID（5桁コード）
  final String municipalityId;

  /// API未提供時に表示する自治体公式案内。
  final MunicipalityConfig config;

  /// 品目APIを呼ばず、公式サイトへの案内を表示するか。
  final bool useOfficialInfoFallback;

  const ItemListView({
    super.key,
    required this.municipalityId,
    required this.config,
    this.useOfficialInfoFallback = false,
  });

  @override
  ConsumerState<ItemListView> createState() => _ItemListViewState();
}

class _ItemListViewState extends ConsumerState<ItemListView> {
  /// 検索テキストフィールドのコントローラー
  late final TextEditingController _searchController;

  /// 現在の検索キーワード
  String _searchKeyword = '';

  /// 現在のソートモード
  ItemSortMode _sortMode = ItemSortMode.name;

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

  /// 検索テキスト変更時のハンドラー
  void _onSearchChanged(String value) {
    setState(() {
      _searchKeyword = value;
    });
  }

  /// 検索テキストをクリア
  void _onClearSearch() {
    _searchController.clear();
    setState(() {
      _searchKeyword = '';
    });
  }

  /// ソートモード変更時のハンドラー
  void _onSortChanged(ItemSortMode? mode) {
    if (mode != null) {
      setState(() {
        _sortMode = mode;
      });
    }
  }

  /// 品目リストをフィルタリングする
  ///
  /// [items] 元の品目リスト
  /// [keyword] 検索キーワード（1文字以上で有効）
  ///
  /// item_name または category に keyword が部分一致する品目のみ返す。
  List<BulkyWasteItem> _filterItems(
      List<BulkyWasteItem> items, String keyword) {
    if (keyword.isEmpty) return items;
    final lower = keyword.toLowerCase();
    return items.where((item) {
      return item.itemName.toLowerCase().contains(lower) ||
          item.category.toLowerCase().contains(lower);
    }).toList();
  }

  /// 品目リストをソートする
  ///
  /// [items] ソート対象のリスト（in-place変更なし、新しいリストを返す）
  /// [mode] ソートモード
  List<BulkyWasteItem> _sortItems(
      List<BulkyWasteItem> items, ItemSortMode mode) {
    final sorted = List<BulkyWasteItem>.from(items);
    switch (mode) {
      case ItemSortMode.name:
        // デフォルト: APIからitem_name_kana順で返されるのでそのまま
        // ローカルではitemNameでソート（APIが五十音順で返す前提）
        break;
      case ItemSortMode.feeAsc:
        sorted.sort((a, b) => a.feeAmount.compareTo(b.feeAmount));
        break;
      case ItemSortMode.feeDesc:
        sorted.sort((a, b) => b.feeAmount.compareTo(a.feeAmount));
        break;
    }
    return sorted;
  }

  /// 品目タップ時: FeeDisplayScreenへ遷移
  void _onItemTap(BulkyWasteItem item) {
    final configResult = ref.read(municipalityConfigProvider).valueOrNull;
    final config = configResult?.data;
    if (config == null) return;

    if (config.applicationMethod == ApplicationMethod.none) {
      showDialog<void>(context: context, builder: (dialogContext) => AlertDialog(
        title: Text(item.itemName),
        content: Text('${item.notes ?? '公式カレンダーで出し方を確認してください。'}\n\n収集日は選択地区のカレンダーで確認してください。'),
        actions: [TextButton(onPressed: () => Navigator.of(dialogContext).pop(),
          child: const Text('閉じる'))],
      ));
      return;
    }

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => FeeDisplayScreen(item: item, config: config),
      ),
    );
  }

  /// BulkyWasteQuery を構築する（API呼び出し用）
  BulkyWasteQuery _buildQuery() {
    return BulkyWasteQuery(
      municipalityId: widget.municipalityId,
      districtId: ref.read(regionSettingProvider).valueOrNull?.districtId,
      sortBy: SortBy.name,
      sortOrder: SortOrder.asc,
    );
  }

  @override
  Widget build(BuildContext context) {
    final itemsAsync = ref.watch(bulkyWasteItemsProvider(_buildQuery()));

    return itemsAsync.when(
      data: (result) {
        if (result == null) {
          return widget.useOfficialInfoFallback
              ? _buildOfficialInfoFallback()
              : _buildErrorState();
        }
        return Column(
          children: [
            _buildSearchBar(),
            _buildSortSelector(result.data.items),
            Expanded(child: _buildItemListContent(result)),
          ],
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, stack) => widget.useOfficialInfoFallback
          ? _buildOfficialInfoFallback()
          : _buildErrorState(),
    );
  }

  /// 品目APIが未提供の場合も、正しい確認先へ進める画面を表示する。
  Widget _buildOfficialInfoFallback() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(
                    Icons.fact_check_outlined,
                    size: 48,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    '品目を公式情報で確認',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    widget.config.applicationMethod == ApplicationMethod.none
                        ? '中島地域の粗大ごみ収集日と出し方は公式カレンダーで確認してください。'
                        : '粗大ごみとして収集できるか、申込区分、受付期間は松山市公式サイトで確認してください。料金はかかりません。',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 20),
                  ExternalLinkHandler(
                    applicationMethod: ApplicationMethod.webForm,
                    webFormUrl: widget.config.webFormUrl,
                    webButtonLabel: '松山市公式サイトで確認',
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.search),
                    label: const Text('アプリの分別検索に戻る'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  /// 検索バーを構築する
  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: TextField(
        controller: _searchController,
        onChanged: _onSearchChanged,
        decoration: InputDecoration(
          hintText: '品目名・カテゴリで検索',
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
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
    );
  }

  /// ソート切替UIを構築する
  Widget _buildSortSelector(List<BulkyWasteItem> items) {
    if (!items.any((item) => item.feeAmount > 0)) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          const Text(
            '並び替え:',
            style: TextStyle(fontSize: 13, color: Colors.black87),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: SegmentedButton<ItemSortMode>(
              segments: const [
                ButtonSegment(
                  value: ItemSortMode.name,
                  label: Text('名前順', style: TextStyle(fontSize: 12)),
                ),
                ButtonSegment(
                  value: ItemSortMode.feeAsc,
                  label: Text('手数料↑', style: TextStyle(fontSize: 12)),
                ),
                ButtonSegment(
                  value: ItemSortMode.feeDesc,
                  label: Text('手数料↓', style: TextStyle(fontSize: 12)),
                ),
              ],
              selected: {_sortMode},
              onSelectionChanged: (selected) {
                _onSortChanged(selected.first);
              },
              style: const ButtonStyle(
                visualDensity: VisualDensity.compact,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 品目リスト内容を構築する（データ取得成功時）
  Widget _buildItemListContent(CachedResult<BulkyWasteItemList> result) {
    final allItems = result.data.items;
    final filteredItems = _filterItems(allItems, _searchKeyword);
    final sortedItems = _sortItems(filteredItems, _sortMode);

    return Column(
      children: [
        // 古いデータ警告バナー
        if (result.isStale) _buildStaleBanner(),
        // 品目リスト or 0件メッセージ
        Expanded(
          child: sortedItems.isEmpty
              ? _buildEmptyResultMessage()
              : ListView.builder(
                  itemCount: sortedItems.length,
                  padding: const EdgeInsets.only(bottom: 16),
                  itemBuilder: (context, index) {
                    return _buildItemTile(sortedItems[index]);
                  },
                ),
        ),
      ],
    );
  }

  /// 古いデータ警告バナーを構築する
  Widget _buildStaleBanner() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: Colors.orange[50],
      child: Row(
        children: [
          Icon(Icons.info_outline, size: 16, color: Colors.orange[800]),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '表示されているデータは以前の取得結果です。最新情報を反映していない可能性があります。',
              style: TextStyle(fontSize: 12, color: Colors.orange[800]),
            ),
          ),
        ],
      ),
    );
  }

  /// 品目タイルを構築する
  Widget _buildItemTile(BulkyWasteItem item) {
    return ListTile(
      title: Text(
        item.itemName,
        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
      ),
      subtitle: Text(
        item.category,
        style: TextStyle(fontSize: 13, color: Colors.grey[600]),
      ),
      trailing: Text(
        widget.config.applicationMethod == ApplicationMethod.none
            ? '資料を確認'
            : item.feeAmount > 0
                ? '${item.feeAmount}円'
                : widget.config.municipalityId == '38201'
                    ? '戸別収集無料'
                    : '料金未確認',
        style: const TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: Colors.teal,
        ),
      ),
      onTap: () => _onItemTap(item),
    );
  }

  /// 検索結果0件時のメッセージを構築する
  Widget _buildEmptyResultMessage() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.search_off, size: 48, color: Colors.grey[400]),
          const SizedBox(height: 12),
          Text(
            '該当する品目が見つかりません',
            style: TextStyle(fontSize: 14, color: Colors.grey[600]),
          ),
        ],
      ),
    );
  }

  /// エラー状態を構築する（API失敗時）
  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.error_outline, size: 48, color: Colors.grey[400]),
          const SizedBox(height: 12),
          Text(
            'データの読み込みに失敗しました',
            style: TextStyle(fontSize: 14, color: Colors.grey[600]),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () {
              ref.invalidate(bulkyWasteItemsProvider(_buildQuery()));
            },
            child: const Text('リトライ'),
          ),
        ],
      ),
    );
  }
}
