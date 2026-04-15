# 使い方

## テスト実行の流れ

1. テスト対象リポジトリに `docs/testing.md` と `docs/e2e-scenarios.md` を用意する
2. API エンドポイントにリポジトリ URL を POST する
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
    "repo_url": "https://github.com/ot-nemoto/eval-hub"
  }'
```

| フィールド | 型 | 必須 | 説明 |
|---|---|:---:|---|
| `repo_url` | string | ✅ | テスト仕様を含む GitHub リポジトリ URL |

**レスポンス**

```json
{
  "execution_id": "exec-20260415-143022",
  "status": "submitted",
  "message": "テストジョブを受け付けました"
}
```

---

## テスト仕様の書き方

### docs/testing.md（テスト方針）

テスト対象サービスの情報、前提条件、注意事項を記載する。

```markdown
## テスト対象
https://eval-hub.example.com

## 前提条件
- テストユーザー: test@example.com / password123
- テスト前のデータリセットは不要

## 注意事項
- 本番データを変更しないこと
```

### docs/e2e-scenarios.md（テストシナリオ）

自然言語でシナリオを記述する。見出し（`##`）で各シナリオを区切る。

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
  "result_url": "https://auto-pilot-g4-results.s3.amazonaws.com/exec-20260415-143022/result.json"
}
```
