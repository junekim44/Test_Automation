import time
import subprocess
import win32gui
import win32com.client 
import win32api 
import win32con 
import requests
import uiautomation as auto # 👈 Windows UI 자동화 라이브러리 (pip install uiautomation)

from appium import webdriver
from typing import Any, Dict
from selenium.webdriver.common.by import By
from appium.options.common import AppiumOptions

# ---------------------------------------------------------
# [설정] 
# ---------------------------------------------------------
WAD_PATH = r"C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe"
WAD_URL = "http://127.0.0.1:4723"

MAIN_WINDOW_TITLE = "IDIS Center Remote Administration System" 
SETUP_WINDOW_TITLE = "IDIS Center 설정"
TARGET_DEVICE = "105_T6831"

# ---------------------------------------------------------
# 🛠️ [핵심] uiautomation을 이용한 안전한 클릭 함수
# ---------------------------------------------------------
def uia_click_list_item(window_handle, automation_id, is_right_click=False, y_offset=None):
    """
    y_offset이 None이면 요소의 '정중앙'을 클릭 (검색창, 버튼용)
    y_offset이 숫자(예: 25)면 '상단 + offset' 위치를 클릭 (리스트 첫 줄용)
    """
    try:
        print(f"   [UIA] 핸들({hex(window_handle)})에서 요소(ID:{automation_id}) 탐색 중...")
        
        window = auto.ControlFromHandle(window_handle)
        target_elem = window.Control(AutomationId=automation_id)
        
        if not target_elem.Exists(maxSearchSeconds=3):
            print(f"❌ [UIA] 요소(ID:{automation_id})를 찾을 수 없습니다.")
            return False
            
        rect = target_elem.BoundingRectangle
        print(f"   [UIA] 좌표 발견: {rect}")
        
        # ---------------------------------------------------------
        # [수정된 부분] 좌표 계산 로직 개선
        # ---------------------------------------------------------
        click_x = int((rect.left + rect.right) / 2) # 가로 중앙
        
        if y_offset is None:
            # 오프셋이 없으면 세로도 '정중앙' 클릭 (검색창 입력용)
            click_y = int((rect.top + rect.bottom) / 2)
        else:
            # 오프셋이 있으면 '상단 + 오프셋' 클릭 (리스트 첫 줄 선택용)
            click_y = int(rect.top + y_offset)
            
        print(f"   [UIA] 마우스 이동 -> ({click_x}, {click_y})")
        
        win32api.SetCursorPos((click_x, click_y))
        time.sleep(0.5)
        
        if is_right_click:
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, click_x, click_y, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, click_x, click_y, 0, 0)
        else:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, click_x, click_y, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, click_x, click_y, 0, 0)
            
        return True

    except Exception as e:
        print(f"🔥 [UIA] 제어 실패: {e}")
        return False

def uia_type_text(window_handle, automation_id, text):
    """uiautomation으로 입력창을 찾아 클릭 후 텍스트 입력"""
    try:
        # 수정됨: y_offset 인자를 주지 않아 정중앙을 클릭하게 함
        if uia_click_list_item(window_handle, automation_id, is_right_click=False): 
            time.sleep(0.5)
            send_native_keys("^a{BACKSPACE}") # 기존 내용 삭제
            time.sleep(0.2)
            send_native_keys(text)
            return True
        return False
    except Exception as e:
        print(f"🔥 [UIA] 입력 실패: {e}")
        return False

# ---------------------------------------------------------
# 🛠️ 윈도우 네이티브 입력 함수
# ---------------------------------------------------------
def send_native_keys(keys):
    shell = win32com.client.Dispatch("WScript.Shell")
    shell.SendKeys(keys)

def get_window_handle(window_name):
    print(f"[System] '{window_name}' 창 찾는 중...")
    hwnd = win32gui.FindWindow(None, window_name)
    
    if not hwnd:
        # 부분 일치 검색
        def callback(h, _):
            if win32gui.IsWindowVisible(h):
                t = win32gui.GetWindowText(h)
                if window_name in t:
                    nonlocal hwnd
                    hwnd = h
                    return False
            return True
        try: win32gui.EnumWindows(callback, None)
        except: pass

    if hwnd:
        # 창을 맨 앞으로
        try:
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
        except: pass
        print(f"✅ 창 핸들 획득: {hex(hwnd)}")
        return hwnd
    else:
        print(f"❌ '{window_name}' 창을 찾을 수 없습니다.")
        return None

# ---------------------------------------------------------
# 메인 실행 로직
# ---------------------------------------------------------
def run_iras_automation():
    # 1. WinAppDriver 실행 (혹시 몰라 켜두지만, UIA 사용시 필수는 아님)
    try:
        subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except: pass
    time.sleep(2)

    # [Step 1] 메인 화면 진입 (키보드 매크로)
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if not main_hwnd: return

    try:
        print("[Step 1] 윈도우 키보드 명령 전송 (Alt+s -> i -> Enter)...")
        send_native_keys("%s") 
        time.sleep(1.0)
        send_native_keys("i")
        time.sleep(1.0)
        send_native_keys("{ENTER}")
        time.sleep(1.0)
        send_native_keys("{ENTER}") # 확인차
        print("✅ 키보드 입력 완료.")
    except Exception as e:
        print(f"❌ 키보드 입력 오류: {e}")

    print("[System] 팝업 창 로딩 대기 (3초)...")
    time.sleep(3) 

    # [Step 2] 설정 팝업창 제어 (UIA 사용)
    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd: 
        print("❌ 설정 창이 뜨지 않았습니다.")
        return

    try:
        # ---------------------------------------------------------
        # [Step 3] 검색창 입력 (ID: "101")
        # ---------------------------------------------------------
        print(f"\n[Step 3] 검색창(ID:101)에 '{TARGET_DEVICE}' 입력 (UIA)...")
        
        # uiautomation으로 직접 찾아서 클릭 & 입력
        if not uia_type_text(setup_hwnd, "101", TARGET_DEVICE):
            print("❌ 검색창 제어 실패")
            return

        print("   -> 필터링 대기 (2초)...")
        time.sleep(2) 

        # ---------------------------------------------------------
        # [Step 4] 장치 선택 및 우클릭 (ID: "1000")
        # ---------------------------------------------------------
        print(f"\n[Step 4] 검색된 장치 리스트(ID:1000) 상단 우클릭 (UIA)...")
        
        # uiautomation으로 리스트 컨테이너 찾아서 상단 클릭
        if uia_click_list_item(setup_hwnd, "1000", is_right_click=True, y_offset=25):
            print("🎉 우클릭 성공! (컨텍스트 메뉴 확인)")
        else:
            print("❌ 리스트 제어 실패")

        time.sleep(2)

    except Exception as e:
        print(f"🔥 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_iras_automation()