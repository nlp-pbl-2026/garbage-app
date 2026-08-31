# あいまい検索評価

松山市の品目辞典を正解ラベルとして、正式名を避けた曖昧クエリを生成し、実際の検索APIを評価します。

## データの扱い

- 正解ラベルには利用条件を確認済みの`items.csv`を使用します。CSVはGitには含まれません。
- ごみサクは出典確認にのみ使用し、サイトを自動取得・複製しません。
- 生成データ、外部から手動で用意した原典、評価応答、レポートは`artifacts/`または`source/`へ置きます。
- 上記2ディレクトリは`.gitignore`対象で、Gitへコミットしません。
- 品目単位でtrain/testを固定分割するため、同じ正解品目が両方へ入ることはありません。
- 改善中はtrainだけを確認し、testは仕組みとプロンプトを確定した後に一度だけ評価します。

## 1. データセット生成

AWSへログインした状態で、`backend/`から実行します。
先に`../data/regions/matsuyama/common/knowledge/items.csv`を配置してください。

```bash
uv run python -m evaluation.build_dataset \
  --train-limit 90 \
  --test-limit 45
```

生成先:

- `evaluation/artifacts/dataset/train.jsonl`
- `evaluation/artifacts/dataset/test.jsonl`
- `evaluation/artifacts/dataset/manifest.json`

件数に`0`を指定すると、そのsplitの全候補を生成します。生成モデルは`EVAL_GENERATOR_MODEL_ID`で変更できます。

## 2. train評価と改善

```bash
export EVAL_API_BASE_URL='https://<evaluation-api-endpoint>'
uv run python -m evaluation.run_evaluation --split train
```

各クエリを実APIへ送り、追加質問が返った場合はLLMが隠れた実物設定に基づいて回答します。結果は`evaluation/artifacts/runs/`へ保存されます。

少数で疎通確認する場合:

```bash
uv run python -m evaluation.run_evaluation --split train --limit 5
```

別のAPIを評価する場合:

```bash
EVAL_API_BASE_URL=http://localhost:8000 \
  uv run python -m evaluation.run_evaluation --split train
```

## 3. 最終評価

trainの失敗分析と改善を終えた後に実行します。

```bash
uv run python -m evaluation.run_evaluation --split test
```

主な指標は分類精度、未確定率、誤分類率、平均追加質問数、カテゴリ別精度、曖昧表現別精度です。追加質問回答モデルは`EVAL_SIMULATOR_MODEL_ID`で変更できます。
