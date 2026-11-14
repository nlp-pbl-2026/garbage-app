import 'package:flutter/material.dart';

import '../services/search_analytics_service.dart';
import '../services/waste_guide_service.dart';

class SearchAnalyticsScreen extends StatefulWidget {
  final SearchAnalyticsService? service;

  const SearchAnalyticsScreen({super.key, this.service});

  @override
  State<SearchAnalyticsScreen> createState() => _SearchAnalyticsScreenState();
}

class _SearchAnalyticsScreenState extends State<SearchAnalyticsScreen> {
  final _keyController = TextEditingController();
  late final _service = widget.service ?? SearchAnalyticsService();
  SearchAnalytics? _analytics;
  String? _error;
  bool _loading = false;

  @override
  void dispose() {
    _keyController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (_keyController.text.trim().isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
      _analytics = null;
    });
    try {
      final value = await _service.fetch(_keyController.text.trim());
      if (mounted) setState(() => _analytics = value);
    } on WasteGuideException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) setState(() => _error = '分析ログの取得に失敗しました。');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: colors.surface,
      appBar: AppBar(
        title: const Text('あいまい検索の分析'),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 980),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              _keyPanel(),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: TextStyle(color: colors.error)),
              ],
              if (_analytics != null) ...[
                const SizedBox(height: 22),
                _summary(_analytics!),
                const SizedBox(height: 22),
                _categories(_analytics!),
                const SizedBox(height: 22),
                _recent(_analytics!),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _keyPanel() => _panel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('管理キー', style: TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            const Text('検索語には生活情報が含まれ得るため、ログは管理キーで保護しています。'),
            const SizedBox(height: 14),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _keyController,
                  obscureText: true,
                  onSubmitted: (_) => _load(),
                  decoration: const InputDecoration(
                    hintText: '管理者から受け取った分析キーを入力',
                    prefixIcon: Icon(Icons.key_rounded),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              FilledButton.icon(
                onPressed: _loading ? null : _load,
                icon: _loading
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.analytics_outlined),
                label: const Text('表示'),
              ),
            ]),
          ],
        ),
      );

  Widget _summary(SearchAnalytics data) {
    final answerRate = data.totalSearches == 0
        ? 0
        : data.answeredCount / data.totalSearches * 100;
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        _metric('検索数', '${data.totalSearches}', Icons.search_rounded),
        _metric('回答率', '${answerRate.toStringAsFixed(1)}%',
            Icons.check_circle_outline),
        _metric('確定不能', '${data.unableCount}', Icons.info_outline_rounded),
        _metric(
          '平均確信度',
          data.averageConfidence == null
              ? '—'
              : '${(data.averageConfidence! * 100).toStringAsFixed(1)}%',
          Icons.psychology_outlined,
        ),
        _metric(
          '平均応答',
          data.averageDurationMs == null
              ? '—'
              : '${(data.averageDurationMs! / 1000).toStringAsFixed(1)}秒',
          Icons.timer_outlined,
        ),
      ],
    );
  }

  Widget _metric(String label, String value, IconData icon) {
    final colors = Theme.of(context).colorScheme;
    return SizedBox(
      width: 218,
      child: _panel(
        child: Row(children: [
          Icon(icon, color: colors.primary),
          const SizedBox(width: 12),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: TextStyle(color: colors.onSurfaceVariant)),
            Text(value,
                style:
                    const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          ]),
        ]),
      ),
    );
  }

  Widget _categories(SearchAnalytics data) => _panel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('分類の内訳',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            const SizedBox(height: 14),
            if (data.categories.isEmpty)
              const Text('まだ確定した分類はありません。')
            else
              ...data.categories.entries.map((item) => Padding(
                    padding: const EdgeInsets.only(bottom: 9),
                    child: Row(children: [
                      Expanded(child: Text(item.key)),
                      Text('${item.value}件',
                          style: const TextStyle(fontWeight: FontWeight.w700)),
                    ]),
                  )),
          ],
        ),
      );

  Widget _recent(SearchAnalytics data) => _panel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('直近の検索',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            if (data.recent.isEmpty)
              const Text('検索ログはまだありません。')
            else
              ...data.recent.take(30).map((item) => Material(
                  type: MaterialType.transparency,
                  child: ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    title: Text(item.query.isEmpty ? '（画像のみの検索）' : item.query),
                    subtitle: Text(
                      '${item.categoryName ?? (item.status == 'unable_to_determine' ? '確定不能' : '追加質問')}・${(item.durationMs / 1000).toStringAsFixed(1)}秒',
                    ),
                    leading: item.confidence == null
                        ? const Icon(Icons.help_outline)
                        : Text('${(item.confidence! * 100).round()}%',
                            style: TextStyle(
                                color: Theme.of(context).colorScheme.primary,
                                fontWeight: FontWeight.w800)),
                    children: [
                      _logText('検索原文', item.query),
                      _logText('AIの言い換え', item.rewrittenQuery),
                      for (final exchange in item.clarifications) ...[
                        _logText('追加質問', exchange.question),
                        _logText('ユーザーの回答', exchange.answer),
                      ],
                      if (item.followUpQuestion != null)
                        _logText('AIからの追加質問', item.followUpQuestion!),
                      if (item.answer != null)
                        _logText('AIの生成回答', item.answer!),
                      _logText('検索日時', item.createdAt),
                    ],
                  ))),
          ],
        ),
      );

  Widget _logText(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
            SelectableText(value.isEmpty ? '（記録なし）' : value),
          ],
        ),
      );

  Widget _panel({required Widget child}) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: colors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: colors.outlineVariant),
      ),
      child: child,
    );
  }
}
