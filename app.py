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

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Instagram Login Bot",
        "endpoints": {
            "/login": "POST - Perform Instagram login",
            "/health": "GET - Health check",
            "/status": "GET - Check credentials status"
        }
    })

@app.route('/status')
def status():
    return jsonify({
        "username_set": bool(USERNAME),
        "password_set": bool(PASSWORD),
        "two_fa_set": bool(TWO_FA_CODE),
        "message": "Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD environment variables"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    """API endpoint to perform Instagram login"""
    try:
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
        
        logger.info(f"Attempting login for user: {username}")
        
        # Run the login with increased timeout
        result = asyncio.run(perform_login(username, password, two_fa_code))
        
        if result['success']:
            return jsonify({
                "success": True,
                "message": "Login successful",
                "cookies": result.get('cookies', []),
                "url": result.get('url', '')
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Login failed'),
                "url": result.get('url', '')
            }), 400
            
    except asyncio.TimeoutError:
        return jsonify({
            "success": False,
            "error": "Login timed out. Instagram may be slow or have additional verification."
        }), 408
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

async def perform_login(username, password, two_fa_code):
    """Perform Instagram login and return cookies"""
    
    try:
        async with async_playwright() as p:
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
                ],
                timeout=30000  # 30 second timeout for browser launch
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            
            page = await context.new_page()
            
            try:
                logger.info("Navigating to Instagram login page...")
                await page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)
                
                # Find and fill username
                try:
                    username_field = await page.wait_for_selector('input[name="email"]', timeout=15000)
                except:
                    username_field = await page.wait_for_selector('input[type="text"]', timeout=15000)
                
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
                    password_field = await page.wait_for_selector('input[name="password"]', timeout=15000)
                except:
                    password_field = await page.wait_for_selector('input[type="password"]', timeout=15000)
                
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
                await page.keyboard.press("Enter")
                
                # Wait for navigation with longer timeout
                try:
                    await page.wait_for_url(
                        lambda url: "two_step_verification" in url or "challenge" in url or ("instagram.com" in url and "login" not in url),
                        timeout=30000
                    )
                except:
                    pass
                
                await asyncio.sleep(5)
                
                current_url = page.url
                
                # Handle 2FA if needed
                if "two_step_verification" in current_url.lower() or "challenge" in current_url.lower():
                    logger.info("2FA page detected!")
                    
                    twofa_field = None
                    
                    try:
                        twofa_field = await page.wait_for_selector('input[type="text"][autocomplete="off"]', timeout=10000)
                    except:
                        pass
                    
                    if not twofa_field:
                        try:
                            inputs = await page.query_selector_all('input[type="text"]')
                            for input_elem in inputs:
                                is_visible = await input_elem.is_visible()
                                if is_visible:
                                    name = await input_elem.get_attribute('name')
                                    if name != "email":
                                        twofa_field = input_elem
                                        break
                        except:
                            pass
                    
                    if twofa_field and two_fa_code:
                        await twofa_field.click()
                        await asyncio.sleep(0.5)
                        await twofa_field.fill("")
                        await asyncio.sleep(0.3)
                        
                        for char in two_fa_code:
                            await twofa_field.type(char, delay=random.uniform(80, 180))
                            await asyncio.sleep(random.uniform(0.02, 0.08))
                        
                        await asyncio.sleep(1)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(5)
                
                # Check final URL
                await asyncio.sleep(3)
                final_url = page.url
                
                if "login" not in final_url and "challenge" not in final_url and "two_step" not in final_url:
                    cookies = await context.cookies()
                    return {
                        "success": True,
                        "cookies": cookies,
                        "url": final_url
                    }
                else:
                    # Take screenshot for debugging
                    await page.screenshot(path="login_debug.png")
                    return {
                        "success": False,
                        "error": "Login failed - still on login page",
                        "url": final_url
                    }
                    
            except asyncio.TimeoutError:
                return {"success": False, "error": "Operation timed out"}
            except Exception as e:
                logger.error(f"Login error: {str(e)}")
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