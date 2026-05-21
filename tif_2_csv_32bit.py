import tkinter as tk
from tkinter import filedialog
import os
import csv
from PIL import Image
import numpy as np

def convert_tiff_to_csv():
    """
    開啟一個檔案對話方塊來選擇 TIFF 檔案，
    讀取其像素強度（保留原始位元深度），並將其匯出為 CSV 檔案。
    """
    # 建立一個 Tkinter 的根視窗，並將其隱藏
    root = tk.Tk()
    root.withdraw()

    # 定義支援的檔案類型
    file_types = [
        ('TIFF 檔案', '*.tif'),
        ('TIFF 檔案', '*.tiff'),
        ('所有檔案', '*.*')
    ]

    # 開啟檔案選擇對話方塊，讓使用者選擇檔案
    filepath = filedialog.askopenfilename(
        title='請選擇一個 TIFF 檔案',
        initialdir='.',
        filetypes=file_types
    )

    # 檢查使用者是否選擇了檔案
    if not filepath:
        print("操作已取消，未選擇任何檔案。")
        return

    print(f"已選擇檔案: {filepath}")

    try:
        # 使用 Pillow 函式庫開啟圖片檔案
        img = Image.open(filepath)

        # 直接將圖片物件轉換為 NumPy 陣列
        # 不使用 convert('L')，以保留原始 32-bit 整數 ('I') 或浮點數 ('F') 的資料型態
        pixel_data = np.array(img)

        # 檢查陣列維度。若為多通道 (例如 RGB)，則預設取第一個通道以符合 CSV 寫入格式
        if pixel_data.ndim > 2:
            print("偵測到多通道資料，僅擷取第一個通道寫入 CSV。")
            pixel_data = pixel_data[:, :, 0]

        # 取得輸入檔案的路徑和檔名，並建立輸出 CSV 檔案的路徑
        base_path = os.path.splitext(filepath)[0]
        csv_filepath = base_path + '.csv'

        # 開啟一個新的 CSV 檔案來寫入資料
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # 將 NumPy 陣列中的所有像素資料一次性寫入 CSV 檔案
            writer.writerows(pixel_data)

        print(f"成功！已將像素強度資料儲存至: {csv_filepath}")
        print(f"輸出的資料型態 (dtype) 為: {pixel_data.dtype}")

    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {filepath}")
    except Exception as e:
        print(f"處理檔案時發生錯誤: {e}")

if __name__ == '__main__':
    # 執行主函式
    convert_tiff_to_csv()