import 'package:flutter/material.dart';

import '../models/garbage_item.dart';
import '../constants/strings.dart';
import 'category_tag.dart';

/// 検索結果1件の表示ウィジェット
///
/// GarbageItemを受け取り、カード形式で品目名・カテゴリタグ・矢印を表示する。
/// 複数カテゴリに該当する場合は補足テキストを表示する。
///
/// 要件2.4: 各品目に対応するGarbage_Categoryを色分けされたタグで表示
/// 要件2.5: 複数カテゴリ該当時に主要分類タグと補足情報を表示
class SearchResultTile extends StatelessWidget {
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
  Widget build(BuildContext context) {
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
                    // カテゴリタグ
                    CategoryTag(category: item.primaryCategory),
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
}
