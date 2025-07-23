import os
import numpy as np
import tifffile
import struct

# --- 設定 ---
# PXM 檔案所在的資料夾名稱
PXM_FOLDER = "PXM"
# 輸出 TIF 檔案的資料夾名稱
TIF_FOLDER = "TIF"
# PXM 檔案的標頭大小 (bytes)
HEADER_SIZE = 217912

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
        print(f"警告：跳過檔案 {os.path.basename(pxm_path)}，因為其大小 ({os.path.getsize(pxm_path) / (1024*1024):.2f} MB) 不符合預期。")
        return

    print(f"正在處理 {os.path.basename(pxm_path)}... 尺寸: {width}x{height}")

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
            print(f"警告：檔案 {os.path.basename(pxm_path)} 的資料長度不符。")
            print(f"預期像素數: {total_pixels}, 實際解析出: {len(pixel_data)}")
            # 如果像素數量不足，用 0 填補剩餘部分
            pixel_data.extend([0] * (total_pixels - len(pixel_data)))


        # 將 list 轉換為 NumPy array，並設定資料型態為 16-bit unsigned integer
        image_array = np.array(pixel_data, dtype=np.uint16)
        
        # 將一維陣列重塑為 (height, width) 的二維影像
        image_array = image_array.reshape((height, width))

        # 使用 tifffile 將 NumPy array 寫入 TIF 檔案
        tifffile.imwrite(tif_path, image_array)
        print(f"成功儲存檔案至 {tif_path}")

    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {pxm_path}")
    except Exception as e:
        print(f"處理檔案 {os.path.basename(pxm_path)} 時發生錯誤：{e}")


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

    # 取得 script 所在的當前目錄
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 設定 PXM 和 TIF 資料夾的路徑
    pxm_dir = os.path.join(base_dir, PXM_FOLDER)
    tif_dir = os.path.join(base_dir, TIF_FOLDER)

    # 檢查 PXM 資料夾是否存在
    if not os.path.isdir(pxm_dir):
        print(f"錯誤：找不到 '{PXM_FOLDER}' 資料夾。請確認它與 script 位於相同目錄。")
        return

    # 如果 TIF 資料夾不存在，則建立它
    os.makedirs(tif_dir, exist_ok=True)
    print(f"TIF 檔案將會儲存在: {tif_dir}")

    # 遍歷 PXM 資料夾中的所有檔案
    for filename in os.listdir(pxm_dir):
        if filename.lower().endswith(".pxm"):
            pxm_file_path = os.path.join(pxm_dir, filename)
            
            # 產生對應的 TIF 檔名
            tif_filename = os.path.splitext(filename)[0] + ".tif"
            tif_file_path = os.path.join(tif_dir, tif_filename)
            
            process_pxm_file(pxm_file_path, tif_file_path)

    print("\n所有檔案處理完成。")

if __name__ == "__main__":
    main()
