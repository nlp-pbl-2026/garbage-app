import 'package:flutter/material.dart';

import '../../models/bulky_waste.dart';
import 'external_link_handler.dart';

const _matsuyamaAreaLookupUrl =
    'https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/chikukensaku.html';

/// 粗大ごみ申し込み手順ガイド表示ウィジェット
///
/// MunicipalityConfigのstepsを番号付きリストで表示する。
/// 自治体ごとの手順を順序どおりに表示し、松山市では公式の住所検索へ案内する。
///
/// Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
class ApplicationGuideView extends StatelessWidget {
  /// 自治体設定データ
  final MunicipalityConfig config;

  /// API未提供時は、直接申込みではなく公式案内ページへの導線として表示する。
  final bool useOfficialInfoFallback;

  const ApplicationGuideView({
    super.key,
    required this.config,
    this.useOfficialInfoFallback = false,
  });

  @override
  Widget build(BuildContext context) {
    // ステップ番号順にソート
    final sortedSteps = List<ApplicationStep>.from(config.steps)
      ..sort((a, b) => a.stepNumber.compareTo(b.stepNumber));

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ヘッダー
          Text(
            config.applicationMethod == ApplicationMethod.none
                ? '${config.municipalityName}の粗大ごみの出し方'
                : '${config.municipalityName}の粗大ごみ申し込み手順',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 16),
          if (config.municipalityId == '38201' &&
              config.applicationMethod != ApplicationMethod.none) ...[
            const _MatsuyamaApplicationGroupHelp(),
            const SizedBox(height: 16),
          ],
          if (config.informationUrl != null) ...[
            ExternalLinkHandler(
              applicationMethod: ApplicationMethod.webForm,
              webFormUrl: config.informationUrl,
              webButtonLabel: '公式の出し方を確認',
            ),
            const SizedBox(height: 16),
          ],
          // ステップ一覧
          ...sortedSteps.map((step) => _StepCard(
                step: step,
                isLast: step == sortedSteps.last,
              )),
          const SizedBox(height: 24),
          // 外部申し込み窓口セクション
          if (config.applicationMethod != ApplicationMethod.none)
            _ExternalLinkSection(
              config: config,
              useOfficialInfoFallback: useOfficialInfoFallback,
            ),
          if (config.municipalityId == '38201' &&
              config.applicationMethod == ApplicationMethod.none)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text('中島地域の公式案内'),
                    const SizedBox(height: 8),
                    const Text('中島地域はA〜Dの戸別収集申込みではなく、地区別カレンダーの収集日に集積場所へ出します。'),
                    const SizedBox(height: 12),
                    ExternalLinkHandler(
                      applicationMethod: ApplicationMethod.webForm,
                      webFormUrl: config.webFormUrl,
                      webButtonLabel: '中島地域の出し方を確認',
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _MatsuyamaApplicationGroupHelp extends StatelessWidget {
  const _MatsuyamaApplicationGroupHelp();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('申込区分A〜Dとは', style: TextStyle(fontWeight: FontWeight.bold)),
            SizedBox(height: 8),
            Text('松山・北条地域の住所ごとに決まる、粗大ごみの申込期間の区分です。ごみカレンダーの地区名とは別です。'),
            SizedBox(height: 8),
            Text(
                '町名・丁目を松山市の「町別地区検索一覧」で確認してください。同じ町に複数の区分がある場合は、推測せず清掃課に確認してください。'),
            SizedBox(height: 12),
            ExternalLinkHandler(
              applicationMethod: ApplicationMethod.webForm,
              webFormUrl: _matsuyamaAreaLookupUrl,
              webButtonLabel: '住所から申込区分を確認',
            ),
          ],
        ),
      ),
    );
  }
}

/// 各ステップを表示するカードウィジェット
class _StepCard extends StatelessWidget {
  final ApplicationStep step;
  final bool isLast;

  const _StepCard({
    required this.step,
    required this.isLast,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 左側：番号バッジとコネクタライン
          Column(
            children: [
              // ステップ番号の円形バッジ
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: theme.colorScheme.primary,
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: Text(
                    '${step.stepNumber}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
              // コネクタライン（最後のステップ以外）
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    color: theme.colorScheme.primary.withValues(alpha: 0.3),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 12),
          // 右側：ステップ内容カード
          Expanded(
            child: Card(
              margin: EdgeInsets.only(bottom: isLast ? 0 : 12),
              elevation: 1,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ステップタイトル
                    Text(
                      step.title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    // ステップ説明
                    Text(
                      step.description,
                      style: theme.textTheme.bodyMedium,
                    ),
                    // ノート（ある場合はハイライトボックスで表示）
                    if (step.notes != null && step.notes!.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      _NotesBox(notes: step.notes!),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// ノート/ヒントをハイライト表示するボックス
class _NotesBox extends StatelessWidget {
  final String notes;

  const _NotesBox({required this.notes});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.amber.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.amber.shade200),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.lightbulb_outline,
            size: 18,
            color: Colors.amber.shade700,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              notes,
              style: TextStyle(
                fontSize: 13,
                color: Colors.amber.shade900,
                fontStyle: FontStyle.italic,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 外部申し込み窓口へのリンクセクション
class _ExternalLinkSection extends StatelessWidget {
  final MunicipalityConfig config;
  final bool useOfficialInfoFallback;

  const _ExternalLinkSection({
    required this.config,
    required this.useOfficialInfoFallback,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.open_in_new,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  '申し込み窓口',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ExternalLinkHandler(
              applicationMethod: config.applicationMethod,
              webFormUrl: config.webFormUrl,
              phoneNumber: config.phoneNumber,
              webButtonLabel: useOfficialInfoFallback
                  ? '${config.municipalityName}公式サイトで確認'
                  : 'Webで申し込む',
            ),
          ],
        ),
      ),
    );
  }
}
