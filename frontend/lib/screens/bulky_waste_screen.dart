import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../models/bulky_waste.dart';
import '../providers/bulky_waste_provider.dart';
import '../providers/region_provider.dart';
import '../repositories/bulky_waste_repository.dart';
import '../widgets/bulky_waste/application_guide_view.dart';
import '../widgets/bulky_waste/item_list_view.dart';
import '../widgets/bulky_waste/status_tracker_view.dart';

/// 粗大ごみ機能のメイン画面
///
/// TabBar構成で品目一覧・出し方ガイド・手動の収集記録の3タブを表示する。
/// [municipalityConfigProvider] を watch し、自治体設定に応じた概要情報を表示する。
/// ローディング中はインジケーター、データ未登録時はメッセージを表示する。
class BulkyWasteScreen extends ConsumerStatefulWidget {
  const BulkyWasteScreen({super.key});

  @override
  ConsumerState<BulkyWasteScreen> createState() => _BulkyWasteScreenState();
}

class _BulkyWasteScreenState extends ConsumerState<BulkyWasteScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final configAsync = ref.watch(municipalityConfigProvider);
    final recordTabLabel =
        switch (configAsync.asData?.value?.data.applicationMethod) {
      ApplicationMethod.none => '収集予定メモ',
      null => '記録',
      _ => '申込記録',
    };

    return Scaffold(
      appBar: AppBar(
        title: _buildAppBarTitle(configAsync),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            const Tab(text: '品目一覧'),
            const Tab(text: '出し方ガイド'),
            Tab(text: recordTabLabel),
          ],
        ),
      ),
      body: configAsync.when(
        data: (cachedResult) {
          if (cachedResult == null) {
            return _buildNoDataMessage();
          }
          final region = ref.watch(regionSettingProvider).valueOrNull;
          return KeyedSubtree(
              key: ValueKey('${region?.municipalityId}/${region?.districtId}'),
              child: _buildContent(cachedResult));
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _buildErrorState(error),
      ),
    );
  }

  /// AppBarのタイトルを構築する
  ///
  /// 自治体設定が取得済みの場合は「粗大ごみ - {自治体名}」を表示し、
  /// ローディング中やデータ未取得の場合は「粗大ごみ」のみ表示する。
  Widget _buildAppBarTitle(
      AsyncValue<CachedResult<MunicipalityConfig>?> configAsync) {
    final config = configAsync.asData?.value?.data;
    if (config != null) {
      return Text('粗大ごみ - ${config.municipalityName}');
    }
    return const Text('粗大ごみ');
  }

  /// データ未登録時のメッセージ表示
  Widget _buildNoDataMessage() {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.info_outline, size: 48, color: Colors.grey),
            SizedBox(height: 16),
            Text(
              '粗大ごみ情報は現在登録されていません',
              style: TextStyle(fontSize: 16, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  /// エラー時の表示
  Widget _buildErrorState(Object error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: AppColors.error),
            const SizedBox(height: 16),
            const Text(
              '粗大ごみ情報の読み込みに失敗しました',
              style: TextStyle(fontSize: 16, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () {
                ref.invalidate(municipalityConfigProvider);
              },
              icon: const Icon(Icons.refresh),
              label: const Text('再試行'),
            ),
          ],
        ),
      ),
    );
  }

  /// データ取得成功時のメインコンテンツ
  Widget _buildContent(CachedResult<MunicipalityConfig> cachedResult) {
    return Column(
      children: [
        // 古いデータの警告バナー
        if (cachedResult.isStale) _buildDataNotice(cachedResult),
        // 概要セクション
        _buildOverviewCard(cachedResult.data),
        // タブコンテンツ
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              ItemListView(
                municipalityId: cachedResult.data.municipalityId,
                config: cachedResult.data,
                useOfficialInfoFallback: cachedResult.isBundledFallback,
              ),
              ApplicationGuideView(
                config: cachedResult.data,
                useOfficialInfoFallback: cachedResult.isBundledFallback,
              ),
              StatusTrackerView(
                  municipalityName: cachedResult.data.municipalityName,
                  isNakajima: cachedResult.data.applicationMethod ==
                      ApplicationMethod.none),
            ],
          ),
        ),
      ],
    );
  }

  /// キャッシュデータ使用時の警告バナー
  Widget _buildDataNotice(CachedResult<MunicipalityConfig> result) {
    final message = result.isBundledFallback
        ? result.data.applicationMethod == ApplicationMethod.none
            ? '品目一覧は${result.data.municipalityId == '38201' ? '松山市' : result.data.municipalityName}の分別資料をもとにした参考情報です。収集日と出し方は、地区別の公式カレンダーで確認してください。'
            : '品目一覧は${result.data.municipalityId == '38201' ? '松山市' : result.data.municipalityName}の分別資料をもとにした参考情報です。収集対象や申込条件、受付期間は自治体の公式サイトで確認してください。'
        : '表示されているデータは以前の取得結果です。最新情報を反映していない可能性があります。';
    return MaterialBanner(
      content: Text(
        message,
        style: const TextStyle(fontSize: 13, color: Colors.black87),
      ),
      leading: const Icon(Icons.warning_amber, color: Colors.orange),
      backgroundColor: Colors.orange.shade50,
      actions: [
        if (result.isBundledFallback)
          TextButton(
            onPressed: () => _tabController.animateTo(1),
            style: TextButton.styleFrom(foregroundColor: Colors.teal.shade800),
            child: const Text('ガイドを見る'),
          )
        else
          TextButton(
            onPressed: () {
              ref.invalidate(municipalityConfigProvider);
            },
            child: const Text('更新'),
          ),
      ],
    );
  }

  /// 自治体情報の概要カード
  ///
  /// 自治体名・収集頻度・受付時間・収集ルールを表示する。
  Widget _buildOverviewCard(MunicipalityConfig config) {
    return Card(
      margin: const EdgeInsets.all(12),
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.location_city, color: AppColors.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    config.municipalityName,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 24),
            _buildOverviewRow(
              icon: Icons.calendar_today,
              label: '収集頻度',
              value: config.collectionFrequency,
            ),
            const SizedBox(height: 8),
            _buildOverviewRow(
              icon: Icons.access_time,
              label: '受付時間',
              value: config.receptionHours,
            ),
            const SizedBox(height: 8),
            _buildOverviewRow(
              icon: Icons.rule,
              label: '収集ルール',
              value: config.collectionRules,
            ),
          ],
        ),
      ),
    );
  }

  /// 概要セクション内の1行
  Widget _buildOverviewRow({
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: Colors.grey[600]),
        const SizedBox(width: 8),
        SizedBox(
          width: 72,
          child: Text(
            label,
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontSize: 14),
          ),
        ),
      ],
    );
  }
}
