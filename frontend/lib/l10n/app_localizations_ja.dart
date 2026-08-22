// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Japanese (`ja`).
class AppLocalizationsJa extends AppLocalizations {
  AppLocalizationsJa([String locale = 'ja']) : super(locale);

  @override
  String get appName => '愛媛ゴミ出しアプリ';

  @override
  String get categoryBurnable => '可燃ごみ';

  @override
  String get categoryRecyclable => '資源ごみ';

  @override
  String get categoryPlastic => 'プラスチック製容器包装';

  @override
  String get categoryPetBottle => 'ペットボトル';

  @override
  String get categoryHazardous => '危険ごみ';

  @override
  String get tabSearch => '検索';

  @override
  String get tabCalendar => 'カレンダー';

  @override
  String get tabSettings => '設定';

  @override
  String get tabImageInput => '画像入力';

  @override
  String get regionSelectionTitle => '地域を選択';

  @override
  String get selectPrefecture => '都道府県を選択';

  @override
  String get selectMunicipality => '市区町村を選択';

  @override
  String get selectDistrict => '地区を選択';

  @override
  String get startWithRegion => 'この地域で始める';

  @override
  String get searchTitle => 'ゴミ品目検索';

  @override
  String get searchHint => '品目名を入力（2文字以上）';

  @override
  String get popularItems => 'よく検索される品目';

  @override
  String get multipleItemsFound => '近い品目が複数見つかりました';

  @override
  String get multipleCategoriesNote => 'または品目により異なる';

  @override
  String get itemDetailTitle => '品目詳細';

  @override
  String get nextCollectionDate => '次回収集日';

  @override
  String get disposalMethod => '出し方';

  @override
  String get caution => '注意事項';

  @override
  String get registerToCalendar => 'カレンダーに登録';

  @override
  String get calendarTitle => '収集カレンダー';

  @override
  String get nextCollection => '次回の収集';

  @override
  String get noSchedule => 'この日の収集予定はありません';

  @override
  String get colorLegend => '色凡例';

  @override
  String get settingsTitle => '設定';

  @override
  String get regionSettings => '地域設定';

  @override
  String get changeRegion => '地域を変更';

  @override
  String get notificationSettings => '通知設定';

  @override
  String get languageSettings => '言語設定';

  @override
  String get reminderToggle => '収集日前日リマインダー';

  @override
  String get reminderDescription => '収集日前日の18:00に通知します';

  @override
  String get noSearchResults => '該当する品目が見つかりませんでした';

  @override
  String get dataLoadError => 'データの取得に失敗しました';

  @override
  String get regionDataError => '地域データの取得に失敗しました';

  @override
  String get saveError => '保存に失敗しました';

  @override
  String get regionNotSet => '地域が設定されていません';

  @override
  String get dataOutdated => 'データが古い可能性があります。ネットワークに接続してデータを更新してください。';

  @override
  String get noOfflineData => 'データが利用できません。ネットワーク接続が必要です。';

  @override
  String get prefectureNotSelected => '都道府県を選択してください';

  @override
  String get municipalityNotSelected => '市区町村を選択してください';

  @override
  String get districtNotSelected => '地区を選択してください';

  @override
  String get regionSaved => '地域設定を保存しました';

  @override
  String get calendarRegistered => 'カレンダーに登録しました';

  @override
  String get calendarPermissionDenied =>
      'カレンダーへのアクセス権限が必要です。設定画面から権限を許可してください。';

  @override
  String get retry => '再試行';

  @override
  String get back => '戻る';

  @override
  String get openSettings => '設定を開く';

  @override
  String get aiErrorMessage => 'リクエストを完了できませんでした。しばらくしてからお試しください。';

  @override
  String get notificationTomorrowTitle => '明日のゴミ出し';

  @override
  String notificationTomorrowBody(String categories) {
    return '明日は$categoriesの日です';
  }

  @override
  String get notificationTodayTitle => '今日のゴミ出し';

  @override
  String notificationTodayBody(String categories) {
    return '今日は$categoriesの日です';
  }

  @override
  String municipalityRomanization(String japaneseName, String romanizedName) {
    return '$japaneseName（$romanizedName）';
  }

  @override
  String get bulkyWaste => '粗大ごみ';

  @override
  String get regionRequired => '地域設定が必要です';

  @override
  String get searchTip => '捨て方がわからないものを検索';

  @override
  String get searchTipDescription => '品目名を入力すると分別方法がわかります';

  @override
  String get searchByCategory => 'カテゴリから探す';

  @override
  String get searchHistory => '検索履歴';

  @override
  String get deleteAll => 'すべて削除';

  @override
  String get searchResults => '検索結果';

  @override
  String get nextCollectionDates => '次回の収集日';

  @override
  String get today => '今日';

  @override
  String get tomorrow => '明日';

  @override
  String get dayAfterTomorrow => '明後日';

  @override
  String daysRemaining(int days) {
    return 'あと$days日';
  }

  @override
  String collectionDaysFor(String category) {
    return '$categoryの収集日';
  }

  @override
  String get noUpcomingCollections => '今後の収集日が見つかりません';

  @override
  String get selectDate => '日付を選択してください';

  @override
  String get exportCalendar => 'カレンダーをエクスポート';

  @override
  String get categoryShortBurnable => '可燃';

  @override
  String get categoryShortRecyclable => '資源';

  @override
  String get categoryShortPlastic => 'プラ';

  @override
  String get categoryShortPetBottle => 'ペット';

  @override
  String get categoryShortHazardous => '危険';

  @override
  String get account => 'アカウント';

  @override
  String get loggedIn => 'ログイン中';

  @override
  String get changePassword => 'パスワード変更';

  @override
  String get logout => 'ログアウト';

  @override
  String get loginOrRegister => 'ログイン / 新規登録';

  @override
  String get loginSyncMessage => '設定を同期するにはログインしてください';

  @override
  String get currentRegion => '現在の地域';

  @override
  String get detectFromLocation => '現在地から再設定';

  @override
  String get theme => 'テーマ';

  @override
  String get themeSystem => 'システム設定';

  @override
  String get themeLight => 'ライト';

  @override
  String get themeDark => 'ダーク';

  @override
  String get other => 'その他';

  @override
  String get faq => 'よくある質問';

  @override
  String get termsOfService => '利用規約';

  @override
  String get reminderNotificationDescription => '収集日の前日と当日に通知します';

  @override
  String get reminderSettingFailed => 'リマインダーの設定に失敗しました';

  @override
  String get regionSettingUpdated => '地域設定を更新しました';

  @override
  String get cancel => 'キャンセル';

  @override
  String get detectFromGps => '現在地から設定';

  @override
  String get setRegionPrompt => 'お住まいの地域を設定してください';

  @override
  String get regionOptimizationDescription =>
      'ごみの収集日や正しい分別ルールを、お住まいの地域に合わせて最適化します。';

  @override
  String get pleaseSelect => '選択してください';

  @override
  String get settingsCanChangeLater => '設定は後から「設定画面」で変更できます';

  @override
  String get gpsResult => 'GPS判定結果';

  @override
  String get gpsRegionDetected => '以下の地域が検出されました：';

  @override
  String get setThisRegion => 'この地域で設定';

  @override
  String get selectImage => '画像を選択してください';

  @override
  String get takePhoto => 'カメラで撮影';

  @override
  String get chooseFromGallery => 'ギャラリーから選択';

  @override
  String get realtimeCamera => 'リアルタイムカメラ';

  @override
  String get noCameraAvailable => 'このデバイスにはカメラがありません';

  @override
  String get send => '送信';

  @override
  String get redo => 'やり直し';

  @override
  String get uploading => 'アップロード中...';

  @override
  String get uploadComplete => 'アップロードが完了しました';

  @override
  String get imageSentSuccess => '画像が正常に送信されました';

  @override
  String get resend => '再送信';

  @override
  String get errorOccurred => 'エラーが発生しました';

  @override
  String get municipality => '市区町村';

  @override
  String get district => '地区';

  @override
  String get city => '市';

  @override
  String get eveningNotification => '前日通知';

  @override
  String get morningNotification => '当日通知';

  @override
  String get addDistrict => '地区を追加';

  @override
  String get districtListLoadError => '地区リストの読み込みに失敗しました';

  @override
  String get inUse => '使用中';

  @override
  String get deleteDistrict => '地区を削除';

  @override
  String deleteDistrictConfirm(String label) {
    return '「$label」を削除しますか？';
  }

  @override
  String get delete => '削除';

  @override
  String get addDistrictDialogTitle => '地区を追加';

  @override
  String get addDistrictDescription => '新しい地区のラベルを入力してください。\n次に市区町村と地区を選択します。';

  @override
  String get label => 'ラベル';

  @override
  String get labelHint => '例: 職場、実家';

  @override
  String get labelRequired => 'ラベルを入力してください';

  @override
  String get next => '次へ';

  @override
  String get reminderLoadError => 'リマインダー設定の読み込みに失敗しました';

  @override
  String get regionSettingLabel => '地域設定';

  @override
  String districtCount(int count) {
    return '$count/5件';
  }
}
