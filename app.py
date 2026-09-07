import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
import time
import os
from flask import Flask, jsonify, request, send_file, render_template_string
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
USERNAME = os.environ.get('INSTAGRAM_USERNAME', 'hopefreymosingi')
PASSWORD = os.environ.get('INSTAGRAM_PASSWORD', 'automationmaster')
TWO_FA_CODE = os.environ.get('INSTAGRAM_2FA_CODE', '123456')

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

# Create screenshots directory
os.makedirs('screenshots', exist_ok=True)

# HTML UI template
UI_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Instagram Login Bot - Screenshot Viewer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            margin-bottom: 20px;
            font-weight: 300;
        }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        .btn {
            padding: 10px 25px;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 500;
        }
        .btn-primary {
            background: #0095f6;
            color: white;
        }
        .btn-primary:hover {
            background: #0077cc;
        }
        .btn-danger {
            background: #ed4956;
            color: white;
        }
        .btn-danger:hover {
            background: #c43a46;
        }
        .btn-success {
            background: #28a745;
            color: white;
        }
        .btn-success:hover {
            background: #218838;
        }
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        .btn-secondary:hover {
            background: #5a6268;
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .status {
            padding: 10px 20px;
            border-radius: 5px;
            font-weight: 500;
            margin-left: auto;
        }
        .status-idle {
            background: #e9ecef;
            color: #495057;
        }
        .status-running {
            background: #fff3cd;
            color: #856404;
            animation: pulse 1s infinite;
        }
        .status-success {
            background: #d4edda;
            color: #155724;
        }
        .status-error {
            background: #f8d7da;
            color: #721c24;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        .screenshot-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .screenshot-item {
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        .screenshot-item:hover {
            transform: translateY(-5px);
        }
        .screenshot-item img {
            width: 100%;
            height: auto;
            display: block;
        }
        .screenshot-item .info {
            padding: 15px;
        }
        .screenshot-item .info .name {
            font-weight: 500;
            color: #333;
            margin-bottom: 5px;
        }
        .screenshot-item .info .time {
            font-size: 12px;
            color: #999;
        }
        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: #999;
        }
        .empty-state svg {
            font-size: 60px;
            margin-bottom: 20px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .log-container {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.6;
        }
        .log-container .log-entry {
            padding: 2px 0;
        }
        .log-container .log-entry .time {
            color: #569cd6;
            margin-right: 10px;
        }
        .log-container .log-entry .level-info {
            color: #4ec9b0;
        }
        .log-container .log-entry .level-error {
            color: #f44747;
        }
        .log-container .log-entry .level-warning {
            color: #dcdcaa;
        }
        .refresh-btn {
            background: #0095f6;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        .refresh-btn:hover {
            background: #0077cc;
        }
        .controls-left {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }
        .auto-refresh {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #666;
            font-size: 14px;
        }
        .auto-refresh input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        @media (max-width: 600px) {
            .screenshot-grid {
                grid-template-columns: 1fr;
            }
            .controls {
                flex-direction: column;
            }
            .status {
                margin-left: 0;
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📸 Instagram Login Bot - Screenshot Viewer</h1>
        
        <div class="controls">
            <div class="controls-left">
                <button class="btn btn-primary" onclick="startLogin()" id="loginBtn">🚀 Start Login</button>
                <button class="btn btn-secondary" onclick="refreshScreenshots()">🔄 Refresh</button>
                <button class="btn btn-danger" onclick="clearScreenshots()">🗑️ Clear All</button>
            </div>
            <div class="auto-refresh">
                <input type="checkbox" id="autoRefresh" checked onchange="toggleAutoRefresh()">
                <label for="autoRefresh">Auto-refresh (5s)</label>
            </div>
            <div id="status" class="status status-idle">⏸ Idle</div>
        </div>
        
        <div id="logContainer" class="log-container"></div>
        
        <div id="screenshotGrid" class="screenshot-grid">
            <div class="loading">Loading screenshots...</div>
        </div>
    </div>

    <script>
        let autoRefreshInterval = null;
        let isRefreshing = false;
        
        function toggleAutoRefresh() {
            const checked = document.getElementById('autoRefresh').checked;
            if (checked) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        }
        
        function startAutoRefresh() {
            if (autoRefreshInterval) return;
            autoRefreshInterval = setInterval(() => {
                if (!document.hidden) {
                    refreshScreenshots();
                }
            }, 5000);
        }
        
        function stopAutoRefresh() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
        }
        
        async function startLogin() {
            const btn = document.getElementById('loginBtn');
            btn.disabled = true;
            btn.textContent = '⏳ Starting...';
            
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        username: '{{ username }}',
                        password: '{{ password }}',
                        two_fa_code: '{{ two_fa_code }}'
                    })
                });
                const data = await response.json();
                if (data.success) {
                    updateStatus('running', '🔄 Login in progress...');
                    addLog('Login started successfully');
                } else {
                    updateStatus('error', '❌ Failed to start: ' + data.message);
                    addLog('Error: ' + data.message, 'error');
                }
            } catch (error) {
                updateStatus('error', '❌ Error: ' + error.message);
                addLog('Error: ' + error.message, 'error');
            }
            
            btn.disabled = false;
            btn.textContent = '🚀 Start Login';
            refreshScreenshots();
        }
        
        async function refreshScreenshots() {
            if (isRefreshing) return;
            isRefreshing = true;
            
            try {
                const response = await fetch('/screenshots');
                const data = await response.json();
                renderScreenshots(data.screenshots);
                
                // Update status
                const statusResponse = await fetch('/status');
                const statusData = await statusResponse.json();
                if (statusData.login_status.in_progress) {
                    updateStatus('running', '🔄 Login in progress...');
                } else if (statusData.login_status.completed) {
                    const result = await fetch('/result');
                    const resultData = await result.json();
                    if (resultData.success) {
                        updateStatus('success', '✅ Login successful!');
                        addLog('✅ Login completed successfully!');
                    } else {
                        updateStatus('error', '❌ Login failed');
                        addLog('❌ Login failed', 'error');
                    }
                } else {
                    updateStatus('idle', '⏸ Idle');
                }
            } catch (error) {
                console.error('Error refreshing:', error);
            }
            
            isRefreshing = false;
        }
        
        function renderScreenshots(screenshots) {
            const grid = document.getElementById('screenshotGrid');
            
            if (!screenshots || screenshots.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state" style="grid-column: 1/-1;">
                        <div style="font-size: 60px; margin-bottom: 20px;">📷</div>
                        <h3>No screenshots yet</h3>
                        <p>Click "Start Login" to begin capturing screenshots</p>
                    </div>
                `;
                return;
            }
            
            // Sort by name (which includes timestamp)
            const sorted = [...screenshots].reverse();
            
            grid.innerHTML = sorted.map(item => `
                <div class="screenshot-item">
                    <img src="${item.data}" alt="${item.name}" loading="lazy">
                    <div class="info">
                        <div class="name">${item.name.replace('.png', '').replace('_', ' - ')}</div>
                        <div class="time">${new Date().toLocaleString()}</div>
                    </div>
                </div>
            `).join('');
        }
        
        function updateStatus(type, message) {
            const statusEl = document.getElementById('status');
            statusEl.className = `status status-${type}`;
            statusEl.textContent = message;
        }
        
        function addLog(message, level = 'info') {
            const container = document.getElementById('logContainer');
            const time = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `
                <span class="time">[${time}]</span>
                <span class="level-${level}">${message}</span>
            `;
            container.appendChild(entry);
            container.scrollTop = container.scrollHeight;
            
            // Keep only last 100 entries
            while (container.children.length > 100) {
                container.removeChild(container.firstChild);
            }
        }
        
        async function clearScreenshots() {
            if (!confirm('Delete all screenshots?')) return;
            
            try {
                const response = await fetch('/clear_screenshots', { method: 'POST' });
                if (response.ok) {
                    document.getElementById('screenshotGrid').innerHTML = `
                        <div class="empty-state" style="grid-column: 1/-1;">
                            <div style="font-size: 60px; margin-bottom: 20px;">🗑️</div>
                            <h3>Screenshots cleared</h3>
                        </div>
                    `;
                    addLog('Screenshots cleared');
                }
            } catch (error) {
                console.error('Error clearing screenshots:', error);
            }
        }
        
        // Initialize
        startAutoRefresh();
        refreshScreenshots();
        
        // Refresh when page becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                refreshScreenshots();
            }
        });
        
        // Add some initial logs
        addLog('Screenshot Viewer started');
        addLog('Click "Start Login" to begin the login process');
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Serve the UI page"""
    return render_template_string(
        UI_TEMPLATE,
        username=USERNAME,
        password=PASSWORD,
        two_fa_code=TWO_FA_CODE
    )

@app.route('/clear_screenshots', methods=['POST'])
def clear_screenshots():
    """Clear all screenshots"""
    try:
        for f in os.listdir('screenshots'):
            try:
                os.remove(os.path.join('screenshots', f))
            except:
                pass
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/screenshots')
def get_screenshots():
    """Get all screenshots taken during login"""
    screenshots = []
    for filename in sorted(os.listdir('screenshots')):
        if filename.endswith('.png'):
            try:
                with open(f'screenshots/{filename}', 'rb') as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')
                    screenshots.append({
                        "name": filename,
                        "data": f"data:image/png;base64,{img_data}"
                    })
            except:
                pass
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

@app.route('/login', methods=['POST'])
def login():
    global login_status
    
    if login_status["in_progress"]:
        return jsonify({
            "success": False,
            "message": "Login already in progress"
        })
    
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
        try:
            os.remove(os.path.join('screenshots', f))
        except:
            pass
    
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
        "message": "Login started in background"
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
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshots/{timestamp}_{name}.png"
        await page.screenshot(path=filename, full_page=True)
        logger.info(f"📸 Screenshot saved: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to take screenshot {name}: {str(e)}")
        return None

async def perform_login_with_screenshots(username, password, two_fa_code):
    """Perform Instagram login with screenshots at every step"""
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer'
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
                await page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle")
                await asyncio.sleep(3)
                await take_screenshot(page, "01_login_page")
                
                # Step 2: Check for cookie consent
                logger.info("📸 Step 2: Looking for cookie consent...")
                try:
                    cookie_button = await page.query_selector('button:has-text("Accept")')
                    if cookie_button:
                        await cookie_button.click()
                        await asyncio.sleep(1)
                        await take_screenshot(page, "02_cookies_accepted")
                        logger.info("✅ Accepted cookies")
                except:
                    logger.info("No cookie consent needed")
                    await take_screenshot(page, "02_no_cookies")
                
                # Step 3: Find username field
                logger.info("📸 Step 3: Looking for username field...")
                username_field = None
                
                # Try multiple selectors for Instagram login
                selectors = [
                    'input[name="username"]',
                    'input[type="text"][name="username"]',
                    'input[autocomplete="username"]',
                    'input[placeholder*="username"]',
                    'input[placeholder*="phone"]',
                    'input[placeholder*="email"]',
                    'input[type="text"]:not([hidden])'
                ]
                
                for selector in selectors:
                    try:
                        logger.info(f"Trying selector: {selector}")
                        username_field = await page.wait_for_selector(selector, timeout=3000)
                        if username_field:
                            logger.info(f"✅ Found username field with: {selector}")
                            await take_screenshot(page, "03_username_field_found")
                            break
                    except:
                        pass
                
                if not username_field:
                    await take_screenshot(page, "03_username_field_not_found")
                    logger.error("❌ Could not find username field!")
                    return {"success": False, "error": "Could not find username field"}
                
                # Step 4: Fill username
                logger.info("📸 Step 4: Filling username...")
                await username_field.click()
                await asyncio.sleep(1)
                await username_field.fill("")
                await asyncio.sleep(1)
                
                for char in username:
                    await username_field.type(char, delay=random.uniform(80, 180))
                    await asyncio.sleep(random.uniform(0.02, 0.08))
                
                await asyncio.sleep(2)
                await take_screenshot(page, "04_username_filled")
                logger.info(f"✅ Username filled: {username}")
                
                # Step 5: Find password field
                logger.info("📸 Step 5: Looking for password field...")
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
                            await take_screenshot(page, "05_password_field_found")
                            break
                    except:
                        pass
                
                if not password_field:
                    await take_screenshot(page, "05_password_field_not_found")
                    logger.error("❌ Could not find password field!")
                    return {"success": False, "error": "Could not find password field"}
                
                # Step 6: Fill password
                logger.info("📸 Step 6: Filling password...")
                await password_field.click()
                await asyncio.sleep(1)
                await password_field.fill("")
                await asyncio.sleep(1)
                
                for char in password:
                    await password_field.type(char, delay=random.uniform(80, 180))
                    await asyncio.sleep(random.uniform(0.02, 0.08))
                
                await asyncio.sleep(2)
                await take_screenshot(page, "06_password_filled")
                logger.info("✅ Password filled")
                
                # Step 7: Submit login
                logger.info("📸 Step 7: Submitting login...")
                # Try to find login button first
                login_button = await page.query_selector('button[type="submit"]')
                if login_button:
                    await login_button.click()
                    logger.info("✅ Clicked login button")
                else:
                    await page.keyboard.press("Enter")
                    logger.info("✅ Pressed Enter")
                
                await asyncio.sleep(5)
                await take_screenshot(page, "07_after_submit")
                
                # Step 8: Wait for response
                logger.info("📸 Step 8: Waiting for response...")
                for i in range(10):
                    await asyncio.sleep(2)
                    current_url = page.url
                    logger.info(f"Check {i+1}: URL: {current_url}")
                    
                    if "two_step_verification" in current_url:
                        logger.info("🔐 2FA page detected!")
                        await take_screenshot(page, f"08_2fa_detected")
                        break
                    elif "login" not in current_url and "instagram.com" in current_url:
                        logger.info("✅ Navigated away from login!")
                        await take_screenshot(page, f"08_logged_in")
                        break
                    
                    if i % 3 == 0:
                        await take_screenshot(page, f"08_waiting_{i+1}")
                
                current_url = page.url
                logger.info(f"URL after waiting: {current_url}")
                await take_screenshot(page, "08_final_url")
                
                # Step 9: Handle 2FA if needed
                if "two_step_verification" in current_url or "challenge" in current_url:
                    logger.info("📸 Step 9: Processing 2FA...")
                    await take_screenshot(page, "09_2fa_page")
                    
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
                        await take_screenshot(page, "09_2fa_filled")
                        
                        logger.info("Pressing Enter to submit 2FA...")
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(5)
                        await take_screenshot(page, "09_2fa_submitted")
                
                # Step 10: Final check
                logger.info("📸 Step 10: Final check...")
                await asyncio.sleep(3)
                final_url = page.url
                await take_screenshot(page, "10_final_page")
                
                if "login" not in final_url and "challenge" not in final_url and "two_step" not in final_url:
                    cookies = await context.cookies()
                    logger.info("🎉 Login successful!")
                    await take_screenshot(page, "11_success")
                    return {
                        "success": True,
                        "cookies": cookies,
                        "url": final_url
                    }
                else:
                    logger.error(f"❌ Login failed. URL: {final_url}")
                    await take_screenshot(page, "11_failed")
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
                await browser.close()
                
    except Exception as e:
        logger.error(f"Playwright error: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)