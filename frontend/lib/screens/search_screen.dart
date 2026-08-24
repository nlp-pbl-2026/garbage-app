import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/region.dart';
import '../models/waste_guide_result.dart';
import '../providers/region_provider.dart';
import '../services/waste_guide_service.dart';
import '../widgets/region_header.dart';
import 'region_selection_screen.dart';

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
  bool _isLoading = false;

  static const _green = Color(0xFF1F6B4F);
  static const _ink = Color(0xFF17352B);
  static const _surface = Color(0xFFF6F4EE);

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
            {'question': _pendingQuestion!, 'answer': input},
          ]
        : <Map<String, String>>[];

    setState(() {
      _isLoading = true;
      _error = null;
      if (!isClarification) {
        _originalQuery = input;
        _result = null;
      }
    });

    try {
      final result = await _service.classify(
        query: query,
        region: region,
        clarifications: clarifications,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _pendingQuestion =
            result.needsClarification ? result.followUpQuestion : null;
        _isLoading = false;
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
      });
    }
  }

  void _startNewSearch([String? suggestion]) {
    setState(() {
      _result = null;
      _error = null;
      _originalQuery = null;
      _pendingQuestion = null;
      _queryController.text = suggestion ?? '';
    });
    _queryFocus.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final region = ref.watch(regionSettingProvider).valueOrNull;
    return Scaffold(
      backgroundColor: _surface,
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
                _buildHero(region),
                const SizedBox(height: 18),
                _buildSearchCard(),
                const SizedBox(height: 18),
                if (_isLoading) _buildLoadingCard(),
                if (_error != null) _buildErrorCard(),
                if (!_isLoading && _error == null && _result != null)
                  _result!.needsClarification
                      ? _buildClarificationCard(_result!)
                      : _buildAnswerCard(_result!),
                if (!_isLoading && _result == null && _error == null)
                  _buildExamples(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHero(RegionSetting? region) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: _ink,
        borderRadius: BorderRadius.circular(28),
        boxShadow: const [
          BoxShadow(
            color: Color(0x2417352B),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.12),
              borderRadius: BorderRadius.circular(99),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.location_on_outlined,
                  color: Color(0xFFD7E9DF),
                  size: 17,
                ),
                const SizedBox(width: 6),
                Text(
                  region == null
                      ? '地域未設定'
                      : '${region.municipalityName}・${region.districtName}地区',
                  style: const TextStyle(
                    color: Color(0xFFD7E9DF),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 22),
          const Text(
            'これ、何ごみ？',
            style: TextStyle(
              color: Colors.white,
              fontSize: 32,
              height: 1.15,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.8,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            '品物の名前や状態を入力すると、分別方法と\n清水地区の次回収集日を調べます。',
            style: TextStyle(
              color: Color(0xFFC5D8CF),
              fontSize: 15,
              height: 1.65,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchCard() {
    final isClarification = _pendingQuestion != null;
    return _panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            isClarification ? '追加情報を入力' : '捨てたいものを入力',
            style: const TextStyle(
              color: _ink,
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
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
                      color: _green,
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
                    backgroundColor: _green,
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

  Widget _buildLoadingCard() {
    return _panel(
      child: const Row(
        children: [
          SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2.5),
          ),
          SizedBox(width: 14),
          Expanded(child: Text('松山市の分別情報を確認しています…')),
        ],
      ),
    );
  }

  Widget _buildErrorCard() {
    return _panel(
      color: const Color(0xFFFFF4F0),
      borderColor: const Color(0xFFF4C8BB),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: Color(0xFFB4482C)),
          const SizedBox(width: 12),
          Expanded(child: Text(_error!)),
          TextButton(onPressed: _submit, child: const Text('再試行')),
        ],
      ),
    );
  }

  Widget _buildClarificationCard(WasteGuideResult result) {
    return _panel(
      color: const Color(0xFFFFF9E9),
      borderColor: const Color(0xFFEBD69A),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.help_outline_rounded, color: Color(0xFF946B00)),
              SizedBox(width: 10),
              Text(
                'もう少しだけ教えてください',
                style: TextStyle(
                  color: Color(0xFF664B00),
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            result.followUpQuestion ?? '品物の状態をもう少し詳しく教えてください。',
            style: const TextStyle(fontSize: 16, height: 1.6, color: _ink),
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
    final classification = result.classification;
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
                    decoration: const BoxDecoration(
                      color: Color(0xFFE1F0E8),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.check_rounded, color: _green),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Text(
                      '分別結果',
                      style: TextStyle(
                        color: _ink,
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
                        color: _ink,
                        borderRadius: BorderRadius.circular(99),
                      ),
                      child: Text(
                        classification.categoryName,
                        style: const TextStyle(
                          color: Colors.white,
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
                style: const TextStyle(fontSize: 16, height: 1.75, color: _ink),
              ),
              if (result.nextCollection != null) ...[
                const SizedBox(height: 18),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEAF5EF),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.event_available_rounded, color: _green),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              '次回の収集日',
                              style: TextStyle(
                                color: Color(0xFF527064),
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              result.nextCollection!.displayDate,
                              style: const TextStyle(
                                color: _ink,
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
    const examples = ['汚れた食品トレー', '壊れた傘', '使い切ったスプレー缶'];
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '入力例',
            style: TextStyle(color: _ink, fontWeight: FontWeight.w700),
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
    Color color = Colors.white,
    Color borderColor = const Color(0xFFE3E7E2),
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: borderColor),
      ),
      child: child,
    );
  }
}
