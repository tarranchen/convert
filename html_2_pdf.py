import os
import asyncio
from playwright.async_api import async_playwright

# --- 設定 ---
SOURCE_DIR = '.'  # HTML 檔案所在的資料夾
OUTPUT_DIR = 'output_pdfs_playwright' # 輸出資料夾

async def convert_file(playwright, html_file_path, pdf_file_path):
    """轉換單一檔案"""
    browser = await playwright.chromium.launch()
    page = await browser.new_page()
    
    try:
        # ==================== 【修改處 1】 ====================
        # 延長單一頁面的逾時時間到 60 秒 (60000 毫秒)
        await page.goto(
            f'file://{os.path.abspath(html_file_path)}', 
            wait_until='load',
            timeout=60000 
        )
        # =======================================================
        
        # 產生 PDF
        await page.pdf(path=pdf_file_path, format='A4', print_background=True)
        print(f"✅ 成功轉換: {os.path.basename(html_file_path)}")
        
    except Exception as e:
        print(f"❌ 轉換失敗: {os.path.basename(html_file_path)} - {e}")
    finally:
        await browser.close()

async def main():
    """主程式"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    html_files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(('.html', '.htm'))]
    
    async with async_playwright() as p:
        # ==================== 【修改處 2】 ====================
        # 從並行處理 (asyncio.gather) 改為循序處理 (for 迴圈)
        # 這樣可以確保一次只跑一個瀏覽器，避免耗盡系統資源。
        print(f"找到 {len(html_files)} 個 HTML 檔案，開始循序轉換...")
        for filename in html_files:
            source_path = os.path.join(SOURCE_DIR, filename)
            output_filename = os.path.splitext(filename)[0] + '.pdf'
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            # 使用 await 直接等待每個轉換任務完成後再開始下一個
            await convert_file(p, source_path, output_path)
        # =======================================================

if __name__ == '__main__':
    asyncio.run(main())