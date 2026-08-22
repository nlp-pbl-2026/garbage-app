import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../providers/locale_provider.dart';

/// 言語選択ウィジェット
///
/// 設定画面に表示され、5言語（日本語・英語・ポルトガル語・中国語・ベトナム語）から
/// アプリの表示言語を選択できる。選択中の言語にはチェックアイコンを表示し、
/// 色に依存しない視覚的マーカーとする。
/// 同一言語を再選択した場合は何もしない（冪等性）。
class LanguageSelector extends ConsumerWidget {
  const LanguageSelector({super.key});

  /// サポート言語の言語コード→母国語名マッピング
  static const Map<String, String> languageNames = {
    'ja': '日本語',
    'en': 'English',
    'pt': 'Português',
    'zh': '中文',
    'vi': 'Tiếng Việt',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentLocale = ref.watch(localeProvider);

    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: languageNames.entries.map((entry) {
          final code = entry.key;
          final name = entry.value;
          final isSelected = currentLocale.languageCode == code;

          return Column(
            children: [
              ListTile(
                leading: Icon(
                  Icons.language,
                  color: isSelected ? AppColors.primary : Colors.grey,
                ),
                title: Text(
                  name,
                  style: TextStyle(
                    fontWeight:
                        isSelected ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
                trailing: isSelected
                    ? const Icon(Icons.check, color: AppColors.primary)
                    : null,
                onTap: () {
                  // 同一言語なら何もしない（localeProvider内でも冪等性を保証）
                  if (!isSelected) {
                    ref.read(localeProvider.notifier).setLocale(Locale(code));
                  }
                },
              ),
              // 最後のアイテム以外にDividerを表示
              if (code != languageNames.keys.last)
                const Divider(height: 1, indent: 56),
            ],
          );
        }).toList(),
      ),
    );
  }
}
