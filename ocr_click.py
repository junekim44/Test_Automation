import pytesseract
from PIL import ImageGrab
import cv2
import numpy as np
import win32api
import win32con
import time

# ⚠️ [중요] Tesseract 설치 경로가 맞는지 확인하세요!
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def click_text_on_screen(target_text, action='right_click'):
    """
    화면 전체를 캡처하고 전처리(확대+이진화)하여 텍스트를 찾아 클릭합니다.
    """
    print(f"[OCR] 화면에서 '{target_text}' 텍스트 정밀 탐색 중...")

    try:
        # 1. 화면 캡처
        screenshot = ImageGrab.grab()
        img_np = np.array(screenshot)
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # 2. [핵심] 전처리 과정 개선
        # (1) 이미지 2배 확대 (작은 글씨 인식률 대폭 향상)
        scale = 2
        width = int(img_cv.shape[1] * scale)
        height = int(img_cv.shape[0] * scale)
        resized = cv2.resize(img_cv, (width, height), interpolation=cv2.INTER_CUBIC)

        # (2) 흑백 변환
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        # (3) 이진화 (글자와 배경을 흑/백으로 명확히 분리)
        # OTSU 알고리즘: 최적의 임계값을 자동으로 계산
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # (4) 색상 반전 체크
        # Tesseract는 '흰 배경에 검은 글씨'를 선호합니다.
        # 만약 배경이 검정색(어두운색)에 가까우면 색상을 반전시킵니다.
        if np.mean(binary) < 127:
             binary = cv2.bitwise_not(binary)

        # [디버깅] OCR이 보고 있는 이미지를 파일로 저장 (인식 안 될 때 이 사진 확인)
        cv2.imwrite("debug_ocr_screen.png", binary)

        # 3. OCR 실행
        # --psm 11: Sparse text (드문드문 있는 텍스트 찾기 모드)
        config = r'--oem 3 --psm 11'
        data = pytesseract.image_to_data(binary, lang='eng', config=config, output_type=pytesseract.Output.DICT)
        
        found = False
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            text = data['text'][i].strip()
            
            if not text: continue
            
            # 4. 텍스트 매칭
            # OCR 특성상 공백이나 특수문자가 섞일 수 있으므로 부분 일치 확인
            if target_text in text:
                # 좌표 복원 (2배 확대했으니 다시 2로 나눔)
                x = int(data['left'][i] / scale)
                y = int(data['top'][i] / scale)
                w = int(data['width'][i] / scale)
                h = int(data['height'][i] / scale)
                
                # 중앙 좌표 계산
                center_x = x + w // 2
                center_y = y + h // 2
                
                print(f"   -> 텍스트 발견! '{text}' 좌표: ({center_x}, {center_y})")
                
                # 5. 마우스 클릭 실행
                win32api.SetCursorPos((center_x, center_y))
                time.sleep(0.5)
                
                if action == 'right_click':
                    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, center_x, center_y, 0, 0)
                    time.sleep(0.1)
                    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, center_x, center_y, 0, 0)
                    print("   -> 우클릭 완료")
                else:
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, center_x, center_y, 0, 0)
                    time.sleep(0.1)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, center_x, center_y, 0, 0)
                    print("   -> 좌클릭 완료")
                
                found = True
                break 
        
        if not found:
            print(f"❌ '{target_text}'를 찾지 못했습니다. (생성된 debug_ocr_screen.png 이미지를 확인해보세요)")
            return False
            
        return True

    except Exception as e:
        print(f"🔥 OCR 처리 중 치명적 오류: {e}")
        return False

# 테스트용
if __name__ == "__main__":
    time.sleep(3)
    click_text_on_screen("105_T6831", "right_click")