// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get appName => '爱媛垃圾分类应用';

  @override
  String get categoryBurnable => '可燃垃圾';

  @override
  String get categoryRecyclable => '可回收垃圾';

  @override
  String get categoryPlastic => '塑料容器包装';

  @override
  String get categoryPetBottle => 'PET塑料瓶';

  @override
  String get categoryHazardous => '危险垃圾';

  @override
  String get tabSearch => '搜索';

  @override
  String get tabCalendar => '日历';

  @override
  String get tabSettings => '设置';

  @override
  String get tabImageInput => '图片输入';

  @override
  String get regionSelectionTitle => '选择地区';

  @override
  String get selectPrefecture => '选择都道府县';

  @override
  String get selectMunicipality => '选择市区町村';

  @override
  String get selectDistrict => '选择地区';

  @override
  String get startWithRegion => '使用此地区开始';

  @override
  String get searchTitle => '搜索垃圾物品';

  @override
  String get searchHint => '输入物品名称（2个字符以上）';

  @override
  String get popularItems => '热门搜索物品';

  @override
  String get multipleItemsFound => '找到多个相似物品';

  @override
  String get multipleCategoriesNote => '或因物品而异';

  @override
  String get itemDetailTitle => '物品详情';

  @override
  String get nextCollectionDate => '下次收集日期';

  @override
  String get disposalMethod => '丢弃方法';

  @override
  String get caution => '注意事项';

  @override
  String get registerToCalendar => '添加到日历';

  @override
  String get calendarTitle => '收集日历';

  @override
  String get nextCollection => '下次收集';

  @override
  String get noSchedule => '当天没有收集安排';

  @override
  String get colorLegend => '颜色图例';

  @override
  String get settingsTitle => '设置';

  @override
  String get regionSettings => '地区设置';

  @override
  String get changeRegion => '更改地区';

  @override
  String get notificationSettings => '通知设置';

  @override
  String get languageSettings => '语言';

  @override
  String get reminderToggle => '收集前一天提醒';

  @override
  String get reminderDescription => '在收集前一天18:00发送通知';

  @override
  String get noSearchResults => '未找到匹配的物品';

  @override
  String get dataLoadError => '数据加载失败';

  @override
  String get regionDataError => '地区数据加载失败';

  @override
  String get saveError => '保存失败';

  @override
  String get regionNotSet => '未设置地区';

  @override
  String get dataOutdated => '数据可能已过期。请连接网络进行更新。';

  @override
  String get noOfflineData => '数据不可用。需要网络连接。';

  @override
  String get prefectureNotSelected => '请选择都道府县';

  @override
  String get municipalityNotSelected => '请选择市区町村';

  @override
  String get districtNotSelected => '请选择地区';

  @override
  String get regionSaved => '地区设置已保存';

  @override
  String get calendarRegistered => '已添加到日历';

  @override
  String get calendarPermissionDenied => '需要日历访问权限。请在设备设置中允许访问。';

  @override
  String get retry => '重试';

  @override
  String get back => '返回';

  @override
  String get openSettings => '打开设置';

  @override
  String get aiErrorMessage => '无法完成请求。请稍后再试。';

  @override
  String get aiBannerText => 'AI为您解答问题';

  @override
  String get aiAssistantTitle => 'AI助手';

  @override
  String get aiEmptyStateText => '关于垃圾分类\n请随时提问！';

  @override
  String get aiInputHint => '输入问题...';

  @override
  String get aiNoResponse => 'AI没有返回回答。';

  @override
  String get aiValidationError => '请输入问题。';

  @override
  String get aiTimeoutError => '请求超时。请稍后再试。';

  @override
  String get aiServiceUnavailable => 'AI服务不可用。请稍后再试。';

  @override
  String get aiGenericError => '发生错误。请稍后再试。';

  @override
  String get aiNetworkError => '网络错误。请检查网络连接。';

  @override
  String get notificationTomorrowTitle => '明天的垃圾';

  @override
  String notificationTomorrowBody(String categories) {
    return '明天是$categories的收集日';
  }

  @override
  String get notificationTodayTitle => '今天的垃圾';

  @override
  String notificationTodayBody(String categories) {
    return '今天是$categories的收集日';
  }

  @override
  String municipalityRomanization(String japaneseName, String romanizedName) {
    return '$japaneseName（$romanizedName）';
  }

  @override
  String get bulkyWaste => '大件垃圾';

  @override
  String get regionRequired => '需要设置地区';

  @override
  String get searchTip => '搜索不知道如何丢弃的物品';

  @override
  String get searchTipDescription => '输入物品名称即可了解分类方法';

  @override
  String get searchByCategory => '按类别搜索';

  @override
  String get searchHistory => '搜索历史';

  @override
  String get deleteAll => '全部删除';

  @override
  String get searchResults => '搜索结果';

  @override
  String get nextCollectionDates => '下次收集日期';

  @override
  String get today => '今天';

  @override
  String get tomorrow => '明天';

  @override
  String get dayAfterTomorrow => '后天';

  @override
  String daysRemaining(int days) {
    return '还剩$days天';
  }

  @override
  String collectionDaysFor(String category) {
    return '$category收集日';
  }

  @override
  String get noUpcomingCollections => '未找到今后的收集日期';

  @override
  String get selectDate => '请选择日期';

  @override
  String get exportCalendar => '导出日历';

  @override
  String get categoryShortBurnable => '可燃';

  @override
  String get categoryShortRecyclable => '资源';

  @override
  String get categoryShortPlastic => '塑料';

  @override
  String get categoryShortPetBottle => 'PET';

  @override
  String get categoryShortHazardous => '危险';

  @override
  String get account => '账户';

  @override
  String get loggedIn => '已登录';

  @override
  String get changePassword => '修改密码';

  @override
  String get logout => '退出登录';

  @override
  String get loginOrRegister => '登录 / 注册';

  @override
  String get loginSyncMessage => '登录以同步您的设置';

  @override
  String get currentRegion => '当前地区';

  @override
  String get detectFromLocation => '从当前位置重新检测';

  @override
  String get theme => '主题';

  @override
  String get themeSystem => '跟随系统';

  @override
  String get themeLight => '浅色';

  @override
  String get themeDark => '深色';

  @override
  String get other => '其他';

  @override
  String get faq => '常见问题';

  @override
  String get termsOfService => '服务条款';

  @override
  String get reminderNotificationDescription => '在收集前一天和当天发送通知';

  @override
  String get reminderSettingFailed => '提醒设置失败';

  @override
  String get regionSettingUpdated => '地区设置已更新';

  @override
  String get cancel => '取消';

  @override
  String get detectFromGps => '从当前位置检测';

  @override
  String get setRegionPrompt => '请设置您的居住区域';

  @override
  String get regionOptimizationDescription => '根据您的区域优化垃圾收集日期和分类规则。';

  @override
  String get pleaseSelect => '请选择';

  @override
  String get settingsCanChangeLater => '稍后可以在设置页面中更改设置';

  @override
  String get gpsResult => 'GPS检测结果';

  @override
  String get gpsRegionDetected => '检测到以下地区：';

  @override
  String get setThisRegion => '使用此地区';

  @override
  String get selectImage => '请选择图片';

  @override
  String get takePhoto => '拍照';

  @override
  String get chooseFromGallery => '从相册选择';

  @override
  String get realtimeCamera => '实时相机';

  @override
  String get noCameraAvailable => '此设备没有可用的相机';

  @override
  String get send => '发送';

  @override
  String get redo => '重做';

  @override
  String get uploading => '上传中...';

  @override
  String get uploadComplete => '上传完成';

  @override
  String get imageSentSuccess => '图片发送成功';

  @override
  String get resend => '重新发送';

  @override
  String get errorOccurred => '发生错误';

  @override
  String get municipality => '市区町村';

  @override
  String get district => '地区';

  @override
  String get city => '市';

  @override
  String get eveningNotification => '前一天通知';

  @override
  String get morningNotification => '当天通知';

  @override
  String get addDistrict => '添加地区';

  @override
  String get districtListLoadError => '地区列表加载失败';

  @override
  String get inUse => '使用中';

  @override
  String get deleteDistrict => '删除地区';

  @override
  String deleteDistrictConfirm(String label) {
    return '删除「$label」吗？';
  }

  @override
  String get delete => '删除';

  @override
  String get addDistrictDialogTitle => '添加地区';

  @override
  String get addDistrictDescription => '请输入新地区的标签。\n然后选择市区町村和地区。';

  @override
  String get label => '标签';

  @override
  String get labelHint => '例：工作地点、老家';

  @override
  String get labelRequired => '请输入标签';

  @override
  String get next => '下一步';

  @override
  String get reminderLoadError => '提醒设置加载失败';

  @override
  String get regionSettingLabel => '地区设置';

  @override
  String districtCount(int count) {
    return '$count/5个';
  }
}
