import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../models/garbage_category.dart';
import '../models/garbage_item.dart';
import '../providers/calendar_provider.dart';
import '../providers/region_provider.dart';
import '../widgets/category_tag.dart';

/// 品目詳細画面
///
/// 品目名、カテゴリタグ、次回収集日、出し方説明、注意事項を表示する。
/// 「カレンダーに登録」ボタンでプロトタイプではSnackBarを表示する。
///
/// 要件4.1: 検索結果から品目を選択した時に品目詳細画面を表示
/// 要件4.2: 品目名、カテゴリタグ、次回収集日、出し方の説明を表示
/// 要件4.3: 注意事項が存在する場合、赤色の注意ボックスで注意事項を表示
/// 要件4.4: 「カレンダーに登録」ボタンを表示
/// 要件4.5: カレンダーに登録ボタン押下で次回収集日をデバイスカレンダーに登録
/// 要件4.6: 登録成功時にフィードバックメッセージを表示
/// 要件4.7: カレンダーアクセス権限拒否時にメッセージと設定画面導線を表示
class ItemDetailScreen extends ConsumerWidget {
  /// 表示するゴミ品目
  final GarbageItem item;

  const ItemDetailScreen({
    super.key,
    required this.item,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final regionAsync = ref.watch(regionSettingProvider);
    final districtId = regionAsync.valueOrNull?.districtId;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 1,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.black87),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          '品目詳細',
          style: TextStyle(color: Colors.black87, fontSize: 16),
        ),
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 検索バー（タップで検索画面に戻る）
            _buildTappableSearchBar(context),
            // 「検索結果」ラベル
            _buildSearchResultLabel(),
            // 品目詳細カード
            _buildDetailCard(context, ref, districtId),
          ],
        ),
      ),
    );
  }

  /// タップ可能な検索バー（タップで検索画面に戻る）
  Widget _buildTappableSearchBar(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: GestureDetector(
        onTap: () => Navigator.of(context).pop(),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: Colors.grey[100],
            borderRadius: BorderRadius.circular(24),
          ),
          child: Row(
            children: [
              const Icon(Icons.search, color: Colors.grey),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  item.name,
                  style: const TextStyle(
                    fontSize: 16,
                    color: Colors.black87,
                  ),
                ),
              ),
              Icon(Icons.close, color: Colors.grey[400], size: 20),
            ],
          ),
        ),
      ),
    );
  }

  /// 「検索結果」ラベル
  Widget _buildSearchResultLabel() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Text(
        '検索結果',
        style: TextStyle(
          fontSize: 14,
          color: Colors.grey[700],
        ),
      ),
    );
  }

  /// 品目詳細カード
  Widget _buildDetailCard(
    BuildContext context,
    WidgetRef ref,
    String? districtId,
  ) {
    final categoryColor = CategoryColors.getColor(item.primaryCategory);

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border(
            left: BorderSide(
              color: categoryColor,
              width: 4,
            ),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.08),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 品目名 + 次回収集日
              _buildHeaderRow(ref, districtId),
              const SizedBox(height: 8),
              // カテゴリタグ
              CategoryTag(category: item.primaryCategory),
              const SizedBox(height: 16),
              // 出し方セクション
              _buildDisposalMethodSection(),
              // 注意事項セクション（cautionがある場合のみ）
              if (item.caution != null && item.caution!.isNotEmpty) ...[
                const SizedBox(height: 12),
                _buildCautionSection(),
              ],
              const SizedBox(height: 16),
              // カレンダーに登録ボタン
              _buildCalendarButton(context),
            ],
          ),
        ),
      ),
    );
  }

  /// ヘッダー行（品目名 + 次回収集日）
  Widget _buildHeaderRow(WidgetRef ref, String? districtId) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 品目名
        Expanded(
          child: Text(
            item.name,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        // 次回収集日
        if (districtId != null) _buildNextCollectionDate(ref, districtId),
      ],
    );
  }

  /// 次回収集日の表示
  Widget _buildNextCollectionDate(WidgetRef ref, String districtId) {
    final scheduleService = ref.watch(scheduleServiceProvider);
    final categoryId = item.primaryCategory.toJsonString();

    return FutureBuilder<DateTime?>(
      future: scheduleService.getNextCollectionDate(districtId, categoryId),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 1),
          );
        }

        final nextDate = snapshot.data;
        if (nextDate == null) {
          return const SizedBox.shrink();
        }

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Text(
            '${AppStrings.nextCollectionDate} ${_formatDate(nextDate)}',
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[700],
            ),
          ),
        );
      },
    );
  }

  /// 出し方セクション
  Widget _buildDisposalMethodSection() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(
          Icons.info_outline,
          size: 18,
          color: Colors.blue,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                AppStrings.disposalMethod,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey[800],
                ),
              ),
              const SizedBox(height: 4),
              Text(
                item.disposalMethod,
                style: const TextStyle(
                  fontSize: 14,
                  color: Colors.black87,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  /// 注意事項セクション（赤色注意ボックス）
  Widget _buildCautionSection() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.cautionBackground,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: AppColors.cautionBorder,
          width: 1,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.warning_amber,
            size: 18,
            color: AppColors.error,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              item.caution!,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.error,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// カレンダーに登録ボタン（プロトタイプではSnackBar表示）
  Widget _buildCalendarButton(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: () {
          // プロトタイプではSnackBarで登録完了を表示
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text(AppStrings.calendarRegistered),
              duration: const Duration(seconds: 2),
              behavior: SnackBarBehavior.floating,
            ),
          );
        },
        icon: const Icon(Icons.calendar_today, size: 18),
        label: const Text(AppStrings.registerToCalendar),
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
    );
  }

  /// 日付をフォーマットする（例: 6月18日（水））
  String _formatDate(DateTime date) {
    const weekdays = ['月', '火', '水', '木', '金', '土', '日'];
    // DateTime.weekday: 1=月曜〜7=日曜
    final weekday = weekdays[date.weekday - 1];
    return '${date.month}月${date.day}日（$weekday）';
  }
}
