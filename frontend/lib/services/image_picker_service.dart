import 'package:image_picker/image_picker.dart';

/// 画像取得サービス
///
/// `image_picker` パッケージをラップし、カメラ撮影とギャラリー選択による
/// 画像取得機能を提供する。テスト可能にするため、[ImagePicker] を
/// コンストラクタパラメータとして受け取る。
class ImagePickerService {
  final ImagePicker _picker;

  /// [ImagePickerService] を生成する。
  ///
  /// [picker] を省略した場合はデフォルトの [ImagePicker] インスタンスを使用する。
  /// テスト時にはモックを注入できる。
  ImagePickerService({ImagePicker? picker}) : _picker = picker ?? ImagePicker();

  /// カメラで撮影した画像を取得する。
  ///
  /// デバイスのカメラを起動し、ユーザーが撮影した画像を [XFile] として返す。
  /// ユーザーがキャンセルした場合は `null` を返す。
  Future<XFile?> pickFromCamera() async {
    return await _picker.pickImage(source: ImageSource.camera);
  }

  /// ギャラリー（フォトライブラリ）から画像を選択する。
  ///
  /// デバイスのギャラリーを開き、ユーザーが選択した画像を [XFile] として返す。
  /// ユーザーがキャンセルした場合は `null` を返す。
  Future<XFile?> pickFromGallery() async {
    return await _picker.pickImage(source: ImageSource.gallery);
  }

  /// デバイスにカメラが搭載されているかチェックする。
  ///
  /// カメラが利用可能な場合は `true`、そうでない場合は `false` を返す。
  Future<bool> isCameraAvailable() async {
    return _picker.supportsImageSource(ImageSource.camera);
  }
}
