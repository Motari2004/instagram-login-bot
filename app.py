import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
import time
import os
from flask import Flask, jsonify, request
from datetime import datetime
import traceback
import threading
import base64

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
USERNAME = os.environ.get('INSTAGRAM_USERNAME', '')
PASSWORD = os.environ.get('INSTAGRAM_PASSWORD', '')
TWO_FA_CODE = os.environ.get('INSTAGRAM_2FA_CODE', '')

logger.info(f"Username set: {'Yes' if USERNAME else 'No'}")
logger.info(f"Password set: {'Yes' if PASSWORD else 'No'}")
logger.info(f"2FA Code set: {'Yes' if TWO_FA_CODE else 'No'}")

# Store login status globally
login_status = {
    "in_progress": False,
    "completed": False,
    "result": None,
    "start_time": None,
    "end_time": None,
    "screenshots": []
}

# Create screenshots directory
os.makedirs('screenshots', exist_ok=True)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Instagram Login Bot",
        "endpoints": {
            "/login": "POST - Start login process",
            "/status": "GET - Check login status",
            "/result": "GET - Get login result",
            "/screenshots": "GET - Get all screenshots",
            "/health": "GET - Health check"
        }
    })

@app.route('/screenshots')
def get_screenshots():
    """Get all screenshots taken during login"""
    screenshots = []
    for filename in os.listdir('screenshots'):
        if filename.endswith('.png'):
            with open(f'screenshots/{filename}', 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
                screenshots.append({
                    "name": filename,
                    "data": f"data:image/png;base64,{img_data}"
                })
    return jsonify({
        "screenshots": screenshots,
        "count": len(screenshots)
    })

@app.route('/status')
def status():
    return jsonify({
        "username_set": bool(USERNAME),
        "password_set": bool(PASSWORD),
        "two_fa_set": bool(TWO_FA_CODE),
        "login_status": {
            "in_progress": login_status["in_progress"],
            "completed": login_status["completed"],
            "start_time": login_status["start_time"],
            "end_time": login_status["end_time"]
        },
        "screenshot_count": len(os.listdir('screenshots'))
    })

@app.route('/result')
def get_result():
    if login_status["completed"]:
        return jsonify(login_status["result"])
    else:
        return jsonify({
            "success": False,
            "message": "Login not completed yet",
            "in_progress": login_status["in_progress"]
        })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    global login_status
    
    if login_status["in_progress"]:
        return jsonify({
            "success": False,
            "message": "Login already in progress",
            "status": "in_progress"
        })
    
    username = USERNAME
    password = PASSWORD
    two_fa_code = TWO_FA_CODE
    
    if request.method == 'POST':
        data = request.json or {}
        username = data.get('username', USERNAME)
        password = data.get('password', PASSWORD)
        two_fa_code = data.get('two_fa_code', TWO_FA_CODE)
    
    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username and password are required"
        }), 400
    
    # Clear old screenshots
    for f in os.listdir('screenshots'):
        os.remove(os.path.join('screenshots', f))
    
    login_status = {
        "in_progress": True,
        "completed": False,
        "result": None,
        "start_time": datetime.now().isoformat(),
        "end_time": None
    }
    
    thread = threading.Thread(
        target=run_login_background,
        args=(username, password, two_fa_code)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "message": "Login started in background",
        "status": "in_progress",
        "check_status": "/status",
        "get_result": "/result",
        "get_screenshots": "/screenshots"
    })

def run_login_background(username, password, two_fa_code):
    global login_status
    
    try:
        logger.info(f"Starting background login for: {username}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            perform_login_with_screenshots(username, password, two_fa_code)
        )
        
        login_status["completed"] = True
        login_status["result"] = result
        login_status["in_progress"] = False
        login_status["end_time"] = datetime.now().isoformat()
        
        if result.get('success'):
            logger.info("✅ Background login successful!")
        else:
            logger.error(f"❌ Background login failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Background login error: {str(e)}")
        login_status["completed"] = True
        login_status["result"] = {"success": False, "error": str(e)}
        login_status["in_progress"] = False

async def take_screenshot(page, name):
    """Take a screenshot and save it with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshots/{timestamp}_{name}.png"
    await page.screenshot(path=filename, full_page=True)
    logger.info(f"📸 Screenshot saved: {filename}")
    return filename

async def perform_login_with_screenshots(username, password, two_fa_code):
    """Perform Instagram login with screenshots at every step"""
    
    try:
        async with async_playwright() as p:
            # Launch browser with headless=False so you can see
            browser = await p.chromium.launch(
                headless=False,  # Show browser
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--start-maximized'
                ]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            
            page = await context.new_page()
            
            try:
                # Step 1: Go to Instagram
                logger.info("📸 Step 1: Navigating to Instagram...")
                await page.goto("https://www.instagram.com/", wait_until="networkidle")
                await asyncio.sleep(3)
                await take_screenshot(page, "01_instagram_home")
                
                current_url = page.url
                logger.info(f"Current URL: {current_url}")
                
                # Step 2: If not on login page, go to login
                if "login" not in current_url:
                    logger.info("📸 Step 2: Going to login page...")
                    await page.goto("https://www.instagram.com/accounts/login/")
                    await asyncio.sleep(3)
                    await take_screenshot(page, "02_login_page")
                else:
                    await take_screenshot(page, "02_already_on_login")
                
                # Step 3: Check if we need to accept cookies
                logger.info("📸 Step 3: Checking for cookie consent...")
                try:
                    cookie_button = await page.query_selector('button:has-text("Accept")')
                    if cookie_button:
                        await cookie_button.click()
                        await asyncio.sleep(1)
                        await take_screenshot(page, "03_cookies_accepted")
                        logger.info("✅ Accepted cookies")
                except:
                    logger.info("No cookie consent needed")
                    await take_screenshot(page, "03_no_cookies")
                
                # Step 4: Find username field
                logger.info("📸 Step 4: Looking for username field...")
                username_field = None
                
                selectors = [
                    'input[name="email"]',
                    'input[type="text"]',
                    'input[autocomplete="username"]',
                    'input[placeholder*="Phone"]',
                    'input[placeholder*="Username"]',
                    'input[placeholder*="Email"]'
                ]
                
                for selector in selectors:
                    try:
                        logger.info(f"Trying selector: {selector}")
                        username_field = await page.wait_for_selector(selector, timeout=3000)
                        if username_field:
                            logger.info(f"✅ Found username field with: {selector}")
                            await take_screenshot(page, "04_username_field_found")
                            break
                    except:
                        pass
                
                if not username_field:
                    await take_screenshot(page, "04_username_field_not_found")
                    html = await page.content()
                    with open('screenshots/page_debug.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    logger.error("❌ Could not find username field!")
                    return {"success": False, "error": "Could not find username field"}
                
                # Step 5: Fill username
                logger.info("📸 Step 5: Filling username...")
                await username_field.click()
                await asyncio.sleep(1)
                await username_field.fill("")
                await asyncio.sleep(1)
                
                for char in username:
                    await username_field.type(char, delay=random.uniform(80, 180))
                    await asyncio.sleep(random.uniform(0.02, 0.08))
                
                await asyncio.sleep(2)
                await take_screenshot(page, "05_username_filled")
                logger.info(f"✅ Username filled: {username}")
                
                # Step 6: Find password field
                logger.info("📸 Step 6: Looking for password field...")
                password_field = None
                
                selectors = [
                    'input[name="password"]',
                    'input[type="password"]',
                    'input[autocomplete="current-password"]'
                ]
                
                for selector in selectors:
                    try:
                        logger.info(f"Trying selector: {selector}")
                        password_field = await page.wait_for_selector(selector, timeout=3000)
                        if password_field:
                            logger.info(f"✅ Found password field with: {selector}")
                            await take_screenshot(page, "06_password_field_found")
                            break
                    except:
                        pass
                
                if not password_field:
                    await take_screenshot(page, "06_password_field_not_found")
                    logger.error("❌ Could not find password field!")
                    return {"success": False, "error": "Could not find password field"}
                
                # Step 7: Fill password
                logger.info("📸 Step 7: Filling password...")
                await password_field.click()
                await asyncio.sleep(1)
                await password_field.fill("")
                await asyncio.sleep(1)
                
                for char in password:
                    await password_field.type(char, delay=random.uniform(80, 180))
                    await asyncio.sleep(random.uniform(0.02, 0.08))
                
                await asyncio.sleep(2)
                await take_screenshot(page, "07_password_filled")
                logger.info("✅ Password filled")
                
                # Step 8: Submit login
                logger.info("📸 Step 8: Submitting login...")
                await page.keyboard.press("Enter")
                await asyncio.sleep(3)
                await take_screenshot(page, "08_after_submit")
                logger.info("✅ Login submitted")
                
                # Step 9: Wait for response
                logger.info("📸 Step 9: Waiting for response...")
                for i in range(10):
                    await asyncio.sleep(2)
                    current_url = page.url
                    logger.info(f"Check {i+1}: URL: {current_url}")
                    
                    if "two_step_verification" in current_url:
                        logger.info("🔐 2FA page detected!")
                        await take_screenshot(page, f"09_2fa_detected_{i+1}")
                        break
                    elif "login" not in current_url and "instagram.com" in current_url:
                        logger.info("✅ Navigated away from login!")
                        await take_screenshot(page, f"09_logged_in_{i+1}")
                        break
                    
                    if i == 4:  # Take screenshot every few seconds
                        await take_screenshot(page, f"09_waiting_{i+1}")
                
                current_url = page.url
                logger.info(f"URL after waiting: {current_url}")
                await take_screenshot(page, "09_final_url")
                
                # Step 10: Handle 2FA if needed
                if "two_step_verification" in current_url or "challenge" in current_url:
                    logger.info("📸 Step 10: Processing 2FA...")
                    await take_screenshot(page, "10_2fa_page")
                    
                    twofa_field = None
                    try:
                        twofa_field = await page.wait_for_selector('input[type="text"]', timeout=5000)
                    except:
                        pass
                    
                    if not twofa_field:
                        try:
                            inputs = await page.query_selector_all('input')
                            for inp in inputs:
                                is_visible = await inp.is_visible()
                                if is_visible:
                                    type_attr = await inp.get_attribute('type')
                                    if type_attr == 'text' or type_attr == 'number':
                                        twofa_field = inp
                                        logger.info("✅ Found 2FA field by scanning all inputs")
                                        break
                        except:
                            pass
                    
                    if twofa_field and two_fa_code:
                        logger.info(f"📸 Filling 2FA code: {two_fa_code}")
                        await twofa_field.click()
                        await asyncio.sleep(1)
                        await twofa_field.fill("")
                        await asyncio.sleep(1)
                        
                        for char in two_fa_code:
                            await twofa_field.type(char, delay=random.uniform(80, 180))
                            await asyncio.sleep(random.uniform(0.02, 0.08))
                        
                        await asyncio.sleep(2)
                        await take_screenshot(page, "10_2fa_filled")
                        
                        logger.info("Pressing Enter to submit 2FA...")
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(5)
                        await take_screenshot(page, "10_2fa_submitted")
                    else:
                        logger.warning("⚠️ 2FA field not found or no code provided")
                        await take_screenshot(page, "10_2fa_field_not_found")
                
                # Step 11: Final check
                logger.info("📸 Step 11: Final check...")
                await asyncio.sleep(3)
                final_url = page.url
                await take_screenshot(page, "11_final_page")
                
                if "login" not in final_url and "challenge" not in final_url and "two_step" not in final_url:
                    cookies = await context.cookies()
                    logger.info("🎉 Login successful!")
                    await take_screenshot(page, "12_success")
                    return {
                        "success": True,
                        "cookies": cookies,
                        "url": final_url
                    }
                else:
                    logger.error(f"❌ Login failed. URL: {final_url}")
                    await take_screenshot(page, "12_failed")
                    return {
                        "success": False,
                        "error": f"Login failed. URL: {final_url}",
                        "url": final_url
                    }
                    
            except Exception as e:
                logger.error(f"Login error: {str(e)}")
                await take_screenshot(page, "error")
                return {"success": False, "error": str(e)}
            finally:
                # Keep browser open for 30 seconds to see result
                logger.info("📸 Keeping browser open for 30 seconds...")
                await asyncio.sleep(30)
                await browser.close()
                
    except Exception as e:
        logger.error(f"Playwright error: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)