import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../constants/app_config.dart';
import '../services/auth_service.dart';
import '../services/image_picker_service.dart';
import '../services/image_upload_service.dart';
import '../services/image_validation_service.dart';

/// 画像入力画面の状態ステータス
enum ImageInputStatus {
  initial, // 入力方法選択待ち
  previewing, // プレビュー表示中
  uploading, // アップロード中
  success, // アップロード成功
  error, // エラー
}

/// 画像入力画面の状態
class ImageInputState {
  final ImageInputStatus status;
  final XFile? selectedImage;
  final String? errorMessage;
  final String? uploadedImageId;
  final bool isCameraAvailable;

  const ImageInputState({
    this.status = ImageInputStatus.initial,
    this.selectedImage,
    this.errorMessage,
    this.uploadedImageId,
    this.isCameraAvailable = true,
  });

  ImageInputState copyWith({
    ImageInputStatus? status,
    XFile? selectedImage,
    String? errorMessage,
    String? uploadedImageId,
    bool? isCameraAvailable,
  }) {
    return ImageInputState(
      status: status ?? this.status,
      selectedImage: selectedImage ?? this.selectedImage,
      errorMessage: errorMessage,
      uploadedImageId: uploadedImageId ?? this.uploadedImageId,
      isCameraAvailable: isCameraAvailable ?? this.isCameraAvailable,
    );
  }
}

/// 画像入力の状態管理 Notifier
class ImageInputNotifier extends StateNotifier<ImageInputState> {
  final ImagePickerService _pickerService;
  final ImageValidationService _validationService;
  final ImageUploadService _uploadService;
  final AuthService _authService;

  ImageInputNotifier({
    required ImagePickerService pickerService,
    required ImageValidationService validationService,
    required ImageUploadService uploadService,
    required AuthService authService,
  })  : _pickerService = pickerService,
        _validationService = validationService,
        _uploadService = uploadService,
        _authService = authService,
        super(const ImageInputState()) {
    _checkCameraAvailability();
  }

  /// カメラの利用可否を確認する
  Future<void> _checkCameraAvailability() async {
    final available = await _pickerService.isCameraAvailable();
    state = state.copyWith(isCameraAvailable: available);
  }

  /// カメラから画像を取得する
  Future<void> pickFromCamera() async {
    try {
      final image = await _pickerService.pickFromCamera();
      if (image == null) return; // ユーザーがキャンセル

      // バリデーション
      final result = await _validationService.validate(image);
      if (!result.isValid) {
        state = state.copyWith(
          status: ImageInputStatus.error,
          errorMessage: result.errorMessage,
        );
        return;
      }

      state = ImageInputState(
        status: ImageInputStatus.previewing,
        selectedImage: image,
        isCameraAvailable: state.isCameraAvailable,
      );
    } catch (e) {
      state = state.copyWith(
        status: ImageInputStatus.error,
        errorMessage: 'カメラのアクセス許可が必要です。設定から許可してください',
      );
    }
  }

  /// ギャラリーから画像を取得する
  Future<void> pickFromGallery() async {
    try {
      final image = await _pickerService.pickFromGallery();
      if (image == null) return; // ユーザーがキャンセル

      // バリデーション
      final result = await _validationService.validate(image);
      if (!result.isValid) {
        state = state.copyWith(
          status: ImageInputStatus.error,
          errorMessage: result.errorMessage,
        );
        return;
      }

      state = ImageInputState(
        status: ImageInputStatus.previewing,
        selectedImage: image,
        isCameraAvailable: state.isCameraAvailable,
      );
    } catch (e) {
      state = state.copyWith(
        status: ImageInputStatus.error,
        errorMessage: '写真へのアクセス許可が必要です。設定から許可してください',
      );
    }
  }

  /// 画像をアップロードする
  Future<void> uploadImage() async {
    if (state.selectedImage == null) return;

    state = state.copyWith(
      status: ImageInputStatus.uploading,
    );

    try {
      final token = await _authService.getToken();
      if (token == null) {
        state = state.copyWith(
          status: ImageInputStatus.error,
          errorMessage: '認証が必要です。ログインしてください',
        );
        return;
      }

      final response = await _uploadService.upload(state.selectedImage!, token);
      state = state.copyWith(
        status: ImageInputStatus.success,
        uploadedImageId: response.imageId,
      );
    } on ImageUploadException catch (e) {
      state = state.copyWith(
        status: ImageInputStatus.error,
        errorMessage: e.message,
      );
    } catch (e) {
      state = state.copyWith(
        status: ImageInputStatus.error,
        errorMessage: 'アップロードに失敗しました。ネットワーク接続を確認してください',
      );
    }
  }

  /// 状態を初期状態にリセットする
  void reset() {
    state = ImageInputState(
      status: ImageInputStatus.initial,
      isCameraAvailable: state.isCameraAvailable,
    );
  }
}

/// ImagePickerService プロバイダー
final imagePickerServiceProvider = Provider<ImagePickerService>(
  (ref) => ImagePickerService(),
);

/// ImageValidationService プロバイダー
final imageValidationServiceProvider = Provider<ImageValidationService>(
  (ref) => ImageValidationService(),
);

/// ImageUploadService プロバイダー
final imageUploadServiceProvider = Provider<ImageUploadService>(
  (ref) => ImageUploadService(baseUrl: AppConfig.apiBaseUrl),
);

/// AuthService プロバイダー
final imageAuthServiceProvider = Provider<AuthService>(
  (ref) => AuthService(),
);

/// 画像入力状態管理プロバイダー
final imageInputProvider =
    StateNotifierProvider<ImageInputNotifier, ImageInputState>((ref) {
  return ImageInputNotifier(
    pickerService: ref.watch(imagePickerServiceProvider),
    validationService: ref.watch(imageValidationServiceProvider),
    uploadService: ref.watch(imageUploadServiceProvider),
    authService: ref.watch(imageAuthServiceProvider),
  );
});
