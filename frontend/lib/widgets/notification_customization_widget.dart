import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/garbage_category.dart';
import '../models/garbage_item.dart';
import '../models/notification_timing_type.dart';
import '../providers/notification_customization_provider.dart';
import '../providers/settings_provider.dart';

/// 種別ごとの通知カスタマイズウィジェット
///
/// 各GarbageCategory（5種別）に対して前日通知・当日通知のトグルスイッチを表示する。
/// リマインダーが無効な場合は非表示（SizedBox.shrink）を返す。
/// ConsumerWidgetとして実装し、notificationCustomizationProviderをwatchする。
class NotificationCustomizationWidget extends ConsumerWidget {
  const NotificationCustomizationWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settingsAsync = ref.watch(notificationCustomizationProvider);
    final reminderEnabled =
        ref.watch(reminderEnabledProvider).valueOrNull ?? false;

    // リマインダーが無効なら非表示
    if (!reminderEnabled) return const SizedBox.shrink();

    return settingsAsync.when(
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: 16),
        child: Center(
          child: SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      ),
      error: (_, __) => const Padding(
        padding: EdgeInsets.all(16),
        child: Text(
          '設定の読み込みに失敗しました',
          style: TextStyle(fontSize: 12, color: Colors.grey),
        ),
      ),
      data: (settings) => _buildCategoryList(context, ref, settings),
    );
  }

  /// カテゴリ別通知設定リストを構築する
  Widget _buildCategoryList(
    BuildContext context,
    WidgetRef ref,
    CategorySettingsMap settings,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Divider(height: 1, indent: 16, endIndent: 16),
        const Padding(
          padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: Text(
            '種別ごとの通知設定',
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        ...GarbageCategory.values.map((category) {
          final setting = settings[category];
          if (setting == null) return const SizedBox.shrink();

          final color = CategoryColors.getColor(category);
          final label = CategoryColors.getLabel(category);

          return _CategoryNotificationTile(
            label: label,
            color: color,
            eveningEnabled: setting.eveningEnabled,
            morningEnabled: setting.morningEnabled,
            onEveningToggle: () => ref
                .read(notificationCustomizationProvider.notifier)
                .toggle(category, NotificationTimingType.evening),
            onMorningToggle: () => ref
                .read(notificationCustomizationProvider.notifier)
                .toggle(category, NotificationTimingType.morning),
          );
        }),
      ],
    );
  }
}

/// 各カテゴリの通知トグル行
///
/// カラードット、カテゴリラベル、前日通知トグル、当日通知トグルを1行に表示する。
class _CategoryNotificationTile extends StatelessWidget {
  final String label;
  final Color color;
  final bool eveningEnabled;
  final bool morningEnabled;
  final VoidCallback onEveningToggle;
  final VoidCallback onMorningToggle;

  const _CategoryNotificationTile({
    required this.label,
    required this.color,
    required this.eveningEnabled,
    required this.morningEnabled,
    required this.onEveningToggle,
    required this.onMorningToggle,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: [
          // カテゴリカラードット
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color,
            ),
          ),
          const SizedBox(width: 8),
          // カテゴリラベル
          Expanded(
            child: Text(
              label,
              style: const TextStyle(fontSize: 13),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          // 前日通知トグル
          _buildToggle(
            label: '前日',
            enabled: eveningEnabled,
            onToggle: onEveningToggle,
          ),
          const SizedBox(width: 8),
          // 当日通知トグル
          _buildToggle(
            label: '当日',
            enabled: morningEnabled,
            onToggle: onMorningToggle,
          ),
        ],
      ),
    );
  }

  /// トグルスイッチとラベルのペアを構築する
  Widget _buildToggle({
    required String label,
    required bool enabled,
    required VoidCallback onToggle,
  }) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            color: Colors.grey[600],
          ),
        ),
        SizedBox(
          width: 40,
          height: 28,
          child: FittedBox(
            fit: BoxFit.contain,
            child: Switch(
              value: enabled,
              onChanged: (_) => onToggle(),
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
          ),
        ),
      ],
    );
  }
}
