import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/bulky_waste.dart';
import '../models/garbage_item.dart';
import '../l10n/app_localizations.dart';
import '../providers/bulky_waste_provider.dart';
import '../providers/calendar_provider.dart';
import '../providers/region_provider.dart';
import '../screens/fee_display_screen.dart';
import 'category_tag.dart';

/// 検索結果1件の表示ウィジェット
///
/// GarbageItemを受け取り、カード形式で品目名・カテゴリタグ・次回収集日・矢印を表示する。
/// 複数カテゴリに該当する場合は補足テキストを表示する。
/// 粗大ごみ品目にマッピングがある場合は粗大ごみリンクを表示する（要件9.1〜9.5）。
class SearchResultTile extends ConsumerWidget {
  /// 表示するゴミ品目
  final GarbageItem item;

  /// タップ時のコールバック（品目詳細画面へ遷移）
  final VoidCallback? onTap;

  const SearchResultTile({
    super.key,
    required this.item,
    this.onTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      elevation: 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              // 品目名とカテゴリタグ
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 品目名
                    Text(
                      item.displayName,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: 6),
                    // カテゴリタグ + 次回収集日
                    Row(
                      children: [
                        CategoryTag(category: item.primaryCategory),
                        const SizedBox(width: 8),
                        _buildNextCollectionDate(ref),
                      ],
                    ),
                    // 複数カテゴリ該当時の補足テキスト
                    if (item.hasMultipleCategories) ...[
                      const SizedBox(height: 4),
                      Text(
                        AppLocalizations.of(context).multipleCategoriesNote,
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                    // 粗大ごみリンク（マッピングあり かつ MunicipalityConfig存在時のみ表示）
                    _buildBulkyWasteLink(context, ref),
                  ],
                ),
              ),
              // 右矢印アイコン
              const Icon(
                Icons.chevron_right,
                color: Colors.grey,
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// 粗大ごみリンクを構築する
  ///
  /// MunicipalityConfigが存在し、かつ品目一覧にGarbageItem.nameと
  /// BulkyWasteItem.garbageItemNameが完全一致するものがある場合のみ表示する。
  /// タップ時はFeeDisplayScreenへ遷移する。
  /// データ取得失敗時はSnackBarでエラーメッセージを表示し、画面に留まる。
  Widget _buildBulkyWasteLink(BuildContext context, WidgetRef ref) {
    final configAsync = ref.watch(municipalityConfigProvider);

    return configAsync.when(
      data: (configResult) {
        // MunicipalityConfigが存在しない場合はリンク非表示
        if (configResult == null) return const SizedBox.shrink();

        final config = configResult.data;
        final municipalityId = config.municipalityId;

        // 品目一覧を取得してマッピングを確認
        final itemsQuery = BulkyWasteQuery(municipalityId: municipalityId);
        final itemsAsync = ref.watch(bulkyWasteItemsProvider(itemsQuery));

        return itemsAsync.when(
          data: (itemsResult) {
            if (itemsResult == null) return const SizedBox.shrink();

            // GarbageItem.name と BulkyWasteItem.garbageItemName の完全一致を探す
            final matchingItem = _findMatchingBulkyWasteItem(
              itemsResult.data.items,
              item.name,
            );

            if (matchingItem == null) return const SizedBox.shrink();

            // マッチした場合: 粗大ごみリンクを表示
            return Padding(
              padding: const EdgeInsets.only(top: 6),
              child: GestureDetector(
                onTap: () => _navigateToFeeDisplay(
                  context,
                  ref,
                  matchingItem,
                  config,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.delete_outline,
                      size: 14,
                      color: Colors.teal[700],
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '粗大ごみ',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Colors.teal[700],
                        decoration: TextDecoration.underline,
                      ),
                    ),
                    const SizedBox(width: 2),
                    Icon(
                      Icons.open_in_new,
                      size: 12,
                      color: Colors.teal[700],
                    ),
                  ],
                ),
              ),
            );
          },
          loading: () => const SizedBox.shrink(),
          error: (_, __) => const SizedBox.shrink(),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }

  /// BulkyWasteItem一覧からGarbageItem.nameと完全一致するものを探す
  BulkyWasteItem? _findMatchingBulkyWasteItem(
    List<BulkyWasteItem> bulkyWasteItems,
    String garbageItemName,
  ) {
    for (final bwi in bulkyWasteItems) {
      if (bwi.garbageItemName == garbageItemName) {
        return bwi;
      }
    }
    return null;
  }

  /// FeeDisplayScreenへ遷移する
  ///
  /// ナビゲーション失敗時はSnackBarでエラーメッセージを表示する。
  void _navigateToFeeDisplay(
    BuildContext context,
    WidgetRef ref,
    BulkyWasteItem bulkyWasteItem,
    MunicipalityConfig config,
  ) {
    try {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => FeeDisplayScreen(
            item: bulkyWasteItem,
            config: config,
          ),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('粗大ごみの詳細情報を取得できませんでした'),
        ),
      );
    }
  }

  /// 次回収集日の表示
  Widget _buildNextCollectionDate(WidgetRef ref) {
    final regionSettingAsync = ref.watch(regionSettingProvider);
    final regionSetting = regionSettingAsync.valueOrNull;

    if (regionSetting == null) {
      return const SizedBox.shrink();
    }

    final scheduleService = ref.watch(scheduleServiceProvider);
    final categoryId = item.primaryCategory.toJsonString();

    return FutureBuilder<DateTime?>(
      future: scheduleService.getNextCollectionDate(
        regionSetting.districtId,
        categoryId,
      ),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SizedBox(
            width: 12,
            height: 12,
            child: CircularProgressIndicator(strokeWidth: 1),
          );
        }

        final nextDate = snapshot.data;
        if (nextDate == null) return const SizedBox.shrink();

        final now = DateTime.now();
        final today = DateTime(now.year, now.month, now.day);
        final diff = nextDate.difference(today).inDays;

        String label;
        if (diff == 0) {
          label = '今日';
        } else if (diff == 1) {
          label = '明日';
        } else {
          label = 'あと${diff}日';
        }

        return Text(
          '次回: $label',
          style: TextStyle(
            fontSize: 11,
            color: diff <= 1 ? Colors.red[700] : Colors.grey[600],
            fontWeight: diff <= 1 ? FontWeight.bold : FontWeight.normal,
          ),
        );
      },
    );
  }
}
