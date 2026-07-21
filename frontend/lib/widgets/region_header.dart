import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../providers/region_provider.dart';

/// 地域ヘッダーウィジェット
///
/// 各画面のAppBarとして使用する。
/// 位置アイコン + 市区町村名・地区名を表示し、
/// 編集アイコン押下で設定画面への遷移を行う。
/// 地域未設定時は未設定メッセージを表示する。
class RegionHeader extends ConsumerWidget implements PreferredSizeWidget {
  /// 編集アイコン押下時のコールバック（設定画面へ遷移）
  final VoidCallback? onEditPressed;

  const RegionHeader({
    super.key,
    this.onEditPressed,
  });

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final regionAsync = ref.watch(regionSettingProvider);

    return AppBar(
      backgroundColor: Colors.white,
      elevation: 1,
      leading: const Padding(
        padding: EdgeInsets.all(12.0),
        child: Icon(
          Icons.location_on,
          color: AppColors.primary,
        ),
      ),
      title: regionAsync.when(
        data: (setting) {
          if (setting == null) {
            // 地域未設定時
            return const Text(
              AppStrings.regionNotSet,
              style: TextStyle(
                color: Colors.black87,
                fontSize: 16,
              ),
            );
          }
          // 地域設定済み：displayNameで20文字制限付き表示
          return Text(
            setting.displayName,
            style: const TextStyle(
              color: Colors.black87,
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
        error: (_, __) => const Text(
          AppStrings.regionNotSet,
          style: TextStyle(
            color: Colors.black87,
            fontSize: 16,
          ),
        ),
      ),
      actions: [
        IconButton(
          icon: const Icon(
            Icons.edit,
            color: Colors.black87,
          ),
          onPressed: onEditPressed,
          tooltip: AppStrings.changeRegion,
        ),
      ],
    );
  }
}
