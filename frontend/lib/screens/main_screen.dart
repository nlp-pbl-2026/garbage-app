import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants/colors.dart';
import '../constants/strings.dart';
import '../providers/region_provider.dart';
import 'bulky_waste_screen.dart';
import 'calendar_screen.dart';
import 'region_selection_screen.dart';
import 'search_screen.dart';
import 'settings_screen.dart';

/// メイン画面（BottomNavigationBarによる3タブ構成）
///
/// 検索・カレンダー・設定の3画面をタブで切り替える。
/// デフォルトは検索タブ（index=0）。
class MainScreen extends ConsumerStatefulWidget {
  const MainScreen({super.key});

  @override
  ConsumerState<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends ConsumerState<MainScreen> {
  /// 現在選択中のタブインデックス
  int _currentIndex = 0;

  /// 各タブに対応する画面ウィジェット
  final List<Widget> _screens = const [
    SearchScreen(),
    CalendarScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _onBulkyWasteTapped,
        icon: const Icon(Icons.delete_outline),
        label: const Text('粗大ごみ'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        selectedItemColor: AppColors.primary,
        unselectedItemColor: Colors.grey,
        backgroundColor: Colors.white,
        type: BottomNavigationBarType.fixed,
        items: [
          BottomNavigationBarItem(
            icon: _buildIcon(Icons.search, 0),
            label: AppStrings.tabSearch,
          ),
          BottomNavigationBarItem(
            icon: _buildIcon(Icons.calendar_today, 1),
            label: AppStrings.tabCalendar,
          ),
          BottomNavigationBarItem(
            icon: _buildIcon(Icons.settings, 2),
            label: AppStrings.tabSettings,
          ),
        ],
      ),
    );
  }

  /// 粗大ごみFABタップ時の処理
  void _onBulkyWasteTapped() {
    final regionAsync = ref.read(regionSettingProvider);
    final regionSetting = regionAsync.valueOrNull;

    if (regionSetting == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('地域設定が必要です'),
          duration: Duration(seconds: 3),
        ),
      );
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => const RegionSelectionScreen(),
        ),
      );
    } else {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => const BulkyWasteScreen(),
        ),
      );
    }
  }

  /// アクティブタブは緑背景色のアイコンを構築する
  Widget _buildIcon(IconData iconData, int index) {
    final isActive = _currentIndex == index;
    if (isActive) {
      return Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppColors.primary,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(
          iconData,
          color: Colors.white,
        ),
      );
    }
    return Icon(
      iconData,
      color: Colors.grey,
    );
  }
}
