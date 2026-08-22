import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_ja.dart';
import 'app_localizations_pt.dart';
import 'app_localizations_vi.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('ja'),
    Locale('pt'),
    Locale('vi'),
    Locale('zh')
  ];

  /// アプリ名
  ///
  /// In ja, this message translates to:
  /// **'愛媛ゴミ出しアプリ'**
  String get appName;

  /// ゴミカテゴリ：可燃ごみ
  ///
  /// In ja, this message translates to:
  /// **'可燃ごみ'**
  String get categoryBurnable;

  /// ゴミカテゴリ：資源ごみ
  ///
  /// In ja, this message translates to:
  /// **'資源ごみ'**
  String get categoryRecyclable;

  /// ゴミカテゴリ：プラスチック製容器包装
  ///
  /// In ja, this message translates to:
  /// **'プラスチック製容器包装'**
  String get categoryPlastic;

  /// ゴミカテゴリ：ペットボトル
  ///
  /// In ja, this message translates to:
  /// **'ペットボトル'**
  String get categoryPetBottle;

  /// ゴミカテゴリ：危険ごみ
  ///
  /// In ja, this message translates to:
  /// **'危険ごみ'**
  String get categoryHazardous;

  /// 検索タブラベル
  ///
  /// In ja, this message translates to:
  /// **'検索'**
  String get tabSearch;

  /// カレンダータブラベル
  ///
  /// In ja, this message translates to:
  /// **'カレンダー'**
  String get tabCalendar;

  /// 設定タブラベル
  ///
  /// In ja, this message translates to:
  /// **'設定'**
  String get tabSettings;

  /// 画像入力タブラベル
  ///
  /// In ja, this message translates to:
  /// **'画像入力'**
  String get tabImageInput;

  /// 地域選択画面タイトル
  ///
  /// In ja, this message translates to:
  /// **'地域を選択'**
  String get regionSelectionTitle;

  /// 都道府県選択ステップ
  ///
  /// In ja, this message translates to:
  /// **'都道府県を選択'**
  String get selectPrefecture;

  /// 市区町村選択ステップ
  ///
  /// In ja, this message translates to:
  /// **'市区町村を選択'**
  String get selectMunicipality;

  /// 地区選択ステップ
  ///
  /// In ja, this message translates to:
  /// **'地区を選択'**
  String get selectDistrict;

  /// 地域設定完了ボタン
  ///
  /// In ja, this message translates to:
  /// **'この地域で始める'**
  String get startWithRegion;

  /// 検索画面タイトル
  ///
  /// In ja, this message translates to:
  /// **'ゴミ品目検索'**
  String get searchTitle;

  /// 検索ヒント
  ///
  /// In ja, this message translates to:
  /// **'品目名を入力（2文字以上）'**
  String get searchHint;

  /// よく検索される品目セクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'よく検索される品目'**
  String get popularItems;

  /// 複数品目該当メッセージ
  ///
  /// In ja, this message translates to:
  /// **'近い品目が複数見つかりました'**
  String get multipleItemsFound;

  /// 複数カテゴリ該当補足
  ///
  /// In ja, this message translates to:
  /// **'または品目により異なる'**
  String get multipleCategoriesNote;

  /// 品目詳細画面タイトル
  ///
  /// In ja, this message translates to:
  /// **'品目詳細'**
  String get itemDetailTitle;

  /// 次回収集日ラベル
  ///
  /// In ja, this message translates to:
  /// **'次回収集日'**
  String get nextCollectionDate;

  /// 出し方ラベル
  ///
  /// In ja, this message translates to:
  /// **'出し方'**
  String get disposalMethod;

  /// 注意事項ラベル
  ///
  /// In ja, this message translates to:
  /// **'注意事項'**
  String get caution;

  /// カレンダーに登録ボタン
  ///
  /// In ja, this message translates to:
  /// **'カレンダーに登録'**
  String get registerToCalendar;

  /// カレンダー画面タイトル
  ///
  /// In ja, this message translates to:
  /// **'収集カレンダー'**
  String get calendarTitle;

  /// 次回収集予定バナー
  ///
  /// In ja, this message translates to:
  /// **'次回の収集'**
  String get nextCollection;

  /// 収集予定なしメッセージ
  ///
  /// In ja, this message translates to:
  /// **'この日の収集予定はありません'**
  String get noSchedule;

  /// 色凡例タイトル
  ///
  /// In ja, this message translates to:
  /// **'色凡例'**
  String get colorLegend;

  /// 設定画面タイトル
  ///
  /// In ja, this message translates to:
  /// **'設定'**
  String get settingsTitle;

  /// 地域設定セクション
  ///
  /// In ja, this message translates to:
  /// **'地域設定'**
  String get regionSettings;

  /// 地域変更ボタン
  ///
  /// In ja, this message translates to:
  /// **'地域を変更'**
  String get changeRegion;

  /// 通知設定セクション
  ///
  /// In ja, this message translates to:
  /// **'通知設定'**
  String get notificationSettings;

  /// 言語設定セクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'言語設定'**
  String get languageSettings;

  /// リマインダートグルラベル
  ///
  /// In ja, this message translates to:
  /// **'収集日前日リマインダー'**
  String get reminderToggle;

  /// リマインダー説明
  ///
  /// In ja, this message translates to:
  /// **'収集日前日の18:00に通知します'**
  String get reminderDescription;

  /// 検索結果なしメッセージ
  ///
  /// In ja, this message translates to:
  /// **'該当する品目が見つかりませんでした'**
  String get noSearchResults;

  /// データ取得失敗メッセージ
  ///
  /// In ja, this message translates to:
  /// **'データの取得に失敗しました'**
  String get dataLoadError;

  /// 地域データ取得失敗メッセージ
  ///
  /// In ja, this message translates to:
  /// **'地域データの取得に失敗しました'**
  String get regionDataError;

  /// 保存失敗メッセージ
  ///
  /// In ja, this message translates to:
  /// **'保存に失敗しました'**
  String get saveError;

  /// 地域未設定メッセージ
  ///
  /// In ja, this message translates to:
  /// **'地域が設定されていません'**
  String get regionNotSet;

  /// データ古い通知メッセージ
  ///
  /// In ja, this message translates to:
  /// **'データが古い可能性があります。ネットワークに接続してデータを更新してください。'**
  String get dataOutdated;

  /// オフラインデータなしメッセージ
  ///
  /// In ja, this message translates to:
  /// **'データが利用できません。ネットワーク接続が必要です。'**
  String get noOfflineData;

  /// 都道府県未選択バリデーション
  ///
  /// In ja, this message translates to:
  /// **'都道府県を選択してください'**
  String get prefectureNotSelected;

  /// 市区町村未選択バリデーション
  ///
  /// In ja, this message translates to:
  /// **'市区町村を選択してください'**
  String get municipalityNotSelected;

  /// 地区未選択バリデーション
  ///
  /// In ja, this message translates to:
  /// **'地区を選択してください'**
  String get districtNotSelected;

  /// 地域設定保存完了メッセージ
  ///
  /// In ja, this message translates to:
  /// **'地域設定を保存しました'**
  String get regionSaved;

  /// カレンダー登録完了メッセージ
  ///
  /// In ja, this message translates to:
  /// **'カレンダーに登録しました'**
  String get calendarRegistered;

  /// カレンダー権限エラーメッセージ
  ///
  /// In ja, this message translates to:
  /// **'カレンダーへのアクセス権限が必要です。設定画面から権限を許可してください。'**
  String get calendarPermissionDenied;

  /// 再試行ボタンラベル
  ///
  /// In ja, this message translates to:
  /// **'再試行'**
  String get retry;

  /// 戻るボタンラベル
  ///
  /// In ja, this message translates to:
  /// **'戻る'**
  String get back;

  /// 設定を開くボタンラベル
  ///
  /// In ja, this message translates to:
  /// **'設定を開く'**
  String get openSettings;

  /// AIチャットエラーメッセージ
  ///
  /// In ja, this message translates to:
  /// **'リクエストを完了できませんでした。しばらくしてからお試しください。'**
  String get aiErrorMessage;

  /// 明日の収集リマインダー通知タイトル
  ///
  /// In ja, this message translates to:
  /// **'明日のゴミ出し'**
  String get notificationTomorrowTitle;

  /// 明日の収集リマインダー通知本文
  ///
  /// In ja, this message translates to:
  /// **'明日は{categories}の日です'**
  String notificationTomorrowBody(String categories);

  /// 今日の収集リマインダー通知タイトル
  ///
  /// In ja, this message translates to:
  /// **'今日のゴミ出し'**
  String get notificationTodayTitle;

  /// 今日の収集リマインダー通知本文
  ///
  /// In ja, this message translates to:
  /// **'今日は{categories}の日です'**
  String notificationTodayBody(String categories);

  /// 自治体名ローマ字表示テンプレート
  ///
  /// In ja, this message translates to:
  /// **'{japaneseName}（{romanizedName}）'**
  String municipalityRomanization(String japaneseName, String romanizedName);

  /// 粗大ごみFABラベル
  ///
  /// In ja, this message translates to:
  /// **'粗大ごみ'**
  String get bulkyWaste;

  /// 地域未設定時のスナックバーメッセージ
  ///
  /// In ja, this message translates to:
  /// **'地域設定が必要です'**
  String get regionRequired;

  /// 検索ヒントカードタイトル
  ///
  /// In ja, this message translates to:
  /// **'捨て方がわからないものを検索'**
  String get searchTip;

  /// 検索ヒントカード説明
  ///
  /// In ja, this message translates to:
  /// **'品目名を入力すると分別方法がわかります'**
  String get searchTipDescription;

  /// カテゴリ別クイック検索セクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'カテゴリから探す'**
  String get searchByCategory;

  /// 検索履歴セクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'検索履歴'**
  String get searchHistory;

  /// 全件削除ボタン
  ///
  /// In ja, this message translates to:
  /// **'すべて削除'**
  String get deleteAll;

  /// 検索結果ラベル
  ///
  /// In ja, this message translates to:
  /// **'検索結果'**
  String get searchResults;

  /// カテゴリ別次回収集日セクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'次回の収集日'**
  String get nextCollectionDates;

  /// 今日ラベル
  ///
  /// In ja, this message translates to:
  /// **'今日'**
  String get today;

  /// 明日ラベル
  ///
  /// In ja, this message translates to:
  /// **'明日'**
  String get tomorrow;

  /// 明後日ラベル
  ///
  /// In ja, this message translates to:
  /// **'明後日'**
  String get dayAfterTomorrow;

  /// 残り日数表示
  ///
  /// In ja, this message translates to:
  /// **'あと{days}日'**
  String daysRemaining(int days);

  /// 指定カテゴリの収集日シートタイトル
  ///
  /// In ja, this message translates to:
  /// **'{category}の収集日'**
  String collectionDaysFor(String category);

  /// 今後の収集日なしメッセージ
  ///
  /// In ja, this message translates to:
  /// **'今後の収集日が見つかりません'**
  String get noUpcomingCollections;

  /// 日付選択プロンプト
  ///
  /// In ja, this message translates to:
  /// **'日付を選択してください'**
  String get selectDate;

  /// カレンダーエクスポートツールチップ
  ///
  /// In ja, this message translates to:
  /// **'カレンダーをエクスポート'**
  String get exportCalendar;

  /// 可燃ごみカテゴリ短縮名
  ///
  /// In ja, this message translates to:
  /// **'可燃'**
  String get categoryShortBurnable;

  /// 資源ごみカテゴリ短縮名
  ///
  /// In ja, this message translates to:
  /// **'資源'**
  String get categoryShortRecyclable;

  /// プラスチックカテゴリ短縮名
  ///
  /// In ja, this message translates to:
  /// **'プラ'**
  String get categoryShortPlastic;

  /// ペットボトルカテゴリ短縮名
  ///
  /// In ja, this message translates to:
  /// **'ペット'**
  String get categoryShortPetBottle;

  /// 危険ごみカテゴリ短縮名
  ///
  /// In ja, this message translates to:
  /// **'危険'**
  String get categoryShortHazardous;

  /// アカウントセクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'アカウント'**
  String get account;

  /// ログイン状態ラベル
  ///
  /// In ja, this message translates to:
  /// **'ログイン中'**
  String get loggedIn;

  /// パスワード変更ボタン
  ///
  /// In ja, this message translates to:
  /// **'パスワード変更'**
  String get changePassword;

  /// ログアウトボタン
  ///
  /// In ja, this message translates to:
  /// **'ログアウト'**
  String get logout;

  /// ログイン/登録ボタン
  ///
  /// In ja, this message translates to:
  /// **'ログイン / 新規登録'**
  String get loginOrRegister;

  /// ログイン同期説明
  ///
  /// In ja, this message translates to:
  /// **'設定を同期するにはログインしてください'**
  String get loginSyncMessage;

  /// 現在の地域セクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'現在の地域'**
  String get currentRegion;

  /// GPS位置情報から地域を再設定するボタン
  ///
  /// In ja, this message translates to:
  /// **'現在地から再設定'**
  String get detectFromLocation;

  /// テーマセクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'テーマ'**
  String get theme;

  /// システムテーマオプション
  ///
  /// In ja, this message translates to:
  /// **'システム設定'**
  String get themeSystem;

  /// ライトテーマオプション
  ///
  /// In ja, this message translates to:
  /// **'ライト'**
  String get themeLight;

  /// ダークテーマオプション
  ///
  /// In ja, this message translates to:
  /// **'ダーク'**
  String get themeDark;

  /// その他セクションタイトル
  ///
  /// In ja, this message translates to:
  /// **'その他'**
  String get other;

  /// よくある質問リンク
  ///
  /// In ja, this message translates to:
  /// **'よくある質問'**
  String get faq;

  /// 利用規約リンク
  ///
  /// In ja, this message translates to:
  /// **'利用規約'**
  String get termsOfService;

  /// リマインダー通知の説明
  ///
  /// In ja, this message translates to:
  /// **'収集日の前日と当日に通知します'**
  String get reminderNotificationDescription;

  /// リマインダー設定失敗メッセージ
  ///
  /// In ja, this message translates to:
  /// **'リマインダーの設定に失敗しました'**
  String get reminderSettingFailed;

  /// 地域設定更新完了メッセージ
  ///
  /// In ja, this message translates to:
  /// **'地域設定を更新しました'**
  String get regionSettingUpdated;

  /// キャンセルボタン
  ///
  /// In ja, this message translates to:
  /// **'キャンセル'**
  String get cancel;

  /// GPS位置情報検出ボタン
  ///
  /// In ja, this message translates to:
  /// **'現在地から設定'**
  String get detectFromGps;

  /// 地域設定プロンプトメッセージ
  ///
  /// In ja, this message translates to:
  /// **'お住まいの地域を設定してください'**
  String get setRegionPrompt;

  /// 地域最適化の説明
  ///
  /// In ja, this message translates to:
  /// **'ごみの収集日や正しい分別ルールを、お住まいの地域に合わせて最適化します。'**
  String get regionOptimizationDescription;

  /// 選択を促すプレースホルダー
  ///
  /// In ja, this message translates to:
  /// **'選択してください'**
  String get pleaseSelect;

  /// 設定変更可能の注記
  ///
  /// In ja, this message translates to:
  /// **'設定は後から「設定画面」で変更できます'**
  String get settingsCanChangeLater;

  /// GPS判定結果ダイアログタイトル
  ///
  /// In ja, this message translates to:
  /// **'GPS判定結果'**
  String get gpsResult;

  /// GPS検出結果の説明
  ///
  /// In ja, this message translates to:
  /// **'以下の地域が検出されました：'**
  String get gpsRegionDetected;

  /// GPS検出地域で設定するボタン
  ///
  /// In ja, this message translates to:
  /// **'この地域で設定'**
  String get setThisRegion;

  /// 画像選択プロンプト
  ///
  /// In ja, this message translates to:
  /// **'画像を選択してください'**
  String get selectImage;

  /// カメラ撮影ボタン
  ///
  /// In ja, this message translates to:
  /// **'カメラで撮影'**
  String get takePhoto;

  /// ギャラリー選択ボタン
  ///
  /// In ja, this message translates to:
  /// **'ギャラリーから選択'**
  String get chooseFromGallery;

  /// リアルタイムカメラボタン
  ///
  /// In ja, this message translates to:
  /// **'リアルタイムカメラ'**
  String get realtimeCamera;

  /// カメラ非搭載メッセージ
  ///
  /// In ja, this message translates to:
  /// **'このデバイスにはカメラがありません'**
  String get noCameraAvailable;

  /// 送信ボタン
  ///
  /// In ja, this message translates to:
  /// **'送信'**
  String get send;

  /// やり直しボタン
  ///
  /// In ja, this message translates to:
  /// **'やり直し'**
  String get redo;

  /// アップロード中メッセージ
  ///
  /// In ja, this message translates to:
  /// **'アップロード中...'**
  String get uploading;

  /// アップロード完了メッセージ
  ///
  /// In ja, this message translates to:
  /// **'アップロードが完了しました'**
  String get uploadComplete;

  /// 画像送信成功メッセージ
  ///
  /// In ja, this message translates to:
  /// **'画像が正常に送信されました'**
  String get imageSentSuccess;

  /// 再送信ボタン
  ///
  /// In ja, this message translates to:
  /// **'再送信'**
  String get resend;

  /// 一般エラーメッセージ
  ///
  /// In ja, this message translates to:
  /// **'エラーが発生しました'**
  String get errorOccurred;

  /// 市区町村ラベル
  ///
  /// In ja, this message translates to:
  /// **'市区町村'**
  String get municipality;

  /// 地区ラベル
  ///
  /// In ja, this message translates to:
  /// **'地区'**
  String get district;

  /// 市ラベル
  ///
  /// In ja, this message translates to:
  /// **'市'**
  String get city;

  /// 前日通知時刻設定ラベル
  ///
  /// In ja, this message translates to:
  /// **'前日通知'**
  String get eveningNotification;

  /// 当日通知時刻設定ラベル
  ///
  /// In ja, this message translates to:
  /// **'当日通知'**
  String get morningNotification;

  /// 地区追加ボタン
  ///
  /// In ja, this message translates to:
  /// **'地区を追加'**
  String get addDistrict;

  /// 地区リスト読み込み失敗メッセージ
  ///
  /// In ja, this message translates to:
  /// **'地区リストの読み込みに失敗しました'**
  String get districtListLoadError;

  /// 使用中チップラベル
  ///
  /// In ja, this message translates to:
  /// **'使用中'**
  String get inUse;

  /// 地区削除ダイアログタイトル
  ///
  /// In ja, this message translates to:
  /// **'地区を削除'**
  String get deleteDistrict;

  /// 地区削除確認メッセージ
  ///
  /// In ja, this message translates to:
  /// **'「{label}」を削除しますか？'**
  String deleteDistrictConfirm(String label);

  /// 削除ボタン
  ///
  /// In ja, this message translates to:
  /// **'削除'**
  String get delete;

  /// 地区追加ダイアログタイトル
  ///
  /// In ja, this message translates to:
  /// **'地区を追加'**
  String get addDistrictDialogTitle;

  /// 地区追加ダイアログ説明
  ///
  /// In ja, this message translates to:
  /// **'新しい地区のラベルを入力してください。\n次に市区町村と地区を選択します。'**
  String get addDistrictDescription;

  /// ラベル入力フィールド
  ///
  /// In ja, this message translates to:
  /// **'ラベル'**
  String get label;

  /// ラベル入力ヒント
  ///
  /// In ja, this message translates to:
  /// **'例: 職場、実家'**
  String get labelHint;

  /// ラベル必須バリデーション
  ///
  /// In ja, this message translates to:
  /// **'ラベルを入力してください'**
  String get labelRequired;

  /// 次へボタン
  ///
  /// In ja, this message translates to:
  /// **'次へ'**
  String get next;

  /// リマインダー設定読み込み失敗メッセージ
  ///
  /// In ja, this message translates to:
  /// **'リマインダー設定の読み込みに失敗しました'**
  String get reminderLoadError;

  /// 地域設定AppBarタイトル
  ///
  /// In ja, this message translates to:
  /// **'地域設定'**
  String get regionSettingLabel;

  /// 地区カウント表示
  ///
  /// In ja, this message translates to:
  /// **'{count}/5件'**
  String districtCount(int count);
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'ja', 'pt', 'vi', 'zh'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'ja':
      return AppLocalizationsJa();
    case 'pt':
      return AppLocalizationsPt();
    case 'vi':
      return AppLocalizationsVi();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
