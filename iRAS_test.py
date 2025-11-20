import time
import subprocess
import win32gui
import win32com.client
import win32api
import win32con
import uiautomation as auto  # pip install uiautomation

# ---------------------------------------------------------
# [설정 및 상수 정의]
# ---------------------------------------------------------
WAD_PATH = r"C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe"
MAIN_WINDOW_TITLE = "IDIS Center Remote Administration System"
SETUP_WINDOW_TITLE = "IDIS Center 설정"
TARGET_DEVICE = "105_T6831"

# ---------------------------------------------------------
# 🛠️ [핵심] UIAutomation 기반 제어 함수
# ---------------------------------------------------------
def uia_click_element(window_handle, automation_id, is_right_click=False, y_offset=None):
    """
    요소를 찾아 클릭합니다.
    :param y_offset: None이면 '요소 정중앙' 클릭, 숫자(예: 25)면 '상단 + offset' 클릭
    """
    try:
        print(f"   [UIA] 핸들({hex(window_handle)})에서 요소(ID:{automation_id}) 탐색 중...")
        
        window = auto.ControlFromHandle(window_handle)
        target_elem = window.Control(AutomationId=automation_id)
        
        if not target_elem.Exists(maxSearchSeconds=3):
            print(f"❌ [UIA] 요소(ID:{automation_id})를 찾을 수 없습니다.")
            return False
            
        rect = target_elem.BoundingRectangle
        # print(f"   [UIA] 좌표 발견: {rect}")  # 디버깅 필요 시 주석 해제
        
        # X 좌표: 가로 중앙
        click_x = int((rect.left + rect.right) / 2)
        
        # Y 좌표: 오프셋 유무에 따라 분기
        if y_offset is None:
            click_y = int((rect.top + rect.bottom) / 2)  # 정중앙 (버튼, 입력창)
        else:
            click_y = int(rect.top + y_offset)           # 상단 기준 (리스트 목록)
            
        # 마우스 이동 및 클릭
        win32api.SetCursorPos((click_x, click_y))
        time.sleep(0.3)
        
        if is_right_click:
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, click_x, click_y, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, click_x, click_y, 0, 0)
            print("   [UIA] 우클릭 완료")
        else:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, click_x, click_y, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, click_x, click_y, 0, 0)
            print("   [UIA] 좌클릭 완료")
            
        return True

    except Exception as e:
        print(f"🔥 [UIA] 클릭 제어 실패: {e}")
        return False

def uia_type_text(window_handle, automation_id, text):
    """입력창을 찾아 클릭(정중앙)하고 텍스트를 입력합니다."""
    try:
        # 입력창은 정중앙을 클릭해야 하므로 y_offset=None
        if uia_click_element(window_handle, automation_id, is_right_click=False, y_offset=None):
            time.sleep(0.5)
            send_native_keys("^a{BACKSPACE}")  # 전체 선택 후 삭제
            time.sleep(0.2)
            send_native_keys(text)
            return True
        return False
    except Exception as e:
        print(f"🔥 [UIA] 텍스트 입력 실패: {e}")
        return False

# ---------------------------------------------------------
# 🛠️ Windows API 헬퍼 함수
# ---------------------------------------------------------
def send_native_keys(keys):
    """WScript.Shell을 이용한 키보드 입력"""
    shell = win32com.client.Dispatch("WScript.Shell")
    shell.SendKeys(keys)

def get_window_handle(window_name):
    """창 제목으로 핸들을 찾고 최상위로 가져옵니다."""
    print(f"[System] '{window_name}' 창 검색...")
    hwnd = win32gui.FindWindow(None, window_name)
    
    # 정확한 일치가 없으면 부분 일치 검색
    if not hwnd:
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
        try:
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, 9) # 최소화 복원
            win32gui.SetForegroundWindow(hwnd)
        except: pass
        print(f"✅ 창 핸들 획득: {hex(hwnd)}")
        return hwnd
    else:
        print(f"❌ '{window_name}' 창을 찾을 수 없습니다.")
        return None

# ---------------------------------------------------------
# 🚀 메인 실행 로직
# ---------------------------------------------------------
def run_iras_automation():
    # 1. WinAppDriver 실행 (필요 시)
    try:
        subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except: pass
    time.sleep(2)

    # [Step 1] 메인 화면 진입
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if not main_hwnd: return

    try:
        print("[Step 1] 설정 메뉴 진입 (Alt+s -> i)...")
        send_native_keys("%s") 
        time.sleep(0.5)
        send_native_keys("i")
        time.sleep(0.5)
        send_native_keys("{ENTER}")
        time.sleep(0.5)
        send_native_keys("{ENTER}")
    except Exception as e:
        print(f"❌ 키보드 입력 오류: {e}")

    print("[System] 팝업 대기 (3초)...")
    time.sleep(3) 

    # [Step 2] 설정 팝업 핸들 획득
    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd: return

    # [Step 3] 검색창 입력 (ID: 101) -> 정중앙 클릭
    print(f"\n[Step 3] 검색창에 '{TARGET_DEVICE}' 입력...")
    if not uia_type_text(setup_hwnd, "101", TARGET_DEVICE):
        return
    
    print("   -> 필터링 대기 (2초)...")
    time.sleep(2) 

    # [Step 4] 리스트 선택 (ID: 1000) -> 상단 클릭 (y_offset=25)
    print(f"\n[Step 4] 검색된 장치 리스트 우클릭...")
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        print("🎉 자동화 성공! (컨텍스트 메뉴 확인)")
    else:
        print("❌ 리스트 선택 실패")

if __name__ == "__main__":
    run_iras_automation()