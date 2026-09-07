import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
import time
import os
from flask import Flask, jsonify, request
from datetime import datetime

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
USERNAME = os.environ.get('INSTAGRAM_USERNAME', 'hopefreymosingi')
PASSWORD = os.environ.get('INSTAGRAM_PASSWORD', 'automationmaster')
TWO_FA_CODE = os.environ.get('INSTAGRAM_2FA_CODE', '123456')

async def instagram_login():
    """Perform Instagram login and return cookies"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        
        page = await context.new_page()
        
        try:
            logger.info("Navigating to Instagram login page...")
            await page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle")
            await asyncio.sleep(3)
            
            # Find and fill username
            try:
                username_field = await page.wait_for_selector('input[name="email"]', timeout=10000)
            except:
                username_field = await page.wait_for_selector('input[type="text"]', timeout=5000)
            
            if not username_field:
                return {"success": False, "error": "Could not find username field"}
            
            await username_field.click()
            await asyncio.sleep(0.5)
            await username_field.fill("")
            await asyncio.sleep(0.3)
            
            for char in USERNAME:
                await username_field.type(char, delay=random.uniform(80, 180))
                await asyncio.sleep(random.uniform(0.02, 0.08))
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Find and fill password
            try:
                password_field = await page.wait_for_selector('input[name="password"]', timeout=5000)
            except:
                password_field = await page.wait_for_selector('input[type="password"]', timeout=5000)
            
            if not password_field:
                return {"success": False, "error": "Could not find password field"}
            
            await password_field.click()
            await asyncio.sleep(0.5)
            await password_field.fill("")
            await asyncio.sleep(0.3)
            
            for char in PASSWORD:
                await password_field.type(char, delay=random.uniform(80, 180))
                await asyncio.sleep(random.uniform(0.02, 0.08))
            
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Press Enter to submit
            await page.keyboard.press("Enter")
            
            # Wait for navigation
            try:
                await page.wait_for_url(
                    lambda url: "two_step_verification" in url or "challenge" in url or ("instagram.com" in url and "login" not in url),
                    timeout=15000
                )
            except:
                pass
            
            await asyncio.sleep(3)
            
            current_url = page.url
            
            # Handle 2FA if needed
            if "two_step_verification" in current_url.lower() or "challenge" in current_url.lower():
                logger.info("2FA page detected!")
                
                twofa_field = None
                
                # Try to find 2FA input
                try:
                    twofa_field = await page.wait_for_selector('input[type="text"][autocomplete="off"]', timeout=5000)
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
                
                if twofa_field and TWO_FA_CODE:
                    await twofa_field.click()
                    await asyncio.sleep(0.5)
                    await twofa_field.fill("")
                    await asyncio.sleep(0.3)
                    
                    for char in TWO_FA_CODE:
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
                return {
                    "success": False,
                    "error": "Login failed",
                    "url": final_url
                }
                
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            return {"success": False, "error": str(e)}
            
        finally:
            await browser.close()

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Instagram Login Bot",
        "endpoints": {
            "/login": "POST - Perform Instagram login",
            "/health": "GET - Health check"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/login', methods=['POST'])
def login():
    """API endpoint to perform Instagram login"""
    try:
        # Update credentials from request if provided
        global USERNAME, PASSWORD, TWO_FA_CODE
        
        data = request.json
        if data:
            if data.get('username'):
                USERNAME = data['username']
            if data.get('password'):
                PASSWORD = data['password']
            if data.get('two_fa_code'):
                TWO_FA_CODE = data['two_fa_code']
        
        # Run the login
        result = asyncio.run(instagram_login())
        
        if result['success']:
            # Save cookies to file (optional)
            with open('cookies.json', 'w') as f:
                json.dump(result['cookies'], f, indent=2)
            
            return jsonify({
                "success": True,
                "message": "Login successful",
                "cookies": result['cookies'],
                "url": result.get('url', '')
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Unknown error'),
                "url": result.get('url', '')
            }), 400
            
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)