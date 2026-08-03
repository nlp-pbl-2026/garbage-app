import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../models/garbage_item.dart';
import '../providers/search_provider.dart';

/// よく検索される品目セクションウィジェット
///
/// 事前定義された「よく検索される品目」をタグ形式で表示する。
/// 検索履歴とは独立して常に表示される。
/// タグ選択時に該当品目名で検索を実行する。
class PopularItemsSection extends ConsumerWidget {
  const PopularItemsSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final popularItemsAsync = ref.watch(popularItemsProvider);
    final currentQuery = ref.watch(searchQueryProvider);

    return popularItemsAsync.when(
      data: (items) {
        if (items.isEmpty) return const SizedBox.shrink();

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
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
            Wrap(
              spacing: 8.0,
              runSpacing: 8.0,
              children: items.map((item) {
                final isSelected = currentQuery == item.name;
                return _PopularItemChip(
                  item: item,
                  isSelected: isSelected,
                  onTap: () {
                    ref.read(searchQueryProvider.notifier).state = item.name;
                  },
                );
              }).toList(),
            ),
          ],
        );
      },
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
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}

/// よく検索される品目の個別タグチップ
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
