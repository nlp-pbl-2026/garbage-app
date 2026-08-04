import 'package:flutter/material.dart';

/// よくある質問（FAQ）画面
///
/// ゴミ出しに関するよくある質問をExpansionTile（アコーディオン形式）で表示する。
class FaqScreen extends StatelessWidget {
  const FaqScreen({super.key});

  static const List<_FaqItem> _faqItems = [
    _FaqItem(
      question: '電池はどのゴミですか？',
      answer: '電池は危険ごみです。収集日に透明または半透明の袋に入れて出してください。充電式電池（リチウムイオン電池など）は回収ボックスがある家電量販店等に持ち込んでください。',
    ),
    _FaqItem(
      question: 'スプレー缶の処理方法は？',
      answer: 'スプレー缶は必ず中身を使い切り、穴を開けずに危険ごみとして出してください。中身が残っている場合は、屋外の火気のない場所で中身を出し切ってから出してください。',
    ),
    _FaqItem(
      question: '粗大ごみの出し方は？',
      answer: '粗大ごみは事前に市役所への電話申込が必要です。指定日に指定場所へ出してください。収集は有料です。自治体によって料金や手続きが異なりますので、お住まいの市役所にお問い合わせください。',
    ),
    _FaqItem(
      question: '収集日の朝何時までに出せばいいですか？',
      answer: '収集日の朝8時までに所定の集積所に出してください。前日の夜に出すとカラスや猫に荒らされる恐れがありますので、当日の朝に出すようにしましょう。',
    ),
    _FaqItem(
      question: '祝日のゴミ収集はありますか？',
      answer: '祝日でも通常通り収集を行います。ただし年末年始（12/31〜1/3）は収集を休止します。振替収集はありませんのでご注意ください。',
    ),
    _FaqItem(
      question: '引っ越しで大量のゴミが出た場合は？',
      answer: '一度に大量のゴミを出す場合は、数回に分けて通常の収集日に出すか、直接クリーンセンターに持ち込んでください。クリーンセンターへの持ち込みは有料（10kgあたり100円程度）です。',
    ),
    _FaqItem(
      question: 'ペットボトルのキャップとラベルは？',
      answer: 'キャップとラベルはプラスチック製容器包装として分別してください。ボトル本体は中をすすいでからペットボトルとして出してください。つぶしてかさを減らすと集積所のスペース節約になります。',
    ),
    _FaqItem(
      question: '雨の日のゴミ出しは？',
      answer: '雨の日でも通常通り収集します。紙類や段ボールは濡れないよう袋に入れて出してください。強風の日はゴミが飛ばないようネットをしっかりかけてください。',
    ),
    _FaqItem(
      question: '食用油の捨て方は？',
      answer: '食用油は紙や布に染み込ませるか、市販の凝固剤で固めてから可燃ごみとして出してください。液体のまま出すことはできません。',
    ),
    _FaqItem(
      question: '蛍光灯・LED電球の捨て方は？',
      answer: '蛍光灯は危険ごみとして出してください。割れないよう購入時のケースや新聞紙に包んで出しましょう。LED電球は不燃ごみまたは危険ごみ（自治体により異なります）です。',
    ),
    _FaqItem(
      question: '割れたガラスや陶器の出し方は？',
      answer: '割れたガラスや陶器は不燃ごみです。作業員がケガをしないよう、新聞紙等に包んで「キケン」と表示して出してください。',
    ),
    _FaqItem(
      question: '段ボールの出し方は？',
      answer: '段ボールは資源ごみです。ガムテープや金具を取り除き、たたんでヒモで十字に縛って出してください。雨の日は濡れないようビニール袋に入れるか、次の収集日に出してください。',
    ),
    _FaqItem(
      question: '家電リサイクル法対象品目は？',
      answer: 'テレビ、冷蔵庫・冷凍庫、洗濯機・衣類乾燥機、エアコンの4品目は通常のゴミ収集では回収できません。購入した販売店か、指定引取場所に持ち込んでください。リサイクル料金が必要です。',
    ),
    _FaqItem(
      question: 'パソコンの処分方法は？',
      answer: 'パソコンは小型家電リサイクル法の対象です。メーカー回収（PCリサイクルマーク付きは無料）、自治体の回収ボックス、または認定事業者による回収をご利用ください。データは事前に消去してください。',
    ),
    _FaqItem(
      question: '生ごみを減らすコツは？',
      answer: '生ごみの約80%は水分です。水切りをしっかり行うだけでゴミの量と重さが大幅に減ります。三角コーナーや水切りネットを活用し、一晩置いて水を切ってから捨てましょう。コンポストの利用もおすすめです。',
    ),
    _FaqItem(
      question: '古着や布製品の出し方は？',
      answer: '洗濯済みの古着は資源ごみとして出せる場合があります（自治体により異なります）。汚れや破れがひどいものは可燃ごみです。ボタンやファスナーはそのままで構いません。',
    ),
    _FaqItem(
      question: 'ゴミ袋に指定はありますか？',
      answer: '自治体によって異なります。指定袋が必要な場合はスーパーやコンビニで購入できます。指定がない場合は透明または半透明の袋をお使いください。黒い袋は中身が確認できないため使用できません。',
    ),
    _FaqItem(
      question: '収集されなかったゴミはどうすれば？',
      answer: '分別間違いや出し方の問題で収集されなかった場合、貼られたシールの内容を確認し、正しく分別し直してから次の収集日に再度出してください。不明な場合は市役所の生活環境課にお問い合わせください。',
    ),
    _FaqItem(
      question: 'アプリの通知が届かないのですが？',
      answer: '端末の設定でこのアプリの通知が許可されているか確認してください。また、設定画面でリマインダーがONになっているか、通知時刻の設定もご確認ください。',
    ),
    _FaqItem(
      question: '地区の設定を間違えた場合は？',
      answer: '設定画面から地域設定を変更できます。「現在の地域」セクションで別の地区をタップするか、新しい地区を追加してください。',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('よくある質問'),
      ),
      body: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _faqItems.length,
        itemBuilder: (context, index) {
          final item = _faqItems[index];
          return ExpansionTile(
            title: Text(
              item.question,
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(item.answer),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

/// FAQ項目のデータモデル
class _FaqItem {
  const _FaqItem({required this.question, required this.answer});

  final String question;
  final String answer;
}
