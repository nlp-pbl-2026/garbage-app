// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Vietnamese (`vi`).
class AppLocalizationsVi extends AppLocalizations {
  AppLocalizationsVi([String locale = 'vi']) : super(locale);

  @override
  String get appName => 'Ứng dụng Rác Ehime';

  @override
  String get categoryBurnable => 'Rác đốt được';

  @override
  String get categoryRecyclable => 'Rác tái chế';

  @override
  String get categoryPlastic => 'Bao bì nhựa';

  @override
  String get categoryPetBottle => 'Chai PET';

  @override
  String get categoryHazardous => 'Rác nguy hại';

  @override
  String get tabSearch => 'Tìm kiếm';

  @override
  String get tabCalendar => 'Lịch';

  @override
  String get tabSettings => 'Cài đặt';

  @override
  String get tabImageInput => 'Hình ảnh';

  @override
  String get regionSelectionTitle => 'Chọn Khu vực';

  @override
  String get selectPrefecture => 'Chọn Tỉnh';

  @override
  String get selectMunicipality => 'Chọn Thành phố/Quận';

  @override
  String get selectDistrict => 'Chọn Phường/Xã';

  @override
  String get startWithRegion => 'Bắt đầu với khu vực này';

  @override
  String get searchTitle => 'Tìm kiếm Vật phẩm Rác';

  @override
  String get searchHint => 'Nhập tên vật phẩm (2 ký tự trở lên)';

  @override
  String get popularItems => 'Vật phẩm Tìm kiếm Nhiều';

  @override
  String get multipleItemsFound => 'Tìm thấy nhiều vật phẩm tương tự';

  @override
  String get multipleCategoriesNote => 'Hoặc khác nhau tùy vật phẩm';

  @override
  String get itemDetailTitle => 'Chi tiết Vật phẩm';

  @override
  String get nextCollectionDate => 'Ngày Thu gom Tiếp theo';

  @override
  String get disposalMethod => 'Cách Vứt bỏ';

  @override
  String get caution => 'Lưu ý';

  @override
  String get registerToCalendar => 'Thêm vào Lịch';

  @override
  String get calendarTitle => 'Lịch Thu gom';

  @override
  String get nextCollection => 'Thu gom Tiếp theo';

  @override
  String get noSchedule => 'Không có lịch thu gom cho ngày này';

  @override
  String get colorLegend => 'Chú giải Màu sắc';

  @override
  String get settingsTitle => 'Cài đặt';

  @override
  String get regionSettings => 'Cài đặt Khu vực';

  @override
  String get changeRegion => 'Thay đổi Khu vực';

  @override
  String get notificationSettings => 'Cài đặt Thông báo';

  @override
  String get languageSettings => 'Ngôn ngữ';

  @override
  String get reminderToggle => 'Nhắc nhở trước ngày thu gom';

  @override
  String get reminderDescription =>
      'Thông báo lúc 18:00 ngày trước ngày thu gom';

  @override
  String get noSearchResults => 'Không tìm thấy vật phẩm phù hợp';

  @override
  String get dataLoadError => 'Không thể tải dữ liệu';

  @override
  String get regionDataError => 'Không thể tải dữ liệu khu vực';

  @override
  String get saveError => 'Không thể lưu';

  @override
  String get regionNotSet => 'Chưa thiết lập khu vực';

  @override
  String get dataOutdated =>
      'Dữ liệu có thể đã cũ. Vui lòng kết nối mạng để cập nhật.';

  @override
  String get noOfflineData => 'Dữ liệu không khả dụng. Cần kết nối mạng.';

  @override
  String get prefectureNotSelected => 'Vui lòng chọn tỉnh';

  @override
  String get municipalityNotSelected => 'Vui lòng chọn thành phố/quận';

  @override
  String get districtNotSelected => 'Vui lòng chọn phường/xã';

  @override
  String get regionSaved => 'Đã lưu cài đặt khu vực';

  @override
  String get calendarRegistered => 'Đã thêm vào lịch';

  @override
  String get calendarPermissionDenied =>
      'Cần quyền truy cập lịch. Vui lòng cho phép truy cập trong cài đặt thiết bị.';

  @override
  String get retry => 'Thử lại';

  @override
  String get back => 'Quay lại';

  @override
  String get openSettings => 'Mở Cài đặt';

  @override
  String get aiErrorMessage =>
      'Không thể hoàn thành yêu cầu. Vui lòng thử lại sau.';

  @override
  String get notificationTomorrowTitle => 'Rác Ngày mai';

  @override
  String notificationTomorrowBody(String categories) {
    return 'Ngày mai là ngày thu gom $categories';
  }

  @override
  String get notificationTodayTitle => 'Rác Hôm nay';

  @override
  String notificationTodayBody(String categories) {
    return 'Hôm nay là ngày thu gom $categories';
  }

  @override
  String municipalityRomanization(String japaneseName, String romanizedName) {
    return '$japaneseName ($romanizedName)';
  }

  @override
  String get bulkyWaste => 'Rác cồng kềnh';

  @override
  String get regionRequired => 'Cần thiết lập khu vực';

  @override
  String get searchTip => 'Tìm kiếm các vật phẩm bạn không biết cách vứt bỏ';

  @override
  String get searchTipDescription => 'Nhập tên vật phẩm để biết cách phân loại';

  @override
  String get searchByCategory => 'Tìm theo Danh mục';

  @override
  String get searchHistory => 'Lịch sử Tìm kiếm';

  @override
  String get deleteAll => 'Xóa Tất cả';

  @override
  String get searchResults => 'Kết quả Tìm kiếm';

  @override
  String get nextCollectionDates => 'Ngày Thu gom Tiếp theo';

  @override
  String get today => 'Hôm nay';

  @override
  String get tomorrow => 'Ngày mai';

  @override
  String get dayAfterTomorrow => 'Ngày kia';

  @override
  String daysRemaining(int days) {
    return 'Còn $days ngày';
  }

  @override
  String collectionDaysFor(String category) {
    return 'Ngày Thu gom $category';
  }

  @override
  String get noUpcomingCollections => 'Không tìm thấy ngày thu gom sắp tới';

  @override
  String get selectDate => 'Vui lòng chọn ngày';

  @override
  String get exportCalendar => 'Xuất Lịch';

  @override
  String get categoryShortBurnable => 'Đốt';

  @override
  String get categoryShortRecyclable => 'Tái chế';

  @override
  String get categoryShortPlastic => 'Nhựa';

  @override
  String get categoryShortPetBottle => 'PET';

  @override
  String get categoryShortHazardous => 'Nguy hại';

  @override
  String get account => 'Tài khoản';

  @override
  String get loggedIn => 'Đã đăng nhập';

  @override
  String get changePassword => 'Đổi Mật khẩu';

  @override
  String get logout => 'Đăng xuất';

  @override
  String get loginOrRegister => 'Đăng nhập / Đăng ký';

  @override
  String get loginSyncMessage => 'Đăng nhập để đồng bộ cài đặt';

  @override
  String get currentRegion => 'Khu vực Hiện tại';

  @override
  String get detectFromLocation => 'Phát hiện lại từ vị trí hiện tại';

  @override
  String get theme => 'Giao diện';

  @override
  String get themeSystem => 'Hệ thống';

  @override
  String get themeLight => 'Sáng';

  @override
  String get themeDark => 'Tối';

  @override
  String get other => 'Khác';

  @override
  String get faq => 'Câu hỏi Thường gặp';

  @override
  String get termsOfService => 'Điều khoản Dịch vụ';

  @override
  String get reminderNotificationDescription =>
      'Thông báo vào ngày trước và ngày thu gom';

  @override
  String get reminderSettingFailed => 'Không thể cài đặt nhắc nhở';

  @override
  String get regionSettingUpdated => 'Đã cập nhật cài đặt khu vực';

  @override
  String get cancel => 'Hủy';

  @override
  String get detectFromGps => 'Phát hiện từ vị trí hiện tại';

  @override
  String get setRegionPrompt => 'Vui lòng thiết lập khu vực cư trú';

  @override
  String get regionOptimizationDescription =>
      'Tối ưu hóa lịch thu gom và quy tắc phân loại cho khu vực của bạn.';

  @override
  String get pleaseSelect => 'Vui lòng chọn';

  @override
  String get settingsCanChangeLater =>
      'Bạn có thể thay đổi cài đặt sau trong màn hình Cài đặt';

  @override
  String get gpsResult => 'Kết quả Phát hiện GPS';

  @override
  String get gpsRegionDetected => 'Khu vực sau đã được phát hiện:';

  @override
  String get setThisRegion => 'Sử dụng khu vực này';

  @override
  String get selectImage => 'Vui lòng chọn hình ảnh';

  @override
  String get takePhoto => 'Chụp ảnh';

  @override
  String get chooseFromGallery => 'Chọn từ Thư viện';

  @override
  String get realtimeCamera => 'Camera Thời gian thực';

  @override
  String get noCameraAvailable => 'Thiết bị này không có camera';

  @override
  String get send => 'Gửi';

  @override
  String get redo => 'Làm lại';

  @override
  String get uploading => 'Đang tải lên...';

  @override
  String get uploadComplete => 'Tải lên hoàn tất';

  @override
  String get imageSentSuccess => 'Hình ảnh đã gửi thành công';

  @override
  String get resend => 'Gửi lại';

  @override
  String get errorOccurred => 'Đã xảy ra lỗi';

  @override
  String get municipality => 'Thành phố/Quận';

  @override
  String get district => 'Phường/Xã';

  @override
  String get city => 'Thành phố';

  @override
  String get eveningNotification => 'Thông báo tối';

  @override
  String get morningNotification => 'Thông báo sáng';

  @override
  String get addDistrict => 'Thêm Khu vực';

  @override
  String get districtListLoadError => 'Không thể tải danh sách khu vực';

  @override
  String get inUse => 'Đang dùng';

  @override
  String get deleteDistrict => 'Xóa Khu vực';

  @override
  String deleteDistrictConfirm(String label) {
    return 'Xóa \"$label\"?';
  }

  @override
  String get delete => 'Xóa';

  @override
  String get addDistrictDialogTitle => 'Thêm Khu vực';

  @override
  String get addDistrictDescription =>
      'Nhập nhãn cho khu vực mới.\nSau đó chọn thành phố/quận và phường/xã.';

  @override
  String get label => 'Nhãn';

  @override
  String get labelHint => 'VD: Nơi làm việc, Nhà bố mẹ';

  @override
  String get labelRequired => 'Vui lòng nhập nhãn';

  @override
  String get next => 'Tiếp theo';

  @override
  String get reminderLoadError => 'Không thể tải cài đặt nhắc nhở';

  @override
  String get regionSettingLabel => 'Cài đặt Khu vực';

  @override
  String districtCount(int count) {
    return '$count/5';
  }
}
