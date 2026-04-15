# プロダクト概要

## システム名

**auto-pilot-g4** — Gemma4 × Playwright 自動E2Eテストシステム

## 概要

自然言語で書かれたテストシナリオを読み込み、LLM（Gemma4）が内容を解釈して Playwright でブラウザ操作を自動実行するシステム。

テスト対象リポジトリに `docs/testing.md`（テスト方針）と `docs/e2e-scenarios.md`（テストシナリオ）を置くだけで、コードを書かずに E2E テストを実行できる。

## 利用イメージ

```
# GitHub リポジトリを指定してテスト実行
POST /tests
{
  "repo_url": "https://github.com/ot-nemoto/eval-hub"
}

# テスト完了後 → S3 に結果保存 & 通知
```

テスト対象リポジトリの構成：

```
(対象リポジトリ)
└── docs/
    ├── testing.md        ← テスト方針・前提条件
    └── e2e-scenarios.md  ← 実行するテストシナリオ（自然言語）
```

## 主要機能

| 機能 | 説明 |
|------|------|
| シナリオ読み込み | GitHub リポジトリ URL から `docs/testing.md` と `docs/e2e-scenarios.md` を取得 |
| LLM 解釈・実行 | Gemma4 がシナリオを解釈し、PlaywrightMCP ツール経由でブラウザ操作を実行 |
| 自己修復 | ツール失敗時に Gemma4 が原因を分析して再試行 |
| 結果保存 | テスト結果（pass/fail）・スクリーンショットを S3 に保存 |
| 完了通知 | SNS / Slack Webhook でテスト完了を通知 |

## 現フェーズのスコープ外

- リアルタイム結果確認 UI
- テスト結果の差分比較・トレンド分析
- 複数シナリオの並列実行
