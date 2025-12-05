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

# ---------------------------------------------------------
# ⚙️ [설정 및 상수]
# ---------------------------------------------------------
TITLE_MAIN = "IDIS Center Remote Administration System"
TITLE_SETUP = "IDIS Center 설정"
TITLE_MODIFY = "장치 수정"

# UI 요소 ID (AutomationId)
ID_DEV_SEARCH_INPUT = "101"     # 설정창 > 장치 검색
ID_DEV_LIST = "1000"            # 설정창 > 장치 리스트
ID_USER_ID_INPUT = "22043"      # 수정창 > 사용자 ID
ID_USER_PW_INPUT = "22045"      # 수정창 > 사용자 PW
ID_ADDR_TYPE_COMBO = "1195"     # 수정창 > 주소 타입 콤보박스
ID_FEN_INPUT = "22047"          # 수정창 > FEN 이름 입력
ID_PORT_INPUT = "1201"          # 수정창 > 원격 포트 입력
ID_TEST_BTN = "22132"           # 수정창 > 연결 테스트 버튼
ID_OK_BTN = "1"                 # 확인 버튼 (공통)
ID_SURVEILLANCE_PANE = "59648"  # 감시 화면 Pane
ID_SAVE_CLIP_BTN = "2005"       # 재생 화면 > 저장 버튼

# 마우스 상대 좌표 (우클릭 메뉴 위치)
COORD_MENU_MODIFY = (50, 20)    # 장치 수정
COORD_MENU_REMOTE = (50, 45)    # 원격 설정
COORD_MENU_FW_UP = (50, 70)     # 펌웨어 업그레이드
COORD_MENU_PLAYBACK = (50, 100) # 녹화 영상 검색
COORD_MENU_PTZ = (50, 125)      # PTZ 제어
COORD_MENU_COLOR = (50, 175)    # 컬러 제어
COORD_MENU_ALARM = (50, 250)    # 알람 출력 제어
COORD_ALARM_ON = (150, 0)       # 알람 > 켜기 (상대좌표)
COORD_CLIP_COPY = (30, 0)       # 클립 복사 메뉴

# DPI 인식
try: ctypes.windll.user32.SetProcessDPIAware()
except: pass

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
            try: win32gui.EnumWindows(callback, None)
            except: pass

        if hwnd:
            try:
                if win32gui.IsIconic(hwnd): 
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                
                if force_focus:
                    # [중요] 윈도우 포커스 락 해제를 위한 Alt 키 트릭
                    if use_alt:
                        self.shell.SendKeys('%')
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.2)
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
                        time.sleep(0.2)

                    try: auto.ControlFromHandle(hwnd).SetFocus()
                    except: pass
            except: pass
        return hwnd
    
    def save_snapshot(self):
        """
        iRAS 스냅샷 저장을 위한 Ctrl+S 키 입력 (win32api 사용으로 신뢰성 향상)
        """
        print("   📸 [Input] Ctrl+S 키 입력 시도...")
        try:
            # 1. Ctrl Key Down (0x11)
            win32api.keybd_event(0x11, 0, 0, 0)
            time.sleep(0.1)
            
            # 2. 'S' Key Down (0x53)
            win32api.keybd_event(0x53, 0, 0, 0)
            time.sleep(0.1)
            
            # 3. 'S' Key Up
            win32api.keybd_event(0x53, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)
            
            # 4. Ctrl Key Up
            win32api.keybd_event(0x11, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            print("   -> 키 입력 완료")
            return True
        except Exception as e:
            print(f"   ⚠️ 키 입력 실패: {e}")
            return False

    def _click(self, hwnd, auto_id, right_click=False, y_offset=None):
        """UIA 요소 클릭 (y_offset 지원)"""
        try:
            win = auto.ControlFromHandle(hwnd)
            elem = win.Control(AutomationId=auto_id)
            if not elem.Exists(maxSearchSeconds=3): return False
            
            rect = elem.BoundingRectangle
            cx = int((rect.left + rect.right) / 2)
            # y_offset이 있으면 Top 기준, 없으면 Center 기준
            cy = int(rect.top + y_offset) if y_offset is not None else int((rect.top + rect.bottom) / 2)

            win32api.SetCursorPos((cx, cy)); time.sleep(0.3)
            
            if right_click:
                # 우클릭 전 좌클릭으로 포커스 확보
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.1)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.2)
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                time.sleep(0.1)
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            else:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                time.sleep(0.1)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except: return False

    def _input(self, hwnd, auto_id, text):
        """입력 필드 값 넣기"""
        if self._click(hwnd, auto_id):
            time.sleep(0.2)
            self.shell.SendKeys("^a{BACKSPACE}"); time.sleep(0.1)
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                self.shell.SendKeys("^v")
                return True
            except: pass
        return False
    

    def _click_relative(self, dx, dy):
        """상대 좌표 클릭"""
        cx, cy = win32api.GetCursorPos()
        win32api.SetCursorPos((cx + dx, cy + dy)); time.sleep(0.3)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0); time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    
    def _right_click_surveillance(self, main_hwnd):
        """감시 화면 상단부(Top+100) 우클릭"""
        return self._click(main_hwnd, ID_SURVEILLANCE_PANE, right_click=True, y_offset=100)

    def _enter_setup(self):
        """메인화면 -> 시스템(S) -> 설정(i) 진입"""
        print("   [iRAS] 메인 화면 전환 및 설정 메뉴 진입...")
        main_hwnd = self._get_handle(TITLE_MAIN, force_focus=True)
        if not main_hwnd: 
            print("❌ iRAS 메인 창을 찾을 수 없습니다.")
            return None
        time.sleep(0.5)
        self.shell.SendKeys("%s"); time.sleep(0.5)
        self.shell.SendKeys("i"); time.sleep(0.5)
        self.shell.SendKeys("{ENTER}"); time.sleep(0.5)
        self.shell.SendKeys("{ENTER}"); time.sleep(2.0)
        
        setup_hwnd = self._get_handle(TITLE_SETUP)
        if setup_hwnd: return setup_hwnd
        print("❌ 설정 창이 열리지 않았습니다.")
        return None

    def _return_to_watch(self):
        """감시 탭 복귀"""
        main_hwnd = self._get_handle(TITLE_MAIN)
        if not main_hwnd: return
        try:
            win = auto.ControlFromHandle(main_hwnd)
            tab = win.TabItemControl() # 첫 번째 탭(감시) 가정
            if tab.Exists(maxSearchSeconds=1): tab.Click()
        except: pass
    
    def _click_network_tab(self, hwnd):
        """장치 수정 창에서 '네트워크' 탭 클릭"""
        try:
            win = auto.ControlFromHandle(hwnd)
            tab_control = win.TabControl()
            if tab_control.Exists(maxSearchSeconds=2):
                # 1. 이름으로 찾기
                network_tab = tab_control.TabItemControl(Name="네트워크")
                if network_tab.Exists(maxSearchSeconds=1):
                    network_tab.Click()
                    return True
                
                # 2. 오프셋으로 찾기 (두 번째 탭 가정)
                rect = tab_control.BoundingRectangle
                # 탭 헤더 높이 등을 고려해 적절히 오프셋 설정
                # 보통 첫 번째 탭 너비만큼 오른쪽으로 이동
                click_x = rect.left + 100 
                click_y = rect.top + 15
                
                win32api.SetCursorPos((int(click_x), int(click_y)))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                return True
        except: return False
        return False
    
    def wait_for_video_attachment(self, timeout=180):
        """
        [수정됨 v4] 스킵 가능한 대기 모드
        - 지정된 시간(timeout) 동안 대기
        - 키보드 'Enter' 키를 누르면 즉시 남은 시간을 건너뛰고 진행
        """
        print(f"   ⏳ [iRAS] 영상 연결 대기 중... ({timeout}초)")
        print(f"   💡 (Tip: 영상이 이미 나왔다면 'Enter'를 눌러 즉시 건너뛸 수 있습니다)")
        
        # 입력 버퍼 비우기 (이전 입력이 남아있어서 바로 스킵되는 것 방지)
        while msvcrt.kbhit():
            msvcrt.getch()

        for i in range(timeout):
            # 1. 키보드 입력 감지 (Windows 전용)
            if msvcrt.kbhit():
                # 눌린 키 값을 읽어옴
                key = msvcrt.getch()
                # 엔터(Enter) 키 코드 = b'\r'
                if key == b'\r':
                    print(f"\n   ⏩ [Skip] 사용자 입력으로 대기 시간을 건너뜁니다!")
                    break

            # 2. 1초 대기
            time.sleep(1)
            remaining = timeout - i
            
            # 3. 진행 상황 출력
            if remaining % 10 == 0:
                print(f"{remaining}s..", end=" ", flush=True)
            elif remaining % 2 == 0:
                print(".", end="", flush=True)
                
        print("\n   ✅ 대기 종료. (다음 단계 진행)")
        return True

    # --- [기능 1] 권한 테스트 (Phase 1) ---
    def run_permission_phase1(self, device_name):
        print("\n🧪 [iRAS] Phase 1: 기능 차단 테스트 (FW, PTZ, Color, Alarm, Clip)...")
        
        # 1. 펌웨어 업그레이드 차단 확인
        setup_hwnd = self._enter_setup()
        if setup_hwnd:
            self._input(setup_hwnd, ID_DEV_SEARCH_INPUT, device_name)
            if self._click(setup_hwnd, ID_DEV_LIST, right_click=True, y_offset=25):
                self._click_relative(*COORD_MENU_FW_UP)
                time.sleep(2.0); self.shell.SendKeys("{ENTER}"); time.sleep(1.0)
            
            # 설정창 닫기 (확인 버튼)
            self._click(setup_hwnd, ID_OK_BTN)
            time.sleep(2.0)

        main_hwnd = self._get_handle(TITLE_MAIN, force_focus=True) # 메인 포커스
        if not main_hwnd: return False

        # 2. 감시 화면 관련 (PTZ)
        if self._right_click_surveillance(main_hwnd):
            self._click_relative(*COORD_MENU_PTZ)
            time.sleep(2.0); self.shell.SendKeys("{ENTER}"); time.sleep(1.0)

        # 3. 컬러 제어
        if self._right_click_surveillance(main_hwnd):
            self._click_relative(*COORD_MENU_COLOR)
            time.sleep(2.0); self.shell.SendKeys("{ENTER}"); time.sleep(1.0)

        # 4. 알람 출력
        if self._right_click_surveillance(main_hwnd):
            self._click_relative(*COORD_MENU_ALARM); time.sleep(0.5)
            self._click_relative(*COORD_ALARM_ON)
            time.sleep(2.0); self.shell.SendKeys("{ENTER}"); time.sleep(1.0)

        # 5. 클립 카피 (재생 -> 저장 -> 클립복사)
        if self._right_click_surveillance(main_hwnd):
            self._click_relative(*COORD_MENU_PLAYBACK)
            time.sleep(5.0) # 재생창 로딩 대기
            
            # 저장 버튼 클릭
            if self._click(main_hwnd, ID_SAVE_CLIP_BTN):
                time.sleep(1.0)
                self._click_relative(*COORD_CLIP_COPY)
                time.sleep(3.0); self.shell.SendKeys("{ENTER}"); time.sleep(1.0)
                self._return_to_watch()
            
        print("   ✅ Phase 1 완료")
        return True
    
    

    # --- [기능 2] 권한 테스트 (Phase 2) ---
    def run_permission_phase2(self, device_name):
        print("\n🧪 [iRAS] Phase 2: 설정/검색 차단 테스트...")
        
        # 1. 원격 설정
        setup_hwnd = self._enter_setup()
        if setup_hwnd:
            self._input(setup_hwnd, ID_DEV_SEARCH_INPUT, device_name)
            if self._click(setup_hwnd, ID_DEV_LIST, right_click=True, y_offset=25):
                self._click_relative(*COORD_MENU_REMOTE)
                print("   [Wait] 차단 팝업 대기 (8초)...")
                time.sleep(8.0) 
                # 차단 메시지가 뜨면 닫아야 함 (Enter 등) - 상황에 따라 다를 수 있음
                # 보통 차단되면 아무 창도 안뜨거나 경고창이 뜸. 일단 Enter 전송.
                # self.shell.SendKeys("{ENTER}") 
            
            # 설정창 닫기
            self._click(setup_hwnd, ID_OK_BTN); time.sleep(2.0)

        # 2. 검색(재생)
        main_hwnd = self._get_handle(TITLE_MAIN, force_focus=True)
        if main_hwnd and self._right_click_surveillance(main_hwnd):
            self._click_relative(*COORD_MENU_PLAYBACK)
            time.sleep(3.0); self.shell.SendKeys("{ENTER}"); time.sleep(1.0)
            self._return_to_watch()

        print("   ✅ Phase 2 완료")
        return True

    # --- [기능 3] FEN 설정 (자동화) ---
    def setup_fen(self, device_search_key, fen_name):
        """
        iRAS에서 장치를 검색하고 FEN 정보를 입력하여 연결 테스트를 수행합니다.
        """
        print(f"\n🖥️ [iRAS] FEN 설정 시작 (검색어: {device_search_key}, FEN: {fen_name})")
        
        # 1. 설정창 진입
        setup_hwnd = self._enter_setup()
        if not setup_hwnd: return False

        # 2. 장치 검색
        print("   [iRAS] 장치 검색...")
        self._input(setup_hwnd, ID_DEV_SEARCH_INPUT, device_search_key)
        time.sleep(1.5)
        
        # 3. 리스트에서 우클릭 -> 장치 수정
        if self._click(setup_hwnd, ID_DEV_LIST, right_click=True, y_offset=25):
            self._click_relative(*COORD_MENU_MODIFY)
            time.sleep(2.0)
        else:
            print("❌ 장치 리스트 클릭 실패")
            self._click(setup_hwnd, ID_OK_BTN) # 닫기
            return False

        modify_hwnd = self._get_handle(TITLE_MODIFY)
        if not modify_hwnd: 
            print("❌ '장치 수정' 창이 뜨지 않았습니다.")
            return False

        # 4. 네트워크 탭으로 이동 (탭 컨트롤의 오른쪽 영역 클릭 시도)
        try:
            win = auto.ControlFromHandle(modify_hwnd)
            tab = win.TabItemControl()
            if tab.Exists(maxSearchSeconds=2):
                rect = tab.BoundingRectangle
                # 탭의 오른쪽 끝에서 약간 더 오른쪽 클릭 (다음 탭 선택)
                cx = rect.left + (rect.right - rect.left) * 1.5 
                cy = (rect.top + rect.bottom) / 2
                win32api.SetCursorPos((int(cx), int(cy)))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(1.0)
        except: pass

        # 5. FEN 설정 (주소 유형 변경)
        print("   [iRAS] 주소 유형 'FEN' 선택...")
        win = auto.ControlFromHandle(modify_hwnd)
        combo = win.ComboBoxControl(AutomationId=ID_ADDR_TYPE_COMBO)
        if combo.Exists(maxSearchSeconds=2):
            combo.Click(); time.sleep(0.5)
            fen_item = auto.ListItemControl(Name="FEN")
            if fen_item.Exists(maxSearchSeconds=1): fen_item.Click()
        
        # 6. FEN 이름 입력
        print(f"   [iRAS] FEN 이름 입력: {fen_name}")
        # 콤보박스 변경 직후라 포커스가 튈 수 있으니 명시적 클릭 후 입력
        if not self._input(modify_hwnd, ID_FEN_INPUT, fen_name):
            # 실패 시 에디트 컨트롤 다시 찾아 클릭 후 재시도
            try: win.EditControl(AutomationId=ID_FEN_INPUT).Click()
            except: pass
            self._input(modify_hwnd, ID_FEN_INPUT, fen_name)

        # 7. 연결 테스트
        print("   [iRAS] 연결 테스트 실행...")
        if self._click(modify_hwnd, ID_TEST_BTN):
            print("   -> 테스트 진행 중 (3초 대기)...")
            time.sleep(5) # 서버 응답 대기
            print("   -> 결과 팝업 닫기 (Enter)")
            self.shell.SendKeys("{ENTER}"); time.sleep(3.0)

        # 8. 저장 및 종료
        print("   [iRAS] 저장 및 설정 완료")
        self._click(modify_hwnd, ID_OK_BTN); time.sleep(1.5) # 수정창 닫기
        self._click(setup_hwnd, ID_OK_BTN) # 설정창 닫기
        return True

    # --- [기능 4] 연결 검증 ---
    def verify_connection(self, expected_mode="TcpDirectExternal"):
        """감시 화면 우클릭(지정 좌표) -> 'c' 입력 -> 클립보드 확인"""
        print(f"\n🔍 [iRAS] 연결 모드 검증 시작: '{expected_mode}' 기대함")
        
        main_hwnd = self._get_handle(TITLE_MAIN, force_focus=True)
        if not main_hwnd:
            print("❌ iRAS 메인 창을 찾을 수 없습니다.")
            return False
        
        # 1. 기존 클립보드 비우기
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except: pass

        # 2. 감시 패널 우클릭 (y_offset=100 적용)
        # 권한 테스트에서 사용했던 '위쪽에서 100px 아래' 지점을 클릭합니다.
        if self._click(main_hwnd, ID_SURVEILLANCE_PANE, right_click=True, y_offset=100):
            time.sleep(0.5)
            
            win32api.keybd_event(0x43, 0, 0, 0)  # Key Down
            time.sleep(0.1)
            win32api.keybd_event(0x43, 0, win32con.KEYEVENTF_KEYUP, 0) # Key Up
            
            print("   -> 우클릭 후 'C' 키 입력 완료. 클립보드 확인 중...")
            time.sleep(1.0) # 복사될 시간 대기
            
            try:
                win32clipboard.OpenClipboard()
                try:
                    content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                except:
                    content = "" # 복사 실패 시 빈 문자열
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
                    # print(f"   (내용: {content[:100]}...)")
            except Exception as e:
                print(f"⚠️ 클립보드 접근 오류: {e}")
                try: win32clipboard.CloseClipboard()
                except: pass
        else:
            print("❌ 감시 화면 클릭 실패")

        return False
    
    def get_current_ips(self):
        """
        감시 화면에서 우클릭 + 'c'를 눌러 클립보드 정보 중 IPS 값을 추출
        Format 예시: [W]{1:4} Fps 05.2 / Ips 05.0 / Mbps 0.21, 0.04
        """
        print("\n📊 [iRAS] IPS(프레임) 측정 시도...")
        main_hwnd = self._get_handle(TITLE_MAIN, force_focus=True)
        if not main_hwnd: return -1
        
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except: pass

        # 우클릭 + C 액션
        if self._click(main_hwnd, ID_SURVEILLANCE_PANE, right_click=True, y_offset=50):
            time.sleep(0.5)
            win32api.keybd_event(0x43, 0, 0, 0); time.sleep(0.1)
            win32api.keybd_event(0x43, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            print("   -> 디버그 정보 복사 완료. 데이터 파싱 중...")
            time.sleep(1.0)
            
            try:
                win32clipboard.OpenClipboard()
                content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                
                # ✅ [수정됨] 사용자 로그 포맷 "Ips 05.0" 파싱
                # 대소문자 무시, "Ips" 뒤에 공백 후 숫자.숫자 패턴 찾기
                match = re.search(r'Ips\s+([\d\.]+)', content, re.IGNORECASE)
                
                if match:
                    ips = float(match.group(1))
                    print(f"   ✅ 측정된 IPS: {ips}")
                    return ips
                else:
                    print(f"   ⚠️ IPS 수치를 찾을 수 없음.")
                    # print(f"   (디버그용: {content})") # 필요시 주석 해제
                    return 0
            except Exception as e:
                print(f"   ⚠️ 클립보드 에러: {e}")
                try: win32clipboard.CloseClipboard()
                except: pass
        return -1
    
    def get_current_ssl_info(self):
        """
        감시 화면에서 우클릭 + 'c' -> 클립보드 복사 -> SSL 정보 파싱
        Target Line Example: "  Ssl - FullPacket"
        """
        print("\n🔐 [iRAS] SSL 정보 확인 시도...")
        main_hwnd = self._get_handle(TITLE_MAIN, force_focus=True)
        if not main_hwnd: return None
        
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except: pass

        # 우클릭 + C (정보 복사)
        if self._click(main_hwnd, ID_SURVEILLANCE_PANE, right_click=True, y_offset=50):
            time.sleep(0.5)
            win32api.keybd_event(0x43, 0, 0, 0); time.sleep(0.1) # 'C' Key
            win32api.keybd_event(0x43, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            print("   -> 디버그 정보 복사 완료. 데이터 파싱 중...")
            time.sleep(1.0)
            
            try:
                win32clipboard.OpenClipboard()
                content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                
                # 정규식 파싱: "Ssl - [문자열]"
                # 예: "Ssl - FullPacket", "Ssl - NotUse" 등
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
                try: win32clipboard.CloseClipboard()
                except: pass
        return None
    
    # --- [기능 6] FEN -> 고정 IP 복구 (NEW) ---
    def restore_ip_connection(self, device_search_key, target_ip):
        print(f"\n🔄 [iRAS] 고정 IP 연결 복구 시작 (Target: {target_ip})")
        setup_hwnd = self._enter_setup()
        if not setup_hwnd: return False

        self._input(setup_hwnd, ID_DEV_SEARCH_INPUT, device_search_key)
        time.sleep(1.0)
        
        if self._click(setup_hwnd, ID_DEV_LIST, right_click=True, y_offset=25):
            self._click_relative(*COORD_MENU_MODIFY)
            time.sleep(2.0)
        else:
            self._click(setup_hwnd, ID_OK_BTN)
            return False

        modify_hwnd = self._get_handle(TITLE_MODIFY)
        if not modify_hwnd: return False

        # 🌟 [추가된 부분] '네트워크' 탭 확실하게 클릭
        print("   [iRAS] '네트워크' 탭으로 이동 시도...")
        try:
            win = auto.ControlFromHandle(modify_hwnd)
            tab_control = win.TabControl() # 탭 컨트롤 찾기
            
            if tab_control.Exists(maxSearchSeconds=2):
                # '네트워크' 탭 찾아서 클릭
                network_tab = tab_control.TabItemControl(Name="네트워크")
                if network_tab.Exists(maxSearchSeconds=1):
                    network_tab.Click()
                else:
                    # 이름으로 못 찾으면 좌표로 클릭 (두 번째 탭 위치 추정)
                    rect = tab_control.BoundingRectangle
                    click_x = rect.left + 100 
                    click_y = rect.top + 15
                    win32api.SetCursorPos((int(click_x), int(click_y)))
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(1.5) # 탭 전환 대기
        except Exception as e:
            print(f"   ⚠️ 탭 이동 중 에러 (무시하고 진행): {e}")

        # 주소 타입 변경
        try:
            win = auto.ControlFromHandle(modify_hwnd)
            combo = win.ComboBoxControl(AutomationId=ID_ADDR_TYPE_COMBO)
            if combo.Exists(maxSearchSeconds=2):
                combo.Click(); time.sleep(1.0)
                ip_item = auto.ListItemControl(Name="IP 주소")
                if ip_item.Exists(maxSearchSeconds=2): ip_item.Click(); time.sleep(1.0)
        except: pass

        # 🌟 [수정 핵심] IP 입력 로직 강화
        ip_parts = target_ip.split('.')
        print(f"   [iRAS] IP 필드 입력: {ip_parts}")
        
        for i, part in enumerate(ip_parts):
            field_id = f"Field{i}"
            try:
                edit = win.EditControl(AutomationId=field_id)
                if edit.Exists(maxSearchSeconds=1):
                    # 1. 클릭 후 기존 값 지우기
                    edit.Click()
                    time.sleep(0.2)
                    self.shell.SendKeys("^a{BACKSPACE}")
                    time.sleep(0.2)
                    
                    # 2. 값 입력 (문자열로 확실하게)
                    # '0'인 경우에도 명확히 입력되도록 함
                    self.shell.SendKeys(str(part))
                    time.sleep(0.3) 
                    
                    # 3. 탭으로 이동 (입력 확정)
                    self.shell.SendKeys("{TAB}")
                    time.sleep(0.2)
                else:
                    print(f"   ⚠️ 입력칸 {field_id}를 찾을 수 없습니다.")
            except Exception as e:
                print(f"   ⚠️ IP 입력 중 예외: {e}")

        print("   [iRAS] 연결 테스트 실행...")
        if self._click(modify_hwnd, ID_TEST_BTN):
            print("   -> 테스트 진행 중 (3초 대기)...")
            time.sleep(5) # 서버 응답 대기
            print("   -> 결과 팝업 닫기 (Enter)")
            self.shell.SendKeys("{ENTER}"); time.sleep(3.0)

        # 저장 및 종료
        print("   -> 입력 완료. 저장...")
        self._click(modify_hwnd, ID_OK_BTN); time.sleep(2.0)
        self._click(setup_hwnd, ID_OK_BTN)
        return True
    
    def update_device_credentials(self, device_name, user_id, user_pw):
        setup_hwnd = self._enter_setup()
        if not setup_hwnd: return False

        # 1. 장치 검색
        time.sleep(1.0)
        self._input(setup_hwnd, ID_DEV_SEARCH_INPUT, device_name)
        time.sleep(1.0)
        
        # 2. 리스트 우클릭 -> 장치 수정
        if self._click(setup_hwnd, ID_DEV_LIST, right_click=True, y_offset=25):
            self._click_relative(*COORD_MENU_MODIFY)
            time.sleep(2.0)
        else:
            self._click(setup_hwnd, ID_OK_BTN)
            return False

        modify_hwnd = self._get_handle(TITLE_MODIFY)
        if not modify_hwnd: return False
        
        try:
            # 3. 네트워크 탭 이동 (요청사항 반영)
            print("   [iRAS] 네트워크 탭으로 이동...")
            self._click_network_tab(modify_hwnd)
            time.sleep(0.5)

            # 4. ID/PW 입력 (요청하신 ID 22043, 22045 사용)
            print(f"   [iRAS] 계정 정보 업데이트 ({user_id})...")
            self._input(modify_hwnd, ID_USER_ID_INPUT, user_id)
            time.sleep(0.5)
            self._input(modify_hwnd, ID_USER_PW_INPUT, user_pw)
            time.sleep(0.5)
            
            # 5. 연결 테스트
            print("   [iRAS] 연결 테스트 실행...")
            if self._click(modify_hwnd, ID_TEST_BTN):
                time.sleep(3.0) 
                self.shell.SendKeys("{ENTER}"); time.sleep(1.0)
            
        except Exception as e:
            print(f"   ⚠️ 계정 변경 중 오류: {e}")
            self._click(modify_hwnd, ID_OK_BTN)
            self._click(setup_hwnd, ID_OK_BTN)
            return False

        # 저장
        self._click(modify_hwnd, ID_OK_BTN); time.sleep(2.0)
        self._click(setup_hwnd, ID_OK_BTN)
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
    """
    [수정됨] IDIS Center 설정 창 진입부터 포트 변경, 검색 검증, 종료까지 수행
    1. IRASController를 이용해 설정 창 열기 (자동 진입)
    2. UIA를 이용해 장치 검색 및 포트 변경 수행
    3. 검색 결과 검증 후 모든 창 닫기
    """
    print(f"🔌 [iRAS] 장치 검색을 통한 포트 변경 시작 (Target: {target_ip}:{target_port})")
    
    # 1. 컨트롤러 생성 및 설정 창 진입 (메인 화면 -> 설정 메뉴)
    controller = IRASController()
    setup_hwnd = controller._enter_setup() # 기존 로직 활용하여 창 열기
    
    if not setup_hwnd:
        print("   ❌ 설정 창 진입 실패")
        return False

    try:
        # 2. UIA로 'IDIS Center 설정' 창 제어 시작
        # 이미 열려있는 창을 잡습니다.
        setting_window = auto.WindowControl(searchDepth=1, Name="IDIS Center 설정")
        if not setting_window.Exists(3):
            print("   ❌ 'IDIS Center 설정' 창을 찾을 수 없습니다 (UIA).")
            return False
        
        setting_window.SetFocus()
        time.sleep(0.5)

        # -----------------------------------------------------------
        # Step 1. '+' 버튼 클릭 (장치 검색 진입) [AutomationId: 22023]
        # -----------------------------------------------------------
        print("   [1] '+' 버튼 클릭 (장치 검색 진입)...")
        plus_btn = setting_window.ButtonControl(AutomationId="22023", Name="+")
        if not plus_btn.Exists(2):
            print("   ❌ '+' 버튼을 찾을 수 없습니다.")
            return False
        plus_btn.Click()
        time.sleep(1) # 대화상자 로딩 대기

        # '장치 검색' 대화상자 핸들링
        search_dialog = setting_window.WindowControl(searchDepth=1, Name="장치 검색")
        if not search_dialog.Exists(3):
            print("   ❌ '장치 검색' 대화상자가 열리지 않았습니다.")
            return False

        # -----------------------------------------------------------
        # Step 2. IP 주소 입력 (Field 0~3, 4~7)
        # -----------------------------------------------------------
        print(f"   [2] IP 주소 입력: {target_ip}...")
        ip_parts = target_ip.split('.')
        if len(ip_parts) != 4:
            print("   ❌ IP 주소 형식이 올바르지 않습니다.")
            return False

        for i in range(4):
            # 시작 IP 입력
            start_edit = search_dialog.EditControl(AutomationId=f"Field{i}")
            if start_edit.Exists(0.5): 
                start_edit.Click()
                start_edit.SendKeys('{Ctrl}a{Delete}') 
                start_edit.SendKeys(ip_parts[i])
            
            # 끝 IP 입력 (동일하게 입력하여 단일 검색 유도)
            end_edit = search_dialog.EditControl(AutomationId=f"Field{i+4}")
            if end_edit.Exists(0.1): 
                end_edit.Click()
                end_edit.SendKeys('{Ctrl}a{Delete}')
                end_edit.SendKeys(ip_parts[i])
                
        time.sleep(0.5)

        # -----------------------------------------------------------
        # Step 3. '포트...' 버튼 클릭 [AutomationId: 22034]
        # -----------------------------------------------------------
        print("   [3] '포트...' 버튼 클릭...")
        port_btn = search_dialog.ButtonControl(AutomationId="22034", Name="포트...")
        port_btn.Click()
        time.sleep(1) 

        # '포트 설정' 대화상자 핸들링
        port_dialog = search_dialog.WindowControl(searchDepth=1, Name="포트 설정")
        if not port_dialog.Exists(3):
            print("   ❌ '포트 설정' 대화상자가 열리지 않았습니다.")
            return False

        # -----------------------------------------------------------
        # Step 4. 포트 번호 입력 및 확인 [AutomationId: 26468]
        # -----------------------------------------------------------
        print(f"   [4] 포트 번호 입력: {target_port}...")
        port_edit = port_dialog.EditControl(AutomationId="26468")
        if port_edit.Exists(1):
            port_edit.Click()
            port_edit.SendKeys('{Ctrl}a{Delete}')
            port_edit.SendKeys(str(target_port))
        else:
            print("   ⚠️ 포트 입력창을 찾을 수 없습니다.")
        
        time.sleep(0.5)
        # 확인 버튼 클릭
        port_dialog.ButtonControl(AutomationId="1", Name="확인").Click()
        time.sleep(0.5)

        # -----------------------------------------------------------
        # Step 5. '검색 시작' 클릭 및 결과 대기 [AutomationId: 22031]
        # -----------------------------------------------------------
        print("   [5] '검색 시작' 클릭 및 결과 검증...")
        search_dialog.ButtonControl(AutomationId="22031", Name="검색 시작").Click()
        
        found_device = False
        for _ in range(10): # 10초 대기
            time.sleep(1)
            print(".", end="")
            # 결과 텍스트 확인
            result_text_ctrl = search_dialog.TextControl(AutomationId="1194")
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
            # 실패 시에도 닫기 시도
            if search_dialog.Exists():
                search_dialog.ButtonControl(AutomationId="1", Name="닫기").Click()
            # 메인 창도 닫아줌
            if setting_window.Exists():
                setting_window.ButtonControl(AutomationId="1", Name="확인").Click()
            return False

        # -----------------------------------------------------------
        # Step 6. 장치 검색 창 '닫기' [AutomationId: 1]
        # -----------------------------------------------------------
        print("   [6] 장치 검색 창 닫기...")
        search_dialog.ButtonControl(AutomationId="1", Name="닫기").Click()
        
        # 창이 사라질 때까지 대기 (최대 3초)
        if not search_dialog.Disappears(3): 
            print("   ⚠️ 장치 검색 창이 아직 닫히지 않았습니다 (진행 계속)...")

        # -----------------------------------------------------------
        # Step 7. 메인 설정 창 '확인' 클릭 (최종 저장/종료) [AutomationId: 1]
        # -----------------------------------------------------------
        print("   [7] 메인 설정 창 저장 및 닫기...")
        
        # 설정 창이 활성화되어 있는지 확인
        if setting_window.Exists(1):
            setting_window.SetFocus()
            main_ok_btn = setting_window.ButtonControl(AutomationId="1", Name="확인")
            
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
            return True # 이미 닫혔다면 성공으로 간주

    except Exception as e:
        print(f"   🔥 [iRAS Error] 프로세스 중 오류: {e}")
        return False

def wait_for_connection(timeout=180):
    """
    영상 연결 대기 함수 (timeout 인자 추가)
    """
    controller = IRASController()
    # 받아온 timeout 값을 내부 메서드에 전달
    return controller.wait_for_video_attachment(timeout=timeout)

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
    
    run_port_change_process("104_T6631", "8016")