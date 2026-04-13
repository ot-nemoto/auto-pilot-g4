import asyncio
from playwright.async_api import async_playwright


async def test_google_page_title():
    """
    Google.comにアクセスし、ページタイトルが'Google'であることを検証するテスト。
    gemma4:e4b が生成したコードをベースに、単独実行できるよう調整。
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print("➡️  google.com にアクセス中...")
        await page.goto("https://www.google.com")

        actual_title = await page.title()
        expected_title = "Google"

        print(f"✅ 実際のタイトル: '{actual_title}'")
        print(f"✅ 期待されるタイトル: '{expected_title}'")

        assert actual_title == expected_title, (
            f"エラー: ページタイトルが期待値と異なります。"
            f"期待値: '{expected_title}', 実際: '{actual_title}'"
        )

        print("\n🎉 テスト成功: ページタイトルは 'Google' でした。")

        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_google_page_title())
