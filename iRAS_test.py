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

TARGET_DEVICE = "104_T6831"
SURVEILLANCE_SCREEN_ID = "59648"
SAVE_BUTTON_ID = "2005"

# 좌표 설정
COORD_DEVICE_MODIFY = (50, 20)
COORD_REMOTE_SETUP = (50, 45)
COORD_FW_UPGRADE = (50, 70)
COORD_PLAYBACK = (50, 100)      
COORD_PTZ_CONTROL = (50, 125)   
COORD_COLOR_CONTROL = (50, 175) 
COORD_ALARM_PARENT = (50, 250)
DELTA_ALARM_ON = (150, 0)
COORD_CLIP_COPY = (30, 0)

# ---------------------------------------------------------
# 🛠️ [Fix] 윈도우 핸들링 (팝업 창 포커스 문제 해결)
# ---------------------------------------------------------
def get_window_handle(window_name, force_focus=False):
    """
    창 핸들을 찾고 포커스를 맞춥니다.
    :param force_focus: True면 '최소화->복구' 트릭을 사용하여 강제로 포커스를 뺏어옵니다.
                        (브라우저에서 iRAS 메인으로 전환할 때만 True 사용)
    """
    hwnd = win32gui.FindWindow(None, window_name)
    
    # 1. 못 찾았을 경우 EnumWindows로 재탐색
    if not hwnd:
        def callback(h, _):
            if win32gui.IsWindowVisible(h) and window_name in win32gui.GetWindowText(h):
                nonlocal hwnd; hwnd = h; return False
            return True
        try: win32gui.EnumWindows(callback, None)
        except: pass
        
    if hwnd:
        try:
            # 최소화 상태라면 일단 복구
            if win32gui.IsIconic(hwnd): 
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # [핵심] 강제 포커싱 트릭은 force_focus=True일 때만 수행
            if force_focus:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                time.sleep(0.2)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
            
            # 일반적인 포커싱 시도
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            # 실패 시 Fallback (Alt키 입력으로 깨우기)
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%')
                win32gui.SetForegroundWindow(hwnd)
            except: pass
                
    return hwnd

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
        cx = int((rect.left + rect.right) / 2)
        cy = int((rect.top + rect.bottom) / 2)
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

def run_fen_setup_process(device_name_to_search, fen_name):
    """
    [통합 시나리오]
    1. iRAS 설정창 진입
    2. 장치 검색 및 수정창 진입
    3. 네트워크 탭 -> FEN 설정 -> 연결 테스트 -> 저장
    4. 설정창 닫기
    """
    print(f"\n🖥️ [iRAS] '{device_name_to_search}' FEN 설정 자동화 시작...")
    
    # 1. iRAS 메인 핸들 확보 (강제 포커스)
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE, force_focus=True)
    if not main_hwnd:
        print("❌ iRAS가 실행되어 있지 않습니다.")
        return False

    # 2. 설정 창 열기 (단축키 시퀀스)
    print("   [iRAS] 설정 창 진입 시도...")
    send_native_keys("%s"); time.sleep(0.3)
    send_native_keys("i"); time.sleep(0.3)
    send_native_keys("{ENTER}"); time.sleep(0.3)
    send_native_keys("{ENTER}")
    time.sleep(3.0)

    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd:
        print("❌ 설정 창을 찾을 수 없습니다.")
        return False

    # 3. 장치 검색 (ID: 101)
    print(f"   [iRAS] 장치 검색: {device_name_to_search}")
    uia_type_text(setup_hwnd, "101", device_name_to_search)
    time.sleep(1.5)

    # 4. 장치 리스트(1000)에서 우클릭 -> 장치 수정(좌표) 클릭
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        click_relative_mouse(*COORD_DEVICE_MODIFY) # (50, 20)
        print("   [Wait] 수정 창 대기...")
        time.sleep(2.0)
        
        modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
        if modify_hwnd:
            print("   [iRAS] 장치 수정 창 진입 성공")
            
            # 5. 네트워크 탭으로 이동
            if not uia_click_network_tab_offset(modify_hwnd):
                print("   ❌ 네트워크 탭 이동 실패")
                return False
            time.sleep(1.0)

            window = auto.ControlFromHandle(modify_hwnd)
            
            # 6. 주소 타입 변경 (콤보박스 ID: 1195 -> 'FEN')
            print("   [iRAS] 주소 타입 'FEN' 변경 시도...")
            combo = window.ComboBoxControl(AutomationId="1195")
            if combo.Exists(maxSearchSeconds=3):
                combo.Click() # 펼치기
                time.sleep(0.5)
                # 리스트에서 'FEN' 아이템 찾아 클릭 (전역 검색)
                fen_item = auto.ListItemControl(Name="FEN")
                if fen_item.Exists(maxSearchSeconds=2):
                    fen_item.Click()
                    print("   -> 'FEN' 선택 완료")
                else:
                    print("   ❌ 'FEN' 항목을 찾을 수 없습니다.")
            else:
                print("   ❌ 주소 타입 콤보박스(1195) 미발견")
            time.sleep(1.0)

            # 7. FEN 이름 입력 (DocumentControl ID: 22047)
            print(f"   [iRAS] FEN 이름 입력: {fen_name}")
            fen_input = window.DocumentControl(AutomationId="22047")
            if not fen_input.Exists(maxSearchSeconds=1):
                # DocumentControl로 안 잡히면 EditControl로 재시도
                fen_input = window.EditControl(AutomationId="22047")
            
            if fen_input.Exists(maxSearchSeconds=2):
                fen_input.Click()
                time.sleep(0.2)
                send_native_keys("^a{BACKSPACE}") # 기존 내용 삭제
                time.sleep(0.2)
                send_native_keys(fen_name)        # 새 이름 입력
                time.sleep(0.5)
            else:
                print("   ❌ FEN 입력 칸(22047)을 찾을 수 없습니다.")
                return False

            # 8. 연결 테스트 및 팝업 처리 (요청하신 방식)
            print("   [iRAS] 연결 테스트 실행...")
            # 연결 테스트 버튼 (ID: 22132)
            if uia_click_element(modify_hwnd, "22132"):
                print("   -> 테스트 버튼 클릭됨. 3초 대기...")
                time.sleep(3.0)
                print("   -> 결과 팝업 닫기 (ENTER)")
                send_native_keys("{ENTER}") 
                time.sleep(1.0)
            else:
                print("   ⚠️ 연결 테스트 버튼(22132) 클릭 실패")

            # 9. 저장 (확인 버튼 ID: 1)
            print("   [iRAS] 설정 저장...")
            uia_click_element(modify_hwnd, "1") 
            time.sleep(2.0)
            print("   ✅ 장치 수정 및 저장 완료")

        else:
            print("❌ '장치 수정' 팝업이 뜨지 않았습니다.")
            return False
    else:
        print("❌ 장치 리스트 클릭 실패")
        return False

    # 10. 설정 창 닫기 (확인 버튼 ID: 1)
    print("   [iRAS] 설정 창 닫기...")
    uia_click_element(setup_hwnd, "1")
    return True

def right_click_surveillance_screen(window_handle):
    print(f"   [UIA] 감시 화면 탐색 중...")
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
            time.sleep(2.0)
            return True
    except: pass
    return False

# ---------------------------------------------------------
# 🧪 [Phases]
# ---------------------------------------------------------
def run_phase1_checks(main_hwnd, setup_hwnd):
    print("\n   🧪 [Phase 1] 기능 차단 테스트 (Clip-Copy 등)...")
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

def restore_admin_login(device_name, admin_id, admin_pw):
    print(f"\n🔄 [iRAS] 관리자({admin_id}) 로그인 복구 시작...")
    # [Fix] 메인 창 찾을 때만 force_focus=True
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE, force_focus=True)
    if not main_hwnd: return False

    send_native_keys("%s"); time.sleep(0.5)
    send_native_keys("i"); time.sleep(0.5)
    send_native_keys("{ENTER}"); time.sleep(0.5)
    send_native_keys("{ENTER}")
    time.sleep(3)

    # [Fix] 설정창은 force_focus=False (기본값)
    setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
    if not setup_hwnd: return False

    uia_type_text(setup_hwnd, "101", device_name)
    time.sleep(1.0)
    
    if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
        click_relative_mouse(*COORD_DEVICE_MODIFY)
        time.sleep(2.0)
        
        # [Fix] 수정창도 force_focus=False
        modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
        if modify_hwnd:
            uia_click_network_tab_offset(modify_hwnd)
            uia_type_text(modify_hwnd, "22043", admin_id)
            uia_type_text(modify_hwnd, "22045", admin_pw)
            
            if uia_click_element(modify_hwnd, "22132"):
                time.sleep(3.0)
                send_native_keys("{ENTER}"); time.sleep(1.0)
            uia_click_element(modify_hwnd, "1")
            time.sleep(2.0)
            
    if setup_hwnd: uia_click_element(setup_hwnd, "1")
    return True

def run_iras_permission_check(device_name_to_search, user_id, user_pw, phase=1):
    print(f"\n🖥️ [iRAS] 테스트 시작 (Phase: {phase})...")
    try: subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except: pass
    time.sleep(2)

    # [Fix] 메인 창 진입 시에만 강제 포커싱 사용
    main_hwnd = get_window_handle(MAIN_WINDOW_TITLE, force_focus=True)
    if not main_hwnd: return False, "iRAS 미실행"

    if phase == 1:
        print("   [iRAS] 로그인 시퀀스...")
        send_native_keys("%s"); time.sleep(0.5)
        send_native_keys("i"); time.sleep(0.5)
        send_native_keys("{ENTER}"); time.sleep(0.5)
        send_native_keys("{ENTER}")
        time.sleep(3)

        # [Fix] 팝업 창들은 부드럽게 핸들만 획득 (force_focus=False)
        setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
        if not setup_hwnd: return False, "설정창 실패"

        uia_type_text(setup_hwnd, "101", device_name_to_search)
        time.sleep(1.0)
        
        if uia_click_element(setup_hwnd, "1000", is_right_click=True, y_offset=25):
            click_relative_mouse(*COORD_DEVICE_MODIFY)
            time.sleep(2.0)
            
            # [Fix]
            modify_hwnd = get_window_handle(MODIFY_WINDOW_TITLE)
            if modify_hwnd:
                uia_click_network_tab_offset(modify_hwnd)
                uia_type_text(modify_hwnd, "22043", user_id)
                uia_type_text(modify_hwnd, "22045", user_pw)
                
                if uia_click_element(modify_hwnd, "22132"):
                    time.sleep(3.0)
                    send_native_keys("{ENTER}"); time.sleep(1.0)
                uia_click_element(modify_hwnd, "1")
                time.sleep(2.0)
        else:
            return False, "로그인 실패"

        return run_phase1_checks(main_hwnd, setup_hwnd)

    elif phase == 2:
        send_native_keys("%s"); time.sleep(0.5)
        send_native_keys("i"); time.sleep(0.5)
        send_native_keys("{ENTER}"); time.sleep(0.5)
        send_native_keys("{ENTER}")
        time.sleep(3)
        
        # [Fix]
        setup_hwnd = get_window_handle(SETUP_WINDOW_TITLE)
        uia_type_text(setup_hwnd, "101", device_name_to_search)
        time.sleep(1.0)
        
        return run_phase2_checks(main_hwnd, setup_hwnd)

    return False, "Invalid Phase"