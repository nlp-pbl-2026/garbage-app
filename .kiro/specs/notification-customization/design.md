# Design Document: 通知カスタマイズ

## Overview

ゴミ種別（GarbageCategory）ごとに前日通知・当日通知のON/OFFを個別設定できる機能を追加する。既存のNotificationServiceのスケジューリングロジックにフィルタリング層を導入し、SettingsProviderパターンに従ったRiverpod状態管理でUIと永続化を接続する。

## Architecture

本機能は以下の3層で構成する:

1. **データ層**: `NotificationCustomizationService` — SharedPreferencesへのカテゴリ別通知設定の読み書き
2. **状態管理層**: `NotificationCustomizationNotifier` — Riverpod StateNotifierによるリアクティブ状態管理
3. **UI層**: 設定画面内の通知カスタマイズセクション — トグルスイッチによる設定変更

既存の`NotificationService.scheduleWeeklyNotifications`にフィルタリングロジックを追加し、カテゴリ設定に基づいて通知対象を絞り込む。

```
┌─────────────────────────────────────────┐
│            Settings Screen               │
│  ┌─────────────────────────────────┐    │
│  │ NotificationCustomizationWidget │    │
│  │  - 5カテゴリ × 2トグル          │    │
│  └──────────────┬──────────────────┘    │
└─────────────────┼───────────────────────┘
                  │ watch / toggle()
                  ▼
┌─────────────────────────────────────────┐
│ NotificationCustomizationNotifier        │
│ (StateNotifier<AsyncValue<Map>>)         │
└──────────────┬──────────────────────────┘
               │ read / write
               ▼
┌─────────────────────────────────────────┐
│ NotificationCustomizationService         │
│  - getCategorySettings()                 │
│  - setCategorySetting(category, timing,  │
│    enabled)                              │
│  - getEnabledCategories(timing)          │
└──────────────┬──────────────────────────┘
               │ SharedPreferences
               ▼
┌─────────────────────────────────────────┐
│ SharedPreferences                        │
│  Key: notification_category_{name}_{t}   │
└─────────────────────────────────────────┘

フィルタリング連携:
┌─────────────────────────────────────────┐
│ NotificationService                      │
│  scheduleWeeklyNotifications()           │
│    → getEnabledCategories(evening)       │
│    → getEnabledCategories(morning)       │
│    → フィルタリング適用後に通知生成       │
└─────────────────────────────────────────┘
```

## Components and Interfaces

### 1. CategoryNotificationSetting データモデル

各カテゴリの前日・当日通知設定を表現するイミュータブルモデル。

```dart
/// 各ゴミ種別に対する通知タイミング別ON/OFF設定
class CategoryNotificationSetting {
  final GarbageCategory category;
  final bool eveningEnabled; // 前日通知
  final bool morningEnabled; // 当日通知

  const CategoryNotificationSetting({
    required this.category,
    this.eveningEnabled = true,
    this.morningEnabled = true,
  });

  CategoryNotificationSetting copyWith({
    bool? eveningEnabled,
    bool? morningEnabled,
  }) {
    return CategoryNotificationSetting(
      category: category,
      eveningEnabled: eveningEnabled ?? this.eveningEnabled,
      morningEnabled: morningEnabled ?? this.morningEnabled,
    );
  }
}
```

### 2. NotificationTimingType 列挙型

通知タイミングの種別を表す列挙型。

```dart
/// 通知タイミング種別
enum NotificationTimingType {
  /// 前日通知（夕方）
  evening,
  /// 当日通知（朝）
  morning,
}
```

### 3. NotificationCustomizationService

SharedPreferencesへの永続化を担当するサービス。

```dart
class NotificationCustomizationService {
  /// SharedPreferencesキーのプレフィックス
  static const String _keyPrefix = 'notification_category_';

  /// 指定カテゴリ・タイミングの設定キーを生成
  String _buildKey(GarbageCategory category, NotificationTimingType timing) {
    return '${_keyPrefix}${category.toJsonString()}_${timing.name}';
  }

  /// 全カテゴリの設定を読み込む
  Future<Map<GarbageCategory, CategoryNotificationSetting>> loadAllSettings();

  /// 指定カテゴリ・タイミングの設定を保存する
  Future<void> saveSetting(
    GarbageCategory category,
    NotificationTimingType timing,
    bool enabled,
  );

  /// 指定タイミングで通知が有効なカテゴリ一覧を取得する
  Future<List<GarbageCategory>> getEnabledCategories(
    NotificationTimingType timing,
  );
}
```

### 4. NotificationCustomizationNotifier（状態管理）

Riverpod StateNotifierパターンで状態を管理。既存のReminderNotifierと同じパターンに従う。

```dart
/// カテゴリ別通知設定の状態型
typedef CategorySettingsMap = Map<GarbageCategory, CategoryNotificationSetting>;

/// カテゴリ別通知設定のStateNotifierProvider
final notificationCustomizationProvider = StateNotifierProvider<
    NotificationCustomizationNotifier, AsyncValue<CategorySettingsMap>>((ref) {
  final customizationService = ref.watch(notificationCustomizationServiceProvider);
  final notificationService = ref.watch(notificationServiceProvider);
  return NotificationCustomizationNotifier(customizationService, notificationService);
});

class NotificationCustomizationNotifier
    extends StateNotifier<AsyncValue<CategorySettingsMap>> {
  final NotificationCustomizationService _customizationService;
  final NotificationService _notificationService;

  NotificationCustomizationNotifier(
    this._customizationService,
    this._notificationService,
  ) : super(const AsyncValue.loading()) {
    _loadSettings();
  }

  /// SharedPreferencesから設定を読み込む
  Future<void> _loadSettings();

  /// 指定カテゴリ・タイミングの設定をトグルする
  Future<void> toggle(
    GarbageCategory category,
    NotificationTimingType timing,
  );
}
```

### 5. NotificationService への統合（フィルタリング）

既存の`scheduleWeeklyNotifications`メソッドにフィルタリングロジックを追加する。

```dart
// NotificationService.scheduleWeeklyNotifications 内の変更点:

// フィルタリング用にカスタマイズサービスを参照
final customizationService = NotificationCustomizationService();
final eveningEnabled = await customizationService.getEnabledCategories(
  NotificationTimingType.evening,
);
final morningEnabled = await customizationService.getEnabledCategories(
  NotificationTimingType.morning,
);

// 前日通知: eveningEnabledに含まれるカテゴリのみ
final eveningEntries = entries
    .where((e) => eveningEnabled.contains(e.category))
    .toList();

// 当日通知: morningEnabledに含まれるカテゴリのみ  
final morningEntries = entries
    .where((e) => morningEnabled.contains(e.category))
    .toList();

// フィルタリング後が空ならスキップ
if (eveningEntries.isNotEmpty) {
  final categoryNames = eveningEntries
      .map((e) => CategoryColors.getLabel(e.category))
      .join('・');
  // 通知スケジュール...
}
```

### 6. UI コンポーネント

設定画面内に配置する通知カスタマイズウィジェット。

```dart
class NotificationCustomizationWidget extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settingsAsync = ref.watch(notificationCustomizationProvider);
    final reminderEnabled = ref.watch(reminderEnabledProvider).valueOrNull ?? false;

    // リマインダーが無効なら非表示
    if (!reminderEnabled) return const SizedBox.shrink();

    return settingsAsync.when(
      loading: () => const CircularProgressIndicator(),
      error: (_, __) => const Text('設定の読み込みに失敗しました'),
      data: (settings) => _buildCategoryList(context, ref, settings),
    );
  }

  Widget _buildCategoryList(
    BuildContext context,
    WidgetRef ref,
    CategorySettingsMap settings,
  ) {
    return Column(
      children: GarbageCategory.values.map((category) {
        final setting = settings[category]!;
        final color = CategoryColors.getColor(category);
        final label = CategoryColors.getLabel(category);

        return _CategoryNotificationTile(
          label: label,
          color: color,
          eveningEnabled: setting.eveningEnabled,
          morningEnabled: setting.morningEnabled,
          onEveningToggle: () => ref
              .read(notificationCustomizationProvider.notifier)
              .toggle(category, NotificationTimingType.evening),
          onMorningToggle: () => ref
              .read(notificationCustomizationProvider.notifier)
              .toggle(category, NotificationTimingType.morning),
        );
      }).toList(),
    );
  }
}
```

## Data Models

### SharedPreferences キー設計

| キー形式 | 型 | デフォルト | 例 |
|---------|-----|----------|-----|
| `notification_category_{category}_{timing}` | bool | true | `notification_category_burnable_evening` |

- `{category}`: GarbageCategoryのtoJsonString()値（burnable, recyclable, plastic, petBottle, hazardous）
- `{timing}`: NotificationTimingTypeのname値（evening, morning）
- 計10個のキー（5カテゴリ × 2タイミング）

### 設定値の初期状態

全カテゴリ・全タイミングが `true`（ON）。SharedPreferencesにキーが存在しない場合はデフォルトとしてtrueを返す。

### NotificationCustomizationService API

```dart
abstract class INotificationCustomizationService {
  /// 全カテゴリの通知設定を読み込む
  /// SharedPreferencesにキーが存在しない場合はtrue（ON）をデフォルトとする
  Future<Map<GarbageCategory, CategoryNotificationSetting>> loadAllSettings();

  /// 指定カテゴリ・タイミングの通知設定を保存する
  Future<void> saveSetting(
    GarbageCategory category,
    NotificationTimingType timing,
    bool enabled,
  );

  /// 指定タイミングで通知が有効なカテゴリ一覧を返す
  Future<List<GarbageCategory>> getEnabledCategories(
    NotificationTimingType timing,
  );
}
```

### NotificationService 変更インターフェース

既存メソッドのシグネチャ変更なし。内部実装のみ変更。

```dart
// 変更なし（既存API）
Future<void> scheduleWeeklyNotifications(String districtId);
Future<void> refreshNotifications();
```

## Error Handling

| エラーケース | 対応方針 |
|-------------|---------|
| SharedPreferences読み込み失敗 | エラー状態を公開しつつ、全カテゴリON（デフォルト）で通知スケジュールを続行 |
| SharedPreferences書き込み失敗 | UI状態はロールバックし、エラーをdebugPrintで記録 |
| 不正なキー値（データ破損） | デフォルト値（true）にフォールバック |
| カテゴリ追加時の互換性 | 未知のキーはデフォルトtrueとして扱う |

## Testing Strategy

### ユニットテスト（Example-based）
- **初期化テスト**: SharedPreferencesが空の状態でサービス初期化後、全10設定がON（true）であること（Requirements 1.3）
- **リスケジュールテスト**: 設定変更後にrefreshNotificationsが呼び出されること（Requirements 2.4）
- **UIウィジェットテスト**: リマインダーON/OFF時のセクション表示/非表示（Requirements 3.1, 3.5）
- **トグル操作テスト**: トグル操作後のUI状態変化と永続化呼び出し（Requirements 3.4）
- **状態遷移テスト**: Loading→Data の非同期初期化フロー（Requirements 4.3）
- **エラーフォールバックテスト**: SharedPreferences読み込み失敗時に全ONデフォルトで動作（Requirements 4.4）

### プロパティベーステスト（Property-based）
- **設定永続化ラウンドトリップ**: 任意の設定値の保存→読み込みの同一性検証
- **通知カテゴリフィルタリング**: 任意のON/OFFパターンに対するフィルタリング正確性
- **通知本文正確性**: フィルタリング後の通知本文に有効カテゴリラベルのみ含まれること

### テスト設定
- プロパティテスト: 最低100回のイテレーション
- モック: SharedPreferencesはテスト用モック実装を使用
- ジェネレータ: GarbageCategory（5値）× NotificationTimingType（2値）× bool（2値）の全組み合わせ空間

## Correctness Properties

*プロパティとは、システムのすべての有効な実行に対して成り立つべき特性または動作のことであり、人間が読める仕様と機械的に検証可能な正しさの保証を橋渡しする形式的な記述です。*

### Property 1: 設定永続化ラウンドトリップ

*任意の*GarbageCategoryと任意のNotificationTimingTypeと任意のbool値に対して、saveSettingで保存した値は、loadAllSettingsで読み込んだ時に同一の値が返される。

**Validates: Requirements 1.2, 1.4, 1.5**

### Property 2: 通知カテゴリフィルタリング

*任意の*カテゴリ別ON/OFF設定パターンに対して、getEnabledCategories(timing)が返すカテゴリリストは、そのtimingでONに設定されているカテゴリのみを含み、OFFに設定されているカテゴリを含まない。

**Validates: Requirements 2.1, 2.2, 2.3**

### Property 3: 通知本文の正確性

*任意の*カテゴリ別ON/OFF設定パターンと任意のスケジュールエントリに対して、生成される通知本文には、該当タイミングでONに設定されたカテゴリのラベルのみが含まれ、OFFに設定されたカテゴリのラベルは含まれない。

**Validates: Requirements 2.5**
