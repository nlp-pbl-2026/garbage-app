import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../models/region.dart';
import '../providers/region_provider.dart';

/// 地域選択画面
///
/// 3段階ステッパー形式（都道府県→市区町村→地区）で地域を選択する画面。
/// 各ステップはカード形式で表示され、タップで選択ダイアログを表示する。
/// すべて選択後に「この地域で始める」ボタンで完了処理を行う。
class RegionSelectionScreen extends ConsumerStatefulWidget {
  /// 地域選択完了時のコールバック
  final VoidCallback? onRegionSelected;

  const RegionSelectionScreen({super.key, this.onRegionSelected});

  @override
  ConsumerState<RegionSelectionScreen> createState() =>
      _RegionSelectionScreenState();
}

class _RegionSelectionScreenState
    extends ConsumerState<RegionSelectionScreen> {
  // 選択状態
  Prefecture? _selectedPrefecture;
  Municipality? _selectedMunicipality;
  District? _selectedDistrict;

  // バリデーションエラー
  RegionValidationResult? _validationResult;

  // 保存中フラグ
  bool _isSaving = false;

  /// 都道府県選択時の処理
  void _onPrefectureSelected(Prefecture prefecture) {
    setState(() {
      _selectedPrefecture = prefecture;
      // 下位階層をリセット
      _selectedMunicipality = null;
      _selectedDistrict = null;
      _validationResult = null;
    });
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
      prefectureId: _selectedPrefecture?.id,
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
      prefectureId: _selectedPrefecture!.id,
      prefectureName: _selectedPrefecture!.name,
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

  /// 都道府県選択ダイアログを表示
  void _showPrefectureSelector() {
    final prefecturesAsync = ref.read(prefecturesProvider);

    prefecturesAsync.when(
      data: (prefectures) {
        _showSelectionDialog<Prefecture>(
          title: AppStrings.selectPrefecture,
          items: prefectures,
          getName: (p) => p.name,
          onSelected: _onPrefectureSelected,
        );
      },
      loading: () {
        // ローディング中は何もしない
      },
      error: (_, __) {
        // エラー時は何もしない（エラー表示はカード上で行う）
      },
    );
  }

  /// 市区町村選択ダイアログを表示
  void _showMunicipalitySelector() {
    if (_selectedPrefecture == null) return;

    final municipalitiesAsync =
        ref.read(municipalitiesProvider(_selectedPrefecture!.id));

    municipalitiesAsync.when(
      data: (municipalities) {
        _showSelectionDialog<Municipality>(
          title: AppStrings.selectMunicipality,
          items: municipalities,
          getName: (m) => m.name,
          onSelected: _onMunicipalitySelected,
        );
      },
      loading: () {},
      error: (_, __) {},
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
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(
            children: [
              const SizedBox(height: 32),
              // 位置アイコンとタイトル
              _buildHeader(),
              const SizedBox(height: 12),
              // 説明文
              _buildDescription(),
              const SizedBox(height: 32),
              // 3つの選択カード
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      _buildPrefectureCard(),
                      const SizedBox(height: 12),
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

  /// 都道府県選択カード
  Widget _buildPrefectureCard() {
    final prefecturesAsync = ref.watch(prefecturesProvider);

    return prefecturesAsync.when(
      data: (_) => _buildStepCard(
        stepNumber: 1,
        label: '都道府県',
        selectedValue: _selectedPrefecture?.name,
        isSelected: _selectedPrefecture != null,
        isActive: true,
        error: _validationResult?.prefectureError,
        onTap: _showPrefectureSelector,
      ),
      loading: () => _buildStepCard(
        stepNumber: 1,
        label: '都道府県',
        selectedValue: null,
        isSelected: false,
        isActive: false,
        isLoading: true,
        onTap: null,
      ),
      error: (error, _) => _buildErrorCard(
        stepNumber: 1,
        label: '都道府県',
        onRetry: () => ref.invalidate(prefecturesProvider),
      ),
    );
  }

  /// 市区町村選択カード
  Widget _buildMunicipalityCard() {
    if (_selectedPrefecture == null) {
      return _buildStepCard(
        stepNumber: 2,
        label: '市区町村',
        selectedValue: null,
        isSelected: false,
        isActive: false,
        onTap: null,
      );
    }

    final municipalitiesAsync =
        ref.watch(municipalitiesProvider(_selectedPrefecture!.id));

    return municipalitiesAsync.when(
      data: (_) => _buildStepCard(
        stepNumber: 2,
        label: '市区町村',
        selectedValue: _selectedMunicipality?.name,
        isSelected: _selectedMunicipality != null,
        isActive: true,
        error: _validationResult?.municipalityError,
        onTap: _showMunicipalitySelector,
      ),
      loading: () => _buildStepCard(
        stepNumber: 2,
        label: '市区町村',
        selectedValue: null,
        isSelected: false,
        isActive: false,
        isLoading: true,
        onTap: null,
      ),
      error: (error, _) => _buildErrorCard(
        stepNumber: 2,
        label: '市区町村',
        onRetry: () =>
            ref.invalidate(municipalitiesProvider(_selectedPrefecture!.id)),
      ),
    );
  }

  /// 地区選択カード
  Widget _buildDistrictCard() {
    if (_selectedMunicipality == null) {
      return _buildStepCard(
        stepNumber: 3,
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
        stepNumber: 3,
        label: '地区',
        selectedValue: _selectedDistrict?.name,
        isSelected: _selectedDistrict != null,
        isActive: true,
        error: _validationResult?.districtError,
        onTap: _showDistrictSelector,
      ),
      loading: () => _buildStepCard(
        stepNumber: 3,
        label: '地区',
        selectedValue: null,
        isSelected: false,
        isActive: false,
        isLoading: true,
        onTap: null,
      ),
      error: (error, _) => _buildErrorCard(
        stepNumber: 3,
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
    final isAllSelected = _selectedPrefecture != null &&
        _selectedMunicipality != null &&
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
    if (_selectedPrefecture == null) return 1;
    if (_selectedMunicipality == null) return 2;
    if (_selectedDistrict == null) return 3;
    return 0; // すべて選択済み
  }
}
