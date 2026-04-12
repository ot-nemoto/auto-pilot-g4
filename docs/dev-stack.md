# 開発基盤 検討

## 構成コンポーネントと必要な技術の整理

まず各コンポーネントで何が必要かを洗い出す。

```
┌─────────────────────────────────────────────────────────┐
│ 1. インフラ定義 (IaC)                                    │
│    API GW / Lambda / Batch / ECR / S3 / VPC / IAM 等    │
├─────────────────────────────────────────────────────────┤
│ 2. Lambda（オーケストレーター）                           │
│    Batch SubmitJob を呼び出すだけ                        │
├─────────────────────────────────────────────────────────┤
│ 3. コンテナ（auto-pilot-runner）                         │
│    ・Gemma4 推論                                         │
│    ・Playwright 実行                                     │
│    ・S3 結果アップロード                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 1. IaC: CFN vs CDK

### CloudFormation（生YAML/JSON）

- **メリット**: 追加ツール不要、AWS ネイティブ
- **デメリット**: 記述量が膨大、ループや条件分岐が書きにくい、型補完なし

### CDK（推奨）

- **メリット**: プログラムで記述できる、型補完あり、L2 Constructで定型処理を抽象化
- **デメリット**: Node.js（CDK CLI）が必須、CloudFormationに変換されるため挙動の把握が必要

### CDK の言語選択

| 言語 | メリット | デメリット |
|------|----------|------------|
| **TypeScript（推奨）** | 型補完が最も充実、CDKの第一級市民 | Node.js環境が必要 |
| Python | コンテナ側と言語統一可能 | 型補完がTSより弱い |

**→ CDK（TypeScript）を推奨**
理由: CDKのサンプル・ドキュメントはTSが最も充実しており、インフラとアプリで言語が違っても実害は少ない。

---

## 2. Lambda（オーケストレーター）

役割はシンプル：
- リクエストのバリデーション
- AWS Batch `SubmitJob` API の呼び出し
- `jobId` をレスポンスとして返却

### 言語選択

| 言語 | コールドスタート | SDK | 判断 |
|------|---------------|-----|------|
| Python 3.12 | 速い | boto3（標準） | **推奨** |
| Node.js 22 | 速い | @aws-sdk/client-batch | CDKと同じ言語で統一したい場合 |

**→ Python 推奨**
Lambdaのロジックが単純なので、boto3 が標準添付で追加パッケージ不要な Python が手軽。

---

## 3. コンテナ（auto-pilot-runner）

最も技術選定が重要。2つのサブコンポーネントがある。

### 3-1. Gemma4 推論

| 方式 | 説明 | メリット | デメリット |
|------|------|----------|------------|
| **Ollama** | Gemma4をOllamaサーバとして起動、REST APIで呼び出し | 設定簡単、モデル管理が楽 | デーモン起動が必要、コンテナ設計が複雑 |
| **llama-cpp-python** | Python バインディングで直接推論 | シンプル、GPU/CPU両対応 | ビルドが複雑（CUDA対応時） |
| **Hugging Face transformers** | transformers ライブラリで推論 | Python標準的、エコシステム豊富 | メモリ使用量が多い |

**→ llama-cpp-python 推奨（CPUの場合）/ transformers（GPUの場合）**

### 3-2. Playwright

| 言語 | パッケージ | 判断 |
|------|-----------|------|
| **Python** | `playwright` (pip) | Gemma4推論と同じ言語で統一できる |
| Node.js/TypeScript | `@playwright/test` (npm) | 公式推奨、型補完・エコシステムが豊富 |

**→ 言語統一の観点から Python 推奨**
コンテナ内で Python 1本に絞ることでランタイムの複雑さを排除できる。
Playwright Python版はNode版と機能的にほぼ同等。

### コンテナのエントリーポイント（Python）

```python
# runner.py
import os
from llama_cpp import Llama
from playwright.sync_api import sync_playwright
import boto3, json

TEST_PROMPT = os.environ["TEST_PROMPT"]
TARGET_URL   = os.environ["TARGET_URL"]
EXECUTION_ID = os.environ["EXECUTION_ID"]
RESULT_BUCKET = os.environ["RESULT_BUCKET"]

# 1. Gemma4でPlaywrightコード生成
llm = Llama(model_path="/models/gemma4.gguf", n_gpu_layers=-1)
code = llm.create_completion(system_prompt + TEST_PROMPT)

# 2. Playwright実行
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    exec(code)  # ※ サンドボックス化が必要

# 3. S3に結果保存
boto3.client("s3").put_object(...)
```

---

## 開発環境 必要スタック 一覧

| ツール | 用途 | 必須 |
|--------|------|------|
| **Node.js 22+** | CDK CLI の実行 | ◎ 必須 |
| **AWS CDK CLI** (`npm i -g aws-cdk`) | `cdk synth / deploy` | ◎ 必須 |
| **Python 3.12+** | Lambda / コンテナ開発 | ◎ 必須 |
| **Docker Desktop** | コンテナビルド・ローカルテスト | ◎ 必須 |
| **AWS CLI v2** | 認証・デプロイ補助 | ◎ 必須 |
| **uv**（pip代替） | Python パッケージ管理（高速） | ○ 推奨 |
| **Ollama**（ローカル） | Gemma4 のローカル動作確認 | ○ 推奨 |
| `playwright` (pip) | ローカルでPlaywright動作確認 | ○ 推奨 |

---

## リポジトリ構成案

```
auto-pilot-g4/
├── docs/                        # 設計ドキュメント（現在）
├── infra/                       # CDK プロジェクト（TypeScript）
│   ├── bin/
│   │   └── app.ts               # CDK App エントリーポイント
│   ├── lib/
│   │   ├── network-stack.ts     # VPC / Security Group
│   │   ├── storage-stack.ts     # S3 / ECR
│   │   ├── batch-stack.ts       # AWS Batch（Job Def / Queue / CE）
│   │   └── api-stack.ts         # API GW / Lambda
│   ├── package.json
│   └── tsconfig.json
├── runner/                      # コンテナ（Python）
│   ├── Dockerfile
│   ├── runner.py                # エントリーポイント
│   ├── prompt_builder.py        # Gemma4へのプロンプト組み立て
│   ├── test_executor.py         # Playwright実行
│   ├── result_uploader.py       # S3アップロード
│   └── requirements.txt
└── lambda/                      # オーケストレーター Lambda（Python）
    ├── handler.py
    └── requirements.txt
```

---

## デプロイフロー

```
ローカル開発
  │
  ├── runner/ → docker build → ECR push
  │    └── aws ecr get-login-password | docker login
  │        docker build -t auto-pilot-runner .
  │        docker tag / push
  │
  ├── infra/ → cdk deploy
  │    └── cd infra && cdk deploy --all
  │
  └── lambda/ → cdk deploy で自動パッケージ
```

---

## 未決事項

- [ ] CDK の言語: TypeScript or Python（チームの好みに合わせて）
- [ ] Gemma4 推論ライブラリ: llama-cpp-python or transformers
- [ ] モデルの配置: S3 / EFS / AMI 内包（ec2-vs-fargate.md 参照）
- [ ] Python パッケージ管理: pip / uv / poetry
- [ ] CI/CD: GitHub Actions で ECR push + cdk deploy を自動化するか
