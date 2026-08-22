import 'package:flutter/material.dart';

import '../constants/colors.dart';
import '../models/bulky_waste.dart';
import '../widgets/bulky_waste/external_link_handler.dart';

/// 品目詳細・手数料表示画面
///
/// 選択された品目の詳細情報と手数料を表示する。
/// [MunicipalityConfig] の `feeStructureType` に応じて、
/// サイズ別・重量別・一律の手数料表示を切り替える。
///
/// 要件4.1: 品目選択時に手数料詳細画面を表示
/// 要件4.2: 品目名・サイズカテゴリ・手数料（整数+"円"）・備考（最大200文字）を表示
/// 要件4.3: サイズ別手数料体系の表示（サイズ閾値cmと各段階の手数料）
/// 要件4.4: 重量別手数料体系の表示（重量範囲kgと各段階の手数料）
/// 要件4.5: 一律手数料体系の表示（単一の手数料金額）
/// 要件4.6: 手数料情報未登録時のメッセージ + 自治体連絡先表示
/// 要件4.7: 該当ティアのハイライト表示
class FeeDisplayScreen extends StatelessWidget {
  /// 表示対象の粗大ごみ品目
  final BulkyWasteItem item;

  /// 自治体設定（手数料体系・申し込み方法・連絡先を含む）
  final MunicipalityConfig config;

  const FeeDisplayScreen({
    super.key,
    required this.item,
    required this.config,
  });

  /// 手数料情報が利用可能かどうかを判定する
  ///
  /// feeAmount が 0 の場合は手数料情報未登録とみなす。
  bool get _isFeeAvailable => item.feeAmount > 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(item.itemName),
      ),
      body: _isFeeAvailable
          ? _buildFeeContent(context)
          : _buildNoFeeContent(context),
    );
  }

  /// 手数料情報がある場合のメインコンテンツ
  Widget _buildFeeContent(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // メイン情報カード
          _buildMainInfoCard(context),
          const SizedBox(height: 16),
          // 手数料体系セクション
          _buildFeeStructureSection(context),
          const SizedBox(height: 24),
          // 外部申し込みリンク
          _buildExternalLinkSection(),
        ],
      ),
    );
  }

  /// 手数料情報がない場合のコンテンツ
  Widget _buildNoFeeContent(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 手数料情報なしメッセージ
          _buildNoFeeMessage(context),
          const SizedBox(height: 24),
          // 外部申し込みリンク
          _buildExternalLinkSection(),
        ],
      ),
    );
  }

  /// メイン情報カード（品目名・カテゴリ・手数料・サイズ/重量カテゴリ・備考）
  Widget _buildMainInfoCard(BuildContext context) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 品目名（大）
            Text(
              item.itemName,
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            // カテゴリ
            Row(
              children: [
                Icon(Icons.category, size: 16, color: Colors.grey[600]),
                const SizedBox(width: 6),
                Text(
                  item.category,
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey[700],
                  ),
                ),
              ],
            ),
            const Divider(height: 24),
            // 手数料（大・カラー表示）
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  '${item.feeAmount}',
                  style: const TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                    color: Colors.teal,
                  ),
                ),
                const SizedBox(width: 4),
                const Text(
                  '円',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: Colors.teal,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // サイズカテゴリ or 重量カテゴリ（該当する場合）
            if (item.sizeCategory != null) ...[
              _buildInfoRow(
                icon: Icons.straighten,
                label: 'サイズ区分',
                value: item.sizeCategory!,
              ),
              if (item.sizeThresholdCm != null)
                _buildInfoRow(
                  icon: Icons.height,
                  label: 'サイズ閾値',
                  value: '${item.sizeThresholdCm}cm',
                ),
            ],
            if (item.weightCategory != null) ...[
              _buildInfoRow(
                icon: Icons.fitness_center,
                label: '重量区分',
                value: item.weightCategory!,
              ),
              if (item.weightThresholdKg != null)
                _buildInfoRow(
                  icon: Icons.scale,
                  label: '重量閾値',
                  value: '${item.weightThresholdKg}kg',
                ),
            ],
            // 備考（最大200文字）
            if (item.notes != null && item.notes!.isNotEmpty) ...[
              const Divider(height: 24),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_outline, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      item.notes!.length > 200
                          ? '${item.notes!.substring(0, 200)}…'
                          : item.notes!,
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey[700],
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// 情報行（アイコン + ラベル + 値）
  Widget _buildInfoRow({
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Icon(icon, size: 16, color: Colors.grey[600]),
          const SizedBox(width: 6),
          Text(
            '$label: ',
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
          Text(
            value,
            style: const TextStyle(fontSize: 14),
          ),
        ],
      ),
    );
  }

  /// 手数料体系セクション（fee_structure_type に応じた表示切替）
  Widget _buildFeeStructureSection(BuildContext context) {
    switch (config.feeStructureType) {
      case FeeStructureType.sizeBased:
        return _buildSizeBasedSection(context);
      case FeeStructureType.weightBased:
        return _buildWeightBasedSection(context);
      case FeeStructureType.fixed:
        return _buildFixedFeeSection(context);
    }
  }

  /// サイズ別手数料表示
  ///
  /// サイズ閾値(cm)と各段階の手数料をティアリストで表示する。
  /// 該当品目のティアをハイライトする。
  Widget _buildSizeBasedSection(BuildContext context) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.straighten, color: AppColors.primary),
                const SizedBox(width: 8),
                const Text(
                  'サイズ別手数料',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // サイズティアの例示リスト
            // 現品目の tier をハイライトする
            _buildSizeTierList(),
          ],
        ),
      ),
    );
  }

  /// サイズティアリストを構築する
  ///
  /// 品目の sizeCategory/sizeThresholdCm に基づいて該当ティアをハイライト表示する。
  /// ティアデータはこの画面に渡された品目情報のみから構築する。
  Widget _buildSizeTierList() {
    // サイズ別の代表的ティア構成を表示
    // 実際のティアデータは同一自治体の全品目から集約すべきだが、
    // 現在のAPIは単一品目データのみを返すため、品目自身のティア情報を表示する。
    final currentThreshold = item.sizeThresholdCm;
    final currentCategory = item.sizeCategory;

    if (currentThreshold == null && currentCategory == null) {
      return Text(
        'サイズ区分情報がありません',
        style: TextStyle(fontSize: 13, color: Colors.grey[600]),
      );
    }

    return _buildHighlightedTierTile(
      label: currentCategory ?? 'サイズ区分',
      detail: currentThreshold != null ? '${currentThreshold}cm以下' : '',
      fee: item.feeAmount,
      isHighlighted: true,
    );
  }

  /// 重量別手数料表示
  ///
  /// 重量範囲(kg)と各段階の手数料をティアリストで表示する。
  /// 該当品目のティアをハイライトする。
  Widget _buildWeightBasedSection(BuildContext context) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.fitness_center, color: AppColors.primary),
                const SizedBox(width: 8),
                const Text(
                  '重量別手数料',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildWeightTierList(),
          ],
        ),
      ),
    );
  }

  /// 重量ティアリストを構築する
  Widget _buildWeightTierList() {
    final currentThreshold = item.weightThresholdKg;
    final currentCategory = item.weightCategory;

    if (currentThreshold == null && currentCategory == null) {
      return Text(
        '重量区分情報がありません',
        style: TextStyle(fontSize: 13, color: Colors.grey[600]),
      );
    }

    return _buildHighlightedTierTile(
      label: currentCategory ?? '重量区分',
      detail: currentThreshold != null ? '${currentThreshold}kg以下' : '',
      fee: item.feeAmount,
      isHighlighted: true,
    );
  }

  /// 一律手数料表示
  ///
  /// 単一の手数料金額を目立つ形式で表示する。
  Widget _buildFixedFeeSection(BuildContext context) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.payments, color: AppColors.primary),
                const SizedBox(width: 8),
                const Text(
                  '一律手数料',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Center(
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                decoration: BoxDecoration(
                  color: Colors.teal.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.teal.shade200),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      '${item.feeAmount}',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        color: Colors.teal.shade700,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '円',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.teal.shade700,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// ハイライト付きティアタイルを構築する
  ///
  /// [isHighlighted] が true の場合、該当ティアとして背景色を変えて表示する。
  Widget _buildHighlightedTierTile({
    required String label,
    required String detail,
    required int fee,
    required bool isHighlighted,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: isHighlighted ? Colors.teal.shade50 : null,
        borderRadius: BorderRadius.circular(8),
        border: isHighlighted
            ? Border.all(color: Colors.teal.shade300, width: 1.5)
            : Border.all(color: Colors.grey.shade300),
      ),
      child: Row(
        children: [
          if (isHighlighted)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Icon(
                Icons.check_circle,
                size: 18,
                color: Colors.teal.shade700,
              ),
            ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight:
                        isHighlighted ? FontWeight.bold : FontWeight.normal,
                    color:
                        isHighlighted ? Colors.teal.shade800 : Colors.black87,
                  ),
                ),
                if (detail.isNotEmpty)
                  Text(
                    detail,
                    style: TextStyle(
                      fontSize: 12,
                      color: isHighlighted
                          ? Colors.teal.shade600
                          : Colors.grey[600],
                    ),
                  ),
              ],
            ),
          ),
          Text(
            '$fee円',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: isHighlighted ? Colors.teal.shade700 : Colors.black87,
            ),
          ),
        ],
      ),
    );
  }

  /// 手数料情報未登録時のメッセージ + 自治体連絡先表示
  Widget _buildNoFeeMessage(BuildContext context) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const Icon(
              Icons.info_outline,
              size: 48,
              color: Colors.orange,
            ),
            const SizedBox(height: 16),
            const Text(
              '手数料情報がありません',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              '${config.municipalityName}に直接お問い合わせください。',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey[700],
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            // 自治体連絡先情報
            _buildContactInfo(),
          ],
        ),
      ),
    );
  }

  /// 自治体連絡先情報を表示する
  Widget _buildContactInfo() {
    return Column(
      children: [
        if (config.phoneNumber != null && config.phoneNumber!.isNotEmpty)
          _buildContactRow(
            icon: Icons.phone,
            label: '電話番号',
            value: config.phoneNumber!,
          ),
        if (config.webFormUrl != null && config.webFormUrl!.isNotEmpty) ...[
          if (config.phoneNumber != null && config.phoneNumber!.isNotEmpty)
            const SizedBox(height: 8),
          _buildContactRow(
            icon: Icons.language,
            label: 'Webサイト',
            value: config.webFormUrl!,
          ),
        ],
      ],
    );
  }

  /// 連絡先行を構築する
  Widget _buildContactRow({
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: Colors.grey[700]),
          const SizedBox(width: 8),
          Text(
            '$label: ',
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
          Expanded(
            child: SelectableText(
              value,
              style: const TextStyle(fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }

  /// 外部リンクセクション
  Widget _buildExternalLinkSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '申し込み窓口',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 12),
        ExternalLinkHandler(
          applicationMethod: config.applicationMethod,
          webFormUrl: config.webFormUrl,
          phoneNumber: config.phoneNumber,
        ),
      ],
    );
  }
}
