# 八幡浜市・2026年度データ

自治体IDは `38204`、版は `yawatahama-2026.2`、収集日の適用期間は2026-04-01～2027-03-31です。松山市のCSV・Embedding・分別ルールは流用していません。八幡浜市内では本土と大島が同じ品目索引を共有し、紙類の収集区分とカレンダーだけを切り替えます。

## 出典と対応範囲

- [2026年度のごみ収集カレンダー](https://www.city.yawatahama.ehime.jp/doc/2026030500028/)：公式PDF20種類。
- 公式品目表[あ～そ](https://www.city.yawatahama.ehime.jp/doc/2023083100038/)・[た～わ](https://www.city.yawatahama.ehime.jp/doc/2023091300024/)：見出しを除いた768品目。分類・持込制限・説明2欄を保持します。
- [ごみ分別ガイドブック](https://www.city.yawatahama.ehime.jp/doc/2021022400010/)：現在案内されている2023年版。確認した12件の区分別説明・品目例を加え、索引は780行です。
- [家庭ごみの出し方](https://www.city.yawatahama.ehime.jp/doc/2022091300010/)：指定袋、搬出期限など。取得日時・URL・SHA-256は `data/regions/yawatahama/sources.json` に記録します。

20種類のPDFに対し、紙類の曜日が住所によって分かれる13番・15番をそれぞれ2つに分け、**23選択地区・23カレンダー（22件は全区分確認済み、1件は紙類4区分未確認）**を生成します。大島19・20番は紙類4分類の収集区分を `paper_all` にまとめ、品目の分類名・出し方は保持します。定期収集の搬出期限は午前8時です。休日・年末年始・同日複数区分は実日付を使用し、通常曜日から補いません。

**郷・中央（郷一木地区・旧道沿い）**は `38204-13-go` として選択できます。公式索引が指定する13番PDFを使い、紙類以外の6区分は通常どおり利用します。紙類の住所枠との対応は一意に確認できないため、段ボール・新聞・雑誌・紙製容器包装の4区分は収集日未確認とします。火曜・金曜のどちらも登録せず、検索結果・カレンダーには注意と公式PDFのリンクを表示し、通知・iCalを生成しません。6番の「郷・中央」で代用しません。住所・GPSによる自動対応表は整備しておらず、八幡浜市では手動選択します。

## 検証

PDF内の日付文字・ベクトル図形の色と位置から収集日を抽出し、独立した描画画像の背景色と暦から求めた日付位置で照合します。20 PDFの全7,300日付セルを対象とし、空欄・日曜・年末年始・同日複数区分・6週目の分割表示160セルも含みます。凡例と13・15番の紙類の住所条件は別途確認し、曜日フィルタをテストします。

これは生成JSON同士の比較ではありません。ただし、画像色検査が凡例の文字を独立に解読するわけではなく、全日付を人手で監査したとの主張でもありません。PDFの色と表示位置が変われば抽出を停止し、`calendar_reviews.json` のハッシュ・記録を更新する前に再確認します。取得した原本が更新された場合も既存の検証済み扱いを引き継ぎません。

品目CSVと索引はID・順序・モデル・次元・有限値・正規化・双方のSHA-256を照合します。「素材で判断」「マークで判断」の65品目を固定分類へ変換していません。`category_options` に公式注記の条件付き候補を記録し、条件が足りなければ追加質問・保留になります。検索対象780行は780品目の無条件な分類成功を意味しません。

品目固有の注記と区分共通の `disposal_instructions` は別列です。Embeddingは品目名・固有注記を対象とし、共通の袋・搬出期限の文章で検索順位を偏らせません。回答用の根拠には両方を渡し、品目固有条件を優先します。例えば洗剤容器の固有条件を、一般的な容器包装の案内で上書きしません。

## Gitに含まれるもの・含まれないもの

今回のPRのコード・テスト・文書を含む全変更ファイルは、`git diff --name-status eb6d0f6..HEAD` で確認できます。自治体データの扱いは次のとおりです。

| パス | 内容 | Git・新規clone |
| --- | --- | --- |
| `data/regions/catalog.json` | 利用可能な自治体と台帳の参照先 | 含む |
| `data/regions/yawatahama/sources.json` | 公式資料50ファイルのURL・取得日時・SHA-256 | 含む |
| `data/regions/yawatahama/calendar_reviews.json` | 20 PDFの照合記録・ハッシュ | 含む |
| `data/regions/yawatahama/calendar_variants.json` | 紙類の住所別曜日と区分別の未確認範囲 | 含む。公式資料を加工した設定 |
| `data/regions/yawatahama/official_rules.json` | 分別ルール・12件の説明例・出し方・粗大ごみ案内 | 含む。公式資料から加工した文章も含む |
| `data/regions/yawatahama/registry.json` | 23地区・カレンダー・分別設定の対応 | 含む。生成した地区名・分類ルールも含む |
| `data/regions/yawatahama/knowledge/index_manifest.json` | CSV・NPZのハッシュ、モデル、次元、件数 | 含む。ベクトル本体は含まない |
| `frontend/assets/data/municipality_catalog.json`、`municipality_38204_registry.json` | Flutter用の自治体・地区・分類表示・粗大ごみ案内 | 含む。生成した設定・案内文も含む |
| `data/regions/yawatahama/source/` | 取得した公式PDF・HTML、`downloads.json` | 含まない。`fetch` で取得 |
| `data/regions/yawatahama/knowledge/items.csv` | 768品目＋12説明例 | 含まない。`build` で生成 |
| `data/regions/yawatahama/knowledge/item_embeddings.npz` | 八幡浜市専用の780ベクトル | 含まない。承認済みファイルの共有、または有償生成が必要 |
| `data/regions/yawatahama/generated/` | カレンダー共通原本、検証レポート、生成チェックポイント、開発時の検索ログ等 | 含まない。カレンダーは `build` で生成。過去のログ・チェックポイントは起動に不要 |
| `frontend/assets/data/municipality_38204_0_calendar.json` | Flutterに同梱する共通原本の複製 | 含まない。`generate_frontend_data.py` で生成 |

**追跡ファイルにも公式資料を加工した文章・設定が含まれます。** 公式PDF・CSVを除外したことだけで利用条件の確認が完了したことにはなりません。資料の利用・加工・再配布条件は未確認です。公開・アプリやLambdaへの同梱前に認められる範囲を確認してください。

## 新規cloneからの取得・再生成

以下は通常の履歴付きcloneを行った後、リポジトリルートから順に実行します。松山市のCSV復元には履歴中の `d28ea90` が必要です。浅いclone等でそのコミットがない場合は、履歴を含むcloneか、既存索引に対応するCSVの共有が別途必要です。

### 1. Python環境

Python 3.12とuvを用意し、ロックファイルどおりに開発依存関係もインストールします。PyMuPDFは開発依存関係です。`uv sync` の省略やPython 3.10ではPDF生成・検証まで揃いません。

```bash
cd backend
uv sync --frozen --python 3.12 --group dev
cd ..
```

### 2. 松山市の既存データ

標準カタログは松山市と八幡浜市の両方を参照します。`generate_frontend_data.py` は全登録自治体を処理するため、**八幡浜市だけを生成しても新規cloneでは不足します**。次はBedrockを呼びません。松山市の既存EmbeddingはGitにあり、再生成しません。

```bash
backend/.venv/bin/python scripts/matsuyama_data.py fetch
backend/.venv/bin/python scripts/matsuyama_data.py fetch-aux
backend/.venv/bin/python scripts/matsuyama_data.py extract
backend/.venv/bin/python scripts/matsuyama_data.py restore-legacy
backend/.venv/bin/python scripts/matsuyama_data.py build
backend/.venv/bin/python scripts/matsuyama_data.py build-knowledge
```

松山市の2つの分別案内HTMLでは、CMSの末尾の「おすすめページ」が変動します。`fetch-aux` は取得した原本を保持し、この1行の `div#lorecommend` だけを除いた残りが従来のハッシュと一致する場合に限り許容します。実際の取得SHA-256と照合方法はGit管理外の `source/auxiliary-verification.json` に記録します。本文・住所表・PDFの変更や想定外のレイアウトは引き続き停止します。

### 3. 八幡浜市の公式資料・品目・カレンダー

```bash
backend/.venv/bin/python scripts/yawatahama_data.py fetch
backend/.venv/bin/python scripts/yawatahama_data.py build
```

`build` は公式原本のハッシュ、日付・記号抽出と画像色の照合、承認済みレビューを検査してから、地区台帳・780行のCSV・23カレンダーを生成します。原本が変わって失敗した場合は、`inspect` で候補を出し、公式資料を再確認してください。候補を無条件に承認済みへコピーしたり、失敗を回避するためにハッシュを書き換えたりしないでください。

### 4. 八幡浜市の索引を配置（手作業）

有償処理を避ける通常手順は、作成者から**現在のマニフェストに対応する `item_embeddings.npz` だけ**を受け取る方法です。原本・CSV・カレンダーは上記の手順で生成でき、過去の検索ログやチェックポイントの共有は不要です。

```bash
cp /path/to/shared/item_embeddings.npz data/regions/yawatahama/knowledge/item_embeddings.npz
```

対応するCSVのSHA-256は `2f36dccd7b2647fc1878c52fdee825c9688e76a4df37625d269072f9c18a0db2`、NPZは `581de598878513f4c14ec6ac8c591fd635fabb0ef268cfe5f2e191a522aebd68` です。後続の `verify` がGit上のマニフェストと照合します。別版のNPZを置いた場合は停止し、マニフェストを書き換えて取り繕わないでください。共有場所はリポジトリ内には用意していないため、ファイルの受け渡しはメンバー間で必要です。

共有ファイルを入手できない場合のみ、費用と認証を別途承認したうえで次を実行できます。**有償のBedrock呼出を行います。通常のセットアップやテストから自動実行しません。**

```bash
backend/.venv/bin/python scripts/build_regional_embeddings.py \
  --source data/regions/yawatahama/knowledge/items.csv \
  --output data/regions/yawatahama/knowledge/item_embeddings.npz \
  --municipality 38204 --profile citywide \
  --checkpoint data/regions/yawatahama/generated/embedding-checkpoint.jsonl \
  --max-calls 900 --budget-usd 0.30
```

チェックポイントは入力テキスト・モデル・次元でキャッシュします。予算枠は実請求額ではなく、失敗・再試行も含めた呼出前の保守的見積りです。再生成でNPZのバイト列が同一になる保証はありません。再生成時は新しいマニフェストも生成されるため、その組を検証してチームで共有してください。松山市索引は変更しません。

### 5. Flutterデータ生成と照合

```bash
backend/.venv/bin/python scripts/generate_frontend_data.py
backend/.venv/bin/python scripts/yawatahama_data.py verify
backend/.venv/bin/python scripts/matsuyama_validation.py
```

Flutterにはバックエンドの共通原本をバイト単位で複製します。`verify` では両者のバージョン・地区・カレンダーの一致と、CSV・索引の対応まで確認します。索引がなければRAG用データの検証は完了しません。Flutterから既存APIを使うだけならローカルNPZは不要ですが、そのAPI自体が八幡浜市に対応済みである必要があります。

### 6. ローカル起動

Flutter SDKとChromeを別途用意します。以下のコマンドはそれぞれリポジトリルートを開いたターミナルで実行します。

バックエンド（別ターミナル）:

```bash
cd backend
USE_BEDROCK_KNOWLEDGE_BASE=false LEXICAL_SEARCH_ENABLED=false \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Flutter（別ターミナル）:

```bash
cd frontend
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

ヘルスチェック・カレンダー・品目一覧の確認にBedrockは不要です。実際の分別検索・画像検索・追加質問には、バックエンド側に許可されたBedrock認証・モデル利用権限が必要で、費用も発生します。FlutterへAWS認証情報を渡してはいけません。未更新の公開APIへつなぐだけでは今回の八幡浜市対応は使えません。

Flutter SDKのバージョンによって `pub get` が解析設定・プラグイン登録・`pubspec.lock` を自動更新する場合があります。今回の検証は一時clone内で行い、これらの環境差分はPRに含めません。

## 粗大ごみと未検証の範囲

粗大ごみには定期収集日を付けません。直接搬入・地域の回収（実施の有無は地区に確認）・電話予約収集を案内します。予約窓口は環境センター0894-23-0053、月～金8:30～17:15、料金・日程は予約時に確認します。室内からの搬出は行いません。「持込み」や市で処理できないものの個別指定を大きさだけで粗大ごみへ変更しません。PETボトルのラベルを必ず外す松山市のルールも適用しません。

実Bedrock評価はローカルサービスから実施し、AWSへのデプロイとFlutter公開は行っていません。画像評価は公式ガイドの缶のイラストであり、実物写真全般の精度評価ではありません。通知のOS許可・バックグラウンド配信、GPS実機、スマートフォンのiCal共有は実機確認が別途必要です。

公式データを使うFlutter照合は通常の単体テストから分離しています。原本・生成物を配置した状態で次を実行すると、全23カレンダー8,395日付セルの画面用変換（追加地区の紙類4区分に日付がないことも含む）と、通知計画・iCalの出力を検査します（OSへの通知登録・外部共有は行いません）。

```bash
cd frontend
flutter test tool/verify_yawatahama_data_test.dart
```

## 今回の検索・回帰評価（2026-11-01）

Nova Lite / Titan Text Embeddings V2を使い、Knowledge Base・表層検索を無効にした現在の検索経路で合計34検索を実施しました。初回は八幡浜市18件中17件が想定と一致し、画像＋文章の洗浄済み缶で汚れ例外が誤適用されたため、地域ルールを補強しました。追加8件では缶の問題が解消し、木製いすの誤判定と、プラマーク明示時の重複質問が見つかりました。

品目固有注記と共通案内を分離して差分索引を生成した後の6検索は、木製いす・素材不明のいす・木製と回答する追加質問・画像＋文章の洗浄済み缶・ラベル付きPETの5件が期待どおりでした。残る汚れたプラ容器は分類候補は燃やすごみでしたが、後段の共通ガードが素材を再質問していました。このガードを修正し、合成データによる判定～次回収集日までの回帰テストを追加しました。**最後のガード修正後に実Bedrockは再呼出していません**。初回の他品目をすべて差分索引でも再評価したわけではありません。検索候補や引用が一般的な同素材の別品目に寄る場合もあり、全品目の検索精度を保証する評価ではありません。

松山市の2件は、大きな家具1件が粗大で回答され、詳細な木製家具1件は既存の厳密な根拠チェックで保留になりました。松山市の判定経路・CSV・索引・カレンダーは変更していません。この保留は残る制限です。

有償処理は初回生成と差分生成を合わせてTitan 1,483回、検索34件でした。承認された合計US$1に対する保守的な費用枠使用量は約US$0.324で、実請求額ではありません。利用量・検索結果・開発中の検証コードは `data/regions/yawatahama/generated/` にローカル保存し、Gitには含めません。

通常テストはバックエンド160件、Flutter179件が通過し、別途の公式データFlutter照合2件も通過しました。Flutter静的解析は既存と同じ62診断（エラー0、警告7、info55）です。ローカルFastAPIのヘルスチェック、八幡浜市本土・大島と松山市清水の粗大ごみ一覧はHTTP 200を確認しました。配布用データのステージングも12ファイルで成功しています。当時のローカル環境ではLambda用Mangumが未導入でしたが、以下の新規clone検証ではロックファイルから導入し、Lambda側のASGIエントリーポイントも確認しています。

## PR前の新規clone検証（2026-11-01）

コミット済みファイルだけを一時cloneし、今回の再現性修正を適用して確認しました。元環境から持ち込んだデータは、手順4で共有する八幡浜市のNPZ 1ファイルだけです。公式PDF・HTML・CSV・生成カレンダー・住所表・中島の根拠CSV・Python仮想環境・Flutterの依存関係はclone側で取得・生成しました。

- `uv sync --frozen --python 3.12 --group dev` が成功。FastAPI・Mangum・PDF検証の依存関係を導入できました。
- 八幡浜市の公式50ファイルを再取得し、768品目＋12説明例、22地区・20 PDF由来のカレンダーを生成しました。CSVとカレンダー原本は元環境とバイト一致しました。共有NPZもGit上のハッシュと一致しています。
- 松山市の43カレンダー・710住所行・中島79根拠・既存CSVを復元し、生成物は元環境とバイト一致しました。2案内HTMLの差分はCMSのおすすめ欄のみで、原本を保持したまま本文の一致を検証しました。
- バックエンド単体テスト166件、Flutter単体・ウィジェット等179件、八幡浜市の公式データを使うFlutter照合2件が通過しました。通常テストは実Bedrockを呼びません。
- FastAPIとLambda用ASGIのヘルスチェック・八幡浜市本土／大島・松山市清水の品目一覧でHTTP 200を確認しました。Uvicornの実HTTP起動も確認し、一時サーバーは終了しています。
- `flutter build web --no-pub --dart-define=API_BASE_URL=http://127.0.0.1:8000` が成功し、成果物内にも八幡浜市のカレンダーが含まれることを確認しました。CupertinoIconsのフォント警告は残っています。画面の目視操作・実機確認はこの検証に含みません。
- バックエンド用データ12ファイルのステージングが成功しました。AWS操作・実検索API・公開・配布は実行していません。

**Gitだけで検索索引までは揃いません。** 残る手作業は承認済みNPZの受け渡しです。実検索を行う際は、別途のAWS認証・モデル利用権限・費用の確認も必要です。公式資料が今後変更されて照合に失敗した場合は、新しい資料の確認が必要になります。

## 区分別の収集日未確認への対応（2026-11-01、2026.2版）

以前の22地区は削除・統合せず、日付・検証状態をそのまま保持して1地区を追加しました。従って現在は23地区です。上記の2026.1版の検索評価・新規clone確認での22地区という件数は、その時点の履歴です。品目CSV・Embedding・分類ルールの内容は変更していません。APIとFlutterを2026.2版の同じデータに揃えて利用します。

13番PDFの「紙類」の対象は、凡例と火曜・金曜の記号を照合した段ボール・新聞・雑誌・紙製容器包装です。`yh-13-go` の `verification_status` は `partially_checked` とし、`collection_type_verification` に全10収集区分の状態を記録します。4区分は `unverified`、ほかの6区分は `checked` です。年365日の日付セルは保持しますが、未確認の区分の予定は一切含めません。元PDF20種類・7,300日付セルの記号／描画色照合を継続し、追加の紙類除外は別のテストで検証します。

分類が確定しても紙類の収集日が未確認なら、APIは `next_collection: null` と `collection_status.status: unverified`、説明、PDF URLを返します。確認済み区分の今後の予定がない場合は `no_upcoming_collection` で区別します。Flutterも同じ区分別状態を読み、空欄を「収集なし」と断定しません。既存の確認済みカレンダーには区分別状態の追加は不要です。

この変更の検証結果は、バックエンド174件、Flutter184件、公式データを使うFlutter照合3件の通過です。既存22カレンダーの日付レコードが変更されていないこと、新地区の全365日が13番の紙類以外の日付に一致すること、全23カレンダー8,395日付セルをFlutterが読み込めることを確認しました。紙類4区分の通知・iCal予定が生成されないこと、検索画面が未確認の日付を表示しないこともテストしています。静的解析は従来と同じ62診断（エラー0、警告7、info55）、Webのローカルビルドも成功しました。実Bedrock・AWS APIは呼び出していません。
