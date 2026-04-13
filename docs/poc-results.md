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

## 現時点の結論

| 項目 | 結論 |
|------|------|
| Gemma4でのコード生成 | ✅ 実用的な品質のPlaywrightコードを生成できる |
| gemma3との差 | 明確にgemma4の方が品質が高い |
| ローカル推論速度 | △ CPU推論のため遅い（PoC用途では許容範囲） |
| 本番環境（GPU） | AWS g4dn.xlarge（NVIDIA T4）で大幅改善見込み |

---

## 未実施・次のステップ

- [ ] `poc/test_google.py` の実行確認（タスク0-4）
- [ ] 複数パターンのプロンプトで品質評価（タスク0-5）
- [ ] PoC結論まとめ・インフラ構成の最終決定（タスク0-6）
