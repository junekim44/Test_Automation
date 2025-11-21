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

# 테스트 정보
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
COORD_CLIP_COPY = (30, 0) # 저장 버튼 기준 상대 좌표

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

def right_click_surveillance_screen(window_handle):
    print(f"   [UIA] 감시 화면(ID: {SURVEILLANCE_SCREEN_ID}) 탐색 중...")
    try:
        window = auto.ControlFromHandle(window_handle)
        target_pane = window.PaneControl(AutomationId=SURVEILLANCE_SCREEN_ID)
        
        if target_pane.Exists(maxSearchSeconds=3):
            rect = target_pane.BoundingRectangle
            print(f"   ✅ 감시 화면 발견 (Rect: {rect})")
            
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
        else:
            print("❌ 감시 화면을 찾을 수 없습니다.")
            return False
    except Exception as e:
        print(f"🔥 감시 화면 탐색 오류: {e}")
        return False

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
# 🧪 [Phase 1] 기능별 권한 거부 테스트
# ---------------------------------------------------------
def run_phase1_checks(main_hwnd, setup_hwnd):
    print("\n   🧪 [Phase 1] 업그레이드/컬러/PTZ/알람/클립카피 테스트...")

    # 1. 펌웨어 업그레이드
    print("   [Test 1-1] 펌웨어 업그레이드")
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        click_relative_mouse(*COORD_FW_UPGRADE)
        time.sleep(2.0)
        send_native_keys("{ENTER}")
        time.sleep(1.0)

    # 설정 창 닫기
    print("   [iRAS] 설정 창 닫기...")
    uia_click_element(setup_hwnd, "1")
    time.sleep(2.0)

    if not main_hwnd: return False, "메인 핸들 없음"

    # 2. PTZ 제어
    print("   [Test 1-2] PTZ 제어")
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_PTZ_CONTROL)
        time.sleep(2.0)
        send_native_keys("{ENTER}")
        time.sleep(1.0)

    # 3. 컬러 제어
    print("   [Test 1-3] 컬러 제어")
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_COLOR_CONTROL)
        time.sleep(2.0)
        send_native_keys("{ENTER}")
        time.sleep(1.0)

    # 4. 알람 아웃
    print("   [Test 1-4] 알람 아웃")
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_ALARM_PARENT)
        time.sleep(0.5)
        click_relative_mouse(*DELTA_ALARM_ON)
        time.sleep(2.0)
        send_native_keys("{ENTER}")
        time.sleep(1.0)

    # 5. 클립-카피
    print("   [Test 1-5] 클립-카피")
    if right_click_surveillance_screen(main_hwnd):
        print("   -> 녹화 데이터 재생 선택")
        click_relative_mouse(*COORD_PLAYBACK)
        
        print("   [Wait] 재생 화면 로딩 (5초)...")
        time.sleep(5.0)
        
        # 저장 버튼 클릭 (ID: 2005)
        print("   -> 저장 버튼(ID: 2005) 클릭")
        if uia_click_element(main_hwnd, SAVE_BUTTON_ID):
            time.sleep(1.0) # 메뉴 뜨는 시간 대기
            
            print("   -> 메뉴 클릭 (Relative)")
            click_relative_mouse(*COORD_CLIP_COPY)
            
            print("   [Wait] 권한 거부 팝업 대기 (3초)...")
            time.sleep(3.0)
            
            print("   -> 팝업 닫기 (Enter)")
            send_native_keys("{ENTER}")
            time.sleep(1.0)
            
            return_to_watch_tab(main_hwnd)
        else:
            print("❌ 저장 버튼을 찾을 수 없습니다.")

    return True, "Phase 1 완료"

# ---------------------------------------------------------
# 🧪 [Phase 2] 설정/검색 권한 거부 테스트
# ---------------------------------------------------------
def run_phase2_checks(main_hwnd, setup_hwnd):
    print("\n   🧪 [Phase 2] 원격설정/재생(검색) 테스트...")

    # 1. 원격 설정
    print("   [Test 2-1] 원격 설정")
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        click_relative_mouse(*COORD_REMOTE_SETUP)
        print("   [Wait] 팝업 자동 닫힘 대기 (8초)...")
        time.sleep(8.0)

    # 설정 창 닫기
    print("   [iRAS] 설정 창 닫기...")
    uia_click_element(setup_hwnd, "1")
    time.sleep(2.0)

    # 2. 녹화 데이터 재생
    print("   [Test 2-2] 녹화 데이터 재생 (차단 확인)")
    if right_click_surveillance_screen(main_hwnd):
        click_relative_mouse(*COORD_PLAYBACK)
        
        print("   [Wait] 권한 거부 팝업 대기 (3초)...")
        time.sleep(3.0)
        
        print("   -> 팝업 닫기 (Enter)")
        send_native_keys("{ENTER}")
        time.sleep(1.0)

    # 3. 최종 마무리: 감시 탭 복귀 (혹시 재생 탭에 있을 경우 대비)
    return_to_watch_tab(main_hwnd)

    return True, "Phase 2 완료"

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

    # ====================================================
    # Phase 1: 로그인 + 검증
    # ====================================================
    if phase == 1:
        print("   [iRAS] Phase 1: 로그인 및 초기 검증 진행...")
        
        # 설정창 진입
        send_native_keys("%s"); time.sleep(0.5)
        send_native_keys("i"); time.sleep(0.5)
        send_native_keys("{ENTER}"); time.sleep(0.5)
        send_native_keys("{ENTER}")
        time.sleep(3)

        setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
        if not setup_hwnd: return False, "설정창 진입 실패"

        # 장치 검색 & 로그인
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
                
                # ⭐️ 연결 테스트 (Phase 1 필수)
                print("   [iRAS] 연결 테스트 수행...")
                if uia_click_element(modify_hwnd, "22132"):
                    time.sleep(3.0) 
                    send_native_keys("{ENTER}") 
                    time.sleep(1.0)

                # 저장
                uia_click_element(modify_hwnd, "1") 
                time.sleep(2.0)
        else:
            return False, "로그인 실패"

        return run_phase1_checks(main_hwnd, setup_hwnd)

    # ====================================================
    # Phase 2: 로그인 생략 + 원격설정/재생 검증
    # ====================================================
    elif phase == 2:
        print("   [iRAS] Phase 2: 로그인 생략, 기능 차단 검증 진행...")
        
        # 설정창만 다시 열기 (로그인 상태 유지됨)
        send_native_keys("%s"); time.sleep(0.5)
        send_native_keys("i"); time.sleep(0.5)
        send_native_keys("{ENTER}"); time.sleep(0.5)
        send_native_keys("{ENTER}")
        time.sleep(3)
        
        setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
        if not setup_hwnd: return False, "설정창 진입 실패"
        
        # 장치 목록이 초기화되었을 수 있으므로 검색 재수행
        uia_type_text(setup_hwnd, "101", device_name_to_search)
        time.sleep(1.0)
        
        return run_phase2_checks(main_hwnd, setup_hwnd)

    else:
        return False, "Invalid Phase"