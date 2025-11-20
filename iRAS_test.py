import time
import subprocess
import win32gui
import win32com.client
import win32api
import win32con
import uiautomation as auto

# ---------------------------------------------------------
# [설정 및 상수 정의]
# ---------------------------------------------------------
WAD_PATH = r"C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe"
MAIN_WINDOW_TITLE = "IDIS Center Remote Administration System"
SETUP_WINDOW_TITLE = "IDIS Center 설정"
MODIFY_WINDOW_TITLE = "장치 수정"

TARGET_DEVICE = "105_T6831"
TARGET_ID = "admin123"
TARGET_PW = "qwerty0-"

# ---------------------------------------------------------
# 🛠️ [UIA] 핵심 함수
# ---------------------------------------------------------
def uia_click_element(window_handle, automation_id, is_right_click=False, y_offset=None):
    """ 요소 ID로 클릭 """
    try:
        print(f"   [UIA] 요소(ID:{automation_id}) 탐색...")
        window = auto.ControlFromHandle(window_handle)
        target_elem = window.Control(AutomationId=automation_id)
        
        if not target_elem.Exists(maxSearchSeconds=3):
            print(f"❌ 요소(ID:{automation_id}) 찾기 실패")
            return False
            
        rect = target_elem.BoundingRectangle
        click_x = int((rect.left + rect.right) / 2)
        click_y = int((rect.top + rect.bottom) / 2) if y_offset is None else int(rect.top + y_offset)
            
        win32api.SetCursorPos((click_x, click_y))
        time.sleep(0.3)
        flags = win32con.MOUSEEVENTF_RIGHTDOWN | win32con.MOUSEEVENTF_RIGHTUP if is_right_click else win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP
        win32api.mouse_event(flags, click_x, click_y, 0, 0)
        print("   ✅ 클릭 완료")
        return True
    except Exception as e:
        print(f"🔥 클릭 실패: {e}")
        return False

def uia_type_text(window_handle, automation_id, text):
    """ 입력창 클릭 후 텍스트 입력 """
    try:
        if uia_click_element(window_handle, automation_id):
            time.sleep(0.5)
            send_native_keys("^a{BACKSPACE}") 
            time.sleep(0.2)
            send_native_keys(text)
            return True
        return False
    except: return False

def uia_click_network_tab_offset(window_handle):
    """ 첫 번째 탭(정보)을 기준으로 오른쪽으로 이동하여 클릭 """
    try:
        print("   [Offset] 탭 위치 계산 중...")
        window = auto.ControlFromHandle(window_handle)
        first_tab = window.TabItemControl()
        
        if not first_tab.Exists(maxSearchSeconds=2):
            return False
            
        rect = first_tab.BoundingRectangle
        tab_width = rect.right - rect.left
        
        # 정보 탭 중앙
        center_x = int((rect.left + rect.right) / 2)
        center_y = int((rect.top + rect.bottom) / 2)
        
        # 네트워크 탭 위치 (오른쪽으로 탭 너비만큼 이동)
        target_x = center_x + tab_width + 5
        
        win32api.SetCursorPos((target_x, center_y))
        time.sleep(0.3)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, target_x, center_y, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, target_x, center_y, 0, 0)
        print("   ✅ 탭 클릭 완료 (Offset 방식)")
        return True
    except: return False

# ---------------------------------------------------------
# 🛠️ 헬퍼 함수
# ---------------------------------------------------------
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
# 🚀 메인 실행 로직
# ---------------------------------------------------------
def run_iras_automation():
    # [Step 1] 메인 -> 설정
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if main_hwnd:
        print("[Step 1] 설정 진입...")
        send_native_keys("%s"); time.sleep(0.5)
        send_native_keys("i"); time.sleep(0.5)
        send_native_keys("{ENTER}"); time.sleep(0.5)
        send_native_keys("{ENTER}")
    
    time.sleep(3)

    # [Step 2] 설정 핸들
    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd: return

    # [Step 3] 장치 검색
    print(f"\n[Step 3] 장치 검색: {TARGET_DEVICE}")
    if not uia_type_text(setup_hwnd, "101", TARGET_DEVICE): return
    time.sleep(2)

    # [Step 4] 우클릭
    print(f"\n[Step 4] 우클릭...")
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        # [Step 5] 메뉴 선택
        print(f"\n[Step 5] 장치 수정 선택...")
        click_relative_mouse(50, 20)
    else: return

    print("[System] 팝업 대기 (2초)...")
    time.sleep(2)

    # [Step 6] 수정 창 제어
    modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
    if modify_hwnd:
        print(f"\n[Step 6] 정보 수정 시작...")

        # 1. 탭 이동
        if uia_click_network_tab_offset(modify_hwnd):
            time.sleep(1.0) 
            
            # 2. 아이디/비번 입력
            print("   -> 아이디 입력")
            uia_type_text(modify_hwnd, "22043", TARGET_ID)
            
            print("   -> 비밀번호 입력")
            uia_type_text(modify_hwnd, "22045", TARGET_PW)
            
            # 3. 연결 테스트 (ID: 22132)
            print("\n[Step 7] 연결 테스트 진행...")
            if uia_click_element(modify_hwnd, "22132"):
                print("   -> 테스트 중... (3초 대기)")
                time.sleep(3.0) # 네트워크 테스트 시간 고려
                
                print("   -> 결과 팝업 닫기 (Enter)")
                send_native_keys("{ENTER}")
                time.sleep(1.0)
            
            # 4. 장치 수정 창 닫기 (ID: 1 - 확인 버튼)
            print("\n[Step 8] 장치 수정 완료 (확인 버튼 클릭)...")
            uia_click_element(modify_hwnd, "1")
            
            time.sleep(1.5) # 창 닫히는 시간 대기

            # 5. 설정 창 닫기 (ID: 1 - 확인 버튼)
            # 주의: 이제 modify_hwnd는 사라졌으므로 setup_hwnd를 사용해야 함
            print("\n[Step 9] 설정 저장 및 종료...")
            uia_click_element(setup_hwnd, "1")
            
            print("\n🎉 모든 자동화 시나리오 성공!")
        else:
            print("❌ 탭 클릭 실패")
    else:
        print("❌ 수정 창 안 뜸")

if __name__ == "__main__":
    run_iras_automation()