/// アプリ内で使用する日本語文字列定数
///
/// すべてのUIテキストをここで一元管理し、
/// 一貫性のある表示と将来的な多言語対応を容易にする。
class AppStrings {
  // プライベートコンストラクタ（インスタンス化防止）
  AppStrings._();

  // アプリ基本情報
  /// アプリ名
  static const String appName = 'ごみサポ';

  // ゴミ分類カテゴリ名
  /// 可燃ごみ
  static const String categoryBurnable = '可燃ごみ';

  /// 資源ごみ
  static const String categoryRecyclable = '資源ごみ';

  /// プラスチック製容器包装
  static const String categoryPlastic = 'プラスチック製容器包装';

  /// ペットボトル
  static const String categoryPetBottle = 'ペットボトル';

  /// 危険ごみ
  static const String categoryHazardous = '危険ごみ';

  // ナビゲーションタブ
  /// 検索タブラベル
  static const String tabSearch = '検索';

  /// カレンダータブラベル
  static const String tabCalendar = 'カレンダー';

  /// 設定タブラベル
  static const String tabSettings = '設定';

  // 地域選択画面
  /// 地域選択画面タイトル
  static const String regionSelectionTitle = '地域を選択';

  /// 都道府県選択ステップ
  static const String selectPrefecture = '都道府県を選択';

  /// 市区町村選択ステップ
  static const String selectMunicipality = '市区町村を選択';

  /// 地区選択ステップ
  static const String selectDistrict = '地区を選択';

  /// 地域設定完了ボタン
  static const String startWithRegion = 'この地域で始める';

  // 検索画面
  /// 検索画面タイトル
  static const String searchTitle = 'ゴミ品目検索';

  /// 検索ヒント
  static const String searchHint = '品目名を入力（2文字以上）';

  /// よく検索される品目セクションタイトル
  static const String popularItems = 'よく検索される品目';

  /// 複数品目該当メッセージ
  static const String multipleItemsFound = '近い品目が複数見つかりました';

  /// 複数カテゴリ該当補足
  static const String multipleCategoriesNote = 'または品目により異なる';

  // 品目詳細画面
  /// 品目詳細画面タイトル
  static const String itemDetailTitle = '品目詳細';

  /// 次回収集日ラベル
  static const String nextCollectionDate = '次回収集日';

  /// 出し方ラベル
  static const String disposalMethod = '出し方';

  /// 注意事項ラベル
  static const String caution = '注意事項';

  /// カレンダーに登録ボタン
  static const String registerToCalendar = 'カレンダーに登録';

  // カレンダー画面
  /// カレンダー画面タイトル
  static const String calendarTitle = '収集カレンダー';

  /// 次回収集予定バナー
  static const String nextCollection = '次回の収集';

  /// 収集予定なしメッセージ
  static const String noSchedule = 'この日の収集予定はありません';

  /// 色凡例タイトル
  static const String colorLegend = '色凡例';

  // 設定画面
  /// 設定画面タイトル
  static const String settingsTitle = '設定';

  /// 地域設定セクション
  static const String regionSettings = '地域設定';

  /// 地域変更ボタン
  static const String changeRegion = '地域を変更';

  /// 通知設定セクション
  static const String notificationSettings = '通知設定';

  /// リマインダートグルラベル
  static const String reminderToggle = '収集日前日リマインダー';

  /// リマインダー説明
  static const String reminderDescription = '収集日前日の18:00に通知します';

  // エラーメッセージ
  /// 検索結果なし
  static const String noSearchResults = '該当する品目が見つかりませんでした';

  /// データ取得失敗
  static const String dataLoadError = 'データの取得に失敗しました';

  /// 地域データ取得失敗
  static const String regionDataError = '地域データの取得に失敗しました';

  /// 保存失敗
  static const String saveError = '保存に失敗しました';

  /// 地域未設定メッセージ
  static const String regionNotSet = '地域が設定されていません';

  /// データ古い通知
  static const String dataOutdated = 'データが古い可能性があります。ネットワークに接続してデータを更新してください。';

  /// オフラインデータなし
  static const String noOfflineData = 'データが利用できません。ネットワーク接続が必要です。';

  // バリデーションエラー
  /// 都道府県未選択
  static const String prefectureNotSelected = '都道府県を選択してください';

  /// 市区町村未選択
  static const String municipalityNotSelected = '市区町村を選択してください';

  /// 地区未選択
  static const String districtNotSelected = '地区を選択してください';

  // フィードバックメッセージ
  /// 地域設定保存完了
  static const String regionSaved = '地域設定を保存しました';

  /// カレンダー登録完了
  static const String calendarRegistered = 'カレンダーに登録しました';

  /// カレンダー権限エラー
  static const String calendarPermissionDenied =
      'カレンダーへのアクセス権限が必要です。設定画面から権限を許可してください。';

  // ボタンラベル
  /// 再試行ボタン
  static const String retry = '再試行';

  /// 戻るボタン
  static const String back = '戻る';

  /// 設定を開くボタン
  static const String openSettings = '設定を開く';
}
