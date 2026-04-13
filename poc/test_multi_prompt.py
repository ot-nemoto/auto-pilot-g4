"""
PlaywrightMCP + Gemma4 複数プロンプト品質評価

以下のシナリオで安定性を検証:
  1. タイトル確認（基本ナビゲーション）
  2. テキスト入力・検索
  3. スクリーンショット取得
  4. 複数ステップの操作
  5. ページ内要素の確認
"""

import asyncio
import json
import time
import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = "gemma4:e4b"

SCENARIOS = [
    {
        "id": 1,
        "name": "タイトル確認",
        "prompt": "https://example.com にアクセスして、ページのタイトルを教えてください。",
    },
    {
        "id": 2,
        "name": "ページ内テキスト確認",
        "prompt": "https://example.com にアクセスして、ページに 'Example Domain' というテキストが存在するか確認してください。",
    },
    {
        "id": 3,
        "name": "スクリーンショット取得",
        "prompt": "https://example.com にアクセスして、スクリーンショットを撮ってください。",
    },
    {
        "id": 4,
        "name": "複数ステップ操作",
        "prompt": "https://example.com にアクセスして、ページのタイトルとURLと、本文の最初の見出しテキストをすべて教えてください。",
    },
    {
        "id": 5,
        "name": "リンク確認",
        "prompt": "https://example.com にアクセスして、ページ内にリンクがいくつあるか、またそのリンク先のURLを教えてください。",
    },
]


def mcp_tool_to_ollama_tool(mcp_tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema,
        },
    }


async def run_scenario(session, ollama_tools, scenario) -> dict:
    """1シナリオを実行して結果を返す"""
    print(f"\n{'='*60}")
    print(f"シナリオ {scenario['id']}: {scenario['name']}")
    print(f"プロンプト: {scenario['prompt']}")
    print(f"{'='*60}")

    messages = [{"role": "user", "content": scenario["prompt"]}]
    tool_calls_log = []
    start_time = time.time()
    success = False
    final_answer = ""
    error_msg = ""

    try:
        # エージェントループ（最大10ターン）
        for turn in range(10):
            response = ollama.chat(
                model=MODEL,
                messages=messages,
                tools=ollama_tools,
            )
            msg = response.message

            # ツール呼び出しがない → 最終回答
            if not msg.tool_calls:
                final_answer = msg.content
                print(f"\n🎉 回答: {final_answer}")
                success = True
                break

            messages.append(msg)

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = tool_call.function.arguments or {}
                print(f"🔧 {name}({json.dumps(args, ensure_ascii=False)[:80]})")

                result = await session.call_tool(name, args)
                content = result.content[0].text if result.content else ""
                is_error = "### Error" in content

                tool_calls_log.append({
                    "tool": name,
                    "args": args,
                    "success": not is_error,
                })

                print(f"   → {'❌ エラー' if is_error else '✅ 成功'}: {content[:100]}")

                messages.append({
                    "role": "tool",
                    "content": content,
                })

    except Exception as e:
        error_msg = str(e)
        print(f"❌ 例外: {error_msg}")

    elapsed = time.time() - start_time

    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "success": success,
        "elapsed_sec": round(elapsed, 1),
        "tool_calls": tool_calls_log,
        "answer": final_answer,
        "error": error_msg,
    }


async def run():
    print(f"▶ PlaywrightMCPサーバーに接続中...")

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

            results = []
            for scenario in SCENARIOS:
                result = await run_scenario(session, ollama_tools, scenario)
                results.append(result)

            # サマリー表示
            print(f"\n{'='*60}")
            print("📊 評価サマリー")
            print(f"{'='*60}")
            passed = sum(1 for r in results if r["success"])
            print(f"結果: {passed}/{len(results)} 成功\n")

            for r in results:
                status = "✅" if r["success"] else "❌"
                tool_count = len(r["tool_calls"])
                print(f"{status} [{r['id']}] {r['name']} "
                      f"({r['elapsed_sec']}秒 / ツール呼び出し{tool_count}回)")
                if r["error"]:
                    print(f"   エラー: {r['error']}")


if __name__ == "__main__":
    asyncio.run(run())
