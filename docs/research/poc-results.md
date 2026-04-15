# PoC 検証結果

## 検証環境

| 項目 | 内容 |
|------|------|
| マシン | Intel Core i7-1165G7 / RAM 32GB / Intel Iris Xe（内蔵GPU） |
| OS | Windows 11 + WSL2 + Docker Desktop |
| 開発環境 | devcontainer（Ubuntu 24.04） |
| Ollama | ローカルインストール済み |

---

## タスク0-2: Gemma4モデルのダウンロード

### 試したモデル

| モデル | サイズ | 結果 |
|--------|--------|------|
| `gemma3` | 3.3GB | ✅ ダウンロード・起動成功 |
| `gemma4:e4b` | 9.6GB | ⚠️ ダウンロード成功・起動はメモリ不足で失敗→WSL2メモリ増量後に成功 |

### メモリ問題

`gemma4:e4b` は 9.8GB のメモリを要求するが、WSL2のデフォルト割り当てでは不足。

```
Error: model requires more system memory (9.8 GiB) than is available (8.5 GiB)
```

**対処**: `C:\Users\nemoto\.wslconfig` で WSL2 メモリを増量。

```ini
[wsl2]
memory=20GB
swap=8GB
```

---

## タスク0-3: プロンプト→コード生成の確認

### 検証プロンプト

```
Playwrightを使ってPythonでgoogle.comにアクセスしてタイトルが'Google'であることを確認するテストコードを書いて
```

### gemma3 の生成結果

```python
# gemma3が生成したコード（抜粋）
page = Page()                          # ❌ 直接インスタンス化（誤り）
title = page.title                     # ❌ プロパティ扱い（メソッドが正しい）
request.add_work_item("page", page)    # ❌ 存在しないAPI
```

**評価**: そのままでは動作しない。Playwright APIの理解が不正確。

---

### gemma4:e4b の生成結果

```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()        # ✅ 正しい取得方法
    await page.goto("https://www.google.com")
    actual_title = await page.title()      # ✅ メソッドとして呼び出し
    assert actual_title == expected_title
    await context.close()
    await browser.close()                  # ✅ 適切なクリーンアップ
```

**評価**: ほぼそのまま動作する品質。async/awaitも正しく使用。

### モデル別コード品質比較

| 評価項目 | gemma3 | gemma4:e4b |
|----------|--------|-----------|
| `Page` の取得方法 | ❌ 直接インスタンス化 | ✅ `context.new_page()` |
| `page.title` の扱い | ❌ プロパティ | ✅ `await page.title()` |
| async/await の使用 | ❌ 未使用 | ✅ 正しく使用 |
| コンテキスト管理 | ❌ なし | ✅ 適切に close() |
| そのまま動作するか | ❌ 要修正 | ✅ ほぼ動作する |

---

## タスク0-4: 生成コードの実行確認

`gemma4:e4b` の生成コードをベースに調整したスクリプト: `poc/test_google.py`

```bash
python poc/test_google.py
```

**結果**: ✅ 成功

```
➡️  google.com にアクセス中...
✅ 実際のタイトル: 'Google'
✅ 期待されるタイトル: 'Google'

🎉 テスト成功: ページタイトルは 'Google' でした。
```

Gemma4:e4b が生成したコードをベースとしたPlaywrightテストが正常に動作することを確認。

---

## 推論速度（CPU推論）

| 項目 | 計測値 |
|------|--------|
| 推論方式 | CPU（Intel i7-1165G7）|
| GPUサポート | なし（Intel Iris Xe は非対応） |
| トークン生成速度 | 2〜5 tok/秒（目安） |
| コード生成時間（500token） | 約2〜4分 |

**補足**: Apple Silicon Mac（M2以降）であればMetal GPU推論で30〜80 tok/秒程度まで高速化できる。

---

---

## PlaywrightMCP + Gemma4 連携検証（タスク0-5 前半）

### アーキテクチャ

```
Ollama(Gemma4:e4b)
    ↓ tool_calls（function calling）
Python MCPクライアント（poc/test_playwright_mcp.py）
    ↓ stdio
PlaywrightMCP Server（@playwright/mcp）
    ↓ Playwright API
Chromium（headless）
```

### 検証スクリプト

`poc/test_playwright_mcp.py`

```bash
python poc/test_playwright_mcp.py
```

### 実行結果

```
▶ PlaywrightMCPサーバーに接続中...
✅ ツール数: 21個
   - browser_navigate, browser_click, browser_snapshot ...

▶ Gemma4 に送信: google.comにアクセスして、ページのタイトルを教えてください。

🔧 ツール呼び出し: browser_navigate({"url": "https://www.google.com"})
   → 結果: ### Ran Playwright code ...

🎉 Gemma4の回答:
google.comのページのタイトルは「Google」です。
```

**結果**: ✅ 成功

### トラブルシュート記録

| エラー | 原因 | 対処 |
|--------|------|------|
| `chrome not found at /opt/google/chrome` | PlaywrightMCPがChromeを探した | `--browser chromium` オプションを追加 |
| `Browser "chrome-for-testing" is not installed` | npm版Playwrightのブラウザ未インストール | `npx playwright install chromium` を実行 |

### コード生成 vs PlaywrightMCP 比較

| 観点 | コード生成アプローチ | PlaywrightMCPアプローチ |
|------|---------------------|------------------------|
| セキュリティ | ❌ exec()が必要 | ✅ 不要 |
| 安定性 | △ 生成コード品質に依存 | ✅ 構造化ツール呼び出し |
| 実装シンプルさ | △ コード実行基盤が必要 | ✅ MCPが抽象化 |
| エラーハンドリング | △ 生成コード次第 | ✅ ツール単位で制御可能 |

**→ PlaywrightMCPアプローチを採用する**

---

## 現時点の結論

| 項目 | 結論 |
|------|------|
| Gemma4 + PlaywrightMCP | ✅ 動作確認済み。コード生成より安全・安定 |
| 採用アーキテクチャ | Gemma4 → MCPツール呼び出し → PlaywrightMCP → ブラウザ |
| Gemma4でのコード生成 | ✅ 品質は高いが、PlaywrightMCPの方が優れるため不採用 |
| ローカル推論速度 | △ CPU推論のため遅い（PoC用途では許容範囲） |
| 本番環境（GPU） | AWS g4dn.xlarge（NVIDIA T4）で大幅改善見込み |

---

---

## 複数プロンプト品質評価（タスク0-5）

`poc/test_multi_prompt.py` で5シナリオを実行。

### 結果サマリー

**5/5 全シナリオ成功**

| # | シナリオ | 結果 | 実行時間 | ツール呼び出し数 |
|---|---------|------|---------|---------------|
| 1 | タイトル確認 | ✅ | 341秒 | 1回 |
| 2 | ページ内テキスト確認 | ✅ | 188秒 | 2回 |
| 3 | スクリーンショット取得 | ✅ | 89秒 | 2回 |
| 4 | 複数ステップ操作 | ✅ | 236秒 | 2回 |
| 5 | リンク確認 | ✅ | 307秒 | 3回（エラー自己回復あり） |

### 注目すべき観察

**エラー自己回復（シナリオ5）**

1回目のツール呼び出しでSyntaxErrorが発生したが、Gemma4が自動的に修正して再試行し成功。

```
🔧 browser_run_code({"code": "await page.evaluate(..."})
   → ❌ エラー: SyntaxError: Unexpected identifier 'page'
🔧 browser_run_code({"code": "async (page) => { ... }"})  ← 自動修正
   → ✅ 成功
```

**適切なツール選択**

シナリオに応じて `browser_navigate` / `browser_evaluate` / `browser_run_code` / `browser_take_screenshot` を自律的に使い分けた。

### 実行時間について

CPU推論（Intel i7-1165G7）のため1シナリオあたり89〜341秒かかった。
本番環境（AWS g4dn.xlarge / NVIDIA T4 GPU）では10〜50倍の高速化が見込まれる。

---

## PoC 最終結論（タスク0-6）

### 採用アーキテクチャ

```
自然言語プロンプト
    ↓
Gemma4:e4b（Ollama）
    ↓ function calling（MCPツール呼び出し）
PlaywrightMCP Server
    ↓ Playwright API
Chromium（headless）
    ↓
テスト結果
```

### 判断基準の達成状況

| 判断基準 | 結果 |
|---------|------|
| 自然言語の指示からブラウザを操作できる | ✅ |
| 実際にブラウザを操作できる | ✅ |
| 異なるプロンプトでも安定して動作する | ✅ 5/5成功・エラー自己回復も確認 |

### 採用・不採用の決定

| 方式 | 決定 | 理由 |
|------|------|------|
| Gemma4 + PlaywrightMCP（MCPツール呼び出し） | ✅ **採用** | 安全・安定・シンプル |
| Gemma4 + コード生成 + exec() | ❌ 不採用 | セキュリティリスク・品質不安定 |

### 次フェーズへの課題

- **推論速度**: CPU推論では遅すぎる → 本番はGPU（g4dn.xlarge）必須
- **インフラ構成**: PlaywrightMCPをコンテナ内で動かす設計が必要
- **モデルサイズ**: gemma4:e4b（9.6GB）が前提 → コンテナイメージが大きい
