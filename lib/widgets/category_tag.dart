import 'package:flutter/material.dart';
import '../constants/colors.dart';
import '../models/garbage_category.dart';
import '../models/garbage_item.dart';

/// カテゴリ分類タグウィジェット
///
/// ゴミ分類カテゴリを色付きタグとして表示する。
/// カテゴリ色の背景（薄い色）にテキストラベルを表示し、
/// 危険ごみの場合は警告アイコンを、それ以外は丸ドットを左側に配置する。
///
/// 要件9.1: カテゴリごとに固定色を適用
/// 要件9.2: 色分けルール（可燃=ピンク、資源=緑、プラ=オレンジ、ペットボトル=青、危険=赤）
/// 要件9.3: 危険ごみには警告アイコンを併記
/// 要件9.4: すべての画面で同一カテゴリに同一色を使用
/// 要件9.5: テキストラベルを常時併記し、色のみに依存しない情報伝達
class CategoryTag extends StatelessWidget {
  /// 表示するゴミ分類カテゴリ
  final GarbageCategory category;

  const CategoryTag({
    super.key,
    required this.category,
  });

  @override
  Widget build(BuildContext context) {
    final color = CategoryColors.getColor(category);
    final label = CategoryColors.getLabel(category);
    final isHazardous = category == GarbageCategory.hazardous;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // 危険ごみの場合: 警告アイコン、それ以外: カテゴリ色の丸ドット
          if (isHazardous)
            Icon(
              Icons.warning,
              size: 14,
              color: AppColors.hazardousWarning,
            )
          else
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: color,
                shape: BoxShape.circle,
              ),
            ),
          const SizedBox(width: 4),
          // カテゴリ名テキストラベル
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
