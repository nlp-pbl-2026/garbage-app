import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../providers/region_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/region_header.dart';
import 'region_selection_screen.dart';

/// 設定画面
///
/// 現在の地域設定の表示・変更と、リマインダー通知の有効/無効切り替えを提供する。
/// ConsumerWidgetで実装し、regionSettingProviderとreminderEnabledProviderを使用する。
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final regionAsync = ref.watch(regionSettingProvider);
    final reminderAsync = ref.watch(reminderEnabledProvider);

    return Scaffold(
      appBar: RegionHeader(
        onEditPressed: () => _navigateToRegionSelection(context, ref),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 「現在の地域」セクション
          _buildSectionTitle('現在の地域'),
          const SizedBox(height: 8),
          _buildRegionCard(context, ref, regionAsync),
          const SizedBox(height: 24),
          // 「地域設定」セクション
          _buildSectionTitle(AppStrings.regionSettings),
          const SizedBox(height: 8),
          _buildRegionSettingCard(context, ref),
          const SizedBox(height: 24),
          // 「通知設定」セクション
          _buildSectionTitle(AppStrings.notificationSettings),
          const SizedBox(height: 8),
          _buildReminderCard(ref, reminderAsync),
        ],
      ),
    );
  }

  /// セクションタイトル
  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.bold,
        color: Colors.grey,
      ),
    );
  }

  /// 現在の地域情報カード
  Widget _buildRegionCard(
    BuildContext context,
    WidgetRef ref,
    AsyncValue<dynamic> regionAsync,
  ) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: regionAsync.when(
        data: (setting) {
          if (setting == null) {
            return ListTile(
              leading: const Icon(Icons.location_off, color: Colors.grey),
              title: const Text(AppStrings.regionNotSet),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => _navigateToRegionSelection(context, ref),
            );
          }
          return Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                const Icon(Icons.location_on, color: AppColors.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        setting.prefectureName,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${setting.municipalityName} ${setting.districtName}',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: Colors.grey),
              ],
            ),
          );
        },
        loading: () => const Padding(
          padding: EdgeInsets.all(16),
          child: Center(
            child: SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          ),
        ),
        error: (_, __) => ListTile(
          leading: const Icon(Icons.error_outline, color: AppColors.error),
          title: const Text(AppStrings.dataLoadError),
          trailing: IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () =>
                ref.read(regionSettingProvider.notifier).loadSetting(),
          ),
        ),
      ),
    );
  }

  /// 地域設定カード（市区町村選択・地区選択への遷移）
  Widget _buildRegionSettingCard(BuildContext context, WidgetRef ref) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: [
          ListTile(
            leading: const Icon(Icons.apartment, color: AppColors.primary),
            title: const Text('市区町村を変更'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _navigateToRegionSelection(context, ref),
          ),
          const Divider(height: 1, indent: 56),
          ListTile(
            leading: const Icon(Icons.map_outlined, color: AppColors.primary),
            title: const Text('地区を変更'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _navigateToRegionSelection(context, ref),
          ),
        ],
      ),
    );
  }

  /// リマインダー通知カード
  Widget _buildReminderCard(WidgetRef ref, AsyncValue<bool> reminderAsync) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: [
          reminderAsync.when(
            data: (enabled) => SwitchListTile(
              secondary: Icon(
                enabled
                    ? Icons.notifications_active
                    : Icons.notifications_off_outlined,
                color: enabled ? AppColors.primary : Colors.grey,
              ),
              title: const Text(AppStrings.reminderToggle),
              subtitle: const Text(
                '夕方に翌日の収集予定を通知します',
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
              value: enabled,
              activeColor: AppColors.primary,
              onChanged: (_) {
                ref.read(reminderEnabledProvider.notifier).toggle();
              },
            ),
            loading: () => const ListTile(
              leading: SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              title: Text(AppStrings.reminderToggle),
            ),
            error: (_, __) => ListTile(
              leading:
                  const Icon(Icons.error_outline, color: AppColors.error),
              title: const Text(AppStrings.reminderToggle),
              subtitle: const Text(
                'リマインダー設定の読み込みに失敗しました',
                style: TextStyle(fontSize: 12, color: AppColors.error),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 地域選択画面へ遷移し、戻ってきた時にフィードバックを表示する
  void _navigateToRegionSelection(BuildContext context, WidgetRef ref) {
    // 遷移前の地域設定を保持（保存失敗時のロールバック用）
    final previousSetting = ref.read(regionSettingProvider).valueOrNull;

    Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => RegionSelectionScreen(
          onRegionSelected: () {
            Navigator.of(context).pop(true);
          },
        ),
      ),
    ).then((result) {
      if (result == true && context.mounted) {
        // 地域変更成功時のフィードバック表示（2秒間）
        final currentSetting = ref.read(regionSettingProvider).valueOrNull;
        if (currentSetting != null && currentSetting != previousSetting) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(AppStrings.regionSaved),
              duration: Duration(seconds: 2),
              behavior: SnackBarBehavior.floating,
            ),
          );
        }
      } else if (result != true && context.mounted) {
        // 保存失敗時：変更前データを保持（regionSettingProviderがエラー状態の場合）
        final currentState = ref.read(regionSettingProvider);
        if (currentState.hasError && previousSetting != null) {
          // エラー状態の場合は変更前データを復元
          ref
              .read(regionSettingProvider.notifier)
              .saveSetting(previousSetting);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(AppStrings.saveError),
              duration: Duration(seconds: 3),
              behavior: SnackBarBehavior.floating,
              backgroundColor: AppColors.error,
            ),
          );
        }
      }
    });
  }
}
