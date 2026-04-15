# 使い方

## テスト実行の流れ

1. シナリオファイル（`e2e-scenarios.md`）を用意する
2. API エンドポイントにリポジトリ URL・テスト対象 URL を POST する
3. 結果を S3 から取得する（または通知を待つ）

---

## API リファレンス

### POST /tests — テスト実行

**リクエスト**

```bash
curl -X POST https://<api-endpoint>/prod/tests \
  -H "Content-Type: application/json" \
  -H "x-api-key: <api-key>" \
  -d '{
    "repo_url": "https://github.com/ot-nemoto/eval-hub",
    "target_url": "https://eval-hub.example.com"
  }'
```

| フィールド | 型 | 必須 | デフォルト | 説明 |
|---|---|:---:|---|---|
| `repo_url` | string | ✅ | — | シナリオファイルを含むリポジトリ URL |
| `target_url` | string | ✅ | — | テスト対象サービスの URL |
| `scenarios_path` | string | | `docs/e2e-scenarios.md` | シナリオファイルのパス |
| `testing_path` | string | | — | テスト方針ファイルのパス（省略可） |

**レスポンス**

```json
{
  "execution_id": "exec-20260415-143022",
  "status": "submitted",
  "message": "テストジョブを受け付けました"
}
```

---

## リポジトリの構成パターン

シナリオファイルはアプリリポジトリに置く必要はなく、用途に応じて自由に構成できる。

### パターン 1: アプリリポジトリにシナリオを置く

```bash
curl -d '{
  "repo_url": "https://github.com/ot-nemoto/eval-hub",
  "target_url": "https://eval-hub.example.com"
}'
```

```
eval-hub/
└── docs/
    ├── e2e-scenarios.md   ← デフォルトパスで読み込まれる
    └── testing.md
```

### パターン 2: シナリオ専用リポジトリで一元管理

複数サービスの E2E テストを 1 つのリポジトリにまとめて管理できる。

```bash
# eval-hub のテスト
curl -d '{
  "repo_url": "https://github.com/ot-nemoto/e2e-scenarios",
  "target_url": "https://eval-hub.example.com",
  "scenarios_path": "eval-hub/e2e-scenarios.md",
  "testing_path": "eval-hub/testing.md"
}'

# another-service のテスト（同じリポジトリから）
curl -d '{
  "repo_url": "https://github.com/ot-nemoto/e2e-scenarios",
  "target_url": "https://another-service.example.com",
  "scenarios_path": "another-service/e2e-scenarios.md"
}'
```

```
e2e-scenarios/              ← シナリオ専用リポジトリ
├── eval-hub/
│   ├── e2e-scenarios.md
│   └── testing.md
├── another-service/
│   └── e2e-scenarios.md
└── policies/
    └── common.md
```

### パターン 3: 環境ごとにテスト対象 URL を切り替える

同じシナリオをステージング・本番で使い回せる。

```bash
# ステージング
curl -d '{
  "repo_url": "https://github.com/ot-nemoto/eval-hub",
  "target_url": "https://staging.eval-hub.example.com"
}'

# 本番
curl -d '{
  "repo_url": "https://github.com/ot-nemoto/eval-hub",
  "target_url": "https://eval-hub.example.com"
}'
```

---

## テスト仕様の書き方

### e2e-scenarios.md（テストシナリオ）

自然言語でシナリオを記述する。見出し（`##`）で各シナリオを区切る。  
`target_url` はリクエストパラメータで指定するため、ファイル内への記載は不要。

```markdown
## シナリオ 1: トップページの表示確認
トップページ（/）にアクセスし、ページタイトルが「EvalHub」であることを確認する。

## シナリオ 2: ログイン
ログインページにアクセスし、メールアドレスとパスワードを入力してログインボタンをクリック。
ダッシュボード（/dashboard）にリダイレクトされることを確認する。

## シナリオ 3: ログアウト
ログイン状態でヘッダーのユーザーアイコンをクリックし、ログアウトを選択。
トップページに戻ることを確認する。
```

### testing.md（テスト方針）— 省略可

前提条件・注意事項・認証情報の扱いなどを記載する。省略した場合はシナリオのみで実行される。

```markdown
## 前提条件
- テストユーザー: test@example.com / password123
- テスト前のデータリセットは不要

## 注意事項
- 本番データを変更しないこと
```

---

## テスト結果

### S3 保存先

```
s3://auto-pilot-g4-results/{execution_id}/
├── result.json          # サマリー
├── steps.json           # ステップ詳細
└── screenshots/
    ├── step-01.png
    ├── step-02.png
    └── ...
```

### result.json の構造

```json
{
  "execution_id": "exec-20260415-143022",
  "repo_url": "https://github.com/ot-nemoto/eval-hub",
  "target_url": "https://eval-hub.example.com",
  "scenarios_path": "docs/e2e-scenarios.md",
  "status": "passed",
  "started_at": "2026-04-15T14:30:22Z",
  "finished_at": "2026-04-15T14:45:10Z",
  "scenarios": [
    {
      "name": "シナリオ 1: トップページの表示確認",
      "status": "passed",
      "duration_sec": 12
    },
    {
      "name": "シナリオ 2: ログイン",
      "status": "passed",
      "duration_sec": 28
    }
  ],
  "error": null
}
```

### ステータス値

| ステータス | 説明 |
|---|---|
| `submitted` | ジョブ投入済み、EC2 起動待ち |
| `running` | テスト実行中 |
| `passed` | 全シナリオ成功 |
| `failed` | 1 件以上のシナリオが失敗 |
| `error` | システムエラー（シナリオ実行前に失敗） |

---

## 通知

SNS または Slack Webhook で完了通知を受け取れる。

```json
{
  "execution_id": "exec-20260415-143022",
  "status": "passed",
  "repo_url": "https://github.com/ot-nemoto/eval-hub",
  "target_url": "https://eval-hub.example.com",
  "result_url": "https://auto-pilot-g4-results.s3.amazonaws.com/exec-20260415-143022/result.json"
}
```
