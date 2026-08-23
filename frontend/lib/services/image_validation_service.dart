import 'package:image_picker/image_picker.dart';

/// 画像バリデーション結果
class ImageValidationResult {
  final bool isValid;
  final String? errorMessage;

  const ImageValidationResult({
    required this.isValid,
    this.errorMessage,
  });

  const ImageValidationResult.valid()
      : isValid = true,
        errorMessage = null;

  const ImageValidationResult.invalid(String message)
      : isValid = false,
        errorMessage = message;
}

/// 画像バリデーションサービス
///
/// フロントエンドで画像ファイルのフォーマットとサイズを検証する。
class ImageValidationService {
  /// 最大ファイルサイズ（10MB）
  static const int maxFileSizeBytes = 10 * 1024 * 1024;

  /// サポートするファイル拡張子
  static const List<String> supportedExtensions = ['jpg', 'jpeg', 'png'];

  /// 画像ファイルを検証する
  /// ファイルパスまたはファイル名から拡張子を取得する（小文字に変換）
  ///
  /// Web環境ではXFile.pathがBlob URLになるため、
  /// XFile.nameも参照して拡張子を取得する。
  String _getExtension(String path) {
    final lastDot = path.lastIndexOf('.');
    if (lastDot == -1 || lastDot == path.length - 1) {
      return '';
    }
    return path.substring(lastDot + 1).toLowerCase();
  }

  /// 画像ファイルを検証する（Web対応版）
  ///
  /// ファイル拡張子、MIMEタイプ、ファイルサイズをチェックし、
  /// [ImageValidationResult] を返す。
  Future<ImageValidationResult> validate(XFile file) async {
    // ファイル拡張子チェック（パスとファイル名の両方を試行）
    var extension = _getExtension(file.path);

    // Web環境ではpathがBlob URLのため拡張子が取れない場合がある
    if (extension.isEmpty || !_isExtensionSupported(extension)) {
      // XFile.name を試行
      extension = _getExtension(file.name);
    }

    // MIMEタイプでもチェック（Web環境のフォールバック）
    if (!_isExtensionSupported(extension)) {
      final mimeType = file.mimeType;
      if (mimeType != null) {
        if (mimeType == 'image/jpeg' || mimeType == 'image/jpg') {
          extension = 'jpg';
        } else if (mimeType == 'image/png') {
          extension = 'png';
        }
      }
    }

    if (!_isExtensionSupported(extension)) {
      return const ImageValidationResult.invalid(
        'JPEG または PNG 形式の画像を選択してください',
      );
    }

    // ファイルサイズチェック
    final fileSize = await file.length();
    if (fileSize > maxFileSizeBytes) {
      return const ImageValidationResult.invalid(
        '画像サイズは10MB以下にしてください',
      );
    }

    return const ImageValidationResult.valid();
  }

  /// 拡張子がサポート対象かチェックする
  bool _isExtensionSupported(String extension) {
    return supportedExtensions.contains(extension);
  }
}
