"""
Simple verification script to check if signin button appears.
This confirms localhost is running smoothly.
"""
import asyncio
from playwright.async_api import async_playwright

async def verify_signin_button():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print("🔍 Navigating to /signin page...")
            await page.goto('http://localhost:3000/signin', timeout=30000, wait_until='domcontentloaded')
            
            print("⏳ Waiting 10 seconds for React to render...")
            await asyncio.sleep(10)
            
            print("⏳ Waiting for network idle...")
            try:
                await page.wait_for_load_state('networkidle', timeout=30000)
                print("✅ Network idle")
            except:
                print("⚠️ Network idle timeout, continuing...")
            
            print("🔍 Looking for signin button...")
            try:
                # Wait for signin button with data-testid
                signin_button = await page.wait_for_selector(
                    '[data-testid="signin-button"]', 
                    timeout=30000, 
                    state='visible'
                )
                print("✅ SUCCESS: Signin button found!")
                print(f"   Button text: {await signin_button.text_content()}")
                print("   ✅ Localhost is running smoothly!")
                return True
            except Exception as e:
                print(f"❌ FAILED: Signin button not found")
                print(f"   Error: {str(e)}")
                
                # Take screenshot for debugging
                await page.screenshot(path='testsprite_tests/signin_page_debug.png')
                print("   Screenshot saved to: testsprite_tests/signin_page_debug.png")
                
                # Check what's actually on the page
                content = await page.content()
                if 'data-testid="signin-button"' in content:
                    print("   ⚠️ Button exists in HTML but not visible")
                else:
                    print("   ⚠️ Button not in HTML at all")
                
                return False
        finally:
            await browser.close()

if __name__ == "__main__":
    result = asyncio.run(verify_signin_button())
    exit(0 if result else 1)
