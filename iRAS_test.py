import time
import subprocess
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

# 테스트 대상 정보
TARGET_DEVICE = "105_T6831"
USER_ID = "admin123"
USER_PW = "qwerty0-"

# 🖱️ [좌표 설정] 우클릭 지점 기준 상대 좌표 (X, Y)
COORD_DEVICE_MODIFY = (50, 20)  # 장치 수정
COORD_FW_UPGRADE = (50, 70)     # 펌웨어 업그레이드 (장치 수정 2칸 아래)

# ---------------------------------------------------------
# 🛠️ [UIA] 공통 유틸리티 함수
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
        flags = win32con.MOUSEEVENTF_RIGHTDOWN | win32con.MOUSEEVENTF_RIGHTUP if is_right_click else win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP
        win32api.mouse_event(flags, cx, cy, 0, 0)
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
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP, tx, cy, 0, 0)
        return True
    except: return False

def send_native_keys(keys):
    win32com.client.Dispatch("WScript.Shell").SendKeys(keys)

def click_relative_mouse(dx, dy):
    cx, cy = win32api.GetCursorPos()
    tx, ty = cx + dx, cy + dy
    win32api.SetCursorPos((tx, ty))
    time.sleep(0.2)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP, tx, ty, 0, 0)

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
# 🚀 메인 실행 로직
# ---------------------------------------------------------
def run_iras_permission_check(device_name_to_search, user_id, user_pw):
    print(f"\n🖥️ [iRAS] 단독 테스트 시작 (ID: {user_id})...")

    # 1. 설정 진입
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if not main_hwnd: 
        print("❌ iRAS 메인 창을 찾을 수 없습니다.")
        return False

    print("   [iRAS] 설정 메뉴 진입...")
    send_native_keys("%s"); time.sleep(0.5)
    send_native_keys("i"); time.sleep(0.5)
    send_native_keys("{ENTER}"); time.sleep(0.5)
    send_native_keys("{ENTER}")
    time.sleep(3)

    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd: return False

    # 2. 장치 검색
    print(f"   [iRAS] 장치 검색: {device_name_to_search}")
    if not uia_type_text(setup_hwnd, "101", device_name_to_search): return False
    time.sleep(2)

    # 3. 장치 수정 진입
    print(f"   [iRAS] 우클릭 -> 장치 수정...")
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        click_relative_mouse(*COORD_DEVICE_MODIFY) 
    else: return False

    time.sleep(2)
    modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
    if not modify_hwnd: return False

    # 4. 정보 수정 (ID/PW 입력)
    print("   [iRAS] 계정 정보 입력...")
    if not uia_click_network_tab_offset(modify_hwnd): return False
    time.sleep(1.0)

    uia_type_text(modify_hwnd, "22043", user_id) 
    uia_type_text(modify_hwnd, "22045", user_pw) 

    print("   [iRAS] 연결 테스트 버튼 클릭...")
    # '22132'는 연결 테스트 버튼의 AutomationId
    if uia_click_element(modify_hwnd, "22132"):
        print("   [Wait] 테스트 수행 중 (3초 대기)...")
        time.sleep(3.0) 
        
        print("   [iRAS] 결과 팝업 닫기 (Enter)")
        send_native_keys("{ENTER}")
        time.sleep(1.0)
    else:
        print("⚠️ 연결 테스트 버튼을 찾지 못했습니다.")

    # 5. 저장 및 닫기
    print("   [iRAS] 정보 저장 (창 닫기)...")
    uia_click_element(modify_hwnd, "1") 
    time.sleep(2.0) 

    # -------------------------------------------------------------
    # 🧪 [권한 테스트] 펌웨어 업그레이드
    # -------------------------------------------------------------
    print("\n   🧪 [권한 테스트] 펌웨어 업그레이드 접근 시도...")
    
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        print(f"   [iRAS] 펌웨어 업그레이드({COORD_FW_UPGRADE}) 클릭...")
        click_relative_mouse(*COORD_FW_UPGRADE)
        
        print("   [Wait] 권한 거부 팝업 대기 (2초)...")
        time.sleep(2.0)
        
        print("   [iRAS] 팝업 닫기 (Enter)")
        send_native_keys("{ENTER}")
        time.sleep(1.0)
    else:
        return False

    # 6. 설정 창 종료
    if setup_hwnd:
        print("   [iRAS] 설정 창 종료...")
        uia_click_element(setup_hwnd, "1")

    print("\n✅ iRAS 단독 테스트 완료.")
    return True

# 단독 실행용
if __name__ == "__main__":
    try: subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except: pass
    time.sleep(2)

    run_iras_permission_check(TARGET_DEVICE, USER_ID, USER_PW)