# -*- coding: utf-8 -*-

"""
txm_2_tif_V3.py
此腳本用於將 TXM 資料夾內的 *.txm 檔案轉換為 16-bit 的 TIF 影像檔案 (V3 版)。

V3 更新重點：
1. 直接解析 .txm 二進位標頭 (Header)，自動讀取：
   - Offset 16 (int32): 標頭大小 (Header Size，預設 8392 bytes)
   - Offset 20 (int32): 影像寬度 (Width)
   - Offset 24 (int32): 影像高度 (Height)
   - Offset 32 (int32): 累加次數 (AccCount)
   - Offset 48 (float64): 曝光時間 (Exposure Time, sec)
   - Offset 2392 (float64): 旋轉台角度 (STN.C, deg)
2. 支援任意影像尺寸 (256x256, 512x512, 1024x1024, 2048x2048 或自訂 ROI)，
   若標頭未記錄有效尺寸則自動退回以檔案大小推算。
3. 像素資料每 4 bytes (<u4, Little-Endian) 一組，安全轉為 16-bit (<u2) 寫入 TIF 資料夾。
"""

import struct
import numpy as np
import tifffile
from pathlib import Path

DEFAULT_HEADER_SIZE = 8392
BYTES_PER_PIXEL = 4
MB = 1024 * 1024
SUPPORTED_DIMS = [256, 512, 1024, 2048]


def parse_txm_header(header_bytes: bytes, file_size: int) -> dict:
    """
    解析 TXM 8392-byte 標頭資訊。
    若標頭內的寬高或標頭長度異常，則自動根據檔案大小推算。
    """
    info = {
        "mode": 0,
        "version": 100,
        "header_size": DEFAULT_HEADER_SIZE,
        "width": 0,
        "height": 0,
        "seq_count": -1,
        "acc_count": 1,
        "ref_exp_time": -1.0,
        "exp_time": -1.0,
        "rot_deg": 0.0,
    }

    if len(header_bytes) >= 56:
        (
            mode,
            version,
            _flag1,
            _flag2,
            hdr_size,
            width,
            height,
            seq_count,
            acc_count,
        ) = struct.unpack("<9i", header_bytes[:36])
        ref_exp, exp_time = struct.unpack("<2d", header_bytes[40:56])

        info["mode"] = mode
        info["version"] = version
        info["seq_count"] = seq_count
        info["acc_count"] = max(acc_count, 1)
        info["ref_exp_time"] = ref_exp
        info["exp_time"] = exp_time

        if 40 <= hdr_size < file_size:
            info["header_size"] = hdr_size

        if 0 < width <= 16384 and 0 < height <= 16384:
            expected_bytes = width * height * BYTES_PER_PIXEL
            if abs((file_size - info["header_size"]) - expected_bytes) <= 65536:
                info["width"] = width
                info["height"] = height

    if len(header_bytes) >= 2400:
        info["rot_deg"] = struct.unpack("<d", header_bytes[2392:2400])[0]

    # Fallback：若標頭尺寸無效，則根據扣除標頭後的資料大小自動判斷
    if info["width"] == 0 or info["height"] == 0:
        data_size = file_size - info["header_size"]
        for dim in SUPPORTED_DIMS:
            expected_bytes = dim * dim * BYTES_PER_PIXEL
            if abs(data_size - expected_bytes) <= 65536:
                info["width"] = info["height"] = dim
                break

    return info


def convert_txm_to_tif():
    """
    主轉換函式，將同目錄下 'TXM' 資料夾內的所有 *.txm 轉換為 16-bit TIF。
    """
    try:
        script_dir = Path(__file__).parent
    except NameError:
        script_dir = Path.cwd()

    txm_dir = script_dir / "TXM"
    tif_dir = script_dir / "TIF"

    if not txm_dir.is_dir():
        print(f"錯誤：找不到輸入資料夾 '{txm_dir}'。")
        print("請確認 'TXM' 資料夾與此腳本位於相同目錄中。")
        return

    tif_dir.mkdir(exist_ok=True)
    print(f"輸出檔案將儲存於：{tif_dir}")

    txm_files = sorted(txm_dir.glob("*.txm"))
    if not txm_files:
        print(f"在 '{txm_dir}' 中找不到任何 *.txm 檔案。")
        return

    print(f"找到 {len(txm_files)} 個 .txm 檔案，準備進行處理。")

    success_count = 0
    for txm_path in txm_files:
        print(f"\n處理中：'{txm_path.name}'...")

        try:
            file_size = txm_path.stat().st_size
            if file_size <= 56:
                print(f"  -> 跳過檔案：檔案過小 ({file_size} bytes)。")
                continue

            with open(txm_path, "rb") as f:
                raw_header = f.read(DEFAULT_HEADER_SIZE)
                meta = parse_txm_header(raw_header, file_size)

                width, height = meta["width"], meta["height"]
                header_size = meta["header_size"]

                if width == 0 or height == 0:
                    print(
                        f"  -> 跳過檔案：無法從標頭或檔案大小 ({file_size / MB:.2f} MB) 識別影像尺寸。"
                    )
                    continue

                print(
                    f"  -> 尺寸: {width}x{height} | Header: {header_size} B | "
                    f"曝光: {meta['exp_time']:g} s | 角度: {meta['rot_deg']:.2f}°"
                )

                f.seek(header_size)
                data_bytes = f.read()

            # 確保讀取長度為 4 bytes 的整數倍
            valid_byte_len = (len(data_bytes) // BYTES_PER_PIXEL) * BYTES_PER_PIXEL
            pixel_u32 = np.frombuffer(data_bytes[:valid_byte_len], dtype="<u4")

            expected_pixels = width * height
            if pixel_u32.size < expected_pixels:
                print(
                    f"  -> 警告：像素數量 ({pixel_u32.size}) 少於預期 ({expected_pixels})，不足處將補 0。"
                )
                pixel_u32 = np.pad(
                    pixel_u32,
                    (0, expected_pixels - pixel_u32.size),
                    mode="constant",
                )

            # 轉換為 16-bit 無號整數 (若因多次累加超過 65535 則進行 clip 防溢位)
            pixel_u16 = np.clip(pixel_u32[:expected_pixels], 0, 65535).astype(np.uint16)
            image_array = pixel_u16.reshape((height, width))

            output_path = tif_dir / txm_path.with_suffix(".tif").name
            tifffile.imwrite(output_path, image_array, imagej=True)

            print(f"  -> 成功轉換並儲存至 '{output_path}'")
            success_count += 1

        except Exception as e:
            print(f"  -> 處理檔案 {txm_path.name} 時發生錯誤: {e}")

    print(f"\n所有轉換處理完成（成功 {success_count}/{len(txm_files)} 個檔案）。")


if __name__ == "__main__":
    convert_txm_to_tif()
