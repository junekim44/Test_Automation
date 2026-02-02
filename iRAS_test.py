import time
import ctypes
import win32gui
import win32com.client
import win32api
import win32con
import win32clipboard
import uiautomation as auto
import re
import msvcrt
from config import (
    IRAS_TITLES, IRAS_IDS, IRAS_COORDS, IRAS_TABS,
    IRAS_DELAYS, IRAS_SURVEILLANCE_OFFSETS, IRAS_KEYS, TIMEOUTS
)

# DPI 인식
try: 
    ctypes.windll.user32.SetProcessDPIAware()
except: 
    pass

# ---------------------------------------------------------
# 🤖 [Class] iRAS 컨트롤러 (통합)
# ---------------------------------------------------------
class IRASController:
    def __init__(self):
        self.shell = win32com.client.Dispatch("WScript.Shell")

    # --- [내부 유틸] ---
    def _get_handle(self, title, force_focus=False, use_alt=True):
        """창 핸들 찾기 및 강력한 포커스 전환"""
        hwnd = win32gui.FindWindow(None, title)
        
        # 정확한 제목으로 못 찾으면 부분 일치 검색
        if not hwnd: 
            def callback(h, _):
                if win32gui.IsWindowVisible(h) and title in win32gui.GetWindowText(h):
                    nonlocal hwnd; hwnd = h
            try: 
                win32gui.EnumWindows(callback, None)
            except: 
                pass

        if hwnd:
            try:
                if win32gui.IsIconic(hwnd): 
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                
                if force_focus:
                    # [중요] 윈도우 포커스 락 해제를 위한 Alt 키 트릭
                    if use_alt:
                        self.shell.SendKeys('%')
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(IRAS_DELAYS["focus"])
                    # UIA를 통한 2차 포커스 시도
                    if not use_alt:
                        rect = win32gui.GetWindowRect(hwnd)
                        # 창의 상단(타이틀바 근처) 안전한 곳 클릭
                        safe_x = rect[0] + 100
                        safe_y = rect[1] + 10
                        
                        current_pos = win32api.GetCursorPos()
                        win32api.SetCursorPos((safe_x, safe_y))
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        win32api.SetCursorPos(current_pos) # 마우스 원위치
                        time.sleep(IRAS_DELAYS["focus"])

                    try: 
                        auto.ControlFromHandle(hwnd).SetFocus()
                    except: 
                        pass
            except: 
                pass
        return hwnd
    
    def _clear_clipboard(self):
        """클립보드 비우기 (공통 유틸)"""
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except: 
            pass

    def _send_key(self, key_code, is_ctrl=False):
        """키 입력 유틸 (공통)"""
        try:
            if is_ctrl:
                win32api.keybd_event(IRAS_KEYS["ctrl"], 0, 0, 0)
                time.sleep(IRAS_DELAYS["key"])
            
            win32api.keybd_event(key_code, 0, 0, 0)
            time.sleep(IRAS_DELAYS["key"])
            win32api.keybd_event(key_code, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(IRAS_DELAYS["key"])
            
            if is_ctrl:
                win32api.keybd_event(IRAS_KEYS["ctrl"], 0, win32con.KEYEVENTF_KEYUP, 0)
            return True
        except Exception as e:
            print(f"   ⚠️ 키 입력 실패: {e}")
            return False

    def _copy_debug_info(self, hwnd, y_offset=None):
        """감시 화면에서 디버그 정보 복사 (우클릭 + C)"""
        offset = y_offset or IRAS_SURVEILLANCE_OFFSETS["right_click_mid"]
        if self._click(hwnd, IRAS_IDS["surveillance_pane"], right_click=True, y_offset=offset):
            time.sleep(IRAS_DELAYS["menu_navigate"])
            self._send_key(IRAS_KEYS["c"])
            time.sleep(IRAS_DELAYS["clipboard_copy"])
            return True
        return False

    def save_snapshot(self):
        """iRAS 스냅샷 저장을 위한 Ctrl+S 키 입력"""
        print("   📸 [Input] Ctrl+S 키 입력 시도...")
        result = self._send_key(IRAS_KEYS["s"], is_ctrl=True)
        if result:
            print("   -> 키 입력 완료")
        return result

    def _click(self, hwnd, auto_id, right_click=False, y_offset=None):
        """UIA 요소 클릭 (y_offset 지원)"""
        try:
            win = auto.ControlFromHandle(hwnd)
            elem = win.Control(AutomationId=auto_id)
            if not elem.Exists(maxSearchSeconds=3): 
                return False
            
            rect = elem.BoundingRectangle
            cx = int((rect.left + rect.right) / 2)
            # y_offset이 있으면 Top 기준, 없으면 Center 기준
            cy = int(rect.top + y_offset) if y_offset is not None else int((rect.top + rect.bottom) / 2)

            win32api.SetCursorPos((cx, cy))
            time.sleep(IRAS_DELAYS["click"])
            
            if right_click:
                # 우클릭 전 좌클릭으로 포커스 확보
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(IRAS_DELAYS["key"])
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(IRAS_DELAYS["focus"])
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                time.sleep(IRAS_DELAYS["key"])
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            else:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(IRAS_DELAYS["key"])
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except: 
            return False

    def _input(self, hwnd, auto_id, text):
        """입력 필드 값 넣기"""
        if self._click(hwnd, auto_id):
            time.sleep(IRAS_DELAYS["input"])
            self.shell.SendKeys("^a{BACKSPACE}")
            time.sleep(IRAS_DELAYS["key"])
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                self.shell.SendKeys("^v")
                return True
            except: 
                pass
        return False

    def _click_relative(self, dx, dy):
        """상대 좌표 클릭"""
        cx, cy = win32api.GetCursorPos()
        win32api.SetCursorPos((cx + dx, cy + dy))
        time.sleep(IRAS_DELAYS["click"])
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(IRAS_DELAYS["key"])
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    def _right_click_surveillance(self, main_hwnd, offset=None):
        """감시 화면 우클릭"""
        offset = offset or IRAS_SURVEILLANCE_OFFSETS["right_click_top"]
        return self._click(main_hwnd, IRAS_IDS["surveillance_pane"], right_click=True, y_offset=offset)

    def _close_window(self, hwnd, auto_id=None):
        """창 닫기 (확인 버튼 클릭)"""
        if auto_id:
            self._click(hwnd, auto_id)
        else:
            self._click(hwnd, IRAS_IDS["ok_btn"])
        time.sleep(IRAS_DELAYS["window_close"])

    def _enter_setup(self):
        """메인화면 -> 시스템(S) -> 설정(i) 진입"""
        print("   [iRAS] 메인 화면 전환 및 설정 메뉴 진입...")
        main_hwnd = self._get_handle(IRAS_TITLES["main"], force_focus=True)
        if not main_hwnd: 
            print("❌ iRAS 메인 창을 찾을 수 없습니다.")
            return None
        time.sleep(IRAS_DELAYS["menu_navigate"])
        self.shell.SendKeys("%s")
        time.sleep(IRAS_DELAYS["menu_navigate"])
        self.shell.SendKeys("i")
        time.sleep(IRAS_DELAYS["menu_navigate"])
        self.shell.SendKeys("{ENTER}")
        time.sleep(IRAS_DELAYS["menu_navigate"])
        self.shell.SendKeys("{ENTER}")
        time.sleep(IRAS_DELAYS["window_open"])
        
        setup_hwnd = self._get_handle(IRAS_TITLES["setup"])
        if setup_hwnd: 
            return setup_hwnd
        print("❌ 설정 창이 열리지 않았습니다.")
        return None

    def _return_to_watch(self):
        """감시 탭 복귀"""
        main_hwnd = self._get_handle(IRAS_TITLES["main"])
        if not main_hwnd: 
            return
        try:
            win = auto.ControlFromHandle(main_hwnd)
            tab = win.TabItemControl()  # 첫 번째 탭(감시) 가정
            if tab.Exists(maxSearchSeconds=1): 
                tab.Click()
        except: 
            pass
    
    def _click_network_tab(self, hwnd):
        """장치 수정 창에서 '네트워크' 탭 클릭"""
        try:
            win = auto.ControlFromHandle(hwnd)
            tab_control = win.TabControl()
            if tab_control.Exists(maxSearchSeconds=2):
                # 1. 이름으로 찾기
                network_tab = tab_control.TabItemControl(Name=IRAS_TABS["network_name"])
                if network_tab.Exists(maxSearchSeconds=1):
                    network_tab.Click()
                    time.sleep(IRAS_DELAYS["tab_switch"])
                    return True
                
                # 2. 오프셋으로 찾기 (두 번째 탭 가정)
                rect = tab_control.BoundingRectangle
                click_x = rect.left + IRAS_TABS["network_offset_x"]
                click_y = rect.top + IRAS_TABS["network_offset_y"]
                
                win32api.SetCursorPos((int(click_x), int(click_y)))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(IRAS_DELAYS["tab_switch"])
                return True
        except: 
            return False
        return False
    
    def wait_for_video_attachment(self, timeout=None, max_retries=3):
        """
        스킵 가능한 대기 모드 (재시도 지원)
        - 지정된 시간(timeout) 동안 대기
        - 키보드 'Enter' 키를 누르면 즉시 남은 시간을 건너뛰고 진행
        - 타임아웃 시 자동 재시도 (최대 max_retries회)
        """
        timeout = timeout or TIMEOUTS["video_connection"]
        
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                print(f"\n   🔄 [iRAS] 영상 연결 재시도 ({attempt}/{max_retries})...")
            else:
                print(f"   ⏳ [iRAS] 영상 연결 대기 중... ({timeout}초)")
            print(f"   💡 (Tip: 영상이 이미 나왔다면 'Enter'를 눌러 즉시 건너뛸 수 있습니다)")
            
            # 입력 버퍼 비우기 (이전 입력이 남아있어서 바로 스킵되는 것 방지)
            while msvcrt.kbhit():
                msvcrt.getch()

            video_detected = False
            for i in range(timeout):
                # 1. 키보드 입력 감지 (Windows 전용)
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    # 엔터(Enter) 키 코드 = b'\r'
                    if key == b'\r':
                        print(f"\n   ⏩ [Skip] 사용자 입력으로 대기 시간을 건너뜁니다!")
                        video_detected = True
                        break

                # 2. 1초 대기
                time.sleep(1)
                remaining = timeout - i
                
                # 3. 진행 상황 출력
                if remaining % 10 == 0:
                    print(f"{remaining}s..", end=" ", flush=True)
                elif remaining % 2 == 0:
                    print(".", end="", flush=True)
            
            if video_detected:
                print("\n   ✅ 영상 연결 확인됨!")
                return True
            else:
                if attempt < max_retries:
                    print(f"\n   ⚠️ 타임아웃 ({timeout}초 경과). 재시도 대기 중...")
                    time.sleep(3)  # 재시도 전 짧은 대기
                else:
                    print(f"\n   ❌ 영상 연결 실패 (최대 재시도 횟수 초과)")
                    return False
                
        return False

    def _handle_permission_action(self, coord_key, wait_time=None):
        """권한 테스트 액션 공통 처리"""
        self._click_relative(*IRAS_COORDS[coord_key])
        wait = wait_time or IRAS_DELAYS["permission_action"]
        time.sleep(wait)
        self.shell.SendKeys("{ENTER}")
        time.sleep(IRAS_DELAYS["permission_result"])

    # --- [기능 1] 권한 테스트 (Phase 1) ---
    def run_permission_phase1(self, device_name):
        print("\n🧪 [iRAS] Phase 1: 기능 차단 테스트 (FW, PTZ, Color, Alarm, Clip)...")
        
        # 1. 펌웨어 업그레이드 차단 확인
        setup_hwnd = self._enter_setup()
        if setup_hwnd:
            self._input(setup_hwnd, IRAS_IDS["dev_search_input"], device_name)
            if self._click(setup_hwnd, IRAS_IDS["dev_list"], right_click=True, 
                          y_offset=IRAS_SURVEILLANCE_OFFSETS["device_list"]):
                self._handle_permission_action("menu_fw_up")
            self._close_window(setup_hwnd)

        main_hwnd = self._get_handle(IRAS_TITLES["main"], force_focus=True)
        if not main_hwnd: 
            return False

        # 2-4. 감시 화면 관련 테스트들
        for coord_key in ["menu_ptz", "menu_color"]:
            if self._right_click_surveillance(main_hwnd):
                self._handle_permission_action(coord_key)

        # 4. 알람 출력
        if self._right_click_surveillance(main_hwnd):
            self._click_relative(*IRAS_COORDS["menu_alarm"])
            time.sleep(IRAS_DELAYS["menu_navigate"])
            self._click_relative(*IRAS_COORDS["alarm_on"])
            self._handle_permission_action("menu_alarm", wait_time=0)  # 이미 대기했으므로

        # 5. 클립 카피 (재생 -> 저장 -> 클립복사)
        if self._right_click_surveillance(main_hwnd):
            self._click_relative(*IRAS_COORDS["menu_playback"])
            time.sleep(IRAS_DELAYS["playback_load"])
            
            if self._click(main_hwnd, IRAS_IDS["save_clip_btn"]):
                time.sleep(IRAS_DELAYS["menu_navigate"])
                self._click_relative(*IRAS_COORDS["clip_copy"])
                time.sleep(IRAS_DELAYS["test_popup"])
                self.shell.SendKeys("{ENTER}")
                time.sleep(IRAS_DELAYS["permission_result"])
                self._return_to_watch()
            
        print("   ✅ Phase 1 완료")
        return True
    
    

    # --- [기능 2] 권한 테스트 (Phase 2) ---
    def run_permission_phase2(self, device_name):
        print("\n🧪 [iRAS] Phase 2: 설정/검색 차단 테스트...")
        
        # 1. 원격 설정
        setup_hwnd = self._enter_setup()
        if setup_hwnd:
            self._input(setup_hwnd, IRAS_IDS["dev_search_input"], device_name)
            if self._click(setup_hwnd, IRAS_IDS["dev_list"], right_click=True, 
                          y_offset=IRAS_SURVEILLANCE_OFFSETS["device_list"]):
                self._click_relative(*IRAS_COORDS["menu_remote"])
                print(f"   [Wait] 차단 팝업 대기 ({IRAS_DELAYS['block_popup']}초)...")
                time.sleep(IRAS_DELAYS["block_popup"])
            self._close_window(setup_hwnd)

        # 2. 검색(재생)
        main_hwnd = self._get_handle(IRAS_TITLES["main"], force_focus=True)
        if main_hwnd and self._right_click_surveillance(main_hwnd):
            self._click_relative(*IRAS_COORDS["menu_playback"])
            time.sleep(IRAS_DELAYS["test_popup"])
            self.shell.SendKeys("{ENTER}")
            time.sleep(IRAS_DELAYS["permission_result"])
            self._return_to_watch()

        print("   ✅ Phase 2 완료")
        return True

    # --- [기능 3] FEN 설정 (자동화) ---
    def setup_fen(self, device_search_key, fen_name):
        """iRAS에서 장치를 검색하고 FEN 정보를 입력하여 연결 테스트를 수행합니다."""
        print(f"\n🖥️ [iRAS] FEN 설정 시작 (검색어: {device_search_key}, FEN: {fen_name})")
        
        # 1. 설정창 진입
        setup_hwnd = self._enter_setup()
        if not setup_hwnd: 
            return False

        # 2. 장치 검색
        print("   [iRAS] 장치 검색...")
        self._input(setup_hwnd, IRAS_IDS["dev_search_input"], device_search_key)
        time.sleep(IRAS_DELAYS["device_search"])
        
        # 3. 리스트에서 우클릭 -> 장치 수정
        if self._click(setup_hwnd, IRAS_IDS["dev_list"], right_click=True, 
                      y_offset=IRAS_SURVEILLANCE_OFFSETS["device_list"]):
            self._click_relative(*IRAS_COORDS["menu_modify"])
            time.sleep(IRAS_DELAYS["device_modify"])
        else:
            print("❌ 장치 리스트 클릭 실패")
            self._close_window(setup_hwnd)
            return False

        modify_hwnd = self._get_handle(IRAS_TITLES["modify"])
        if not modify_hwnd: 
            print("❌ '장치 수정' 창이 뜨지 않았습니다.")
            return False

        # 4. 네트워크 탭으로 이동
        self._click_network_tab(modify_hwnd)

        # 5. FEN 설정 (주소 유형 변경)
        print("   [iRAS] 주소 유형 'FEN' 선택...")
        try:
            win = auto.ControlFromHandle(modify_hwnd)
            combo = win.ComboBoxControl(AutomationId=IRAS_IDS["addr_type_combo"])
            if combo.Exists(maxSearchSeconds=2):
                combo.Click()
                time.sleep(IRAS_DELAYS["combo_select"])
                fen_item = auto.ListItemControl(Name="FEN")
                if fen_item.Exists(maxSearchSeconds=1): 
                    fen_item.Click()
        except: 
            pass
        
        # 6. FEN 이름 입력
        print(f"   [iRAS] FEN 이름 입력: {fen_name}")
        if not self._input(modify_hwnd, IRAS_IDS["fen_input"], fen_name):
            # 실패 시 에디트 컨트롤 다시 찾아 클릭 후 재시도
            try: 
                win = auto.ControlFromHandle(modify_hwnd)
                win.EditControl(AutomationId=IRAS_IDS["fen_input"]).Click()
            except: 
                pass
            self._input(modify_hwnd, IRAS_IDS["fen_input"], fen_name)

        # 7. 연결 테스트
        print("   [iRAS] 연결 테스트 실행...")
        if self._click(modify_hwnd, IRAS_IDS["test_btn"]):
            print(f"   -> 테스트 진행 중 ({IRAS_DELAYS['test_response']}초 대기)...")
            time.sleep(IRAS_DELAYS["test_response"])
            print("   -> 결과 팝업 닫기 (Enter)")
            self.shell.SendKeys("{ENTER}")
            time.sleep(IRAS_DELAYS["test_popup"])

        # 8. 저장 및 종료
        print("   [iRAS] 저장 및 설정 완료")
        self._close_window(modify_hwnd)
        self._close_window(setup_hwnd)
        return True

    # --- [기능 4] 연결 검증 ---
    def verify_connection(self, expected_mode="TcpDirectExternal"):
        """감시 화면 우클릭(지정 좌표) -> 'c' 입력 -> 클립보드 확인"""
        print(f"\n🔍 [iRAS] 연결 모드 검증 시작: '{expected_mode}' 기대함")
        
        main_hwnd = self._get_handle(IRAS_TITLES["main"], force_focus=True)
        if not main_hwnd:
            print("❌ iRAS 메인 창을 찾을 수 없습니다.")
            return False
        
        # 클립보드 비우기 및 디버그 정보 복사
        self._clear_clipboard()
        if not self._copy_debug_info(main_hwnd, IRAS_SURVEILLANCE_OFFSETS["right_click_top"]):
            print("❌ 감시 화면 클릭 실패")
            return False
            
        print("   -> 우클릭 후 'C' 키 입력 완료. 클립보드 확인 중...")
        
        try:
            win32clipboard.OpenClipboard()
            try:
                content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            except:
                content = ""
            win32clipboard.CloseClipboard()
            
            if not content:
                print("⚠️ 클립보드가 비어있습니다. (복사 실패)")
                return False

            if expected_mode in content:
                print(f"🎉 검증 성공! 연결 모드: {expected_mode}")
                return True
            else:
                match = re.search(r"Fen - (.+)", content)
                actual = match.group(1) if match else "Unknown"
                print(f"❌ 검증 실패. 기대값: {expected_mode}, 실제값: {actual}")
        except Exception as e:
            print(f"⚠️ 클립보드 접근 오류: {e}")
            try: 
                win32clipboard.CloseClipboard()
            except: 
                pass

        return False
    
    def get_current_ips(self):
        """감시 화면에서 우클릭 + 'c'를 눌러 클립보드 정보 중 IPS 값을 추출"""
        print("\n📊 [iRAS] IPS(프레임) 측정 시도...")
        main_hwnd = self._get_handle(IRAS_TITLES["main"], force_focus=True)
        if not main_hwnd: 
            return -1
        
        self._clear_clipboard()
        if not self._copy_debug_info(main_hwnd, IRAS_SURVEILLANCE_OFFSETS["right_click_mid"]):
            return -1
            
        print("   -> 디버그 정보 복사 완료. 데이터 파싱 중...")
        
        try:
            win32clipboard.OpenClipboard()
            content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            
            match = re.search(r'Ips\s+([\d\.]+)', content, re.IGNORECASE)
            if match:
                ips = float(match.group(1))
                print(f"   ✅ 측정된 IPS: {ips}")
                return ips
            else:
                print(f"   ⚠️ IPS 수치를 찾을 수 없음.")
                return 0
        except Exception as e:
            print(f"   ⚠️ 클립보드 에러: {e}")
            try: 
                win32clipboard.CloseClipboard()
            except: 
                pass
        return -1
    
    def get_current_ssl_info(self):
        """감시 화면에서 우클릭 + 'c' -> 클립보드 복사 -> SSL 정보 파싱"""
        print("\n🔐 [iRAS] SSL 정보 확인 시도...")
        main_hwnd = self._get_handle(IRAS_TITLES["main"], force_focus=True)
        if not main_hwnd: 
            return None
        
        self._clear_clipboard()
        if not self._copy_debug_info(main_hwnd, IRAS_SURVEILLANCE_OFFSETS["right_click_mid"]):
            return None
            
        print("   -> 디버그 정보 복사 완료. 데이터 파싱 중...")
        
        try:
            win32clipboard.OpenClipboard()
            content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            
            match = re.search(r'Ssl\s+-\s+(.+)', content, re.IGNORECASE)
            if match:
                ssl_status = match.group(1).strip()
                print(f"   ✅ 감지된 SSL 상태: {ssl_status}")
                return ssl_status
            else:
                print(f"   ⚠️ SSL 정보를 찾을 수 없음.")
                return None
        except Exception as e:
            print(f"   ⚠️ 클립보드 에러: {e}")
            try: 
                win32clipboard.CloseClipboard()
            except: 
                pass
        return None
    
    # --- [기능 6] FEN -> 고정 IP 복구 (NEW) ---
    def restore_ip_connection(self, device_search_key, target_ip):
        print(f"\n🔄 [iRAS] 고정 IP 연결 복구 시작 (Target: {target_ip})")
        setup_hwnd = self._enter_setup()
        if not setup_hwnd: 
            return False

        self._input(setup_hwnd, IRAS_IDS["dev_search_input"], device_search_key)
        time.sleep(IRAS_DELAYS["device_search"])
        
        if self._click(setup_hwnd, IRAS_IDS["dev_list"], right_click=True, 
                      y_offset=IRAS_SURVEILLANCE_OFFSETS["device_list"]):
            self._click_relative(*IRAS_COORDS["menu_modify"])
            time.sleep(IRAS_DELAYS["device_modify"])
        else:
            self._close_window(setup_hwnd)
            return False

        modify_hwnd = self._get_handle(IRAS_TITLES["modify"])
        if not modify_hwnd: 
            return False

        # 네트워크 탭으로 이동
        print("   [iRAS] '네트워크' 탭으로 이동 시도...")
        self._click_network_tab(modify_hwnd)

        # 주소 타입 변경
        try:
            win = auto.ControlFromHandle(modify_hwnd)
            combo = win.ComboBoxControl(AutomationId=IRAS_IDS["addr_type_combo"])
            if combo.Exists(maxSearchSeconds=2):
                combo.Click()
                time.sleep(IRAS_DELAYS["combo_select"])
                ip_item = auto.ListItemControl(Name="IP 주소")
                if ip_item.Exists(maxSearchSeconds=2): 
                    ip_item.Click()
                    time.sleep(IRAS_DELAYS["combo_select"])
        except: 
            pass

        # IP 입력 로직 (개선: 한 글자씩 입력하여 "0" 누락 방지)
        ip_parts = target_ip.split('.')
        print(f"   [iRAS] IP 필드 입력: {ip_parts}")
        
        for i, part in enumerate(ip_parts):
            field_id = f"Field{i}"
            try:
                edit = win.EditControl(AutomationId=field_id)
                if edit.Exists(maxSearchSeconds=1):
                    edit.Click()
                    time.sleep(IRAS_DELAYS["input"])
                    
                    # 전체 선택 및 삭제
                    self.shell.SendKeys("^a")
                    time.sleep(IRAS_DELAYS["key"])
                    self.shell.SendKeys("{BACKSPACE}")
                    time.sleep(IRAS_DELAYS["input"])
                    
                    # 🔥 핵심 수정: 한 글자씩 입력하여 "0" 누락 방지
                    part_str = str(part)
                    for char in part_str:
                        self.shell.SendKeys(char)
                        time.sleep(IRAS_DELAYS["key"] * 0.5)  # 각 글자 입력 간 짧은 대기
                    
                    time.sleep(IRAS_DELAYS["click"])
                    self.shell.SendKeys("{TAB}")
                    time.sleep(IRAS_DELAYS["input"])
                else:
                    print(f"   ⚠️ 입력칸 {field_id}를 찾을 수 없습니다.")
            except Exception as e:
                print(f"   ⚠️ IP 입력 중 예외: {e}")

        print("   [iRAS] 연결 테스트 실행...")
        if self._click(modify_hwnd, IRAS_IDS["test_btn"]):
            print(f"   -> 테스트 진행 중 ({IRAS_DELAYS['test_response']}초 대기)...")
            time.sleep(IRAS_DELAYS["test_response"])
            print("   -> 결과 팝업 닫기 (Enter)")
            self.shell.SendKeys("{ENTER}")
            time.sleep(IRAS_DELAYS["test_popup"])

        # 저장 및 종료
        print("   -> 입력 완료. 저장...")
        self._close_window(modify_hwnd)
        self._close_window(setup_hwnd)
        return True
    
    def update_device_credentials(self, device_name, user_id, user_pw):
        setup_hwnd = self._enter_setup()
        if not setup_hwnd: 
            return False

        # 1. 장치 검색
        time.sleep(IRAS_DELAYS["device_search"])
        self._input(setup_hwnd, IRAS_IDS["dev_search_input"], device_name)
        time.sleep(IRAS_DELAYS["device_search"])
        
        # 2. 리스트 우클릭 -> 장치 수정
        if self._click(setup_hwnd, IRAS_IDS["dev_list"], right_click=True, 
                      y_offset=IRAS_SURVEILLANCE_OFFSETS["device_list"]):
            self._click_relative(*IRAS_COORDS["menu_modify"])
            time.sleep(IRAS_DELAYS["device_modify"])
        else:
            self._close_window(setup_hwnd)
            return False

        modify_hwnd = self._get_handle(IRAS_TITLES["modify"])
        if not modify_hwnd: 
            return False
        
        try:
            # 3. 네트워크 탭 이동
            print("   [iRAS] 네트워크 탭으로 이동...")
            self._click_network_tab(modify_hwnd)

            # 4. ID/PW 입력
            print(f"   [iRAS] 계정 정보 업데이트 ({user_id})...")
            self._input(modify_hwnd, IRAS_IDS["user_id_input"], user_id)
            time.sleep(IRAS_DELAYS["combo_select"])
            self._input(modify_hwnd, IRAS_IDS["user_pw_input"], user_pw)
            time.sleep(IRAS_DELAYS["combo_select"])
            
            # 5. 연결 테스트
            print("   [iRAS] 연결 테스트 실행...")
            if self._click(modify_hwnd, IRAS_IDS["test_btn"]):
                time.sleep(IRAS_DELAYS["test_popup"])
                self.shell.SendKeys("{ENTER}")
                time.sleep(IRAS_DELAYS["permission_result"])
            
        except Exception as e:
            print(f"   ⚠️ 계정 변경 중 오류: {e}")
            self._close_window(modify_hwnd)
            self._close_window(setup_hwnd)
            return False

        # 저장
        self._close_window(modify_hwnd)
        self._close_window(setup_hwnd)
        return True
    

def run_fen_setup_process(device_name_to_search, fen_name):
    """
    network_test.py에서 호출하는 진입점 함수
    """
    controller = IRASController()
    
    # FEN 설정 자동화 실행
    if not controller.setup_fen(device_name_to_search, fen_name):
        print("🔥 [iRAS] FEN 설정 중 오류 발생")
        return False
    
    print("🎉 [iRAS] FEN 설정 프로세스 성공")
    time.sleep(2.0) # 안정화 대기
    return True

def run_fen_verification(expected_mode="TcpDirectExternal"):
    """network_test.py에서 호출할 검증 함수"""
    controller = IRASController()
    return controller.verify_connection(expected_mode)

def run_port_change_process(device_name, target_port, target_ip="10.0.131.104"):
    """IDIS Center 설정 창 진입부터 포트 변경, 검색 검증, 종료까지 수행"""
    print(f"🔌 [iRAS] 장치 검색을 통한 포트 변경 시작 (Target: {target_ip}:{target_port})")
    
    controller = IRASController()
    setup_hwnd = controller._enter_setup()
    
    if not setup_hwnd:
        print("   ❌ 설정 창 진입 실패")
        return False

    try:
        setting_window = auto.WindowControl(searchDepth=1, Name=IRAS_TITLES["setup"])
        if not setting_window.Exists(3):
            print("   ❌ 'IDIS Center 설정' 창을 찾을 수 없습니다 (UIA).")
            return False
        
        setting_window.SetFocus()
        time.sleep(IRAS_DELAYS["menu_navigate"])

        # Step 1. '+' 버튼 클릭
        print("   [1] '+' 버튼 클릭 (장치 검색 진입)...")
        plus_btn = setting_window.ButtonControl(AutomationId=IRAS_IDS["plus_btn"], Name="+")
        if not plus_btn.Exists(2):
            print("   ❌ '+' 버튼을 찾을 수 없습니다.")
            return False
        plus_btn.Click()
        time.sleep(IRAS_DELAYS["device_search"])

        search_dialog = setting_window.WindowControl(searchDepth=1, Name=IRAS_TITLES["search"])
        if not search_dialog.Exists(3):
            print("   ❌ '장치 검색' 대화상자가 열리지 않았습니다.")
            return False

        # Step 2. IP 주소 입력
        print(f"   [2] IP 주소 입력: {target_ip}...")
        ip_parts = target_ip.split('.')
        if len(ip_parts) != 4:
            print("   ❌ IP 주소 형식이 올바르지 않습니다.")
            return False

        for i in range(4):
            start_edit = search_dialog.EditControl(AutomationId=f"Field{i}")
            if start_edit.Exists(0.5): 
                start_edit.Click()
                start_edit.SendKeys('{Ctrl}a{Delete}') 
                start_edit.SendKeys(ip_parts[i])
            
            end_edit = search_dialog.EditControl(AutomationId=f"Field{i+4}")
            if end_edit.Exists(0.1): 
                end_edit.Click()
                end_edit.SendKeys('{Ctrl}a{Delete}')
                end_edit.SendKeys(ip_parts[i])
                
        time.sleep(IRAS_DELAYS["combo_select"])

        # Step 3. '포트...' 버튼 클릭
        print("   [3] '포트...' 버튼 클릭...")
        port_btn = search_dialog.ButtonControl(AutomationId=IRAS_IDS["port_btn"], Name="포트...")
        port_btn.Click()
        time.sleep(IRAS_DELAYS["device_search"])

        port_dialog = search_dialog.WindowControl(searchDepth=1, Name=IRAS_TITLES["port_setting"])
        if not port_dialog.Exists(3):
            print("   ❌ '포트 설정' 대화상자가 열리지 않았습니다.")
            return False

        # Step 4. 포트 번호 입력 및 확인
        print(f"   [4] 포트 번호 입력: {target_port}...")
        port_edit = port_dialog.EditControl(AutomationId=IRAS_IDS["port_edit"])
        if port_edit.Exists(1):
            port_edit.Click()
            port_edit.SendKeys('{Ctrl}a{Delete}')
            port_edit.SendKeys(str(target_port))
        else:
            print("   ⚠️ 포트 입력창을 찾을 수 없습니다.")
        
        time.sleep(IRAS_DELAYS["combo_select"])
        port_dialog.ButtonControl(AutomationId=IRAS_IDS["ok_btn"], Name="확인").Click()
        time.sleep(IRAS_DELAYS["combo_select"])

        # Step 5. '검색 시작' 클릭 및 결과 대기
        print("   [5] '검색 시작' 클릭 및 결과 검증...")
        search_dialog.ButtonControl(AutomationId=IRAS_IDS["search_start_btn"], Name="검색 시작").Click()
        
        found_device = False
        for _ in range(IRAS_DELAYS["search_timeout"]):
            time.sleep(IRAS_DELAYS["search_result"])
            print(".", end="")
            result_text_ctrl = search_dialog.TextControl(AutomationId=IRAS_IDS["search_result_text"])
            if result_text_ctrl.Exists(0.5):
                result_msg = result_text_ctrl.Name
                if "총 1개의 장치가" in result_msg:
                    print(f"\n   ✅ 검색 성공: {result_msg}")
                    found_device = True
                    break
                elif "장치가 없습니다" in result_msg:
                    print(f"\n   ❌ 검색 실패: {result_msg}")
                    break
        
        if not found_device:
            print("\n   ⚠️ 타임아웃 또는 장치 미발견")
            if search_dialog.Exists():
                search_dialog.ButtonControl(AutomationId=IRAS_IDS["ok_btn"], Name="닫기").Click()
            if setting_window.Exists():
                setting_window.ButtonControl(AutomationId=IRAS_IDS["ok_btn"], Name="확인").Click()
            return False

        # Step 6. 장치 검색 창 닫기
        print("   [6] 장치 검색 창 닫기...")
        search_dialog.ButtonControl(AutomationId=IRAS_IDS["ok_btn"], Name="닫기").Click()
        
        if not search_dialog.Disappears(IRAS_DELAYS["test_popup"]): 
            print("   ⚠️ 장치 검색 창이 아직 닫히지 않았습니다 (진행 계속)...")

        # Step 7. 메인 설정 창 저장 및 닫기
        print("   [7] 메인 설정 창 저장 및 닫기...")
        if setting_window.Exists(1):
            setting_window.SetFocus()
            main_ok_btn = setting_window.ButtonControl(AutomationId=IRAS_IDS["ok_btn"], Name="확인")
            
            if not main_ok_btn.Exists(1):
                main_ok_btn = setting_window.ButtonControl(Name="확인")
                
            if main_ok_btn.Exists(2):
                main_ok_btn.Click()
                print("   🎉 iRAS 포트 변경 및 설정 완료")
                return True
            else:
                print("   ⚠️ 메인 설정 창의 '확인' 버튼을 찾을 수 없습니다.")
                return False
        else:
            print("   ⚠️ 메인 설정 창이 이미 닫혔거나 찾을 수 없습니다.")
            return True

    except Exception as e:
        print(f"   🔥 [iRAS Error] 프로세스 중 오류: {e}")
        return False

def wait_for_connection(timeout=None, max_retries=3):
    """영상 연결 대기 함수 (재시도 지원)"""
    controller = IRASController()
    return controller.wait_for_video_attachment(timeout=timeout, max_retries=max_retries)

def run_restore_ip_process(device_name, ip_address):
    """
    FEN 테스트 종료 후 IP 연결 모드로 복구하는 함수
    (network_test.py에서 호출)
    """
    controller = IRASController()
    if controller.restore_ip_connection(device_name, ip_address):
        print("🎉 [iRAS] IP 모드 복구 성공")
        return True
    else:
        print("🔥 [iRAS] IP 모드 복구 실패")
        return False

def run_iras_permission_check(device_name_to_search, user_id, user_pw, phase=1):
    """
    [복원된 함수] 사용자 권한 확인 통합 테스트
    :param phase: 1 (기능 차단), 2 (설정/검색 차단)
    """
    print(f"\n🖥️ [iRAS] 테스트 시작 (Phase: {phase})...")
    
    controller = IRASController()
    
    # [Step 1] 계정 변경 (Phase 1일 때만 수행)
    # Phase 2는 Phase 1에서 이미 로그인된 상태라고 가정하고 스킵합니다.
    if phase == 1:
        print(f"   [iRAS] 로그인 시퀀스 및 계정 변경 ({user_id})...")
        if not controller.update_device_credentials(device_name_to_search, user_id, user_pw):
            return False, "계정 변경 및 로그인 실패"
        
        print("   ⏳ 설정 적용 대기 (5초)...")
        time.sleep(5)
    else:
        print(f"   ℹ️ [iRAS] 계정 변경 스킵 (Phase {phase} - 기존 로그인 유지)")

    # [Step 2] Phase별 검증
    result = False
    if phase == 1:
        result = controller.run_permission_phase1(device_name_to_search)
    elif phase == 2:
        result = controller.run_permission_phase2(device_name_to_search)
    else:
        return False, "Invalid Phase"
        
    if result:
        return True, f"Phase {phase} 테스트 성공"
    else:
        return False, f"Phase {phase} 테스트 실패"

def restore_admin_login(device_name, admin_id, admin_pw):
    controller = IRASController()
    print(f"\n🔄 [iRAS] 관리자 계정 복구: {admin_id} ...")
    return controller.update_device_credentials(device_name, admin_id, admin_pw)

if __name__ == "__main__":
    
    # 1. 컨트롤러 인스턴스 생성
    controller = IRASController()
    
    # 2. 테스트에 필요한 정보 설정 (config.py의 값을 쓰거나 직접 입력)
    device_name = "104_T6631"  # 예: "104_T6631"
    
    # 3. Phase 1 테스트 실행
    # 이 함수는 내부적으로 _enter_setup()을 호출하여 자동으로 iRAS 메뉴로 진입합니다.
    success = controller.run_permission_phase1(device_name)
    
    if success:
        print("\n✅ Phase 1 단독 테스트 성공")
    else:
        print("\n❌ Phase 1 단독 테스트 실패")