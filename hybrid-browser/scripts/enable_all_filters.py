import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        page = await context.new_page()
        ubol_id = "ddkjiahejlhfcafbddmgiahcphecmpfh"
        await page.goto(f"chrome-extension://{ubol_id}/dashboard.html")
        await page.wait_for_timeout(1000)
        
        # Navigate to Filter lists pane
        await page.locator('button[data-pane="rulesets"]').click()
        await page.wait_for_timeout(1000)
        
        # Expand any collapsed categories (Ads, Annoyances, etc.)
        headers = page.locator('summary')
        count = await headers.count()
        for i in range(count):
            try:
                await headers.nth(i).click()
            except Exception:
                pass
        await page.wait_for_timeout(1000)
        
        # Check all checkboxes that are not checked
        checkboxes = page.locator('section[data-pane="rulesets"] input[type="checkbox"]:not(:checked)')
        cb_count = await checkboxes.count()
        print(f"Found {cb_count} unchecked filter lists to enable.")
        for i in range(cb_count):
            try:
                await checkboxes.nth(i).click(force=True)
            except Exception as e:
                print(f"Error clicking checkbox {i}: {e}")
                
        await page.wait_for_timeout(2000)
        await page.screenshot(path="/tmp/ubol_all_filters_enabled.png", full_page=True)
        print("All additional filters toggled.")
        await browser.close()

asyncio.run(main())
