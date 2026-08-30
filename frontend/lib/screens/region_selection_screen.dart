import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../models/gps_detection.dart';
import '../models/region.dart';
import '../providers/gps_detection_provider.dart';
import '../providers/region_provider.dart';
import '../widgets/candidate_bottom_sheet.dart';

/// 初回起動時と設定変更時に使う地域選択画面。
///
/// 審査用デモでは検索バックエンドが対応する松山市・清水地区を最短で
/// 選べるようにし、詳細指定では都道府県から順に選択できる。
class RegionSelectionScreen extends ConsumerStatefulWidget {
  final VoidCallback? onRegionSelected;
  final bool autoDetect;

  const RegionSelectionScreen({
    super.key,
    this.onRegionSelected,
    this.autoDetect = false,
  });

  @override
  ConsumerState<RegionSelectionScreen> createState() =>
      _RegionSelectionScreenState();
}

class _RegionSelectionScreenState extends ConsumerState<RegionSelectionScreen> {
  static final Prefecture _ehime = Prefecture(id: '38', name: '愛媛県');
  static final Municipality _matsuyama = Municipality(
    id: '38201',
    prefectureId: '38',
    name: '松山市',
  );
  static final District _shimizu = District(
    id: '38201-08',
    municipalityId: '38201',
    name: '清水',
  );

  Prefecture? _selectedPrefecture = _ehime;
  Municipality? _selectedMunicipality;
  District? _selectedDistrict;
  RegionValidationResult? _validationResult;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    if (widget.autoDetect) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(gpsDetectionProvider.notifier).detectDistrict();
      });
    }
  }

  Future<void> _saveRegion(
    Prefecture prefecture,
    Municipality municipality,
    District district,
  ) async {
    if (_isSaving) return;
    setState(() => _isSaving = true);

    await ref.read(regionSettingProvider.notifier).saveSetting(
          RegionSetting(
            prefectureId: prefecture.id,
            prefectureName: prefecture.name,
            municipalityId: municipality.id,
            municipalityName: municipality.name,
            districtId: district.id,
            districtName: district.name,
          ),
        );

    if (!mounted) return;
    setState(() => _isSaving = false);
    widget.onRegionSelected?.call();
  }

  Future<void> _useRecommendedRegion() =>
      _saveRegion(_ehime, _matsuyama, _shimizu);

  Future<void> _useManualRegion() async {
    final result = ref.read(regionSettingProvider.notifier).validate(
          prefectureId: _selectedPrefecture?.id,
          municipalityId: _selectedMunicipality?.id,
          districtId: _selectedDistrict?.id,
        );
    if (!result.isValid) {
      setState(() => _validationResult = result);
      return;
    }

    await _saveRegion(
      _selectedPrefecture!,
      _selectedMunicipality!,
      _selectedDistrict!,
    );
  }

  void _selectPrefecture(Prefecture prefecture) {
    setState(() {
      _selectedPrefecture = prefecture;
      _selectedMunicipality = null;
      _selectedDistrict = null;
      _validationResult = null;
    });
  }

  void _selectMunicipality(Municipality municipality) {
    setState(() {
      _selectedMunicipality = municipality;
      _selectedDistrict = null;
      _validationResult = null;
    });
  }

  void _selectDistrict(District district) {
    setState(() {
      _selectedDistrict = district;
      _validationResult = null;
    });
  }

  Future<void> _showSelectionSheet<T>({
    required String title,
    required List<T> items,
    required String Function(T) nameOf,
    required void Function(T) onSelected,
  }) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (sheetContext) {
        return ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.65,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 4, 24, 18),
                child: Text(
                  title,
                  style: Theme.of(sheetContext).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              const Divider(height: 1),
              if (items.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(28),
                  child: Text('現在選択できる地域がありません'),
                )
              else
                Flexible(
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: items.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final item = items[index];
                      return ListTile(
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 24,
                          vertical: 4,
                        ),
                        title: Text(nameOf(item)),
                        trailing: const Icon(Icons.arrow_forward_ios_rounded,
                            size: 16),
                        onTap: () {
                          onSelected(item);
                          Navigator.of(sheetContext).pop();
                        },
                      );
                    },
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  void _showPrefectureSelector() {
    ref.read(prefecturesProvider).when(
          data: (items) => _showSelectionSheet<Prefecture>(
            title: '都道府県を選択',
            items: items.where((item) => item.id == _ehime.id).toList(),
            nameOf: (item) => item.name,
            onSelected: _selectPrefecture,
          ),
          loading: () {},
          error: (_, __) => _showDataError(),
        );
  }

  void _showMunicipalitySelector() {
    final prefecture = _selectedPrefecture;
    if (prefecture == null) return;
    ref.read(municipalitiesProvider(prefecture.id)).when(
          data: (items) => _showSelectionSheet<Municipality>(
            title: '市区町村を選択',
            items: items.where((item) => item.id == _matsuyama.id).toList(),
            nameOf: (item) => item.displayName,
            onSelected: _selectMunicipality,
          ),
          loading: () {},
          error: (_, __) => _showDataError(),
        );
  }

  void _showDistrictSelector() {
    final municipality = _selectedMunicipality;
    if (municipality == null) return;
    ref.read(districtsProvider(municipality.id)).when(
          data: (items) => _showSelectionSheet<District>(
            title: '地区を選択',
            items: items.where((item) => item.id == _shimizu.id).toList(),
            nameOf: (item) => '${item.name}地区',
            onSelected: _selectDistrict,
          ),
          loading: () {},
          error: (_, __) => _showDataError(),
        );
  }

  void _showDataError() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('地域データを読み込めませんでした')),
    );
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<GpsDetectionState>(gpsDetectionProvider, (previous, next) {
      if (next is GpsDetectionSuccess) {
        _showGpsConfirmationDialog(next.result);
      } else if (next is GpsDetectionMultipleCandidates) {
        _showCandidateSelection(next);
      } else if (next is GpsDetectionError) {
        if (next.errorType == GpsDetectionErrorType.permissionDenied ||
            next.errorType == GpsDetectionErrorType.serviceDisabled) {
          _showSettingsSnackBar(next.message);
        } else if (next.errorType == GpsDetectionErrorType.timeout ||
            next.errorType == GpsDetectionErrorType.inaccurate) {
          _showRetrySnackBar(next.message);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(next.message)),
          );
        }
        ref.read(gpsDetectionProvider.notifier).reset();
      }
    });

    final canPop = Navigator.of(context).canPop();
    final colors = Theme.of(context).colorScheme;
    final gpsState = ref.watch(gpsDetectionProvider);

    return Scaffold(
      appBar: canPop
          ? AppBar(
              title: const Text('地域設定'),
              centerTitle: true,
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('キャンセル'),
                ),
              ],
            )
          : null,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 620),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!canPop) const SizedBox(height: 6),
                  _buildHeader(colors),
                  const SizedBox(height: 18),
                  _buildRecommendedCard(colors),
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: gpsState is GpsDetectionLoading
                        ? null
                        : () => ref
                            .read(gpsDetectionProvider.notifier)
                            .detectDistrict(),
                    icon: gpsState is GpsDetectionLoading
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.my_location_rounded),
                    label: const Text('現在地から設定'),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(48),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  _buildDivider(colors),
                  const SizedBox(height: 16),
                  Text(
                    '都道府県から選ぶ',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '現在、検索に対応している地域だけを表示しています。',
                    style: TextStyle(
                      fontSize: 12,
                      color: colors.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 12),
                  _buildManualSelectors(colors),
                  const SizedBox(height: 14),
                  FilledButton(
                    key: const Key('manual-region-button'),
                    onPressed: _isSaving ? null : _useManualRegion,
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(52),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(15),
                      ),
                    ),
                    child: _isSaving
                        ? const SizedBox.square(
                            dimension: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('選んだ地域で始める'),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    '設定はあとから変更できます',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 12,
                      color: colors.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(ColorScheme colors) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [colors.primaryContainer, colors.tertiaryContainer],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(26),
      ),
      child: Row(
        children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              color: colors.surface.withValues(alpha: 0.9),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Icon(Icons.location_on_rounded, color: colors.primary),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '地域をひとつ選ぶだけ',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                    color: colors.onPrimaryContainer,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  '収集日と分別ルールを地域に合わせます。',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.4,
                    color: colors.onPrimaryContainer.withValues(alpha: 0.75),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendedCard(ColorScheme colors) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: colors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: colors.primary.withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: colors.primaryContainer,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'デモにおすすめ',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: colors.onPrimaryContainer,
                  ),
                ),
              ),
              const Spacer(),
              Icon(Icons.cloud_done_outlined, size: 19, color: colors.primary),
              const SizedBox(width: 5),
              Text(
                'AWS検索対応',
                style: TextStyle(
                  fontSize: 11,
                  color: colors.onSurfaceVariant,
                ),
              ),
            ],
          ),
          const SizedBox(height: 13),
          const Text(
            '愛媛県  松山市  清水地区',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 14),
          FilledButton.icon(
            key: const Key('quick-region-button'),
            onPressed: _isSaving ? null : _useRecommendedRegion,
            icon: const Icon(Icons.bolt_rounded),
            label: const Text('この地域ですぐ始める'),
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(50),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(15),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDivider(ColorScheme colors) {
    return Row(
      children: [
        Expanded(child: Divider(color: colors.outlineVariant)),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Text(
            'または',
            style: TextStyle(fontSize: 12, color: colors.onSurfaceVariant),
          ),
        ),
        Expanded(child: Divider(color: colors.outlineVariant)),
      ],
    );
  }

  Widget _buildManualSelectors(ColorScheme colors) {
    final prefectures = ref.watch(prefecturesProvider);
    final municipalities = _selectedPrefecture == null
        ? null
        : ref.watch(municipalitiesProvider(_selectedPrefecture!.id));
    final districts = _selectedMunicipality == null
        ? null
        : ref.watch(districtsProvider(_selectedMunicipality!.id));

    return Container(
      decoration: BoxDecoration(
        color: colors.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: colors.outlineVariant),
      ),
      child: Column(
        children: [
          _RegionSelectorTile(
            key: const Key('prefecture-selector'),
            icon: Icons.map_outlined,
            label: '都道府県',
            value: _selectedPrefecture?.name,
            loading: prefectures.isLoading,
            error: _validationResult?.prefectureError,
            enabled: prefectures.hasValue,
            onTap: _showPrefectureSelector,
          ),
          const Divider(height: 1, indent: 56),
          _RegionSelectorTile(
            key: const Key('municipality-selector'),
            icon: Icons.apartment_rounded,
            label: '市区町村',
            value: _selectedMunicipality?.name,
            loading: municipalities?.isLoading ?? false,
            error: _validationResult?.municipalityError,
            enabled: municipalities?.hasValue ?? false,
            onTap: _showMunicipalitySelector,
          ),
          const Divider(height: 1, indent: 56),
          _RegionSelectorTile(
            key: const Key('district-selector'),
            icon: Icons.home_work_outlined,
            label: '地区',
            value: _selectedDistrict == null
                ? null
                : '${_selectedDistrict!.name}地区',
            loading: districts?.isLoading ?? false,
            error: _validationResult?.districtError,
            enabled: districts?.hasValue ?? false,
            onTap: _showDistrictSelector,
          ),
        ],
      ),
    );
  }

  void _showSettingsSnackBar(String message) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(days: 365),
        action: SnackBarAction(
          label: '設定を開く',
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
            Geolocator.openAppSettings();
          },
        ),
      ),
    );
  }

  void _showRetrySnackBar(String message) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(seconds: 10),
        action: SnackBarAction(
          label: '再試行',
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
            ref.read(gpsDetectionProvider.notifier).detectDistrict();
          },
        ),
      ),
    );
  }

  void _showGpsConfirmationDialog(DistrictMatchResult result) {
    final supported = result.districtName == _shimizu.name;
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        icon: Icon(
          supported ? Icons.location_on_rounded : Icons.info_outline_rounded,
        ),
        title: Text(supported ? '現在地を確認しました' : '検索対象外の地区です'),
        content: Text(
          supported
              ? '愛媛県 松山市 ${result.districtName}地区で設定します。'
              : '${result.districtName}地区を検出しました。現在のデモは清水地区のみ検索に対応しています。',
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(dialogContext).pop();
              ref.read(gpsDetectionProvider.notifier).reset();
            },
            child: Text(supported ? 'キャンセル' : '閉じる'),
          ),
          if (supported)
            FilledButton(
              onPressed: () async {
                Navigator.of(dialogContext).pop();
                ref.read(gpsDetectionProvider.notifier).reset();
                await _useRecommendedRegion();
              },
              child: const Text('この地域で設定'),
            ),
        ],
      ),
    );
  }

  Future<void> _showCandidateSelection(
    GpsDetectionMultipleCandidates state,
  ) async {
    final selected = await showCandidateBottomSheet(
      context: context,
      candidates: state.candidates,
      overflowMessage: state.overflowMessage,
    );
    if (!mounted) return;

    if (selected?.districtName == _shimizu.name) {
      await _useRecommendedRegion();
    } else if (selected != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '${selected.districtName}地区は準備中です。現在は清水地区を選択してください。',
          ),
        ),
      );
    }
    ref.read(gpsDetectionProvider.notifier).reset();
  }
}

class _RegionSelectorTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? value;
  final bool loading;
  final bool enabled;
  final String? error;
  final VoidCallback onTap;

  const _RegionSelectorTile({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    required this.loading,
    required this.enabled,
    required this.error,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return InkWell(
      onTap: enabled ? onTap : null,
      borderRadius: BorderRadius.circular(18),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Icon(icon,
                size: 22, color: enabled ? colors.primary : colors.outline),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 11,
                      color: colors.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 2),
                  if (loading)
                    Text(
                      '読み込み中…',
                      style: TextStyle(
                        color: colors.onSurfaceVariant,
                        fontSize: 13,
                      ),
                    )
                  else
                    Text(
                      value ?? (enabled ? '選択してください' : '上から選択してください'),
                      style: TextStyle(
                        fontWeight:
                            value == null ? FontWeight.w400 : FontWeight.w700,
                        color: enabled ? colors.onSurface : colors.outline,
                      ),
                    ),
                  if (error != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      error!,
                      style: TextStyle(fontSize: 11, color: colors.error),
                    ),
                  ],
                ],
              ),
            ),
            if (!loading)
              Icon(
                Icons.expand_more_rounded,
                color: enabled ? colors.onSurfaceVariant : colors.outline,
              ),
          ],
        ),
      ),
    );
  }
}
