import time
import subprocess
import os
import ctypes
import win32gui
import win32com.client
import win32api
import win32con
import uiautomation as auto

# ---------------------------------------------------------
# 🖥️ 다중 모니터/DPI 좌표 보정
# ---------------------------------------------------------
try:
    ctypes.windll.user32.SetProcessDPIAware()
except: pass

# ---------------------------------------------------------
# [설정 상수]
# ---------------------------------------------------------
WAD_PATH = r"C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe"
MAIN_WINDOW_TITLE = "IDIS Center Remote Administration System"
SETUP_WINDOW_TITLE = "IDIS Center 설정"
MODIFY_WINDOW_TITLE = "장치 수정"

# 테스트 정보 (Restricted User)
TARGET_DEVICE = "105_T6831"
USER_ID = "admin123"
USER_PW = "qwerty0-"

# 🎯 [핵심 ID]
SURVEILLANCE_SCREEN_ID = "59648" # 감시 화면
SAVE_BUTTON_ID = "2005"          # 재생 화면의 저장 버튼

# 🖱️ [좌표 설정]
COORD_DEVICE_MODIFY = (50, 20)
COORD_REMOTE_SETUP = (50, 45)
COORD_FW_UPGRADE = (50, 70)

COORD_PLAYBACK = (50, 100)      
COORD_PTZ_CONTROL = (50, 125)   
COORD_COLOR_CONTROL = (50, 175) 
COORD_ALARM_PARENT = (50, 250)

DELTA_ALARM_ON = (150, 0)
DELTA_ALARM_OFF = (150, 25)
COORD_CLIP_COPY = (30, 0)

# ---------------------------------------------------------
# 🛠️ [UIA] 유틸리티 함수 (기존과 동일)
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
    
    # 1. FindWindow로 못 찾았을 경우 EnumWindows로 재탐색
    if not hwnd:
        def callback(h, _):
            if win32gui.IsWindowVisible(h) and window_name in win32gui.GetWindowText(h):
                nonlocal hwnd; hwnd = h; return False
            return True
        try: win32gui.EnumWindows(callback, None)
        except: pass
        
    if hwnd:
        try:
            # 2. [핵심 수정] 강제 포커싱을 위한 '최소화 -> 복구' 트릭
            # Windows는 사용자 인터랙션이 없으면 포커스 이동을 막으므로,
            # 창을 잠깐 최소화했다가 복구하는 동작(Action)을 주어 권한을 획득합니다.
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            time.sleep(0.2)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
            
            # 3. 최상단으로 가져오기
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"⚠️ 창 포커싱 실패 (우회 시도): {e}")
            # 4. [Fallback] 위 방법도 실패 시 Alt 키 입력으로 윈도우를 속임
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%') # Alt 키 입력 시뮬레이션
                win32gui.SetForegroundWindow(hwnd)
            except:
                pass
                
    return hwnd

def right_click_surveillance_screen(window_handle):
    print(f"   [UIA] 감시 화면(ID: {SURVEILLANCE_SCREEN_ID}) 탐색 중...")
    try:
        window = auto.ControlFromHandle(window_handle)
        target_pane = window.PaneControl(AutomationId=SURVEILLANCE_SCREEN_ID)
        
        if target_pane.Exists(maxSearchSeconds=3):
            rect = target_pane.BoundingRectangle
            cx = int((rect.left + rect.right) / 2)
            cy = int(rect.top + 100) 
            if cy > rect.bottom: cy = int((rect.top + rect.bottom) / 2)
            
            win32api.SetCursorPos((cx, cy))
            time.sleep(0.5)
            
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.2)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            return True
        return False
    except: return False

def return_to_watch_tab(main_hwnd):
    print("   [iRAS] 감시 탭 복귀 시도...")
    try:
        window = auto.ControlFromHandle(main_hwnd)
        first_tab = window.TabItemControl()
        if first_tab.Exists(maxSearchSeconds=3):
            rect = first_tab.BoundingRectangle
            cx = int((rect.left + rect.right) / 2)
            cy = int((rect.top + rect.bottom) / 2)
            win32api.SetCursorPos((cx, cy))
            time.sleep(0.3)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            print("   ✅ 감시 탭 복귀 완료")
            time.sleep(2.0)
            return True
    except: pass
    return False

# ---------------------------------------------------------
# 🧪 [Phases] (기존과 동일)
# ---------------------------------------------------------
def run_phase1_checks(main_hwnd, setup_hwnd):
    # (기존 Phase 1 코드와 동일 - 생략 없이 그대로 사용)
    print("\n   🧪 [Phase 1] 기능 차단 테스트...")
    # 1. 펌웨어
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        click_relative_mouse(*COORD_FW_UPGRADE)
        time.sleep(2.0)
        send_native_keys("{ENTER}"); time.sleep(1.0)
    
    # 설정 닫기
    uia_click_element(setup_hwnd, "1"); time.sleep(2.0)
    if not main_hwnd: return False, "핸들 없음"

    # 2. PTZ
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_PTZ_CONTROL)
        time.sleep(2.0)
        send_native_keys("{ENTER}"); time.sleep(1.0)

    # 3. 컬러
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_COLOR_CONTROL)
        time.sleep(2.0)
        send_native_keys("{ENTER}"); time.sleep(1.0)

    # 4. 알람
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_ALARM_PARENT); time.sleep(0.5)
        click_relative_mouse(*DELTA_ALARM_ON)
        time.sleep(2.0)
        send_native_keys("{ENTER}"); time.sleep(1.0)

    # 5. 클립카피
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_PLAYBACK)
        time.sleep(5.0)
        if uia_click_element(main_hwnd, SAVE_BUTTON_ID):
            time.sleep(1.0)
            click_relative_mouse(*COORD_CLIP_COPY)
            time.sleep(3.0)
            send_native_keys("{ENTER}"); time.sleep(1.0)
            return_to_watch_tab(main_hwnd)
    
    return True, "Phase 1 완료"

def run_phase2_checks(main_hwnd, setup_hwnd):
    # (기존 Phase 2 코드와 동일)
    print("\n   🧪 [Phase 2] 설정/검색 차단 테스트...")
    # 1. 원격 설정
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        click_relative_mouse(*COORD_REMOTE_SETUP)
        print("   [Wait] 팝업 대기 (8초)...")
        time.sleep(8.0)

    # 설정 닫기
    uia_click_element(setup_hwnd, "1"); time.sleep(2.0)

    # 2. 재생
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_PLAYBACK)
        time.sleep(3.0)
        send_native_keys("{ENTER}"); time.sleep(1.0)

    return_to_watch_tab(main_hwnd)
    return True, "Phase 2 완료"

# ---------------------------------------------------------
# 🔄 [신규] 관리자 로그인 복구 함수
# ---------------------------------------------------------
def restore_admin_login(device_name, admin_id, admin_pw):
    """테스트 종료 후 관리자 계정으로 로그인 상태 원복"""
    print(f"\n🔄 [iRAS] 관리자({admin_id}) 로그인 복구 시작...")
    
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if not main_hwnd: return False

    # 설정창 진입
    send_native_keys("%s"); time.sleep(0.5)
    send_native_keys("i"); time.sleep(0.5)
    send_native_keys("{ENTER}"); time.sleep(0.5)
    send_native_keys("{ENTER}")
    time.sleep(3)

    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd: return False

    # 장치 검색 & 수정 진입
    uia_type_text(setup_hwnd, "101", device_name)
    time.sleep(1.0)
    
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        click_relative_mouse(*COORD_DEVICE_MODIFY)
        time.sleep(2.0)
        
        modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
        if modify_hwnd:
            uia_click_network_tab_offset(modify_hwnd)
            # 관리자 ID/PW 입력
            uia_type_text(modify_hwnd, "22043", admin_id)
            uia_type_text(modify_hwnd, "22045", admin_pw)
            
            # 연결 테스트
            print("   [iRAS] 연결 테스트...")
            if uia_click_element(modify_hwnd, "22132"):
                time.sleep(3.0)
                send_native_keys("{ENTER}"); time.sleep(1.0)
            
            # 저장
            uia_click_element(modify_hwnd, "1")
            time.sleep(2.0)
            
    # 설정창 닫기
    if setup_hwnd:
        uia_click_element(setup_hwnd, "1")
        
    print("✅ 관리자 로그인 복구 완료.")
    return True

# ---------------------------------------------------------
# 🚀 메인 진입점
# ---------------------------------------------------------
def run_iras_permission_check(device_name_to_search, user_id, user_pw, phase=1):
    print(f"\n🖥️ [iRAS] 테스트 시작 (Phase: {phase})...")
    try: subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except: pass
    time.sleep(2)

    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE)
    if not main_hwnd: return False, "iRAS 미실행"

    # Phase 1: 로그인 + 검증
    if phase == 1:
        # 설정창 진입 -> 로그인
        print("   [iRAS] 로그인 시퀀스...")
        send_native_keys("%s"); time.sleep(0.5)
        send_native_keys("i"); time.sleep(0.5)
        send_native_keys("{ENTER}"); time.sleep(0.5)
        send_native_keys("{ENTER}")
        time.sleep(3)

        setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
        if not setup_hwnd: return False, "설정창 실패"

        uia_type_text(setup_hwnd, "101", device_name_to_search)
        time.sleep(1.0)
        
        if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
            click_relative_mouse(*COORD_DEVICE_MODIFY)
            time.sleep(2.0)
            modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
            if modify_hwnd:
                uia_click_network_tab_offset(modify_hwnd)
                uia_type_text(modify_hwnd, "22043", user_id)
                uia_type_text(modify_hwnd, "22045", user_pw)
                
                # 연결 테스트
                if uia_click_element(modify_hwnd, "22132"):
                    time.sleep(3.0)
                    send_native_keys("{ENTER}"); time.sleep(1.0)
                
                uia_click_element(modify_hwnd, "1")
                time.sleep(2.0)
        else:
            return False, "로그인 실패"

        return run_phase1_checks(main_hwnd, setup_hwnd)

    # Phase 2: 로그인 생략 + 검증
    elif phase == 2:
        # 설정창만 다시 열기
        send_native_keys("%s"); time.sleep(0.5)
        send_native_keys("i"); time.sleep(0.5)
        send_native_keys("{ENTER}"); time.sleep(0.5)
        send_native_keys("{ENTER}")
        time.sleep(3)
        
        setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
        uia_type_text(setup_hwnd, "101", device_name_to_search)
        time.sleep(1.0)
        
        return run_phase2_checks(main_hwnd, setup_hwnd)

    return False, "Invalid Phase"