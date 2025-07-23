# -*- coding: utf-8 -*-

"""
此腳本用於將 TXM 資料夾內的 *.txm 檔案轉換為 16-bit 的 TIF 影像檔案。

執行流程：
1. 讀取與腳本相同目錄下的 'TXM' 資料夾中的所有 *.txm 檔案。
2. 根據檔案大小判斷影像的寬與高：
   - 約 2 MB -> 512x512
   - 約 4 MB -> 1024x1024
   - 約 8 MB -> 2048x2048
3. 檔案為 Little Endian，跳過開頭 8392 bytes 的標頭 (header)。
4. 像素資料每 4 bytes 一組，其中前 2 bytes 為 0，後 2 bytes 為 16-bit 像素值。
5. 建立一個新的 TIF 資料夾。
6. 將轉換後的 TIF 檔案寫入 'TIF' 資料夾，檔名與來源檔相同。
"""

import os
import numpy as np
import tifffile
from pathlib import Path

def convert_txm_to_tif():
    """
    主轉換函式，執行所有 TXM 到 TIF 的轉換工作。
    """
    try:
        # 獲取腳本所在的目錄
        script_dir = Path(__file__).parent
    except NameError:
        # 若在互動式環境 (如 Jupyter) 中執行，則獲取當前工作目錄
        script_dir = Path.cwd()

    # --- 1. 設定輸入與輸出資料夾路徑 ---
    txm_dir = script_dir / 'TXM'
    tif_dir = script_dir / 'TIF'

    # 檢查 TXM 資料夾是否存在
    if not txm_dir.is_dir():
        print(f"錯誤：找不到輸入資料夾 '{txm_dir}'。")
        print("請確認 'TXM' 資料夾與此腳本位於相同目錄中。")
        return

    # --- 6. 建立 TIF 輸出資料夾 (若不存在) ---
    tif_dir.mkdir(exist_ok=True)
    print(f"輸出檔案將儲存於：{tif_dir}")

    # 讀取所有 .txm 檔案
    txm_files = list(txm_dir.glob('*.txm'))

    if not txm_files:
        print(f"在 '{txm_dir}' 中找不到任何 *.txm 檔案。")
        return

    print(f"找到 {len(txm_files)} 個 .txm 檔案，準備進行處理。")

    # --- 定義常數 ---
    HEADER_SIZE = 8392  # 要略過的標頭大小 (bytes)
    MB = 1024 * 1024    # 1 MB (Megabyte) 的 byte 數

    # 遍歷所有找到的 .txm 檔案
    for txm_path in txm_files:
        print(f"\n處理中：'{txm_path.name}'...")

        try:
            # --- 2. 根據檔案大小判斷影像尺寸 ---
            file_size = txm_path.stat().st_size
            width, height = 0, 0

            # 允許 0.5 MB 的誤差範圍
            if (2 * MB - 0.5 * MB) < file_size < (2 * MB + 0.5 * MB):
                width, height = 512, 512
            elif (4 * MB - 0.5 * MB) < file_size < (4 * MB + 0.5 * MB):
                width, height = 1024, 1024
            elif (8 * MB - 0.5 * MB) < file_size < (8 * MB + 0.5 * MB):
                width, height = 2048, 2048
            else:
                print(f"  -> 跳過檔案。檔案大小 {file_size / MB:.2f} MB 不在預期範圍內 (約 2, 4, 或 8 MB)。")
                continue

            print(f"  -> 檔案大小 {file_size / MB:.2f} MB，設定影像尺寸為 {width}x{height}。")

            # --- 3. 讀取二進位資料並略過標頭 ---
            with open(txm_path, 'rb') as f:
                f.seek(HEADER_SIZE)
                data_bytes = f.read()

            # --- 4. 解析資料 ---
            # 定義資料結構：2 bytes 的填充 (padding)，接著 2 bytes 的 16-bit 無號整數 (Little Endian)
            dt = np.dtype([('value', '<u2'), ('padding', 'V2')])

            # 使用 NumPy 將 raw bytes 轉換為結構化陣列
            structured_array = np.frombuffer(data_bytes, dtype=dt)

            # 提取有效的 16-bit 像素資料
            pixel_data = structured_array['value']

            # --- 5. 將資料填入 TIFF 影像中 ---
            expected_pixels = width * height
            if pixel_data.size < expected_pixels:
                print(f"  -> 警告：檔案包含的數據點 ({pixel_data.size}) 少於 {width}x{height} 影像的預期數量 ({expected_pixels})。")
                print("  -> 結果影像可能不完整。將以 0 填充缺失的像素。")
                # 調整陣列大小以匹配預期尺寸，不足處補 0
                pixel_data.resize(expected_pixels, refcheck=False)

            # 將一維像素陣列重塑為二維影像陣列
            image_array = pixel_data[:expected_pixels].reshape((height, width))

            # --- 6. 寫入 TIF 檔案 ---
            # 產生輸出檔名 (例如: data.txm -> data.tif)
            output_filename = txm_path.with_suffix('.tif').name
            output_path = tif_dir / output_filename

            # 使用 tifffile 將 NumPy 陣列儲存為 16-bit TIFF 檔案
            tifffile.imwrite(output_path, image_array, imagej=True)

            print(f"  -> 成功轉換並儲存至 '{output_path}'")

        except Exception as e:
            print(f"  -> 處理檔案 {txm_path.name} 時發生錯誤: {e}")

    print("\n所有轉換處理完成。")

if __name__ == "__main__":
    convert_txm_to_tif()