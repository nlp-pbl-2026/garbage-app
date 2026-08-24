import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/strings.dart';
import '../providers/auth_provider.dart';
import '../providers/region_provider.dart';
import '../screens/login_screen.dart';

/// 地域ヘッダーウィジェット
///
/// 各画面のAppBarとして使用する。
/// 位置アイコン + 市区町村名・地区名を表示し、
/// 編集アイコン押下で設定画面への遷移を行う。
/// 地域未設定時は未設定メッセージを表示する。
/// 右端にログイン状態アイコンを表示する。
class RegionHeader extends ConsumerWidget implements PreferredSizeWidget {
  /// 編集アイコン押下時のコールバック（設定画面へ遷移）
  final VoidCallback? onEditPressed;

  /// AppBarに追加表示するアクションウィジェット
  final List<Widget>? extraActions;

  const RegionHeader({
    super.key,
    this.onEditPressed,
    this.extraActions,
  });

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final regionAsync = ref.watch(regionSettingProvider);
    final authAsync = ref.watch(authStateProvider);
    final colors = Theme.of(context).colorScheme;

    return AppBar(
      elevation: 1,
      leading: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Icon(
          Icons.location_on,
          color: colors.primary,
        ),
      ),
      title: regionAsync.when(
        data: (setting) {
          if (setting == null) {
            // 地域未設定時
            return Text(
              AppStrings.regionNotSet,
              style: TextStyle(
                color: colors.onSurface,
                fontSize: 16,
              ),
            );
          }
          // 地域設定済み：displayNameで20文字制限付き表示
          return Text(
            setting.displayName,
            style: TextStyle(
              color: colors.onSurface,
              fontSize: 16,
            ),
            overflow: TextOverflow.ellipsis,
            maxLines: 1,
          );
        },
        loading: () => const SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
        error: (_, __) => Text(
          AppStrings.regionNotSet,
          style: TextStyle(
            color: colors.onSurface,
            fontSize: 16,
          ),
        ),
      ),
      actions: [
        // 追加アクション（各画面から指定可能）
        if (extraActions != null) ...extraActions!,
        // 地域変更ボタン
        IconButton(
          icon: Icon(
            Icons.edit,
            color: colors.onSurface,
          ),
          onPressed: onEditPressed,
          tooltip: AppStrings.changeRegion,
        ),
        // ログイン状態アイコン（タップでログイン画面へ遷移）
        _buildAuthStatusIcon(context, authAsync, colors),
        const SizedBox(width: 4),
      ],
    );
  }

  /// ログイン状態を示すアイコンウィジェット（タップ可能）
  Widget _buildAuthStatusIcon(
    BuildContext context,
    AsyncValue<AuthState> authAsync,
    ColorScheme colors,
  ) {
    return authAsync.when(
      data: (authState) {
        if (authState.isLoggedIn) {
          return GestureDetector(
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('${authState.username} でログイン中'),
                  duration: const Duration(seconds: 2),
                ),
              );
            },
            child: Tooltip(
              message: '${authState.username} でログイン中',
              child: Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: colors.primaryContainer,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.person,
                  color: colors.onPrimaryContainer,
                  size: 20,
                ),
              ),
            ),
          );
        } else {
          return GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const LoginScreen(),
                ),
              );
            },
            child: Tooltip(
              message: 'ログイン / 新規登録',
              child: Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: colors.surfaceContainerHighest,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.person_outline,
                  color: colors.onSurfaceVariant,
                  size: 20,
                ),
              ),
            ),
          );
        }
      },
      loading: () => const SizedBox(
        width: 32,
        height: 32,
        child: CircularProgressIndicator(strokeWidth: 2),
      ),
      error: (_, __) => Icon(
        Icons.person_off,
        color: colors.onSurfaceVariant,
        size: 20,
      ),
    );
  }
}
