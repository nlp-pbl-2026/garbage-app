import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/region.dart';
import '../models/waste_guide_result.dart';
import '../providers/region_provider.dart';
import '../services/waste_guide_service.dart';
import '../widgets/region_header.dart';
import '../widgets/search_pipeline_view.dart';
import 'region_selection_screen.dart';
import 'search_analytics_screen.dart';
import 'search_system_guide_screen.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final TextEditingController _queryController = TextEditingController();
  final FocusNode _queryFocus = FocusNode();
  final WasteGuideService _service = WasteGuideService();

  WasteGuideResult? _result;
  String? _error;
  String? _originalQuery;
  String? _pendingQuestion;
  List<Map<String, String>> _clarifications = [];
  bool _isLoading = false;
  SearchPipelineStage _pipelineStage = SearchPipelineStage.idle;

  @override
  void dispose() {
    _queryController.dispose();
    _queryFocus.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final input = _queryController.text.trim();
    if (input.isEmpty || _isLoading) return;

    final RegionSetting? region = ref.read(regionSettingProvider).valueOrNull;
    if (region == null) {
      setState(() => _error = '先に地域を設定してください。');
      return;
    }

    final isClarification = _pendingQuestion != null && _originalQuery != null;
    final query = isClarification ? _originalQuery! : input;
    final clarifications = isClarification
        ? [
            ..._clarifications,
            {'question': _pendingQuestion!, 'answer': input},
          ]
        : <Map<String, String>>[];

    setState(() {
      _isLoading = true;
      _error = null;
      if (!isClarification) {
        _originalQuery = input;
        _result = null;
        _clarifications = [];
      }
    });

    try {
      final result = await _service.classify(
        query: query,
        region: region,
        clarifications: clarifications,
        onStageChanged: (stage) {
          if (mounted) setState(() => _pipelineStage = stage);
        },
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _pendingQuestion =
            result.needsClarification ? result.followUpQuestion : null;
        _clarifications = clarifications;
        _isLoading = false;
        _pipelineStage = SearchPipelineStage.completed;
        _queryController.clear();
      });
      if (result.needsClarification) {
        _queryFocus.requestFocus();
      }
    } on WasteGuideException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _isLoading = false;
        _pipelineStage = SearchPipelineStage.idle;
      });
    }
  }

  void _startNewSearch([String? suggestion]) {
    setState(() {
      _result = null;
      _error = null;
      _originalQuery = null;
      _pendingQuestion = null;
      _clarifications = [];
      _pipelineStage = SearchPipelineStage.idle;
      _queryController.text = suggestion ?? '';
    });
    _queryFocus.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: colors.surface,
      appBar: RegionHeader(
        onEditPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => const RegionSelectionScreen(),
            ),
          );
        },
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 120),
              children: [
                if (!_isLoading &&
                    _error == null &&
                    _result?.needsClarification == true) ...[
                  _buildClarificationCard(_result!),
                  const SizedBox(height: 10),
                ],
                _buildSearchCard(),
                const SizedBox(height: 12),
                _buildPipelineCard(),
                const SizedBox(height: 12),
                if (_error != null) _buildErrorCard(),
                if (!_isLoading &&
                    _error == null &&
                    _result != null &&
                    !_result!.needsClarification)
                  _buildAnswerCard(_result!),
                if (!_isLoading && _result == null && _error == null)
                  _buildExamples(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSearchCard() {
    final isClarification = _pendingQuestion != null;
    final colors = Theme.of(context).colorScheme;
    return _panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.auto_awesome_rounded, color: colors.primary, size: 18),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  isClarification ? '回答を入力' : 'AIあいまい検索',
                  style: TextStyle(
                    color: colors.onSurface,
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              IconButton(
                tooltip: 'あいまい検索の仕組み',
                visualDensity: VisualDensity.compact,
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const SearchSystemGuideScreen(),
                  ),
                ),
                icon: const Icon(Icons.help_outline_rounded, size: 21),
              ),
              IconButton(
                tooltip: '検索ログを分析',
                visualDensity: VisualDensity.compact,
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const SearchAnalyticsScreen(),
                  ),
                ),
                icon: const Icon(Icons.analytics_outlined, size: 21),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: _queryController,
                  focusNode: _queryFocus,
                  minLines: 1,
                  maxLines: 3,
                  maxLength: 500,
                  textInputAction: TextInputAction.search,
                  onSubmitted: (_) => _submit(),
                  decoration: InputDecoration(
                    hintText: isClarification
                        ? '例：プラスチック製で、汚れています'
                        : '例：汚れた食品トレーはどう捨てる？',
                    counterText: '',
                    prefixIcon: Icon(
                      isClarification
                          ? Icons.edit_note_rounded
                          : Icons.search_rounded,
                      color: colors.primary,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              SizedBox(
                height: 54,
                child: FilledButton(
                  onPressed: _isLoading ? null : _submit,
                  style: FilledButton.styleFrom(
                    backgroundColor: colors.primary,
                    foregroundColor: colors.onPrimary,
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                  ),
                  child: Text(isClarification ? '回答する' : '調べる'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPipelineCard() {
    final colors = Theme.of(context).colorScheme;
    final compact = MediaQuery.sizeOf(context).width < 620;
    final message = switch (_pipelineStage) {
      SearchPipelineStage.idle => '検索すると、4つの処理が順番に動きます',
      SearchPipelineStage.rewriting => '言い換えAIが質問の意味を整理しています',
      SearchPipelineStage.retrieving => '清水地区の資料から根拠を探しています',
      SearchPipelineStage.classifying => '根拠から分別を判定し、収集日を照合しています',
      SearchPipelineStage.completed => 'すべての処理が完了しました',
    };
    return _panel(
      padding: EdgeInsets.all(compact ? 12 : 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (_isLoading)
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                Icon(Icons.hub_outlined, size: 18, color: colors.primary),
              const SizedBox(width: 9),
              Expanded(
                child: Text(
                  message,
                  style: TextStyle(
                    color: colors.onSurface,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          SizedBox(height: compact ? 10 : 16),
          SearchPipelineView(stage: _pipelineStage),
        ],
      ),
    );
  }

  Widget _buildErrorCard() {
    final colors = Theme.of(context).colorScheme;
    return _panel(
      color: colors.errorContainer,
      borderColor: colors.error,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error_outline, color: colors.onErrorContainer),
          const SizedBox(width: 12),
          Expanded(child: Text(_error!)),
          TextButton(onPressed: _submit, child: const Text('再試行')),
        ],
      ),
    );
  }

  Widget _buildClarificationCard(WasteGuideResult result) {
    final colors = Theme.of(context).colorScheme;
    return _panel(
      color: colors.tertiaryContainer,
      borderColor: colors.tertiary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.help_outline_rounded,
                  color: colors.onTertiaryContainer),
              const SizedBox(width: 10),
              Text(
                'もう少しだけ教えてください',
                style: TextStyle(
                  color: colors.onTertiaryContainer,
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            result.followUpQuestion ?? '品物の状態をもう少し詳しく教えてください。',
            style: TextStyle(
                fontSize: 16, height: 1.6, color: colors.onTertiaryContainer),
          ),
          const SizedBox(height: 12),
          TextButton.icon(
            onPressed: _startNewSearch,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('別のものを調べる'),
          ),
        ],
      ),
    );
  }

  Widget _buildAnswerCard(WasteGuideResult result) {
    final colors = Theme.of(context).colorScheme;
    final classification = result.classification;
    final unable = result.unableToDetermine;
    return Column(
      children: [
        _panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: unable
                          ? colors.tertiaryContainer
                          : colors.primaryContainer,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      unable ? Icons.info_outline_rounded : Icons.check_rounded,
                      color: unable
                          ? colors.onTertiaryContainer
                          : colors.onPrimaryContainer,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      unable ? '今回は確定できませんでした' : '分別結果',
                      style: TextStyle(
                        color: colors.onSurface,
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  if (classification != null)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 7,
                      ),
                      decoration: BoxDecoration(
                        color: colors.primary,
                        borderRadius: BorderRadius.circular(99),
                      ),
                      child: Text(
                        classification.categoryName,
                        style: TextStyle(
                          color: colors.onPrimary,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                result.answer ?? '',
                style: TextStyle(
                    fontSize: 16, height: 1.75, color: colors.onSurface),
              ),
              if (classification != null) ...[
                const SizedBox(height: 14),
                Row(children: [
                  Icon(Icons.psychology_outlined,
                      size: 18, color: colors.onSurfaceVariant),
                  const SizedBox(width: 7),
                  Text(
                    '判定の確信度 ${(classification.confidence * 100).round()}%',
                    style: TextStyle(
                        color: colors.onSurfaceVariant,
                        fontWeight: FontWeight.w700),
                  ),
                ]),
              ],
              if (result.rewrittenQuery.isNotEmpty &&
                  result.rewrittenQuery != _originalQuery) ...[
                const SizedBox(height: 10),
                Text(
                  '検索時の言い換え: ${result.rewrittenQuery}',
                  style:
                      TextStyle(fontSize: 12, color: colors.onSurfaceVariant),
                ),
              ],
              if (result.nextCollection != null) ...[
                const SizedBox(height: 18),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: colors.primaryContainer,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.event_available_rounded,
                          color: colors.onPrimaryContainer),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '次回の収集日',
                              style: TextStyle(
                                color: colors.onPrimaryContainer,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              result.nextCollection!.displayDate,
                              style: TextStyle(
                                color: colors.onPrimaryContainer,
                                fontSize: 18,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              if (result.sources.isNotEmpty) ...[
                const SizedBox(height: 10),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text(
                    '確認に使った情報',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                  children: result.sources
                      .map(
                        (source) => ListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          leading:
                              const Icon(Icons.description_outlined, size: 19),
                          title: Text(source.title ?? '松山市ごみ分別資料'),
                          subtitle: source.snippet == null
                              ? null
                              : Text(
                                  source.snippet!,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                        ),
                      )
                      .toList(),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _startNewSearch,
          icon: const Icon(Icons.add_rounded),
          label: const Text('別のものを調べる'),
        ),
      ],
    );
  }

  Widget _buildExamples() {
    final colors = Theme.of(context).colorScheme;
    const examples = ['お弁当の透明なフタ', '雨の日に使う壊れた長いやつ', '中身を使い切った銀色の缶'];
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '入力例',
            style:
                TextStyle(color: colors.onSurface, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: examples
                .map(
                  (example) => ActionChip(
                    avatar: const Icon(Icons.north_west_rounded, size: 16),
                    label: Text(example),
                    onPressed: () => _startNewSearch(example),
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }

  Widget _panel({
    required Widget child,
    Color? color,
    Color? borderColor,
    EdgeInsetsGeometry padding = const EdgeInsets.all(20),
  }) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? colors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: borderColor ?? colors.outlineVariant),
      ),
      child: child,
    );
  }
}
