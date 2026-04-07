import os
import numpy as np
import tifffile
import struct
import time
import shutil
import tkinter as tk
import tempfile
from tkinter import filedialog

# --- 設定 ---
# PXM 檔案所在的資料夾名稱
PXM_FOLDER_NAME = "PXM"
# 輸出 TIF 檔案的資料夾名稱
TIF_FOLDER_NAME = "TIF"
# PXM 檔案的標頭大小 (bytes)
HEADER_SIZE = 217912
# 觸發處理程序的 PXM 檔案數量
PROCESSING_TRIGGER_COUNT = 723
# 監控資料夾的檢查間隔 (秒)
POLL_INTERVAL_SECONDS = 10

def get_image_dimensions(file_path):
    """
    根據檔案大小判斷影像的寬和高。

    Args:
        file_path (str): 檔案的路徑。

    Returns:
        tuple: (寬, 高) 或 (None, None) 如果檔案大小不符合預期。
    """
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if 1.8 <= file_size_mb <= 2.2:
        return 1280, 1080  # 2MB 左右的檔案
    elif 7.8 <= file_size_mb <= 8.2:
        return 2560, 2160  # 8MB 左右的檔案
    else:
        return None, None

def process_pxm_file(pxm_path, tif_path):
    """
    讀取單一 PXM 檔案，轉換並儲存為 TIF 檔案。

    Args:
        pxm_path (str): 來源 PXM 檔案的路徑。
        tif_path (str): 目標 TIF 檔案的路徑。
    """
    width, height = get_image_dimensions(pxm_path)
    if not width:
        print(f"\n警告：跳過檔案 {os.path.basename(pxm_path)}，因為其大小 ({os.path.getsize(pxm_path) / (1024*1024):.2f} MB) 不符合預期。")
        return

    # 呼叫此函數的地方會顯示進度，這裡不再重複輸出
    try:
        with open(pxm_path, 'rb') as f:
            # 略過檔案開頭的標頭
            f.seek(HEADER_SIZE)
            
            # 讀取剩下的資料內容
            raw_data = f.read()

        # 預期像素總數
        total_pixels = width * height
        
        # 存放解碼後的 16-bit 像素資料
        pixel_data = []

        # 每 3 個 bytes 為一組進行處理
        # 這會產生 2 個 16-bit 的資料點
        for i in range(0, len(raw_data), 3):
            # 確保不會讀取到檔案結尾的不完整資料組
            if i + 2 >= len(raw_data):
                break

            # 使用 struct.unpack 讀取 3 個 unsigned bytes
            byte1, byte2, byte3 = struct.unpack_from('<BBB', raw_data, i)

            # --- 根據規則重組資料點 ---
            # 資料點 1:
            # bits 13-16 來自 byte2 的前 4 bits
            # bits 5-12 來自 byte1
            # bits 1-4 為 0 (透過左移 4 bits 實現)
            datapoint1 = (byte1 << 4) | (byte2 >> 4)

            # 資料點 2:
            # bits 13-16 來自 byte2 的後 4 bits
            # bits 5-12 來自 byte3
            # bits 1-4 為 0 (透過左移 4 bits 實現)
            datapoint2 = (byte3 << 4) | (byte2 & 0x0F)

            pixel_data.append(datapoint1)
            pixel_data.append(datapoint2)

        # 檢查解析出的像素數量是否正確
        if len(pixel_data) != total_pixels:
            print(f"\n警告：檔案 {os.path.basename(pxm_path)} 的資料長度不符。")
            print(f"  預期像素數: {total_pixels}, 實際解析出: {len(pixel_data)}")
            # 如果像素數量不足，用 0 填補剩餘部分
            pixel_data.extend([0] * (total_pixels - len(pixel_data)))


        # 將 list 轉換為 NumPy array，並設定資料型態為 16-bit unsigned integer
        image_array = np.array(pixel_data, dtype=np.uint16)
        
        # 將一維陣列重塑為 (height, width) 的二維影像
        image_array = image_array.reshape((height, width))

        # 使用 tifffile 將上下翻轉後的 NumPy array 寫入 TIF 檔案
        tifffile.imwrite(tif_path, np.flipud(image_array))

    except FileNotFoundError:
        print(f"\n錯誤：找不到檔案 {pxm_path}")
    except Exception as e:
        print(f"\n處理檔案 {os.path.basename(pxm_path)} 時發生錯誤：{e}")


def perform_background_subtraction(temp_tif_dir, final_tif_dir):
    """
    讀取暫存的 16-bit TIF 檔案，執行扣背並儲存為 32-bit TIF。
    - PXMs_04...[0000-0360] 除以 PXMs_00...0000
    - PXMs_04...[0361-0720] 除以 PXMs_00...0001
    """
    # 定義扣背任務
    background_tasks = [
        {
            "bg_filename": "PXMs_00_0000_0000.tif",
            "img_prefix": "PXMs_04_0000_",
            "start_index": 0,
            "end_index": 360,
        },
        {
            "bg_filename": "PXMs_00_0000_0001.tif",
            "img_prefix": "PXMs_04_0000_",
            "start_index": 361,
            "end_index": 720,
        },
    ]

    total_files_to_process = 721
    processed_count = 0

    for task in background_tasks:
        bg_path = os.path.join(temp_tif_dir, task["bg_filename"])
        
        try:
            print(f"  正在讀取背景檔案: {task['bg_filename']}")
            bg_image = tifffile.imread(bg_path).astype(np.float32)
            
            # 避免除以零，將背景中的 0 替換為 1
            bg_image[bg_image == 0] = 1.0

        except FileNotFoundError:
            print(f"  錯誤：找不到背景檔案 {bg_path}。跳過此輪扣背程序。")
            continue
        except Exception as e:
            print(f"  讀取背景檔案 {bg_path} 時發生錯誤: {e}。跳過此輪扣背程序。")
            continue

        # 處理對應的影像範圍
        for i in range(task["start_index"], task["end_index"] + 1):
            img_filename = f"{task['img_prefix']}{i:04d}.tif"
            img_path = os.path.join(temp_tif_dir, img_filename)
            final_path = os.path.join(final_tif_dir, img_filename)

            processed_count += 1
            print(f"  ({processed_count}/{total_files_to_process}) 正在處理 {img_filename}...", end='\r')

            if not os.path.exists(img_path):
                print(f"\n  警告：找不到影像檔案 {img_path}，已跳過。")
                continue

            try:
                # 讀取樣本影像並轉換為 float32
                sample_image = tifffile.imread(img_path).astype(np.float32)

                # 執行除法 (扣背)
                corrected_image = sample_image / bg_image

                # 將結果儲存為 32-bit float TIF
                tifffile.imwrite(final_path, corrected_image)
            except Exception as e:
                print(f"\n  處理檔案 {img_filename} 時發生錯誤: {e}")

    print("\n扣背程序完成。")


def process_sample_folder(sample_dir):
    """
    對單一樣品資料夾執行完整的處理流程：
    1. 將 PXM 轉換為暫存的 16-bit TIF。
    2. 執行扣背程序，產生最終的 32-bit TIF。
    3. 清理暫存檔案。
    """
    print(f"\n--- 開始處理樣品資料夾: {os.path.basename(sample_dir)} ---")

    pxm_dir = os.path.join(sample_dir, PXM_FOLDER_NAME)
    final_tif_dir = os.path.join(sample_dir, TIF_FOLDER_NAME)
    temp_tif_dir = None  # 確保在 finally 區塊中可用

    try:
        # 在本機的系統暫存區建立一個唯一的資料夾
        temp_tif_dir = tempfile.mkdtemp(prefix="pxm_processing_")

        # 建立輸出資料夾
        os.makedirs(final_tif_dir, exist_ok=True)
        print(f"暫存 TIF 資料夾 (本機): {temp_tif_dir}")
        print(f"最終 TIF 資料夾: {final_tif_dir}")

        # --- 步驟 1: PXM -> 16-bit TIF ---
        print(f"\n步驟 1: 正在將 {PROCESSING_TRIGGER_COUNT} 個 PXM 檔案轉換為 16-bit TIF...")
        pxm_files = sorted([f for f in os.listdir(pxm_dir) if f.lower().endswith(".pxm")])

        for i, filename in enumerate(pxm_files):
            pxm_file_path = os.path.join(pxm_dir, filename)
            tif_filename = os.path.splitext(filename)[0] + ".tif"
            temp_tif_path = os.path.join(temp_tif_dir, tif_filename)

            print(f"  ({i+1}/{len(pxm_files)}) 正在轉換 {filename}...", end='\r')
            process_pxm_file(pxm_file_path, temp_tif_path)
        print(f"\n16-bit TIF 轉換完成。")

        # --- 步驟 2: 執行扣背程序 ---
        print("\n步驟 2: 正在執行扣背程序...")
        perform_background_subtraction(temp_tif_dir, final_tif_dir)

        print(f"--- 樣品資料夾 '{os.path.basename(sample_dir)}' 處理完成 ---\n")
    finally:
        # --- 步驟 3: 清理暫存資料夾 ---
        if temp_tif_dir and os.path.isdir(temp_tif_dir):
            print("\n步驟 3: 正在清理暫存檔案...")
            try:
                shutil.rmtree(temp_tif_dir)
                print(f"成功刪除本機暫存資料夾: {temp_tif_dir}")
            except Exception as e:
                print(f"錯誤：刪除本機暫存資料夾 {temp_tif_dir} 時失敗: {e}")


def monitor_folder(monitoring_dir):
    """
    監控指定資料夾，尋找符合條件的樣品資料夾並進行處理。
    """
    print(f"開始監控資料夾: {monitoring_dir}")
    print(f"每隔 {POLL_INTERVAL_SECONDS} 秒檢查一次。按 Ctrl+C 停止程式。")
    
    try:
        while True:
            # 取得監控資料夾中的所有子目錄 (樣品資料夾)
            for item in os.listdir(monitoring_dir):
                sample_dir = os.path.join(monitoring_dir, item)
                
                if not os.path.isdir(sample_dir):
                    continue

                # 檢查是否已處理過：檢查 TIF 資料夾中的檔案數量是否已達標
                final_tif_dir = os.path.join(sample_dir, TIF_FOLDER_NAME)
                is_processed = False
                if os.path.isdir(final_tif_dir):
                    try:
                        num_tif_files = len([f for f in os.listdir(final_tif_dir) if f.lower().endswith(('.tif', '.tiff'))])
                        if num_tif_files >= 721:
                            is_processed = True
                    except Exception as e:
                        print(f"檢查資料夾 {final_tif_dir} 時發生錯誤: {e}，為安全起見將跳過此資料夾。")
                        is_processed = True # 避免因錯誤重複處理

                if is_processed:
                    continue

                # 檢查 PXM 資料夾是否存在
                pxm_dir = os.path.join(sample_dir, PXM_FOLDER_NAME)
                if not os.path.isdir(pxm_dir):
                    continue

                # 檢查 PXM 資料夾中的檔案數量是否達到觸發條件
                try:
                    files = [f for f in os.listdir(pxm_dir) if os.path.isfile(os.path.join(pxm_dir, f))]
                    if len(files) == PROCESSING_TRIGGER_COUNT:
                        print(f"\n偵測到 '{os.path.basename(sample_dir)}/{PXM_FOLDER_NAME}' 中有 {len(files)} 個檔案，觸發處理程序。")
                        process_sample_folder(sample_dir)
                except Exception as e:
                    print(f"處理資料夾 {sample_dir} 時發生錯誤: {e}")

            # 等待一段時間後再次檢查
            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n使用者手動停止監控，程式結束。")

def main():
    """
    主執行函數。
    """
    # 確保在執行前已安裝必要的套件
    try:
        import numpy
        import tifffile
    except ImportError:
        print("錯誤：缺少必要的套件。請先安裝 numpy 和 tifffile。")
        print("您可以使用以下指令安裝：")
        print("pip install numpy tifffile")
        return

    # 使用 Tkinter GUI 讓使用者選擇要監控的資料夾
    root = tk.Tk()
    root.withdraw()  # 隱藏主視窗
    
    print("請在彈出視窗中選擇一個要監控的資料夾...")
    monitoring_dir = filedialog.askdirectory(title="請選擇要監控的資料夾")

    if not monitoring_dir:
        print("未選擇任何資料夾，程式即將結束。")
        return

    # 開始監控指定的資料夾
    monitor_folder(monitoring_dir)

if __name__ == "__main__":
    main()
