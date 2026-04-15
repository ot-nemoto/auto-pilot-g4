"""
E2Eテストランナー（Gemma4 + PlaywrightMCP）

GitHub リポジトリのシナリオファイルを読み込み、
Gemma4 が解釈して PlaywrightMCP でブラウザテストを実行する。

使い方:
  # 全セクション実行
  python runner/run_test.py \\
    --target-url https://eval-hub-xi.vercel.app \\
    --scenarios-url https://github.com/ot-nemoto/eval-hub/blob/develop/docs/e2e-scenarios.md

  # 特定セクションのみ実行（部分一致）
  python runner/run_test.py \\
    --target-url https://eval-hub-xi.vercel.app \\
    --scenarios-url https://github.com/ot-nemoto/eval-hub/blob/develop/docs/e2e-scenarios.md \\
    --section "認証・リダイレクト"

  # テスト方針ファイルも渡す
  python runner/run_test.py \\
    --target-url https://eval-hub-xi.vercel.app \\
    --scenarios-url https://github.com/ot-nemoto/eval-hub/blob/develop/docs/e2e-scenarios.md \\
    --testing-url https://github.com/ot-nemoto/eval-hub/blob/develop/docs/testing.md \\
    --section "認証・リダイレクト"
"""

import argparse
import asyncio
import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = "gemma4:e4b"
MAX_TURNS = 30  # セクションあたりの最大ターン数


# ────────────────────────────────────────────────
# ユーティリティ
# ────────────────────────────────────────────────

def github_url_to_raw(url: str) -> str:
    """GitHub の blob URL を raw コンテンツ URL に変換"""
    pattern = r"https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)"
    match = re.match(pattern, url)
    if match:
        owner, repo, branch, path = match.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    return url  # すでに raw URL の場合はそのまま


def fetch_content(url: str) -> str:
    """URL からテキストコンテンツを取得"""
    raw_url = github_url_to_raw(url)
    req = urllib.request.Request(raw_url, headers={"User-Agent": "auto-pilot-g4"})
    with urllib.request.urlopen(req) as response:
        return response.read().decode("utf-8")


def parse_sections(markdown: str) -> dict[str, str]:
    """マークダウンを ## 見出しごとにセクション分割"""
    sections = {}
    current_title = None
    current_lines: list[str] = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            if current_title is not None:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = line[3:].strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        sections[current_title] = "\n".join(current_lines).strip()

    return sections


def mcp_tool_to_ollama_tool(mcp_tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema,
        },
    }


# ────────────────────────────────────────────────
# プロンプト構築
# ────────────────────────────────────────────────

def build_system_prompt(target_url: str, testing_content: str = "") -> str:
    prompt = f"""あなたはE2Eテストを実行するエージェントです。
PlaywrightMCPのツールを使ってブラウザを操作し、与えられたテスト項目を一つずつ確認してください。

## テスト対象URL
{target_url}

## 実行ルール
- 各確認項目について、実際にブラウザで操作・確認を行うこと
- URLへのアクセスは必ず {target_url} をベースにすること（外部サイトにはアクセスしない）
- 各項目の結果を以下の形式で報告すること:
    ✅ PASS: [確認項目]
    ❌ FAIL: [確認項目] - [失敗理由]
    ⚠️ SKIP: [確認項目] - [スキップ理由]
- 全項目の確認が終わったら、最後に以下のサマリーを出力すること:
    ## サマリー
    PASS: X件 / FAIL: Y件 / SKIP: Z件"""

    if testing_content:
        prompt += f"\n\n## テスト方針・前提条件\n{testing_content}"

    return prompt


# ────────────────────────────────────────────────
# セクション実行
# ────────────────────────────────────────────────

async def run_section(
    session,
    ollama_tools: list,
    section_name: str,
    section_content: str,
    target_url: str,
    testing_content: str = "",
) -> dict:
    print(f"\n{'=' * 60}")
    print(f"▶ セクション: {section_name}")
    print(f"{'=' * 60}")

    system_prompt = build_system_prompt(target_url, testing_content)
    user_prompt = (
        f"以下のテスト項目をすべて実行してください。\n\n"
        f"## {section_name}\n{section_content}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    tool_calls_log = []
    start_time = time.time()
    final_answer = ""
    error_msg = ""
    success = False

    try:
        for turn in range(MAX_TURNS):
            response = ollama.chat(
                model=MODEL,
                messages=messages,
                tools=ollama_tools,
            )
            msg = response.message

            # ツール呼び出しなし → 最終回答
            if not msg.tool_calls:
                final_answer = msg.content or ""
                print(f"\n📋 結果:\n{final_answer}")
                success = True
                break

            messages.append(msg)

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = tool_call.function.arguments or {}
                print(f"🔧 {name}({json.dumps(args, ensure_ascii=False)[:100]})")

                result = await session.call_tool(name, args)
                content = result.content[0].text if result.content else ""
                is_error = "### Error" in content

                tool_calls_log.append({
                    "tool": name,
                    "args": args,
                    "success": not is_error,
                })

                status_icon = "❌" if is_error else "✅"
                print(f"   {status_icon} {content[:150]}{'...' if len(content) > 150 else ''}")

                messages.append({"role": "tool", "content": content})

        else:
            # MAX_TURNS 到達
            error_msg = f"MAX_TURNS ({MAX_TURNS}) に達しました"
            print(f"⚠️  {error_msg}")

    except Exception as e:
        error_msg = str(e)
        print(f"❌ 例外: {error_msg}")

    elapsed = time.time() - start_time

    return {
        "section": section_name,
        "success": success,
        "elapsed_sec": round(elapsed, 1),
        "tool_calls_count": len(tool_calls_log),
        "tool_calls": tool_calls_log,
        "answer": final_answer,
        "error": error_msg,
    }


# ────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    # シナリオ取得
    print(f"▶ シナリオ取得中: {args.scenarios_url}")
    scenarios_content = fetch_content(args.scenarios_url)

    # テスト方針取得（任意）
    testing_content = ""
    if args.testing_url:
        print(f"▶ テスト方針取得中: {args.testing_url}")
        testing_content = fetch_content(args.testing_url)

    # セクション分割
    sections = parse_sections(scenarios_content)
    print(f"\n✅ セクション一覧 ({len(sections)}件):")
    for title in sections:
        print(f"   - {title}")

    # セクション絞り込み（--section 指定時）
    if args.section:
        sections = {k: v for k, v in sections.items() if args.section in k}
        if not sections:
            print(f"\n❌ セクション '{args.section}' が見つかりません")
            return
        print(f"\n▶ 実行対象: {list(sections.keys())}")

    # PlaywrightMCP 起動
    print(f"\n▶ PlaywrightMCPサーバーに接続中...")
    server_params = StdioServerParameters(
        command="npx",
        args=["@playwright/mcp", "--headless", "--browser", "chromium"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            ollama_tools = [mcp_tool_to_ollama_tool(t) for t in tools_result.tools]
            print(f"✅ ツール数: {len(ollama_tools)}個")

            # セクションを順に実行
            results = []
            for section_name, section_content in sections.items():
                result = await run_section(
                    session=session,
                    ollama_tools=ollama_tools,
                    section_name=section_name,
                    section_content=section_content,
                    target_url=args.target_url,
                    testing_content=testing_content,
                )
                results.append(result)

            # サマリー表示
            print(f"\n{'=' * 60}")
            print("📊 実行サマリー")
            print(f"{'=' * 60}")
            completed = sum(1 for r in results if r["success"])
            total_time = sum(r["elapsed_sec"] for r in results)
            print(f"完了: {completed}/{len(results)} セクション  合計時間: {total_time:.0f}秒\n")

            for r in results:
                icon = "✅" if r["success"] else "❌"
                print(
                    f"{icon} {r['section']}"
                    f"  ({r['elapsed_sec']}秒 / ツール{r['tool_calls_count']}回)"
                )
                if r["error"]:
                    print(f"   ⚠️  {r['error']}")

            # JSON 保存
            output_dir = Path("results")
            output_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"result_{ts}.json"
            output_path.write_text(
                json.dumps(
                    {
                        "executed_at": ts,
                        "target_url": args.target_url,
                        "scenarios_url": args.scenarios_url,
                        "testing_url": args.testing_url,
                        "section_filter": args.section,
                        "results": results,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            print(f"\n💾 結果保存: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="E2Eテストランナー（Gemma4 + PlaywrightMCP）"
    )
    parser.add_argument(
        "--target-url", required=True,
        help="テスト対象サービスの URL (例: https://eval-hub-xi.vercel.app)",
    )
    parser.add_argument(
        "--scenarios-url", required=True,
        help="シナリオファイルの URL (GitHub blob URL または raw URL)",
    )
    parser.add_argument(
        "--testing-url",
        help="テスト方針ファイルの URL（省略可）",
    )
    parser.add_argument(
        "--section",
        help="実行するセクション名の部分一致フィルター（省略時は全セクション）",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
