import time
import subprocess
import os
import win32gui
import win32com.client
import win32api
import win32con
import uiautomation as auto

# ---------------------------------------------------------
# [설정 상수]
# ---------------------------------------------------------
WAD_PATH = r"C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe"
MAIN_WINDOW_TITLE = "IDIS Center Remote Administration System"
SETUP_WINDOW_TITLE = "IDIS Center 설정"
MODIFY_WINDOW_TITLE = "장치 수정"

# 테스트 정보
TARGET_DEVICE = "105_T6831"
USER_ID = "admin123"
USER_PW = "qwerty0-"

# 🖱️ [좌표 설정]
COORD_DEVICE_MODIFY = (50, 20)
COORD_REMOTE_SETUP = (50, 45)
COORD_FW_UPGRADE = (50, 70)
COORD_COLOR_CONTROL = (50, 175) # 색상 제어 (8번째 메뉴)
COORD_PTZ_CONTROL = (50, 125)

# 🎯 [핵심] 감시 화면 AutomationID
SURVEILLANCE_SCREEN_ID = "59648"

# ---------------------------------------------------------
# 🛠️ [UIA] 유틸리티 함수
# ---------------------------------------------------------
def uia_click_element(window_handle, automation_id, is_right_click=False, y_offset=None):
    try:
        window = auto.ControlFromHandle(window_handle)
        target_elem = window.Control(AutomationId=automation_id)
        if not target_elem.Exists(maxSearchSeconds=3): return False
        rect = target_elem.BoundingRectangle
        cx = int((rect.left + rect.right) / 2)
        cy = int((rect.top + rect.bottom) / 2) if y_offset is None else int(rect.top + y_offset)
        
        win32api.SetCursorPos((cx, cy))
        time.sleep(0.3)
        
        if is_right_click:
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        else:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        return True
    except: return False

def uia_type_text(window_handle, automation_id, text):
    try:
        if uia_click_element(window_handle, automation_id):
            time.sleep(0.5)
            win32com.client.Dispatch("WScript.Shell").SendKeys("^a{BACKSPACE}") 
            time.sleep(0.2)
            win32com.client.Dispatch("WScript.Shell").SendKeys(text)
            return True
        return False
    except: return False

def uia_click_network_tab_offset(window_handle):
    try:
        window = auto.ControlFromHandle(window_handle)
        first_tab = window.TabItemControl()
        if not first_tab.Exists(maxSearchSeconds=2): return False
        rect = first_tab.BoundingRectangle
        cx, cy = int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2)
        tx = cx + (rect.right - rect.left) + 5
        
        win32api.SetCursorPos((tx, cy))
        time.sleep(0.3)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        return True
    except: return False

def send_native_keys(keys):
    win32com.client.Dispatch("WScript.Shell").SendKeys(keys)

def click_relative_mouse(dx, dy):
    cx, cy = win32api.GetCursorPos()
    tx, ty = cx + dx, cy + dy
    win32api.SetCursorPos((tx, ty))
    time.sleep(0.3)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.1)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def get_window_handle(window_name):
    hwnd = win32gui.FindWindow(None, window_name)
    if not hwnd:
        def callback(h, _):
            if win32gui.IsWindowVisible(h) and window_name in win32gui.GetWindowText(h):
                nonlocal hwnd; hwnd = h; return False
            return True
        try: win32gui.EnumWindows(callback, None)
        except: pass
    if hwnd:
        try:
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, 9)
            win32gui.SetForegroundWindow(hwnd)
        except: pass
    return hwnd

# ---------------------------------------------------------
# 🔍 [수정됨] 비디오 패널 찾기 (AutomationId 사용)
# ---------------------------------------------------------
def right_click_surveillance_screen(window_handle):
    print(f"   [UIA] 감시 화면(ID: {SURVEILLANCE_SCREEN_ID}) 탐색 중...")
    try:
        window = auto.ControlFromHandle(window_handle)
        
        # 🎯 AutomationId로 직접 찾기
        target_pane = window.PaneControl(AutomationId=SURVEILLANCE_SCREEN_ID)
        
        if target_pane.Exists(maxSearchSeconds=3):
            rect = target_pane.BoundingRectangle
            print(f"   ✅ 감시 화면 발견! (Rect: {rect})")
            
            # 좌표 계산: 중앙 X, 상단 Y (위에서 100px 아래)
            cx = int((rect.left + rect.right) / 2)
            cy = int(rect.top + 100) 
            if cy > rect.bottom: cy = int((rect.top + rect.bottom) / 2)
            
            print(f"   [Mouse] 화면 상단({cx}, {cy}) 우클릭...")
            win32api.SetCursorPos((cx, cy))
            time.sleep(0.5)
            
            # 포커스 확보 (좌클릭)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.2)
            
            # 우클릭 실행
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            return True
        else:
            print(f"❌ 감시 화면(ID: {SURVEILLANCE_SCREEN_ID})을 찾을 수 없습니다.")
            return False
            
    except Exception as e:
        print(f"🔥 화면 탐색 오류: {e}")
        return False

# ---------------------------------------------------------
# 🚀 메인 실행 로직
# ---------------------------------------------------------
def run_iras_permission_check(device_name_to_search, user_id, user_pw):
    print(f"\n🖥️ [iRAS] 단독 테스트 시작 (ID: {user_id})...")

    # 1. 설정 진입
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if not main_hwnd: 
        print("❌ iRAS 메인 창을 찾을 수 없습니다.")
        return False

    # print("   [iRAS] 설정 메뉴 진입...")
    # send_native_keys("%s"); time.sleep(0.5)
    # send_native_keys("i"); time.sleep(0.5)
    # send_native_keys("{ENTER}"); time.sleep(0.5)
    # send_native_keys("{ENTER}")
    # time.sleep(3)

    # setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    # if not setup_hwnd: return False

    # # 2. 장치 검색
    # print(f"   [iRAS] 장치 검색: {device_name_to_search}")
    # if not uia_type_text(setup_hwnd, "101", device_name_to_search): return False
    # time.sleep(2)

    # # 3. 장치 수정 진입
    # print(f"   [iRAS] 우클릭 -> 장치 수정...")
    # if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
    #     click_relative_mouse(*COORD_DEVICE_MODIFY) 
    # else: return False

    # time.sleep(2)
    # modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
    # if not modify_hwnd: return False

    # # 4. 정보 수정 (ID/PW 입력)
    # print("   [iRAS] 계정 정보 입력...")
    # if not uia_click_network_tab_offset(modify_hwnd): return False
    # time.sleep(1.0)

    # uia_type_text(modify_hwnd, "22043", user_id) 
    # uia_type_text(modify_hwnd, "22045", user_pw) 

    # # 5. 연결 테스트
    # print("   [iRAS] 연결 테스트 수행...")
    # if uia_click_element(modify_hwnd, "22132"):
    #     time.sleep(3.0) 
    #     send_native_keys("{ENTER}") 
    #     time.sleep(1.0)

    # # 6. 저장 및 닫기
    # print("   [iRAS] 정보 저장 (창 닫기)...")
    # uia_click_element(modify_hwnd, "1") 
    # time.sleep(2.0) 

    # # =============================================================
    # # 🧪 [권한 테스트] 설정 창 내부
    # # =============================================================
    
    # # 7. 펌웨어 업그레이드
    # print("\n   🧪 [권한 테스트 1/3] 펌웨어 업그레이드...")
    # if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
    #     click_relative_mouse(*COORD_FW_UPGRADE)
    #     time.sleep(2.0)
    #     print("   [iRAS] 팝업 닫기 (Enter)")
    #     send_native_keys("{ENTER}")
    #     time.sleep(1.0)

    # # 8. 원격 설정
    # print("\n   🧪 [권한 테스트 2/3] 원격 설정...")
    # if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
    #     click_relative_mouse(*COORD_REMOTE_SETUP)
    #     print("   [Wait] 팝업 자동 닫힘 대기 (8초)...")
    #     time.sleep(8.0)
    
    # # 9. 설정 창 종료
    # print("   [iRAS] 설정 창 종료...")
    # if setup_hwnd:
    #     uia_click_element(setup_hwnd, "1")
    # time.sleep(3.0) 

    # =============================================================
    # 🧪 [권한 테스트 3] 감시 화면 색상 제어 (AutomationId 사용)
    # =============================================================
    # print("\n   🧪 [권한 테스트 3/3] 감시 화면 색상 제어...")
    
    # main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    # if not main_hwnd: return False
    
    # # 수정된 탐색 함수 호출 (AutomationId 사용)
    # if right_click_surveillance_screen(main_hwnd):
    #     print(f"   [iRAS] 색상 제어({COORD_COLOR_CONTROL}) 클릭...")
    #     click_relative_mouse(*COORD_COLOR_CONTROL)
        
    #     print("   [Wait] 권한 거부 팝업 대기 (3초)...")
    #     time.sleep(3.0)
        
    #     print("   [iRAS] 팝업 닫기 (Enter)")
    #     send_native_keys("{ENTER}")
    #     time.sleep(1.0)
        
    # else:
    #     print("❌ 감시 화면을 찾지 못해 테스트 실패")
    #     return False
    
    # -------------------------------------------------
    # 4. PTZ 제어 (추가됨)
    # -------------------------------------------------
    print("\n   🧪 [권한 테스트 4/4] PTZ 제어...")
    # 다시 우클릭
    if right_click_surveillance_screen(main_hwnd):
        print(f"   [iRAS] PTZ 제어({COORD_PTZ_CONTROL}) 클릭...")
        click_relative_mouse(*COORD_PTZ_CONTROL) # (50, 125)
        
        print("   [Wait] 권한 거부 팝업 대기 (3초)...")
        time.sleep(3.0)
        
        print("   [iRAS] 팝업 닫기 (Enter)")
        send_native_keys("{ENTER}")
        time.sleep(1.0)
    else:
        print("❌ 감시 화면 탐색 실패")
        return False

    print("\n✅ iRAS 모든 권한 테스트 완료.")
    return True

if __name__ == "__main__":
    try: subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except: pass
    time.sleep(2)

    run_iras_permission_check(TARGET_DEVICE, USER_ID, USER_PW)