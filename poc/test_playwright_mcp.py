"""
PlaywrightMCP + Ollama(Gemma4) 連携 PoC

アーキテクチャ:
  Ollama(Gemma4) → tool_calls → Python MCP Client → PlaywrightMCP Server → ブラウザ

実行前に必要なもの:
  pip install "mcp[cli]" ollama
  npx @playwright/mcp (自動でインストール)
"""

import asyncio
import json
import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = "gemma4:e4b"
PROMPT = "google.comにアクセスして、ページのタイトルを教えてください。"


def mcp_tool_to_ollama_tool(mcp_tool) -> dict:
    """MCP形式のツール定義をOllama形式に変換"""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema,
        },
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

            # 利用可能なツール一覧を取得
            tools_result = await session.list_tools()
            ollama_tools = [mcp_tool_to_ollama_tool(t) for t in tools_result.tools]
            print(f"✅ ツール数: {len(ollama_tools)}個")
            for t in ollama_tools:
                print(f"   - {t['function']['name']}")

            # エージェントループ
            messages = [{"role": "user", "content": PROMPT}]
            print(f"\n▶ Gemma4 に送信: {PROMPT}\n")

            while True:
                response = ollama.chat(
                    model=MODEL,
                    messages=messages,
                    tools=ollama_tools,
                )
                msg = response.message

                # ツール呼び出しがない場合 → 最終回答
                if not msg.tool_calls:
                    print(f"\n🎉 Gemma4の回答:\n{msg.content}")
                    break

                # ツール呼び出しをMCPサーバーに転送
                messages.append(msg)
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = tool_call.function.arguments or {}
                    print(f"🔧 ツール呼び出し: {name}({json.dumps(args, ensure_ascii=False)})")

                    result = await session.call_tool(name, args)
                    content = result.content[0].text if result.content else ""
                    print(f"   → 結果: {content[:100]}{'...' if len(content) > 100 else ''}")

                    messages.append({
                        "role": "tool",
                        "content": content,
                    })


if __name__ == "__main__":
    asyncio.run(run())
