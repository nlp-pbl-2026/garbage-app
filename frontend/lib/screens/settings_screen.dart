import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../models/gps_detection.dart';
import '../models/region.dart';
import '../providers/auth_provider.dart';
import '../providers/gps_detection_provider.dart';
import '../providers/multi_region_provider.dart';
import '../providers/region_provider.dart';
import '../providers/settings_provider.dart';
import '../providers/theme_provider.dart';
import '../services/notification_service.dart';
import '../widgets/notification_customization_widget.dart';
import '../widgets/region_header.dart';
import 'faq_screen.dart';
import 'login_screen.dart';
import 'region_selection_screen.dart';
import 'terms_of_service_screen.dart';

/// 設定画面
///
/// 現在の地域設定の表示・変更と、リマインダー通知の有効/無効切り替えを提供する。
/// ConsumerStatefulWidgetで実装し、regionSettingProviderとreminderEnabledProviderを使用する。
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  @override
  Widget build(BuildContext context) {
    final regionAsync = ref.watch(regionSettingProvider);
    final reminderAsync = ref.watch(reminderEnabledProvider);
    final authAsync = ref.watch(authStateProvider);
    final multiRegionAsync = ref.watch(multiRegionProvider);

    // GPS判定結果をリッスンし、成功時に確認ダイアログ、エラー時にSnackBarを表示
    ref.listen<GpsDetectionState>(gpsDetectionProvider, (previous, next) {
      if (next is GpsDetectionSuccess) {
        _showGpsConfirmationDialog(next.result);
      } else if (next is GpsDetectionError) {
        if (next.errorType == GpsDetectionErrorType.permissionDenied ||
            next.errorType == GpsDetectionErrorType.serviceDisabled) {
          _showSettingsSnackBar(next.message);
        } else if (next.errorType == GpsDetectionErrorType.timeout ||
            next.errorType == GpsDetectionErrorType.inaccurate) {
          _showRetrySnackBar(next.message);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(next.message),
              duration: const Duration(seconds: 3),
            ),
          );
        }
        // 状態を Idle にリセットしてボタンを再タップ可能にする
        ref.read(gpsDetectionProvider.notifier).reset();
      }
    });

    return Scaffold(
      appBar: RegionHeader(
        onEditPressed: () => _navigateToRegionSelection(context, ref),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 「アカウント」セクション
          _buildSectionTitle('アカウント'),
          const SizedBox(height: 8),
          _buildAccountCard(context, ref, authAsync),
          const SizedBox(height: 24),
          // 「現在の地域」セクション
          _buildSectionTitle('現在の地域'),
          const SizedBox(height: 8),
          _buildRegionCard(context, ref, regionAsync),
          const SizedBox(height: 8),
          _buildMultiRegionCard(context, ref, multiRegionAsync),
          const SizedBox(height: 24),
          // 「地域設定」セクション
          _buildSectionTitle(AppStrings.regionSettings),
          const SizedBox(height: 8),
          _buildRegionSettingCard(context, ref),
          const SizedBox(height: 24),
          // 「通知設定」セクション
          _buildSectionTitle(AppStrings.notificationSettings),
          const SizedBox(height: 8),
          _buildReminderCard(context, ref, reminderAsync),
          const SizedBox(height: 24),
          // 「テーマ」セクション
          _buildSectionTitle('テーマ'),
          const SizedBox(height: 8),
          _buildThemeCard(context, ref),
          const SizedBox(height: 24),
          // 「その他」セクション
          _buildSectionTitle('その他'),
          const SizedBox(height: 8),
          _buildFaqCard(context),
          const SizedBox(height: 8),
          _buildTermsCard(context),
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

  /// アカウントカード
  Widget _buildAccountCard(
    BuildContext context,
    WidgetRef ref,
    AsyncValue<AuthState> authAsync,
  ) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: authAsync.when(
        data: (state) {
          if (state.isLoggedIn) {
            // ログイン済み
            return Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.person, color: AppColors.primary),
                  title: Text(state.username ?? ''),
                  subtitle: const Text(
                    'ログイン中',
                    style: TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                ),
                const Divider(height: 1, indent: 56),
                ListTile(
                  leading: const Icon(Icons.lock_outline, color: AppColors.primary),
                  title: const Text('パスワード変更'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _showChangePasswordDialog(context, ref),
                ),
                const Divider(height: 1, indent: 56),
                ListTile(
                  leading: const Icon(Icons.logout, color: Colors.red),
                  title: const Text('ログアウト'),
                  onTap: () {
                    ref.read(authStateProvider.notifier).logout();
                  },
                ),
              ],
            );
          } else {
            // 未ログイン
            return ListTile(
              leading: const Icon(Icons.login, color: AppColors.primary),
              title: const Text('ログイン / 新規登録'),
              subtitle: const Text(
                '設定を同期するにはログインしてください',
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                );
              },
            );
          }
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
          leading: const Icon(Icons.login, color: AppColors.primary),
          title: const Text('ログイン / 新規登録'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const LoginScreen()),
            );
          },
        ),
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
    final gpsState = ref.watch(gpsDetectionProvider);
    final isGpsLoading = gpsState is GpsDetectionLoading;

    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: [
          ListTile(
            leading: isGpsLoading
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.my_location, color: AppColors.primary),
            title: const Text('現在地から再設定'),
            trailing: const Icon(Icons.chevron_right),
            onTap: isGpsLoading
                ? null
                : () {
                    ref.read(gpsDetectionProvider.notifier).detectDistrict();
                  },
          ),
          const Divider(height: 1, indent: 56),
          ListTile(
            leading: const Icon(Icons.edit_location_alt, color: AppColors.primary),
            title: const Text('地域を変更'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _navigateToRegionSelection(context, ref),
          ),
          const Divider(height: 1, indent: 56),
          ListTile(
            leading: const Icon(Icons.my_location, color: AppColors.primary),
            title: const Text('現在地から再設定'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _navigateToRegionSelectionWithAutoDetect(context, ref),
          ),
        ],
      ),
    );
  }

  /// リマインダー通知カード
  Widget _buildReminderCard(BuildContext context, WidgetRef ref, AsyncValue<bool> reminderAsync) {
    final notificationService = ref.watch(notificationServiceProvider);

    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: [
          reminderAsync.when(
            data: (enabled) => Column(
              children: [
                SwitchListTile(
                  secondary: Icon(
                    enabled
                        ? Icons.notifications_active
                        : Icons.notifications_off_outlined,
                    color: enabled ? AppColors.primary : Colors.grey,
                  ),
                  title: const Text(AppStrings.reminderToggle),
                  subtitle: const Text(
                    '収集日の前日と当日に通知します',
                    style: TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                  value: enabled,
                  activeColor: AppColors.primary,
                  onChanged: (_) async {
                    try {
                      await ref.read(reminderEnabledProvider.notifier).toggle();
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: const Text('リマインダーの設定に失敗しました'),
                            duration: const Duration(seconds: 10),
                            action: SnackBarAction(
                              label: '再試行',
                              onPressed: () {
                                ref.read(reminderEnabledProvider.notifier).toggle();
                              },
                            ),
                          ),
                        );
                      }
                    }
                  },
                ),
                if (enabled) ...[
                  const Divider(height: 1, indent: 16, endIndent: 16),
                  _buildTimePicker(
                    context,
                    notificationService,
                    icon: Icons.nightlight_round,
                    label: '前日通知',
                    getTime: () => notificationService.getEveningTime(),
                    setTime: (h, m) => notificationService.setEveningTime(h, m),
                  ),
                  _buildTimePicker(
                    context,
                    notificationService,
                    icon: Icons.wb_sunny,
                    label: '当日通知',
                    getTime: () => notificationService.getMorningTime(),
                    setTime: (h, m) => notificationService.setMorningTime(h, m),
                  ),
                  const NotificationCustomizationWidget(),
                ],
              ],
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
              trailing: TextButton.icon(
                onPressed: () {
                  ref.invalidate(reminderEnabledProvider);
                },
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('再試行', style: TextStyle(fontSize: 12)),
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.primary,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// GPS自動検出付きで地域選択画面へ遷移する
  void _navigateToRegionSelectionWithAutoDetect(
      BuildContext context, WidgetRef ref) {
    Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => RegionSelectionScreen(
          autoDetect: true,
          onRegionSelected: () {
            Navigator.of(context).pop(true);
          },
        ),
      ),
    ).then((result) {
      if (result == true && context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('地域設定を更新しました'),
            duration: Duration(seconds: 2),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    });
  }

  /// 通知時刻ピッカー行
  Widget _buildTimePicker(
    BuildContext context,
    NotificationService service, {
    required IconData icon,
    required String label,
    required Future<({int hour, int minute})> Function() getTime,
    required Future<void> Function(int hour, int minute) setTime,
  }) {
    return FutureBuilder<({int hour, int minute})>(
      future: getTime(),
      builder: (context, snapshot) {
        final hour = snapshot.data?.hour ?? 0;
        final minute = snapshot.data?.minute ?? 0;
        final timeStr =
            '${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')}';

        return ListTile(
          leading: Icon(icon, color: Colors.grey[600], size: 20),
          title: Text(label, style: const TextStyle(fontSize: 14)),
          trailing: TextButton(
            onPressed: () async {
              final picked = await showTimePicker(
                context: context,
                initialTime: TimeOfDay(hour: hour, minute: minute),
              );
              if (picked != null) {
                await setTime(picked.hour, picked.minute);
                // リビルドのため setState 相当（StatelessWidget なので ref.invalidate で代替）
                (context as Element).markNeedsBuild();
              }
            },
            child: Text(
              timeStr,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppColors.primary,
              ),
            ),
          ),
        );
      },
    );
  }

  /// テーマ設定カード
  Widget _buildThemeCard(BuildContext context, WidgetRef ref) {
    final currentMode = ref.watch(themeModeProvider);

    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          children: [
            _buildThemeOption(
              context,
              ref,
              icon: Icons.light_mode,
              label: 'ライト',
              mode: ThemeMode.light,
              currentMode: currentMode,
            ),
            const Divider(height: 1, indent: 56),
            _buildThemeOption(
              context,
              ref,
              icon: Icons.dark_mode,
              label: 'ダーク',
              mode: ThemeMode.dark,
              currentMode: currentMode,
            ),
          ],
        ),
      ),
    );
  }

  /// テーマ選択肢の行
  Widget _buildThemeOption(
    BuildContext context,
    WidgetRef ref, {
    required IconData icon,
    required String label,
    required ThemeMode mode,
    required ThemeMode currentMode,
  }) {
    final isSelected = currentMode == mode;

    return ListTile(
      leading: Icon(
        icon,
        color: isSelected ? AppColors.primary : Colors.grey,
      ),
      title: Text(label),
      trailing: isSelected
          ? const Icon(Icons.check, color: AppColors.primary)
          : null,
      onTap: () {
        ref.read(themeModeProvider.notifier).setThemeMode(mode);
      },
    );
  }

  /// よくある質問カード
  Widget _buildFaqCard(BuildContext context) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: const Icon(Icons.help_outline, color: AppColors.primary),
        title: const Text('よくある質問'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => const FaqScreen(),
            ),
          );
        },
      ),
    );
  }

  /// 利用規約カード
  Widget _buildTermsCard(BuildContext context) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: const Icon(Icons.description_outlined, color: AppColors.primary),
        title: const Text('利用規約'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => const TermsOfServiceScreen(),
            ),
          );
        },
      ),
    );
  }

  /// 複数地区管理カード
  ///
  /// 保存済み地区リストを表示し、タップでアクティブ切り替え、
  /// スワイプで削除、「地区を追加」ボタンで新規追加を提供する。
  Widget _buildMultiRegionCard(
    BuildContext context,
    WidgetRef ref,
    AsyncValue<List<SavedRegion>> multiRegionAsync,
  ) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: multiRegionAsync.when(
        data: (regions) {
          return Column(
            children: [
              if (regions.isNotEmpty) ...[
                ...regions.map((region) => _buildSavedRegionTile(
                      context, ref, region, regions.length)),
              ],
              if (regions.length < 5)
                ListTile(
                  leading: const Icon(Icons.add_location_alt,
                      color: AppColors.primary),
                  title: const Text('地区を追加'),
                  subtitle: Text(
                    '${regions.length}/5件',
                    style: const TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _showAddRegionDialog(context, ref),
                ),
            ],
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
          title: const Text('地区リストの読み込みに失敗しました'),
          trailing: TextButton.icon(
            onPressed: () {
              ref.read(multiRegionProvider.notifier).loadRegions();
            },
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('再試行', style: TextStyle(fontSize: 12)),
            style: TextButton.styleFrom(
              foregroundColor: AppColors.primary,
            ),
          ),
        ),
      ),
    );
  }

  /// 保存済み地区の個別タイル
  Widget _buildSavedRegionTile(
    BuildContext context,
    WidgetRef ref,
    SavedRegion region,
    int totalCount,
  ) {
    return Dismissible(
      key: Key(region.id),
      direction:
          totalCount > 1 ? DismissDirection.endToStart : DismissDirection.none,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 16),
        color: AppColors.error,
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      confirmDismiss: (_) async {
        return await _showDeleteConfirmDialog(context, region.label);
      },
      onDismissed: (_) {
        ref.read(multiRegionProvider.notifier).removeRegion(region.id);
      },
      child: ListTile(
        leading: Icon(
          region.isActive ? Icons.radio_button_checked : Icons.radio_button_off,
          color: region.isActive ? AppColors.primary : Colors.grey,
        ),
        title: Text(
          region.label,
          style: TextStyle(
            fontWeight: region.isActive ? FontWeight.bold : FontWeight.normal,
          ),
        ),
        subtitle: Text(
          '${region.setting.municipalityName} ${region.setting.districtName}',
          style: const TextStyle(fontSize: 12, color: Colors.grey),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (region.isActive)
              const Chip(
                label: Text('使用中', style: TextStyle(fontSize: 11)),
                backgroundColor: Color(0xFFE8F5E9),
                padding: EdgeInsets.zero,
                visualDensity: VisualDensity.compact,
              ),
            if (!region.isActive && totalCount > 1)
              IconButton(
                icon: const Icon(Icons.delete_outline, size: 20),
                color: Colors.red[400],
                onPressed: () async {
                  final confirmed =
                      await _showDeleteConfirmDialog(context, region.label);
                  if (confirmed == true) {
                    ref
                        .read(multiRegionProvider.notifier)
                        .removeRegion(region.id);
                  }
                },
              ),
          ],
        ),
        onTap: region.isActive
            ? null
            : () {
                ref
                    .read(multiRegionProvider.notifier)
                    .setActiveRegion(region.id);
              },
      ),
    );
  }

  /// 地区追加ダイアログを表示する
  void _showAddRegionDialog(BuildContext context, WidgetRef ref) {
    final labelController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('地区を追加'),
          content: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  '新しい地区のラベルを入力してください。\n次に市区町村と地区を選択します。',
                  style: TextStyle(fontSize: 13, color: Colors.grey),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: labelController,
                  decoration: const InputDecoration(
                    labelText: 'ラベル',
                    hintText: '例: 職場、実家',
                    border: OutlineInputBorder(),
                  ),
                  maxLength: 10,
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'ラベルを入力してください';
                    }
                    return null;
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('キャンセル'),
            ),
            ElevatedButton(
              onPressed: () {
                if (formKey.currentState!.validate()) {
                  final label = labelController.text.trim();
                  Navigator.of(dialogContext).pop();
                  // 地域選択画面に遷移し、選択結果を新しい地区として保存
                  _navigateToAddRegion(context, ref, label);
                }
              },
              child: const Text('次へ'),
            ),
          ],
        );
      },
    );
  }

  /// 地区削除確認ダイアログを表示する
  Future<bool> _showDeleteConfirmDialog(
    BuildContext context,
    String label,
  ) async {
    return await showDialog<bool>(
          context: context,
          builder: (dialogContext) {
            return AlertDialog(
              title: const Text('地区を削除'),
              content: Text('「$label」を削除しますか？'),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(false),
                  child: const Text('キャンセル'),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.error,
                  ),
                  onPressed: () => Navigator.of(dialogContext).pop(true),
                  child: const Text('削除'),
                ),
              ],
            );
          },
        ) ??
        false;
  }

  /// 設定アプリ誘導SnackBarを表示する。
  ///
  /// permissionDenied / serviceDisabled エラー時に、「設定を開く」アクションボタン付き
  /// SnackBarを表示する。ユーザーがアクションをタップするか閉じるまで維持される。
  /// タップ時は Geolocator.openAppSettings() を呼び出す。
  /// 設定から戻った後は自動再試行せず、ボタン再タップ可能な状態を維持する。
  void _showSettingsSnackBar(String message) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(days: 365),
        action: SnackBarAction(
          label: '設定を開く',
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
            Geolocator.openAppSettings();
          },
        ),
      ),
    );
  }

  /// タイムアウト・精度不足エラー時の再試行SnackBarを表示
  ///
  /// 10秒後に自動で消えるか、ユーザーが「再試行」をタップすると消える。
  /// 「再試行」タップ時: SnackBarを閉じてGPS判定フローを再実行する。
  /// 再試行が再度失敗した場合は再度SnackBarを表示する（再試行回数に上限なし）。
  void _showRetrySnackBar(String message) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(seconds: 10),
        action: SnackBarAction(
          label: '再試行',
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
            ref.read(gpsDetectionProvider.notifier).detectDistrict();
          },
        ),
      ),
    );
  }

  /// GPS判定成功時の確認ダイアログを表示
  void _showGpsConfirmationDialog(DistrictMatchResult result) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('GPS判定結果'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('以下の地域が検出されました：'),
              const SizedBox(height: 12),
              const Text('都道府県: 愛媛県'),
              const Text('市区町村: 松山市'),
              Text('地区: ${result.districtName}'),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
                ref.read(gpsDetectionProvider.notifier).reset();
              },
              child: const Text('キャンセル'),
            ),
            ElevatedButton(
              onPressed: () async {
                final setting = RegionSetting(
                  prefectureId: '38',
                  prefectureName: '愛媛県',
                  municipalityId: '38201',
                  municipalityName: '松山市',
                  districtId: '38201-${result.districtNumber}',
                  districtName: result.districtName,
                );
                await ref
                    .read(regionSettingProvider.notifier)
                    .saveSetting(setting);
                if (dialogContext.mounted) {
                  Navigator.of(dialogContext).pop();
                }
                // 成功フィードバック表示
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(AppStrings.regionSaved),
                      duration: Duration(seconds: 2),
                      behavior: SnackBarBehavior.floating,
                    ),
                  );
                }
                ref.read(gpsDetectionProvider.notifier).reset();
              },
              child: const Text('この地域で設定'),
            ),
          ],
        );
      },
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

  /// 新しい地区を追加するための地域選択画面に遷移する
  ///
  /// ユーザーが地域を選択したら、その設定を指定ラベルで保存地区に追加する。
  void _navigateToAddRegion(BuildContext context, WidgetRef ref, String label) {
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
        // 地域選択が完了した → 選択された地域を指定ラベルで保存
        final newSetting = ref.read(regionSettingProvider).valueOrNull;
        if (newSetting != null) {
          ref.read(multiRegionProvider.notifier).addRegion(label, newSetting);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('「$label」を追加しました'),
              duration: const Duration(seconds: 2),
              behavior: SnackBarBehavior.floating,
            ),
          );
        }
      }
    });
  }

  /// パスワード変更ダイアログを表示する
  void _showChangePasswordDialog(BuildContext context, WidgetRef ref) {
    final currentPasswordController = TextEditingController();
    final newPasswordController = TextEditingController();
    final confirmPasswordController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            bool isLoading = false;
            String? errorMessage;

            return AlertDialog(
              title: const Text('パスワード変更'),
              content: Form(
                key: formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextFormField(
                      controller: currentPasswordController,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: '現在のパスワード',
                        border: OutlineInputBorder(),
                      ),
                      validator: (v) =>
                          v == null || v.isEmpty ? '入力してください' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: newPasswordController,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: '新しいパスワード',
                        border: OutlineInputBorder(),
                      ),
                      validator: (v) {
                        if (v == null || v.isEmpty) return '入力してください';
                        if (v.length < 6) return '6文字以上で入力してください';
                        return null;
                      },
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: confirmPasswordController,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: '新しいパスワード（確認）',
                        border: OutlineInputBorder(),
                      ),
                      validator: (v) {
                        if (v != newPasswordController.text) {
                          return 'パスワードが一致しません';
                        }
                        return null;
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  child: const Text('キャンセル'),
                ),
                ElevatedButton(
                  onPressed: () async {
                    if (!formKey.currentState!.validate()) return;

                    try {
                      final authService = ref.read(authServiceProvider);
                      await authService.changePassword(
                        currentPasswordController.text,
                        newPasswordController.text,
                      );
                      if (dialogContext.mounted) {
                        Navigator.of(dialogContext).pop();
                      }
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('パスワードを変更しました'),
                            behavior: SnackBarBehavior.floating,
                          ),
                        );
                      }
                    } catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              e.toString().replaceAll('Exception: ', ''),
                            ),
                            backgroundColor: AppColors.error,
                            behavior: SnackBarBehavior.floating,
                          ),
                        );
                      }
                    }
                  },
                  child: const Text('変更'),
                ),
              ],
            );
          },
        );
      },
    );
  }
}