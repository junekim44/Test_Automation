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

# ---------------------------------------------------------
# 🛠️ [UIA] 공통 함수 (기존과 동일)
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
    win32api.SetCursorPos((cx + dx, cy + dy))
    time.sleep(0.2)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP, cx + dx, cy + dy, 0, 0)

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
# 🚀 [핵심] 외부에서 호출할 실행 함수
# ---------------------------------------------------------
def run_iras_permission_check(device_name_to_search, user_id, user_pw):
    """
    UserGroupTest에서 호출하는 함수.
    생성된 ID/PW를 받아 iRAS에서 로그인 및 권한 동작을 수행함.
    """
    print(f"\n🖥️ [iRAS] 데스크톱 자동화 시작 (ID: {user_id})...")

    # 1. WinAppDriver 실행 (옵션)
    try: subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except: pass
    time.sleep(2)

    # 2. iRAS 메인 -> 설정 진입
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if not main_hwnd:
        return False, "iRAS 메인 창을 찾을 수 없음"

    print("   [iRAS] 설정 메뉴 진입...")
    send_native_keys("%s"); time.sleep(0.5)
    send_native_keys("i"); time.sleep(0.5)
    send_native_keys("{ENTER}"); time.sleep(0.5)
    send_native_keys("{ENTER}")
    time.sleep(3)

    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd: return False, "설정 창 진입 실패"

    # 3. 장치 검색
    print(f"   [iRAS] 장치 검색: {device_name_to_search}")
    if not uia_type_text(setup_hwnd, "101", device_name_to_search): return False, "검색창 입력 실패"
    time.sleep(2)

    # 4. 우클릭 -> 장치 수정
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        print("   [iRAS] 메뉴 진입 (상대 좌표)...")
        click_relative_mouse(50, 20) # 장치 수정 클릭
    else: return False, "리스트 우클릭 실패"

    time.sleep(2)
    modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
    if not modify_hwnd: return False, "장치 수정 팝업 안 뜸"

    # 5. 정보 수정 (ID/PW 입력)
    print("   [iRAS] 아이디/비번 입력 중...")
    if not uia_click_network_tab_offset(modify_hwnd): return False, "탭 전환 실패"
    time.sleep(1.0)

    uia_type_text(modify_hwnd, "22043", user_id) # 아이디 입력
    uia_type_text(modify_hwnd, "22045", user_pw) # 비번 입력
    
    # -------------------------------------------------------------
    # 🧪 [추가 동작] 권한 테스트 로직이 들어갈 자리
    # -------------------------------------------------------------
    print("\n   🧪 [iRAS] 권한 동작 테스트 수행...")
    
    # 예: 연결 테스트 버튼 누르기
    print("   -> 연결 테스트 시도...")
    if uia_click_element(modify_hwnd, "22132"):
        time.sleep(3.0)
        send_native_keys("{ENTER}") # 결과 팝업 닫기
    
    # TODO: 여기에 추가하고 싶은 동작(권한 확인 등)을 더 넣으세요.
    # 예: 특정 버튼이 비활성화 되어 있는지 확인 등...
    
    # 6. 마무리 (창 닫기)
    print("   [iRAS] 창 닫기 및 종료...")
    uia_click_element(modify_hwnd, "1") # 수정 창 확인(닫기)
    time.sleep(1.5)
    
    # 설정 창 닫기 (setup_hwnd 핸들이 유효한지 확인 필요하므로 다시 찾음)
    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if setup_hwnd:
        uia_click_element(setup_hwnd, "1") # 설정 창 확인(닫기)

    return True, "iRAS 자동화 테스트 완료"