// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'Ehime Garbage App';

  @override
  String get categoryBurnable => 'Burnable';

  @override
  String get categoryRecyclable => 'Recyclable';

  @override
  String get categoryPlastic => 'Plastic Containers';

  @override
  String get categoryPetBottle => 'PET Bottles';

  @override
  String get categoryHazardous => 'Hazardous';

  @override
  String get tabSearch => 'Search';

  @override
  String get tabCalendar => 'Calendar';

  @override
  String get tabSettings => 'Settings';

  @override
  String get tabImageInput => 'Image';

  @override
  String get regionSelectionTitle => 'Select Region';

  @override
  String get selectPrefecture => 'Select Prefecture';

  @override
  String get selectMunicipality => 'Select Municipality';

  @override
  String get selectDistrict => 'Select District';

  @override
  String get startWithRegion => 'Start with this region';

  @override
  String get searchTitle => 'Search Garbage Items';

  @override
  String get searchHint => 'Enter item name (2+ characters)';

  @override
  String get popularItems => 'Frequently Searched Items';

  @override
  String get multipleItemsFound => 'Multiple similar items found';

  @override
  String get multipleCategoriesNote => 'Or varies by item';

  @override
  String get itemDetailTitle => 'Item Details';

  @override
  String get nextCollectionDate => 'Next Collection Date';

  @override
  String get disposalMethod => 'How to Dispose';

  @override
  String get caution => 'Caution';

  @override
  String get registerToCalendar => 'Add to Calendar';

  @override
  String get calendarTitle => 'Collection Calendar';

  @override
  String get nextCollection => 'Next Collection';

  @override
  String get noSchedule => 'No collection scheduled for this day';

  @override
  String get colorLegend => 'Color Legend';

  @override
  String get settingsTitle => 'Settings';

  @override
  String get regionSettings => 'Region Settings';

  @override
  String get changeRegion => 'Change Region';

  @override
  String get notificationSettings => 'Notification Settings';

  @override
  String get languageSettings => 'Language';

  @override
  String get reminderToggle => 'Day-before collection reminder';

  @override
  String get reminderDescription =>
      'Notifies you at 18:00 the day before collection';

  @override
  String get noSearchResults => 'No matching items found';

  @override
  String get dataLoadError => 'Failed to load data';

  @override
  String get regionDataError => 'Failed to load region data';

  @override
  String get saveError => 'Failed to save';

  @override
  String get regionNotSet => 'Region not set';

  @override
  String get dataOutdated =>
      'Data may be outdated. Please connect to the internet to update.';

  @override
  String get noOfflineData =>
      'Data is unavailable. An internet connection is required.';

  @override
  String get prefectureNotSelected => 'Please select a prefecture';

  @override
  String get municipalityNotSelected => 'Please select a municipality';

  @override
  String get districtNotSelected => 'Please select a district';

  @override
  String get regionSaved => 'Region settings saved';

  @override
  String get calendarRegistered => 'Added to calendar';

  @override
  String get calendarPermissionDenied =>
      'Calendar access permission is required. Please allow access in your device settings.';

  @override
  String get retry => 'Retry';

  @override
  String get back => 'Back';

  @override
  String get openSettings => 'Open Settings';

  @override
  String get aiErrorMessage =>
      'Unable to complete the request. Please try again later.';

  @override
  String get notificationTomorrowTitle => 'Tomorrow\'s Garbage';

  @override
  String notificationTomorrowBody(String categories) {
    return 'Tomorrow is $categories day';
  }

  @override
  String get notificationTodayTitle => 'Today\'s Garbage';

  @override
  String notificationTodayBody(String categories) {
    return 'Today is $categories day';
  }

  @override
  String municipalityRomanization(String japaneseName, String romanizedName) {
    return '$japaneseName ($romanizedName)';
  }

  @override
  String get bulkyWaste => 'Bulky Waste';

  @override
  String get regionRequired => 'Region setup required';

  @override
  String get searchTip => 'Search for items you don\'t know how to dispose of';

  @override
  String get searchTipDescription =>
      'Enter an item name to find the disposal method';

  @override
  String get searchByCategory => 'Search by Category';

  @override
  String get searchHistory => 'Search History';

  @override
  String get deleteAll => 'Delete All';

  @override
  String get searchResults => 'Search Results';

  @override
  String get nextCollectionDates => 'Next Collection Dates';

  @override
  String get today => 'Today';

  @override
  String get tomorrow => 'Tomorrow';

  @override
  String get dayAfterTomorrow => 'Day after tomorrow';

  @override
  String daysRemaining(int days) {
    return '$days days left';
  }

  @override
  String collectionDaysFor(String category) {
    return '$category Collection Days';
  }

  @override
  String get noUpcomingCollections => 'No upcoming collection dates found';

  @override
  String get selectDate => 'Please select a date';

  @override
  String get exportCalendar => 'Export Calendar';

  @override
  String get categoryShortBurnable => 'Burn';

  @override
  String get categoryShortRecyclable => 'Recy';

  @override
  String get categoryShortPlastic => 'Plas';

  @override
  String get categoryShortPetBottle => 'PET';

  @override
  String get categoryShortHazardous => 'Haz';

  @override
  String get account => 'Account';

  @override
  String get loggedIn => 'Logged in';

  @override
  String get changePassword => 'Change Password';

  @override
  String get logout => 'Log Out';

  @override
  String get loginOrRegister => 'Log In / Register';

  @override
  String get loginSyncMessage => 'Log in to sync your settings';

  @override
  String get currentRegion => 'Current Region';

  @override
  String get detectFromLocation => 'Re-detect from current location';

  @override
  String get theme => 'Theme';

  @override
  String get themeSystem => 'System';

  @override
  String get themeLight => 'Light';

  @override
  String get themeDark => 'Dark';

  @override
  String get other => 'Other';

  @override
  String get faq => 'FAQ';

  @override
  String get termsOfService => 'Terms of Service';

  @override
  String get reminderNotificationDescription =>
      'Notifies you the day before and on the day of collection';

  @override
  String get reminderSettingFailed => 'Failed to set reminder';

  @override
  String get regionSettingUpdated => 'Region settings updated';

  @override
  String get cancel => 'Cancel';

  @override
  String get detectFromGps => 'Detect from current location';

  @override
  String get setRegionPrompt => 'Please set your residential area';

  @override
  String get regionOptimizationDescription =>
      'Optimize garbage collection days and sorting rules for your area.';

  @override
  String get pleaseSelect => 'Please select';

  @override
  String get settingsCanChangeLater =>
      'You can change settings later from the Settings screen';

  @override
  String get gpsResult => 'GPS Detection Result';

  @override
  String get gpsRegionDetected => 'The following region was detected:';

  @override
  String get setThisRegion => 'Use this region';

  @override
  String get selectImage => 'Please select an image';

  @override
  String get takePhoto => 'Take Photo';

  @override
  String get chooseFromGallery => 'Choose from Gallery';

  @override
  String get realtimeCamera => 'Realtime Camera';

  @override
  String get noCameraAvailable => 'No camera available on this device';

  @override
  String get send => 'Send';

  @override
  String get redo => 'Redo';

  @override
  String get uploading => 'Uploading...';

  @override
  String get uploadComplete => 'Upload complete';

  @override
  String get imageSentSuccess => 'Image sent successfully';

  @override
  String get resend => 'Resend';

  @override
  String get errorOccurred => 'An error occurred';

  @override
  String get municipality => 'Municipality';

  @override
  String get district => 'District';

  @override
  String get city => 'City';

  @override
  String get eveningNotification => 'Evening notification';

  @override
  String get morningNotification => 'Morning notification';

  @override
  String get addDistrict => 'Add District';

  @override
  String get districtListLoadError => 'Failed to load district list';

  @override
  String get inUse => 'Active';

  @override
  String get deleteDistrict => 'Delete District';

  @override
  String deleteDistrictConfirm(String label) {
    return 'Delete \"$label\"?';
  }

  @override
  String get delete => 'Delete';

  @override
  String get addDistrictDialogTitle => 'Add District';

  @override
  String get addDistrictDescription =>
      'Enter a label for the new district.\nThen select a municipality and district.';

  @override
  String get label => 'Label';

  @override
  String get labelHint => 'e.g., Work, Parents\' home';

  @override
  String get labelRequired => 'Please enter a label';

  @override
  String get next => 'Next';

  @override
  String get reminderLoadError => 'Failed to load reminder settings';

  @override
  String get regionSettingLabel => 'Region Settings';

  @override
  String districtCount(int count) {
    return '$count/5';
  }
}
