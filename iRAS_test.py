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
CONTEXT_MENU_ITEM = "장치 수정..." # ⚠️ 정확한 텍스트여야 함 (점 3개 확인)

# ---------------------------------------------------------
# 🛠️ [핵심] UIAutomation 기반 제어 함수
# ---------------------------------------------------------
def uia_click_element(window_handle, automation_id, is_right_click=False, y_offset=None):
    """
    요소(ID)를 찾아 클릭합니다.
    :param y_offset: None이면 '정중앙', 숫자면 '상단 + offset'
    """
    try:
        print(f"   [UIA] 핸들({hex(window_handle)})에서 요소(ID:{automation_id}) 탐색 중...")
        
        window = auto.ControlFromHandle(window_handle)
        target_elem = window.Control(AutomationId=automation_id)
        
        if not target_elem.Exists(maxSearchSeconds=3):
            print(f"❌ [UIA] 요소(ID:{automation_id})를 찾을 수 없습니다.")
            return False
            
        rect = target_elem.BoundingRectangle
        
        click_x = int((rect.left + rect.right) / 2)
        if y_offset is None:
            click_y = int((rect.top + rect.bottom) / 2)
        else:
            click_y = int(rect.top + y_offset)
            
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
    """입력창 중앙 클릭 후 텍스트 입력"""
    try:
        if uia_click_element(window_handle, automation_id, is_right_click=False, y_offset=None):
            time.sleep(0.5)
            send_native_keys("^a{BACKSPACE}")
            time.sleep(0.2)
            send_native_keys(text)
            return True
        return False
    except Exception as e:
        print(f"🔥 [UIA] 텍스트 입력 실패: {e}")
        return False

def click_relative_from_current_pos(dx, dy):
    """
    현재 마우스 위치에서 가로(dx), 세로(dy)만큼 이동하여 좌클릭합니다.
    예: dx=20, dy=20 이면 오른쪽 아래 대각선으로 살짝 이동
    """
    try:
        # 1. 현재 마우스 좌표 가져오기 (우클릭 직후의 위치)
        current_x, current_y = win32api.GetCursorPos()
        
        target_x = current_x + dx
        target_y = current_y + dy
        
        print(f"   [Mouse] 현재({current_x}, {current_y}) -> 이동({target_x}, {target_y})")
        
        # 2. 마우스 이동 (부드럽게 보이기 위해 sleep 약간 추가 가능)
        win32api.SetCursorPos((target_x, target_y))
        time.sleep(0.5) # 이동 확인용 대기
        
        # 3. 좌클릭
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, target_x, target_y, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, target_x, target_y, 0, 0)
        print("   [Mouse] 상대 좌표 클릭 완료")
        return True
        
    except Exception as e:
        print(f"🔥 마우스 이동 실패: {e}")
        return False


# ---------------------------------------------------------
# 🛠️ Windows API 헬퍼
# ---------------------------------------------------------
def send_native_keys(keys):
    shell = win32com.client.Dispatch("WScript.Shell")
    shell.SendKeys(keys)

def get_window_handle(window_name):
    print(f"[System] '{window_name}' 창 검색...")
    hwnd = win32gui.FindWindow(None, window_name)
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
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, 9)
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
    # 1. WinAppDriver (필요 시)
    try: subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except: pass
    time.sleep(2)

    # [Step 1] 메인 화면 진입
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if not main_hwnd: return
    try:
        send_native_keys("%s") 
        time.sleep(0.5); send_native_keys("i")
        time.sleep(0.5); send_native_keys("{ENTER}"); time.sleep(0.5); send_native_keys("{ENTER}")
    except: pass

    print("[System] 팝업 대기 (3초)...")
    time.sleep(3) 

    # [Step 2] 설정 팝업 핸들
    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd: return

    # [Step 3] 검색창 입력
    print(f"\n[Step 3] 검색창 입력...")
    if not uia_type_text(setup_hwnd, "101", TARGET_DEVICE): return
    time.sleep(2) 

    # [Step 4] 리스트 우클릭
    print(f"\n[Step 4] 장치 리스트 우클릭...")
    if not uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        return
    
    time.sleep(1.0) # 메뉴 뜨는 시간 대기

    # [Step 5] 마우스 위치 살짝 옮겨서 첫 번째 항목 클릭
    print(f"\n[Step 5] 마우스를 살짝 옮겨서 '장치 수정' 클릭...")
    
    # 오른쪽(x)으로 30픽셀, 아래(y)로 30픽셀 이동 후 클릭
    # 만약 클릭 위치가 빗나가면 이 숫자를 조절하세요 (예: 20, 20)
    click_relative_from_current_pos(50, 20)
    
    print("🎉 클릭 동작 완료 (장치 수정 창 확인)")
    
    print("🎉 완료")

if __name__ == "__main__":
    run_iras_automation()