import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/locale_provider.dart';
import '../services/romanization_service.dart';

/// 自治体名を表示するウィジェット
///
/// 現在のロケールに応じて、日本語名のみまたはローマ字読み付きで表示する。
/// - 日本語ロケール: "松山市"
/// - 非日本語ロケール: "松山市 (Matsuyama-shi)"
///
/// Requirements 11.1, 11.2, 11.3, 11.4 を実現する。
class MunicipalityNameText extends ConsumerWidget {
  /// 日本語の自治体名
  final String japaneseName;

  /// テキストスタイル（省略時はデフォルトTextStyleを使用）
  final TextStyle? style;

  /// テキストの最大行数
  final int? maxLines;

  /// テキストのオーバーフロー処理
  final TextOverflow? overflow;

  const MunicipalityNameText(
    this.japaneseName, {
    super.key,
    this.style,
    this.maxLines,
    this.overflow,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locale = ref.watch(localeProvider);
    final isJapanese = locale.languageCode == 'ja';

    final displayText = RomanizationService.instance.formatMunicipalityName(
      japaneseName,
      isJapaneseLocale: isJapanese,
    );

    return Text(
      displayText,
      style: style,
      maxLines: maxLines,
      overflow: overflow,
    );
  }
}

/// 自治体名のフォーマット済み文字列を取得するユーティリティ関数
///
/// ウィジェットを使わずに文字列だけ必要な場合に利用する。
/// [locale] は現在のアプリロケール。
String formatMunicipalityDisplay(String japaneseName, Locale locale) {
  return RomanizationService.instance.formatMunicipalityName(
    japaneseName,
    isJapaneseLocale: locale.languageCode == 'ja',
  );
}
