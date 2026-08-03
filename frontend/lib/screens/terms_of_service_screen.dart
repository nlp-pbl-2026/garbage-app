import 'package:flutter/material.dart';

import '../constants/colors.dart';

/// 利用規約画面
///
/// 日本語/英語の利用規約テキストを表示する。
/// 初回起動時の同意画面としても、設定画面からの閲覧用としても使用する。
class TermsOfServiceScreen extends StatefulWidget {
  /// trueの場合は同意ボタンを表示する（初回起動時）
  final bool showAcceptButton;

  /// 同意ボタン押下時のコールバック
  final VoidCallback? onAccepted;

  const TermsOfServiceScreen({
    super.key,
    this.showAcceptButton = false,
    this.onAccepted,
  });

  @override
  State<TermsOfServiceScreen> createState() => _TermsOfServiceScreenState();
}

class _TermsOfServiceScreenState extends State<TermsOfServiceScreen> {
  bool _isJapanese = true;

  @override
  Widget build(BuildContext context) {
    final canPop = Navigator.of(context).canPop();
    return Scaffold(
      appBar: AppBar(
        title: Text(_isJapanese ? '利用規約' : 'Terms of Service'),
        backgroundColor: Colors.white,
        foregroundColor: Colors.black87,
        elevation: 1,
        leading: canPop
            ? IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => Navigator.of(context).pop(),
              )
            : null,
        automaticallyImplyLeading: false,
        actions: [
          TextButton(
            onPressed: () {
              setState(() {
                _isJapanese = !_isJapanese;
              });
            },
            child: Text(
              _isJapanese ? 'English' : '日本語',
              style: const TextStyle(color: AppColors.primary),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Text(
                _isJapanese ? _termsJa : _termsEn,
                style: const TextStyle(fontSize: 14, height: 1.6),
              ),
            ),
          ),
          if (widget.showAcceptButton) ...[
            const Divider(height: 1),
            SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: widget.onAccepted,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Text(
                      _isJapanese ? '同意して続ける' : 'Agree and Continue',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  // --- 日本語利用規約 ---
  static const String _termsJa = '''
利用規約

最終更新日: 2024年1月1日

本利用規約（以下「本規約」）は、愛媛ゴミ出しアプリ（以下「本アプリ」）の利用条件を定めるものです。本アプリをご利用いただく前に、本規約をよくお読みください。本アプリをダウンロードまたは使用することにより、本規約に同意したものとみなされます。

第1条（サービスの概要）
本アプリは、愛媛県内の市町村におけるゴミ収集スケジュールおよび分別情報を提供するアプリケーションです。

第2条（利用条件）
1. 本アプリは個人的かつ非営利目的でのみ利用できます。
2. 利用者は本規約に同意の上、自己の責任において本アプリを利用するものとします。
3. 本アプリの利用に際して、利用者は法令および公序良俗に反する行為をしてはなりません。

第3条（情報の正確性）
1. 本アプリが提供する収集スケジュール・分別情報は、公開情報に基づいて作成されていますが、その正確性・完全性・最新性を保証するものではありません。
2. 実際の収集日程は、祝日・天候・その他の事情により変更される場合があります。正確な情報は各市町村の公式情報をご確認ください。

第4条（天気予報情報）
1. 本アプリは、第三者が提供する天気予報API（Open-Meteo）を利用して天気情報を表示しています。
2. 天気予報情報の正確性について、当方は一切の責任を負いません。
3. 天気予報サービスの提供が中断・終了した場合、本アプリの天気表示機能が利用できなくなる可能性があります。

第5条（免責事項）
1. 本アプリの利用により生じた損害について、当方は一切の責任を負いません。
2. 本アプリの提供を予告なく中断・終了することがあります。
3. 通信環境やデバイスの状態により、本アプリが正常に動作しない場合があります。

第6条（個人情報の取扱い）
1. 本アプリは、選択された地域情報をデバイス内にのみ保存します。
2. 本アプリは、外部サーバーへの個人情報の送信を行いません。
3. 天気予報の取得時に、選択地域の座標情報が天気予報APIに送信されますが、個人を特定する情報は含まれません。

第7条（知的財産権）
本アプリに関する著作権その他の知的財産権は、当方または正当な権利を有する第三者に帰属します。

第8条（規約の変更）
1. 当方は、必要に応じて本規約を変更することがあります。
2. 変更後の規約は、本アプリ内に表示した時点から効力を生じるものとします。

第9条（準拠法・管轄）
本規約の解釈は日本法に準拠するものとし、本アプリに関する紛争については、松山地方裁判所を第一審の専属的合意管轄裁判所とします。

以上
''';

  // --- 英語利用規約 ---
  static const String _termsEn = '''
Terms of Service

Last updated: January 1, 2024

These Terms of Service ("Terms") govern your use of the Ehime Garbage Collection App ("the App"). Please read these Terms carefully before using the App. By downloading or using the App, you agree to be bound by these Terms.

Article 1 (Service Overview)
The App provides garbage collection schedules and sorting information for municipalities in Ehime Prefecture, Japan.

Article 2 (Conditions of Use)
1. The App may only be used for personal, non-commercial purposes.
2. Users agree to use the App at their own responsibility in accordance with these Terms.
3. Users shall not engage in any activity that violates laws or public order when using the App.

Article 3 (Accuracy of Information)
1. The collection schedules and sorting information provided by the App are based on publicly available information, but we do not guarantee their accuracy, completeness, or timeliness.
2. Actual collection schedules may change due to holidays, weather, or other circumstances. Please check official municipal information for the most accurate details.

Article 4 (Weather Forecast Information)
1. The App displays weather information using a third-party weather forecast API (Open-Meteo).
2. We assume no responsibility for the accuracy of weather forecast information.
3. If the weather forecast service is interrupted or discontinued, the weather display feature of the App may become unavailable.

Article 5 (Disclaimer)
1. We shall not be liable for any damages arising from the use of the App.
2. We may suspend or discontinue the provision of the App without prior notice.
3. The App may not function properly depending on network conditions or device status.

Article 6 (Handling of Personal Information)
1. The App stores selected region information only on the device.
2. The App does not transmit personal information to external servers.
3. When retrieving weather forecasts, coordinate information of the selected region is sent to the weather API, but no personally identifiable information is included.

Article 7 (Intellectual Property)
All copyrights and other intellectual property rights related to the App belong to us or legitimate third-party rights holders.

Article 8 (Changes to Terms)
1. We may modify these Terms as necessary.
2. Modified Terms shall take effect from the time they are displayed within the App.

Article 9 (Governing Law and Jurisdiction)
These Terms shall be governed by the laws of Japan. Any disputes related to the App shall be subject to the exclusive jurisdiction of the Matsuyama District Court as the court of first instance.

End of Terms
''';
}
