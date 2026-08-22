import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../models/gps_detection.dart';
import '../models/region.dart';
import '../providers/gps_detection_provider.dart';
import '../providers/region_provider.dart';
import '../widgets/candidate_bottom_sheet.dart';

/// 地域選択画面
///
/// 2段階ステッパー形式（市区町村→地区）で地域を選択する画面。
/// 都道府県は愛媛県固定（このアプリは愛媛県専用）。
/// 各ステップはカード形式で表示され、タップで選択ダイアログを表示する。
/// すべて選択後に「この地域で始める」ボタンで完了処理を行う。
class RegionSelectionScreen extends ConsumerStatefulWidget {
  /// 地域選択完了時のコールバック
  final VoidCallback? onRegionSelected;

  /// trueの場合、画面表示時にGPS自動検出を開始する
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

class _RegionSelectionScreenState
    extends ConsumerState<RegionSelectionScreen> {
  // 愛媛県固定（このアプリは愛媛県専用）
  final Prefecture _fixedPrefecture = Prefecture(id: '38', name: '愛媛県');

  // 選択状態
  Municipality? _selectedMunicipality;
  District? _selectedDistrict;

  // バリデーションエラー
  RegionValidationResult? _validationResult;

  // 保存中フラグ
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    // autoDetect: true の場合、画面描画後にGPS検出を自動実行する
    if (widget.autoDetect) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(gpsDetectionProvider.notifier).detectDistrict();
      });
    }
  }

  /// 市区町村選択時の処理
  void _onMunicipalitySelected(Municipality municipality) {
    setState(() {
      _selectedMunicipality = municipality;
      // 下位階層をリセット
      _selectedDistrict = null;
      _validationResult = null;
    });
  }

  /// 地区選択時の処理
  void _onDistrictSelected(District district) {
    setState(() {
      _selectedDistrict = district;
      _validationResult = null;
    });
  }

  /// 「この地域で始める」ボタン押下時の処理
  Future<void> _onStartPressed() async {
    // バリデーション実行
    final result = ref.read(regionSettingProvider.notifier).validate(
      prefectureId: _fixedPrefecture.id,
      municipalityId: _selectedMunicipality?.id,
      districtId: _selectedDistrict?.id,
    );

    if (!result.isValid) {
      setState(() {
        _validationResult = result;
      });
      return;
    }

    // 地域設定を保存
    setState(() {
      _isSaving = true;
    });

    final setting = RegionSetting(
      prefectureId: _fixedPrefecture.id,
      prefectureName: _fixedPrefecture.name,
      municipalityId: _selectedMunicipality!.id,
      municipalityName: _selectedMunicipality!.name,
      districtId: _selectedDistrict!.id,
      districtName: _selectedDistrict!.name,
    );

    await ref.read(regionSettingProvider.notifier).saveSetting(setting);

    setState(() {
      _isSaving = false;
    });

    // コールバックがあれば呼び出す
    widget.onRegionSelected?.call();
  }

  /// 市区町村選択ダイアログを表示
  void _showMunicipalitySelector() {
    final municipalitiesAsync =
        ref.read(municipalitiesProvider('38'));

    municipalitiesAsync.when(
      data: (municipalities) {
        _showMunicipalityGroupedDialog(municipalities);
      },
      loading: () {},
      error: (_, __) {},
    );
  }

  /// 市区町村をグループ分けして表示するダイアログ
  void _showMunicipalityGroupedDialog(List<Municipality> municipalities) {
    // 市と町村に分類
    final cities = municipalities.where((m) => m.gun == null).toList();
    final towns = municipalities.where((m) => m.gun != null).toList();

    // 郡ごとにグループ化
    final townsByGun = <String, List<Municipality>>{};
    for (final town in towns) {
      final gunName = town.gun!;
      townsByGun.putIfAbsent(gunName, () => []).add(town);
    }

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) {
        return DraggableScrollableSheet(
          initialChildSize: 0.6,
          minChildSize: 0.3,
          maxChildSize: 0.8,
          expand: false,
          builder: (context, scrollController) {
            return Column(
              children: [
                // ハンドルバー
                Container(
                  margin: const EdgeInsets.only(top: 12, bottom: 8),
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                // タイトル
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  child: Text(
                    AppStrings.selectMunicipality,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const Divider(),
                // グループ分けリスト
                Expanded(
                  child: ListView(
                    controller: scrollController,
                    children: [
                      // 市セクション
                      if (cities.isNotEmpty) ...[
                        _buildSectionHeader('市'),
                        ...cities.map((city) => ListTile(
                              title: Text(city.name),
                              onTap: () {
                                _onMunicipalitySelected(city);
                                Navigator.of(context).pop();
                              },
                            )),
                      ],
                      // 郡・町セクション
                      for (final entry in townsByGun.entries) ...[
                        _buildSectionHeader(entry.key),
                        ...entry.value.map((town) => ListTile(
                              title: Text(town.name),
                              onTap: () {
                                _onMunicipalitySelected(town);
                                Navigator.of(context).pop();
                              },
                            )),
                      ],
                    ],
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  /// セクションヘッダーウィジェット
  Widget _buildSectionHeader(String title) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: Colors.grey[100],
      child: Text(
        title,
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.bold,
          color: Colors.grey[700],
        ),
      ),
    );
  }

  /// 地区選択ダイアログを表示
  void _showDistrictSelector() {
    if (_selectedMunicipality == null) return;

    final districtsAsync =
        ref.read(districtsProvider(_selectedMunicipality!.id));

    districtsAsync.when(
      data: (districts) {
        _showSelectionDialog<District>(
          title: AppStrings.selectDistrict,
          items: districts,
          getName: (d) => d.name,
          onSelected: _onDistrictSelected,
        );
      },
      loading: () {},
      error: (_, __) {},
    );
  }

  /// 汎用選択ダイアログ表示
  void _showSelectionDialog<T>({
    required String title,
    required List<T> items,
    required String Function(T) getName,
    required void Function(T) onSelected,
  }) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) {
        return DraggableScrollableSheet(
          initialChildSize: 0.5,
          minChildSize: 0.3,
          maxChildSize: 0.8,
          expand: false,
          builder: (context, scrollController) {
            return Column(
              children: [
                // ハンドルバー
                Container(
                  margin: const EdgeInsets.only(top: 12, bottom: 8),
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                // タイトル
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  child: Text(
                    title,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const Divider(),
                // リスト
                Expanded(
                  child: ListView.builder(
                    controller: scrollController,
                    itemCount: items.length,
                    itemBuilder: (context, index) {
                      final item = items[index];
                      return ListTile(
                        title: Text(getName(item)),
                        onTap: () {
                          onSelected(item);
                          Navigator.of(context).pop();
                        },
                      );
                    },
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    // GPS判定結果をリッスンし、成功時に確認ダイアログ、複数候補時にボトムシート、エラー時にSnackBarを表示
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
            SnackBar(
              content: Text(next.message),
              duration: const Duration(seconds: 3),
            ),
          );
        }
        // 状態を Idle にリセットしてボタンを再タップ可能にする
        ref.read(gpsDetectionProvider.notifier).reset();
      }
    });

    final canPop = Navigator.of(context).canPop();
    return Scaffold(
      appBar: canPop
          ? AppBar(
              leading: IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => Navigator.of(context).pop(),
              ),
              title: const Text(
                '地域設定',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
              centerTitle: true,
              backgroundColor: Colors.transparent,
              elevation: 0,
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: Text(
                    'キャンセル',
                    style: TextStyle(color: Colors.grey[600]),
                  ),
                ),
              ],
            )
          : null,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(
            children: [
              if (!canPop) const SizedBox(height: 32),
              // 位置アイコンとタイトル
              _buildHeader(),
              const SizedBox(height: 12),
              // 説明文
              _buildDescription(),
              const SizedBox(height: 32),
              // 2つの選択カード
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      // GPS「現在地から設定」ボタン
                      _buildGpsDetectionButton(),
                      const SizedBox(height: 20),
                      _buildMunicipalityCard(),
                      const SizedBox(height: 12),
                      _buildDistrictCard(),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              // 「この地域で始める →」ボタン
              _buildStartButton(),
              const SizedBox(height: 12),
              // 注記
              _buildNote(),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }

  /// GPS「現在地から設定」ボタン
  Widget _buildGpsDetectionButton() {
    final gpsState = ref.watch(gpsDetectionProvider);
    final isLoading = gpsState is GpsDetectionLoading;

    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: isLoading
            ? null
            : () {
                ref.read(gpsDetectionProvider.notifier).detectDistrict();
              },
        icon: isLoading
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.my_location),
        label: const Text('現在地から設定'),
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }

  /// 設定アプリ誘導SnackBarを表示する。
  ///
  /// permissionDenied / serviceDisabled エラー時に、「設定を開く」アクションボタン付き
  /// SnackBarを表示する。ユーザーがアクションをタップするか閉じるまで維持される。
  /// タップ時は Geolocator.openAppSettings() を呼び出す。
  /// 設定から戻った後は自動再試行せず、ボタン再タップ可能な状態を維持する。
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

  /// タイムアウト・精度不足エラー時の再試行SnackBarを表示
  ///
  /// 10秒後に自動で消えるか、ユーザーが「再試行」をタップすると消える。
  /// 「再試行」タップ時: SnackBarを閉じてGPS判定フローを再実行する。
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

  /// GPS判定成功時の確認ダイアログを表示
  void _showGpsConfirmationDialog(DistrictMatchResult result) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('GPS判定結果'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('以下の地域が検出されました：'),
              const SizedBox(height: 12),
              Text('都道府県: 愛媛県'),
              Text('市区町村: 松山市'),
              Text('地区: ${result.districtName}'),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop();
                ref.read(gpsDetectionProvider.notifier).reset();
              },
              child: const Text('キャンセル'),
            ),
            ElevatedButton(
              onPressed: () async {
                final setting = RegionSetting(
                  prefectureId: '38',
                  prefectureName: '愛媛県',
                  municipalityId: '38201',
                  municipalityName: '松山市',
                  districtId: '38201-${result.districtNumber}',
                  districtName: result.districtName,
                );
                await ref
                    .read(regionSettingProvider.notifier)
                    .saveSetting(setting);
                if (dialogContext.mounted) {
                  Navigator.of(dialogContext).pop();
                }
                widget.onRegionSelected?.call();
              },
              child: const Text('この地域で設定'),
            ),
          ],
        );
      },
    );
  }

  /// GPS判定で複数候補が見つかった場合のボトムシート表示と結果処理
  Future<void> _showCandidateSelection(
    GpsDetectionMultipleCandidates state,
  ) async {
    final selectedCandidate = await showCandidateBottomSheet(
      context: context,
      candidates: state.candidates,
      overflowMessage: state.overflowMessage,
    );

    if (selectedCandidate != null) {
      // ユーザーが候補を選択し確認した → 地区を適用
      final setting = RegionSetting(
        prefectureId: '38',
        prefectureName: '愛媛県',
        municipalityId: '38201',
        municipalityName: '松山市',
        districtId: '38201-${selectedCandidate.districtNumber}',
        districtName: selectedCandidate.districtName,
      );
      await ref.read(regionSettingProvider.notifier).saveSetting(setting);
      widget.onRegionSelected?.call();
    }

    // null の場合: ボトムシート外タップで閉じた → 手動選択モードに戻る
    ref.read(gpsDetectionProvider.notifier).reset();
  }

  /// ヘッダー（位置アイコン + タイトル）
  Widget _buildHeader() {
    return Column(
      children: [
        Icon(
          Icons.location_on,
          size: 48,
          color: AppColors.primary,
        ),
        const SizedBox(height: 12),
        const Text(
          'お住まいの地域を設定してください',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  /// 説明文
  Widget _buildDescription() {
    return const Text(
      'ごみの収集日や正しい分別ルールを、お住まいの地域に合わせて最適化します。',
      style: TextStyle(
        fontSize: 14,
        color: Colors.grey,
      ),
      textAlign: TextAlign.center,
    );
  }

  /// 市区町村選択カード
  Widget _buildMunicipalityCard() {
    final municipalitiesAsync =
        ref.watch(municipalitiesProvider('38'));

    return municipalitiesAsync.when(
      data: (_) => _buildStepCard(
        stepNumber: 1,
        label: '市区町村',
        selectedValue: _selectedMunicipality?.displayName,
        isSelected: _selectedMunicipality != null,
        isActive: true,
        error: _validationResult?.municipalityError,
        onTap: _showMunicipalitySelector,
      ),
      loading: () => _buildStepCard(
        stepNumber: 1,
        label: '市区町村',
        selectedValue: null,
        isSelected: false,
        isActive: false,
        isLoading: true,
        onTap: null,
      ),
      error: (error, _) => _buildErrorCard(
        stepNumber: 1,
        label: '市区町村',
        onRetry: () =>
            ref.invalidate(municipalitiesProvider('38')),
      ),
    );
  }

  /// 地区選択カード
  Widget _buildDistrictCard() {
    if (_selectedMunicipality == null) {
      return _buildStepCard(
        stepNumber: 2,
        label: '地区',
        selectedValue: null,
        isSelected: false,
        isActive: false,
        onTap: null,
      );
    }

    final districtsAsync =
        ref.watch(districtsProvider(_selectedMunicipality!.id));

    return districtsAsync.when(
      data: (_) => _buildStepCard(
        stepNumber: 2,
        label: '地区',
        selectedValue: _selectedDistrict?.name,
        isSelected: _selectedDistrict != null,
        isActive: true,
        error: _validationResult?.districtError,
        onTap: _showDistrictSelector,
      ),
      loading: () => _buildStepCard(
        stepNumber: 2,
        label: '地区',
        selectedValue: null,
        isSelected: false,
        isActive: false,
        isLoading: true,
        onTap: null,
      ),
      error: (error, _) => _buildErrorCard(
        stepNumber: 2,
        label: '地区',
        onRetry: () =>
            ref.invalidate(districtsProvider(_selectedMunicipality!.id)),
      ),
    );
  }

  /// ステップカードウィジェット
  Widget _buildStepCard({
    required int stepNumber,
    required String label,
    required String? selectedValue,
    required bool isSelected,
    required bool isActive,
    String? error,
    bool isLoading = false,
    VoidCallback? onTap,
  }) {
    // アクティブで選択中のステップは緑枠ハイライト
    final bool isHighlighted = isActive && !isSelected && _selectedDistrict == null;
    final borderColor = isSelected
        ? AppColors.primary
        : (isHighlighted && stepNumber == _currentActiveStep)
            ? AppColors.primary
            : Colors.grey[300]!;
    final borderWidth = (isSelected || (isHighlighted && stepNumber == _currentActiveStep)) ? 2.0 : 1.0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Material(
          elevation: isActive ? 2 : 0,
          borderRadius: BorderRadius.circular(12),
          child: InkWell(
            onTap: isActive ? onTap : null,
            borderRadius: BorderRadius.circular(12),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: isActive ? Colors.white : Colors.grey[100],
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: error != null ? AppColors.error : borderColor,
                  width: error != null ? 2.0 : borderWidth,
                ),
              ),
              child: Row(
                children: [
                  // ステップ番号
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: isSelected
                          ? AppColors.primary
                          : isActive
                              ? AppColors.primary.withOpacity(0.1)
                              : Colors.grey[200],
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        '$stepNumber',
                        style: TextStyle(
                          color: isSelected ? Colors.white : AppColors.primary,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  // ラベルと選択値
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          label,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                        const SizedBox(height: 2),
                        if (isLoading)
                          const SizedBox(
                            height: 16,
                            width: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        else
                          Text(
                            selectedValue ?? '選択してください',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: selectedValue != null
                                  ? FontWeight.w600
                                  : FontWeight.normal,
                              color: selectedValue != null
                                  ? Colors.black87
                                  : Colors.grey[400],
                            ),
                          ),
                      ],
                    ),
                  ),
                  // チェックマークまたは矢印
                  if (isSelected)
                    const Icon(
                      Icons.check_circle,
                      color: AppColors.primary,
                      size: 24,
                    )
                  else if (isActive)
                    Icon(
                      Icons.chevron_right,
                      color: Colors.grey[400],
                      size: 24,
                    ),
                ],
              ),
            ),
          ),
        ),
        // バリデーションエラー表示
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(left: 16, top: 4),
            child: Text(
              error,
              style: const TextStyle(
                color: AppColors.error,
                fontSize: 12,
              ),
            ),
          ),
      ],
    );
  }

  /// エラーカード（データ取得失敗時）
  Widget _buildErrorCard({
    required int stepNumber,
    required String label,
    required VoidCallback onRetry,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.red[50],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.error),
      ),
      child: Row(
        children: [
          // ステップ番号
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: Colors.red[100],
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                '$stepNumber',
                style: const TextStyle(
                  color: AppColors.error,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          // エラーメッセージ
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                  ),
                ),
                const SizedBox(height: 2),
                const Text(
                  AppStrings.regionDataError,
                  style: TextStyle(
                    fontSize: 14,
                    color: AppColors.error,
                  ),
                ),
              ],
            ),
          ),
          // 再試行ボタン
          TextButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text(AppStrings.retry),
            style: TextButton.styleFrom(
              foregroundColor: AppColors.error,
            ),
          ),
        ],
      ),
    );
  }

  /// 「この地域で始める →」ボタン
  Widget _buildStartButton() {
    final isAllSelected = _selectedMunicipality != null &&
        _selectedDistrict != null;

    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: _isSaving ? null : _onStartPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          elevation: isAllSelected ? 2 : 0,
        ),
        child: _isSaving
            ? const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    AppStrings.startWithRegion,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  SizedBox(width: 8),
                  Icon(Icons.arrow_forward, size: 20),
                ],
              ),
      ),
    );
  }

  /// 注記テキスト
  Widget _buildNote() {
    return Text(
      '設定は後から「設定画面」で変更できます',
      style: TextStyle(
        fontSize: 12,
        color: Colors.grey[500],
      ),
      textAlign: TextAlign.center,
    );
  }

  /// 現在アクティブなステップ番号を取得
  int get _currentActiveStep {
    if (_selectedMunicipality == null) return 1;
    if (_selectedDistrict == null) return 2;
    return 0; // すべて選択済み
  }
}
