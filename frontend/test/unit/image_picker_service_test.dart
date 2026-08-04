import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:garbage_app/services/image_picker_service.dart';

/// テスト用のImagePickerモック
class MockImagePicker extends ImagePicker {
  XFile? pickImageResult;
  ImageSource? lastSource;
  bool cameraSupported;

  MockImagePicker({
    this.pickImageResult,
    this.cameraSupported = true,
  });

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    bool requestFullMetadata = true,
  }) async {
    lastSource = source;
    return pickImageResult;
  }

  @override
  bool supportsImageSource(ImageSource source) {
    if (source == ImageSource.camera) {
      return cameraSupported;
    }
    return true;
  }
}

void main() {
  group('ImagePickerService.pickFromCamera', () {
    test('カメラで撮影した画像を返す', () async {
      final mockFile = XFile('test/path/photo.jpg');
      final mockPicker = MockImagePicker(pickImageResult: mockFile);
      final service = ImagePickerService(picker: mockPicker);

      final result = await service.pickFromCamera();

      expect(result, equals(mockFile));
      expect(mockPicker.lastSource, equals(ImageSource.camera));
    });

    test('ユーザーがキャンセルした場合はnullを返す', () async {
      final mockPicker = MockImagePicker(pickImageResult: null);
      final service = ImagePickerService(picker: mockPicker);

      final result = await service.pickFromCamera();

      expect(result, isNull);
      expect(mockPicker.lastSource, equals(ImageSource.camera));
    });
  });

  group('ImagePickerService.pickFromGallery', () {
    test('ギャラリーから選択した画像を返す', () async {
      final mockFile = XFile('test/path/gallery_image.png');
      final mockPicker = MockImagePicker(pickImageResult: mockFile);
      final service = ImagePickerService(picker: mockPicker);

      final result = await service.pickFromGallery();

      expect(result, equals(mockFile));
      expect(mockPicker.lastSource, equals(ImageSource.gallery));
    });

    test('ユーザーがキャンセルした場合はnullを返す', () async {
      final mockPicker = MockImagePicker(pickImageResult: null);
      final service = ImagePickerService(picker: mockPicker);

      final result = await service.pickFromGallery();

      expect(result, isNull);
      expect(mockPicker.lastSource, equals(ImageSource.gallery));
    });
  });

  group('ImagePickerService.isCameraAvailable', () {
    test('カメラが利用可能な場合はtrueを返す', () async {
      final mockPicker = MockImagePicker(cameraSupported: true);
      final service = ImagePickerService(picker: mockPicker);

      final result = await service.isCameraAvailable();

      expect(result, isTrue);
    });

    test('カメラが利用不可の場合はfalseを返す', () async {
      final mockPicker = MockImagePicker(cameraSupported: false);
      final service = ImagePickerService(picker: mockPicker);

      final result = await service.isCameraAvailable();

      expect(result, isFalse);
    });
  });

  group('ImagePickerService コンストラクタ', () {
    test('カスタムImagePickerインスタンスを受け取れる', () {
      final mockPicker = MockImagePicker();
      final service = ImagePickerService(picker: mockPicker);

      expect(service, isNotNull);
    });

    test('引数なしでデフォルトのImagePickerを使用する', () {
      final service = ImagePickerService();

      expect(service, isNotNull);
    });
  });
}
