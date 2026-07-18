import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../models/garbage_item.dart';
import '../providers/search_provider.dart';

/// よく検索される品目セクションウィジェット
///
/// 検索画面下部に表示し、事前定義されたよく検索される品目を
/// タグ形式（5-10件）で表示する。
/// タグ選択時に該当品目名で検索を実行する。
///
/// 要件3.1: 事前定義されたよく検索される品目を5件以上10件以下のタグ形式で表示
/// 要件3.2: タグ選択時に選択された品目名を検索語として検索を実行
/// 要件3.3: データ取得失敗時はタグ表示領域を非表示にする
class PopularItemsSection extends ConsumerWidget {
  const PopularItemsSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final popularItemsAsync = ref.watch(popularItemsProvider);
    final currentQuery = ref.watch(searchQueryProvider);

    return popularItemsAsync.when(
      data: (items) {
        // 品目が空の場合はセクション非表示
        if (items.isEmpty) {
          return const SizedBox.shrink();
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // セクションタイトル
            const Padding(
              padding: EdgeInsets.only(bottom: 12.0),
              child: Text(
                AppStrings.popularItems,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.black87,
                ),
              ),
            ),
            // タグをWrap（折り返し）レイアウトで配置
            Wrap(
              spacing: 8.0,
              runSpacing: 8.0,
              children: items.map((item) {
                final isSelected = currentQuery == item.name;
                return _PopularItemChip(
                  item: item,
                  isSelected: isSelected,
                  onTap: () {
                    // タグ選択時: searchQueryProviderの値を更新 → 検索実行
                    ref.read(searchQueryProvider.notifier).state = item.name;
                  },
                );
              }).toList(),
            ),
          ],
        );
      },
      // ローディング中は小さいインジケーター表示
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: 16.0),
        child: Center(
          child: SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      ),
      // データ取得失敗時はセクション全体を非表示
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}

/// よく検索される品目の個別タグチップ
///
/// ボーダー付き角丸タグで表示し、選択中は緑色ハイライトにする。
class _PopularItemChip extends StatelessWidget {
  final GarbageItem item;
  final bool isSelected;
  final VoidCallback onTap;

  const _PopularItemChip({
    required this.item,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary.withOpacity(0.1) : Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? AppColors.primary : Colors.grey.shade300,
            width: isSelected ? 1.5 : 1.0,
          ),
        ),
        child: Text(
          item.name,
          style: TextStyle(
            fontSize: 14,
            color: isSelected ? AppColors.primary : Colors.black87,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}
