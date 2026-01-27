import sys
import os
import cv2
import numpy as np

# 尝试导入 pytesseract
try:
    import pytesseract
    # 如果系统没有安装 tesseract，import 不会报错，但调用时会报错
except ImportError:
    pytesseract = None

def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    图像预处理：转为 numpy -> 灰度 -> 二值化 -> 去噪
    """
    # 1. Bytes -> Numpy
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # 2. 转灰度
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 3. 自适应二值化 (Adaptive Thresholding)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # 4. 简单的去噪 (Median Blur)
    denoised = cv2.medianBlur(binary, 3)
    
    return denoised

def ocr_image(image_bytes: bytes) -> str:
    """
    对图片字节流进行 OCR 识别 (使用 Tesseract)
    """
    if pytesseract is None:
        print("WARNING: pytesseract not installed. OCR disabled.")
        return ""
    
    try:
        # 预处理
        processed_img = preprocess_image(image_bytes)
        
        # Tesseract 识别
        # lang='chi_sim+eng' 表示同时识别简体中文和英文
        # psm 6 表示假设是一块统一的文本块
        text = pytesseract.image_to_string(processed_img, lang='chi_sim+eng', config='--psm 6')
        
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        print("ERROR: Tesseract binary not found. Please install tesseract-ocr (e.g., 'brew install tesseract').")
        return ""
    except Exception as e:
        print(f"ERROR: OCR failed: {e}")
        return ""
