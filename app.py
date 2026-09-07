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
    "end_time": None
}

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Instagram Login Bot",
        "endpoints": {
            "/login": "GET/POST - Start login process",
            "/status": "GET - Check login status",
            "/result": "GET - Get login result",
            "/health": "GET - Health check"
        }
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
        "message": "Use /login to start login, /result to get result"
    })

@app.route('/result')
def get_result():
    """Get the login result"""
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
    """Start the login process"""
    global login_status
    
    # Check if login is already in progress
    if login_status["in_progress"]:
        return jsonify({
            "success": False,
            "message": "Login already in progress",
            "status": "in_progress",
            "start_time": login_status["start_time"]
        })
    
    # Get credentials
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
    
    # Reset status
    login_status = {
        "in_progress": True,
        "completed": False,
        "result": None,
        "start_time": datetime.now().isoformat(),
        "end_time": None
    }
    
    # Start login in background thread
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
        "start_time": login_status["start_time"],
        "check_status": "/status",
        "get_result": "/result"
    })

def run_login_background(username, password, two_fa_code):
    """Run login in background thread"""
    global login_status
    
    try:
        logger.info(f"Starting background login for: {username}")
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the login
        result = loop.run_until_complete(
            perform_login(username, password, two_fa_code)
        )
        
        login_status["completed"] = True
        login_status["result"] = result
        login_status["in_progress"] = False
        login_status["end_time"] = datetime.now().isoformat()
        
        if result.get('success'):
            logger.info("✅ Background login successful!")
            # Save cookies
            if result.get('cookies'):
                with open('cookies.json', 'w') as f:
                    json.dump(result['cookies'], f, indent=2)
        else:
            logger.error(f"❌ Background login failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Background login error: {str(e)}")
        login_status["completed"] = True
        login_status["result"] = {"success": False, "error": str(e)}
        login_status["in_progress"] = False
        login_status["end_time"] = datetime.now().isoformat()

async def perform_login(username, password, two_fa_code):
    """Perform Instagram login with NO timeouts"""
    
    try:
        async with async_playwright() as p:
            # Launch browser with NO timeout
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-extensions',
                    '--disable-setuid-sandbox'
                ]
                # REMOVED timeout parameter
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            
            page = await context.new_page()
            
            try:
                logger.info("Navigating to Instagram login page...")
                # REMOVED timeout from goto
                await page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle")
                await asyncio.sleep(3)
                
                # Find and fill username
                try:
                    username_field = await page.wait_for_selector('input[name="email"]', timeout=30000)
                except:
                    username_field = await page.wait_for_selector('input[type="text"]', timeout=30000)
                
                if not username_field:
                    return {"success": False, "error": "Could not find username field"}
                
                await username_field.click()
                await asyncio.sleep(0.5)
                await username_field.fill("")
                await asyncio.sleep(0.3)
                
                for char in username:
                    await username_field.type(char, delay=random.uniform(80, 180))
                    await asyncio.sleep(random.uniform(0.02, 0.08))
                
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
                # Find and fill password
                try:
                    password_field = await page.wait_for_selector('input[name="password"]', timeout=30000)
                except:
                    password_field = await page.wait_for_selector('input[type="password"]', timeout=30000)
                
                if not password_field:
                    return {"success": False, "error": "Could not find password field"}
                
                await password_field.click()
                await asyncio.sleep(0.5)
                await password_field.fill("")
                await asyncio.sleep(0.3)
                
                for char in password:
                    await password_field.type(char, delay=random.uniform(80, 180))
                    await asyncio.sleep(random.uniform(0.02, 0.08))
                
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
                # Press Enter to submit
                logger.info("Pressing Enter to submit...")
                await page.keyboard.press("Enter")
                
                # Wait for navigation - NO TIMEOUT
                logger.info("Waiting for navigation (no timeout)...")
                await asyncio.sleep(5)
                
                # Check URL repeatedly until it changes
                max_checks = 30  # Check 30 times
                for i in range(max_checks):
                    current_url = page.url
                    logger.info(f"Check {i+1}: Current URL: {current_url}")
                    
                    if "two_step_verification" in current_url.lower() or "challenge" in current_url.lower():
                        logger.info("🔐 2FA page detected!")
                        break
                    elif "login" not in current_url.lower():
                        logger.info("✅ Navigated away from login page!")
                        break
                    
                    await asyncio.sleep(2)
                
                current_url = page.url
                logger.info(f"Final URL after navigation check: {current_url}")
                
                # Handle 2FA if needed
                if "two_step_verification" in current_url.lower() or "challenge" in current_url.lower():
                    logger.info("🔐 Processing 2FA...")
                    
                    # Wait for 2FA input - NO TIMEOUT
                    await asyncio.sleep(3)
                    
                    twofa_field = None
                    
                    # Try multiple strategies to find 2FA input
                    try:
                        logger.info("Looking for 2FA input field...")
                        inputs = await page.query_selector_all('input[type="text"]')
                        for input_elem in inputs:
                            is_visible = await input_elem.is_visible()
                            if is_visible:
                                name = await input_elem.get_attribute('name') or ''
                                placeholder = await input_elem.get_attribute('placeholder') or ''
                                aria_label = await input_elem.get_attribute('aria-label') or ''
                                
                                logger.info(f"Found input: name='{name}', placeholder='{placeholder}', aria-label='{aria_label}'")
                                
                                if name != "email" and "username" not in name.lower():
                                    twofa_field = input_elem
                                    logger.info(f"✅ Selected 2FA field: name='{name}'")
                                    break
                    except Exception as e:
                        logger.error(f"Error finding 2FA input: {str(e)}")
                    
                    # If not found, try by placeholder
                    if not twofa_field:
                        try:
                            twofa_field = await page.wait_for_selector(
                                'input[placeholder*="code" i], input[placeholder*="2FA" i]', 
                                timeout=10000
                            )
                            if twofa_field:
                                logger.info("✅ Found 2FA field by placeholder")
                        except:
                            pass
                    
                    if twofa_field and two_fa_code:
                        logger.info(f"Filling 2FA code: {two_fa_code}")
                        
                        await twofa_field.click()
                        await asyncio.sleep(0.5)
                        await twofa_field.fill("")
                        await asyncio.sleep(0.3)
                        
                        for char in two_fa_code:
                            await twofa_field.type(char, delay=random.uniform(80, 180))
                            await asyncio.sleep(random.uniform(0.02, 0.08))
                        
                        await asyncio.sleep(1)
                        logger.info("Pressing Enter to submit 2FA...")
                        await page.keyboard.press("Enter")
                        
                        # Wait for 2FA to process - NO TIMEOUT
                        logger.info("Waiting for 2FA verification...")
                        await asyncio.sleep(5)
                        
                        # Check if 2FA worked
                        for i in range(10):
                            final_url = page.url
                            logger.info(f"2FA check {i+1}: {final_url}")
                            if "two_step" not in final_url and "challenge" not in final_url:
                                logger.info("✅ 2FA completed!")
                                break
                            await asyncio.sleep(2)
                    else:
                        logger.warning("⚠️ 2FA field not found or no code provided")
                
                # Final check
                await asyncio.sleep(3)
                final_url = page.url
                logger.info(f"Final URL: {final_url}")
                
                if "login" not in final_url and "challenge" not in final_url and "two_step" not in final_url:
                    cookies = await context.cookies()
                    return {
                        "success": True,
                        "cookies": cookies,
                        "url": final_url
                    }
                else:
                    await page.screenshot(path="login_failed.png")
                    return {
                        "success": False,
                        "error": "Login failed - still on login page",
                        "url": final_url
                    }
                    
            except Exception as e:
                logger.error(f"Login error: {str(e)}")
                await page.screenshot(path="login_error.png")
                return {"success": False, "error": str(e)}
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error(f"Playwright error: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)