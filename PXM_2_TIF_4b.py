import os
import numpy as np
import tifffile

def convert_pxm_to_tif():
    # 設定參數
    INPUT_FOLDER_NAME = "PXM"
    OUTPUT_FOLDER_NAME = "TIF"
    HEADER_SIZE = 217904  # 要跳過的檔頭 byte 數
    WIDTH = 2560
    HEIGHT = 2160
    
    # 取得腳本所在的絕對路徑
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(script_dir, INPUT_FOLDER_NAME)
    output_dir = os.path.join(script_dir, OUTPUT_FOLDER_NAME)

    # 1. 檢查輸入資料夾是否存在
    if not os.path.exists(input_dir):
        print(f"錯誤: 找不到輸入資料夾 '{INPUT_FOLDER_NAME}' 於: {input_dir}")
        return

    # 2. 建立輸出資料夾 (如果不存在)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已建立輸出資料夾: {output_dir}")

    # 獲取所有 .pxm 檔案
    pxm_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pxm')]
    
    if not pxm_files:
        print("在 PXM 資料夾中找不到任何 .pxm 檔案。")
        return

    print(f"找到 {len(pxm_files)} 個 PXM 檔案，開始轉換...")

    for filename in pxm_files:
        input_path = os.path.join(input_dir, filename)
        
        # 設定輸出檔名 (保持原檔名，副檔名改為 .tif)
        output_filename = os.path.splitext(filename)[0] + ".tif"
        output_path = os.path.join(output_dir, output_filename)

        try:
            # 3. 讀取檔案
            with open(input_path, 'rb') as f:
                # 跳過檔頭
                f.seek(HEADER_SIZE)
                
                # 4. 讀取剩下的資料
                # dtype='<f4' 表示 Little Endian 的 32-bit float
                raw_data = np.fromfile(f, dtype='<f4')

            # 驗證資料長度是否符合預期的像素數量
            expected_pixels = WIDTH * HEIGHT
            if raw_data.size != expected_pixels:
                print(f"[警告] 檔案 {filename} 的資料大小不符合預期。")
                print(f"       預期像素: {expected_pixels}, 實際讀取: {raw_data.size}")
                # 如果資料過多，則截斷；如果過少，則略過此檔案以免報錯
                if raw_data.size > expected_pixels:
                    raw_data = raw_data[:expected_pixels]
                else:
                    print(f"       跳過檔案 {filename}")
                    continue

            # 將一維陣列重塑為 (Height, Width) 的二維影像矩陣
            image_array = raw_data.reshape((HEIGHT, WIDTH))

            # 上下翻轉影像
            image_array = np.flipud(image_array)

            # 轉換為 16-bit 整數
            # 原始值介於 0-4096，這完全落在 uint16 (0-65535) 的範圍內
            # 我們直接轉換型別，保留原始數值
            image_uint16 = image_array.astype(np.uint16)

            # 5. 儲存為 TIF 檔 (使用 tifffile)
            tifffile.imwrite(output_path, image_uint16)
            
            print(f"[成功] 已轉換: {filename} -> {output_filename}")

        except Exception as e:
            print(f"[失敗] 處理檔案 {filename} 時發生錯誤: {e}")

    print("所有作業已完成。")

if __name__ == "__main__":
    convert_pxm_to_tif()