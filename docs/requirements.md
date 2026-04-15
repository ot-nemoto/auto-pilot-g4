# 要件定義

## 機能要件

### FR-01: テスト実行リクエスト受付

- API エンドポイント（POST /tests）でテスト実行を受け付ける
- レスポンスとして実行 ID（`execution_id`）を即時返却する

```json
// リクエスト
{
  "repo_url": "https://github.com/ot-nemoto/eval-hub",  // 必須
  "target_url": "https://eval-hub.example.com",          // 必須
  "scenarios_path": "docs/e2e-scenarios.md",              // 省略可（デフォルト値）
  "testing_path": "docs/testing.md"                       // 省略可
}

// レスポンス
{
  "execution_id": "exec-20260415-001",
  "status": "submitted"
}
```

| フィールド | 必須 | デフォルト | 説明 |
|---|:---:|---|---|
| `repo_url` | ✅ | — | シナリオファイルを含むリポジトリ URL |
| `target_url` | ✅ | — | テスト対象サービスの URL |
| `scenarios_path` | | `docs/e2e-scenarios.md` | シナリオファイルのパス |
| `testing_path` | | — | テスト方針ファイルのパス |

### FR-02: テスト仕様の読み込み

- 指定されたリポジトリから `scenarios_path` のファイルを取得する
- `testing_path` が指定された場合はテスト方針ファイルも取得する
- `scenarios_path` のファイルが存在しない場合はエラーを返す
- リポジトリはアプリリポジトリ・シナリオ専用リポジトリのどちらでも可

### FR-03: テストシナリオの実行

- Gemma4 がシナリオファイルの内容（および方針ファイルがあればその内容）を解釈する
- `target_url` を起点としてブラウザテストを実行する
- PlaywrightMCP を通じて Chromium を操作する
- ツール呼び出しが失敗した場合、Gemma4 が原因を分析して再試行する（最大 3 回）

### FR-04: テスト結果の保存

- テスト完了後、以下を S3 に保存する

```
s3://auto-pilot-g4-results/{execution_id}/
├── result.json          # テスト結果サマリー
├── steps.json           # ステップごとの詳細ログ
└── screenshots/
    └── step-{n}.png     # 各ステップのスクリーンショット
```

### FR-05: 完了通知

- テスト完了（成功・失敗問わず）後に SNS または Slack Webhook へ通知する
- 通知内容：実行 ID・結果（passed/failed/error）・S3 結果 URL

---

## 非機能要件

### NFR-01: 実行時間

- テスト実行全体の時間は問わない（コールドスタート含め 10〜20 分を許容）

### NFR-02: スケールゼロ

- テスト未実行時は EC2 インスタンスを起動しない
- アイドルコストを発生させない

### NFR-03: 再現性

- Docker コンテナで実行環境を統一する
- 同じシナリオ・同じ `target_url` で実行した場合、同等の結果が得られること

### NFR-04: セキュリティ

- API エンドポイントは認証（API キーまたは IAM）で保護する
- テスト結果の S3 バケットは非公開とし、署名付き URL でアクセスする
- EC2 の IAM ロールは最小権限（S3 書き込み・SNS 発行のみ）とする

### NFR-05: 可観測性

- 全ての実行ログを CloudWatch Logs に収集する
- エラー発生時はログから原因を特定できること

---

## テスト仕様フォーマット

### e2e-scenarios.md（テストシナリオ）

各シナリオを自然言語で記述する。見出し（`##`）で区切る。  
テスト対象 URL は `target_url` パラメータで渡されるため、ファイル内への記載は不要。

```markdown
## シナリオ 1: ログイン確認
ログインページにアクセスし、メールアドレスとパスワードを入力してログインできることを確認する。
ログイン後、ダッシュボードページが表示されることを確認する。

## シナリオ 2: 商品一覧表示
ログイン後、商品一覧ページを開き、商品が 1 件以上表示されることを確認する。
```

### testing.md（テスト方針）— 省略可

前提条件・認証情報の扱い・注意事項を記載する。省略した場合はシナリオのみで実行される。

```markdown
## 前提条件
- テストユーザー: test@example.com / password123
- テスト実行前にデータのリセットは不要

## 注意事項
- 購入フローは実際に決済しないこと
```

---

## リポジトリ構成パターン

シナリオファイルの置き場所は自由。代表的なパターンは以下の通り。

```
# パターン 1: アプリリポジトリにシナリオを置く
my-app/
└── docs/
    ├── e2e-scenarios.md
    └── testing.md

# パターン 2: シナリオ専用リポジトリで複数サービスを一元管理
e2e-scenarios/
├── my-app/
│   ├── e2e-scenarios.md
│   └── testing.md
├── another-service/
│   └── e2e-scenarios.md
└── policies/
    └── common.md
```
