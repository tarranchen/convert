import tkinter as tk
from tkinter import filedialog
import os
import csv
from PIL import Image
import numpy as np

def convert_folder_tiffs_to_csv():
    """
    開啟一個檔案對話方塊來選擇資料夾，
    讀取該資料夾內所有 TIFF 檔案的像素強度（保留原始位元深度），
    並將其分別匯出為同名的 CSV 檔案於該資料夾中。
    """
    # 建立一個 Tkinter 的根視窗，並將其隱藏
    root = tk.Tk()
    root.withdraw()

    # 開啟資料夾選擇對話方塊，讓使用者選擇資料夾
    folderpath = filedialog.askdirectory(title='請選擇包含 TIFF 檔案的資料夾', initialdir='.')

    # 檢查使用者是否選擇了資料夾
    if not folderpath:
        print("操作已取消，未選擇任何資料夾。")
        return

    print(f"已選擇資料夾: {folderpath}")

    # 取得資料夾中所有的檔案列表
    all_files = os.listdir(folderpath)
    # 過濾出 .tif 或 .tiff 結尾的檔案（不分大小寫）
    tiff_files = [f for f in all_files if f.lower().endswith(('.tif', '.tiff'))]

    if not tiff_files:
        print("該資料夾內找不到任何 TIFF 檔案。")
        return

    print(f"共找到 {len(tiff_files)} 個 TIFF 檔案，開始處理...")

    # 逐一處理每個 TIFF 檔案
    for filename in tiff_files:
        filepath = os.path.join(folderpath, filename)
        
        try:
            # 使用 Pillow 函式庫開啟圖片檔案
            img = Image.open(filepath)
            
            # 直接將圖片物件轉換為 NumPy 陣列
            # 不使用 convert('L')，以保留原始 32-bit 整數 ('I') 或浮點數 ('F') 的資料型態
            pixel_data = np.array(img)
            
            # 檢查陣列維度。若為多通道 (例如 RGB)，則預設取第一個通道以符合 CSV 寫入格式
            if pixel_data.ndim > 2:
                print(f"[{filename}] 偵測到多通道資料，僅擷取第一個通道寫入 CSV。")
                pixel_data = pixel_data[:, :, 0]
                
            # 取得輸入檔案的檔名，並建立輸出 CSV 檔案的路徑
            base_name = os.path.splitext(filename)[0]
            csv_filepath = os.path.join(folderpath, base_name + '.csv')
            
            # 開啟一個新的 CSV 檔案來寫入資料
            with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # 將 NumPy 陣列中的所有像素資料一次性寫入 CSV 檔案
                writer.writerows(pixel_data)
                
            print(f"成功轉換: {filename} -> {base_name}.csv (dtype: {pixel_data.dtype})")
            
        except Exception as e:
            print(f"處理檔案 {filename} 時發生錯誤: {e}")

    print("所有檔案處理完成。")

if __name__ == '__main__':
    # 執行主函式
    convert_folder_tiffs_to_csv()