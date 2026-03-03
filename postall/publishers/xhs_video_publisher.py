#!/usr/bin/env python3
"""
小红书视频发布器
用于攀岩二创视频自动发布
"""
import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright

# Video publishing account
ACCOUNT_FILE = "/opt/social-auto-upload/cookies/xiaohongshu_climbing/account.json"

def extract_title_and_content(txt_path):
    """从 .txt 文件提取标题和正文"""
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    title = ""
    body_lines = []
    
    for i, line in enumerate(lines):
        if line.startswith('标题：') or line.startswith('标题:'):
            title = line.replace('标题：', '').replace('标题:', '').strip()
        elif title:  # 标题之后的都是正文
            body_lines.append(line)
    
    # 如果没找到标题，用第一行
    if not title and lines:
        title = lines[0][:20]
        body_lines = lines[1:]
    
    body = '\n'.join(body_lines).strip()
    
    # 确保有攀岩相关标签
    if '#攀岩' not in body:
        body += '\n\n#攀岩 #攀岩教学 #室内攀岩 #抱石 #bouldering'
    
    return title[:20], body[:1000]

async def publish_xhs_video(video_path, title, content):
    """发布小红书视频"""
    video_path = Path(video_path)
    
    if not video_path.exists():
        return {"success": False, "message": f"视频文件不存在: {video_path}"}
    
    print(f"准备发布视频: {title}")
    print(f"  视频: {video_path}")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                storage_state=ACCOUNT_FILE,
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            print("  1. 打开发布页面...")
            await page.goto("https://creator.xiaohongshu.com/publish/publish", timeout=30000)
            await asyncio.sleep(3)
            
            # 默认就是"上传视频"tab，不需要切换
            print("  2. 上传视频...")
            video_input = page.locator('input[type="file"][accept*="mp4"]').first
            await video_input.set_input_files(str(video_path))
            
            # 等待视频上传和处理（视频比图片慢很多）
            print("  3. 等待视频处理...")
            await asyncio.sleep(30)  # 等待上传
            
            # 等待视频处理完成（检测上传进度消失或发布按钮可用）
            for _ in range(60):  # 最多等5分钟
                try:
                    # 检查是否有上传进度
                    progress = await page.locator('.upload-progress, .progress-bar, [class*="progress"]').count()
                    if progress == 0:
                        break
                except:
                    pass
                await asyncio.sleep(5)
            
            print("  4. 输入标题...")
            await page.fill('input[placeholder*="标题"]', title)
            await asyncio.sleep(1)
            
            print("  5. 输入正文...")
            await page.evaluate('''(content) => {
                const editor = document.querySelector('#post-textarea') || 
                               document.querySelector('[contenteditable="true"]');
                if (editor) {
                    editor.focus();
                    editor.textContent = content;
                    editor.dispatchEvent(new Event('input', { bubbles: true }));
                    return true;
                }
                return false;
            }''', content)
            await asyncio.sleep(2)
            
            # 截图
            screenshot_path = f"/tmp/xhs_video_{video_path.stem}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"  截图: {screenshot_path}")
            
            print("  6. 点击发布...")
            await page.evaluate('''() => {
                const buttons = document.querySelectorAll('button');
                for (let btn of buttons) {
                    if (btn.textContent && btn.textContent.trim() === '发布') {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }''')
            await asyncio.sleep(10)
            
            current_url = page.url
            success = "published=true" in current_url or "publish" not in current_url
            
            await browser.close()
            
            if success:
                print("  ✅ 发布成功!")
                return {"success": True, "message": "发布成功", "screenshot": screenshot_path}
            else:
                print(f"  ⚠️ 发布状态未知，URL: {current_url}")
                return {"success": False, "message": "发布状态未知", "screenshot": screenshot_path}
    
    except Exception as e:
        print(f"  ❌ 发布失败: {e}")
        return {"success": False, "message": str(e)}

def publish_video_sync(video_path, title=None, content=None, txt_path=None):
    """同步版本"""
    if txt_path and (not title or not content):
        title, content = extract_title_and_content(txt_path)
    
    if not title:
        title = Path(video_path).stem[:20]
    if not content:
        content = f"{title}\n\n#攀岩 #攀岩教学 #室内攀岩"
    
    return asyncio.run(publish_xhs_video(video_path, title, content))

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python xhs_video_publisher.py <video_id>")
        print("例如: python xhs_video_publisher.py 30y8Uy0B_uk")
        sys.exit(1)
    
    video_id = sys.argv[1]
    video_path = f"/root/.openclaw/workspace/xhs-climbing/output/videos/{video_id}.mp4"
    txt_path = f"/root/.openclaw/workspace/xhs-climbing/output/copy/{video_id}.txt"
    
    result = publish_video_sync(video_path, txt_path=txt_path)
    print(result)
