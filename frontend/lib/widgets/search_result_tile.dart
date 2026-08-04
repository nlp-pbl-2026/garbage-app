import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/garbage_item.dart';
import '../constants/strings.dart';
import '../providers/calendar_provider.dart';
import '../providers/region_provider.dart';
import 'category_tag.dart';

/// 検索結果1件の表示ウィジェット
///
/// GarbageItemを受け取り、カード形式で品目名・カテゴリタグ・次回収集日・矢印を表示する。
/// 複数カテゴリに該当する場合は補足テキストを表示する。
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
                      item.name,
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
                        AppStrings.multipleCategoriesNote,
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
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
