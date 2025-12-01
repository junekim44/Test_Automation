import time
import ctypes
import win32gui
import win32com.client
import win32api
import win32con
import win32clipboard
import uiautomation as auto
import re

# ---------------------------------------------------------
# ⚙️ [설정 및 상수]
# ---------------------------------------------------------
TITLE_MAIN = "IDIS Center Remote Administration System"
TITLE_SETUP = "IDIS Center 설정"
TITLE_MODIFY = "장치 수정"

# UI 요소 ID (AutomationId)
ID_DEV_SEARCH_INPUT = "101"     # 설정창 > 장치 검색
ID_DEV_LIST = "1000"            # 설정창 > 장치 리스트
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
    def _get_handle(self, title, force_focus=False):
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
                    self.shell.SendKeys('%')
                    win32gui.SetForegroundWindow(hwnd)
                    # UIA를 통한 2차 포커스 시도
                    try: auto.ControlFromHandle(hwnd).SetFocus()
                    except: pass
            except: pass
        return hwnd

    def _click(self, hwnd, auto_id, right_click=False, y_offset=None):
        """UIA 요소 클릭"""
        try:
            win = auto.ControlFromHandle(hwnd)
            elem = win.Control(AutomationId=auto_id)
            if not elem.Exists(maxSearchSeconds=3): return False
            
            rect = elem.BoundingRectangle
            cx, cy = int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2)
            if y_offset: cy = int(rect.top + y_offset)

            win32api.SetCursorPos((cx, cy)); time.sleep(0.3)
            flags = (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP) if right_click else (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP)
            win32api.mouse_event(flags[0], 0, 0, 0, 0); time.sleep(0.1)
            win32api.mouse_event(flags[1], 0, 0, 0, 0)
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
    
    def _double_click(self, hwnd, auto_id):
        """UIA 요소 더블 클릭 [추가됨]"""
        try:
            win = auto.ControlFromHandle(hwnd)
            elem = win.Control(AutomationId=auto_id)
            if not elem.Exists(maxSearchSeconds=3): return False
            
            rect = elem.BoundingRectangle
            cx, cy = int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2)
            
            win32api.SetCursorPos((cx, cy)); time.sleep(0.2)
            # 더블 클릭 수행
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.05) # 더블 클릭 간격
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except: return False

    def _click_relative(self, dx, dy):
        """상대 좌표 클릭"""
        cx, cy = win32api.GetCursorPos()
        win32api.SetCursorPos((cx + dx, cy + dy)); time.sleep(0.3)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0); time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

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
    
    def wait_for_video_attachment(self, timeout=180):
        """
        [수정됨 v3] 단순 대기 모드
        - 복잡한 UI 검증(클릭, 클립보드) 로직 제거
        - 지정된 시간(timeout) 동안 무조건 대기 후 True 반환
        """
        print(f"   ⏳ [iRAS] 영상 연결 대기 중... ({timeout}초 고정 대기)")
        
        # 1초씩 대기하며 진행 상황 출력 (스크립트 멈춤 오해 방지)
        for i in range(timeout):
            time.sleep(1)
            remaining = timeout - i
            
            # 10초마다 남은 시간 출력, 그 외에는 점 찍기
            if remaining % 10 == 0:
                print(f"{remaining}s..", end=" ", flush=True)
            elif remaining % 2 == 0:
                print(".", end="", flush=True)
                
        print("\n   ✅ 대기 시간 종료. (연결되었다고 가정하고 진행)")
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
            self._click(setup_hwnd, ID_OK_BTN) # 설정 닫기

        main_hwnd = self._get_handle(TITLE_MAIN, force_focus=True)
        if not main_hwnd: return False

        # 2. 감시 화면 관련 차단 확인 (PTZ, Color, Alarm)
        ops = [COORD_MENU_PTZ, COORD_MENU_COLOR]
        for op in ops:
            if self._click(main_hwnd, ID_SURVEILLANCE_PANE, right_click=True):
                self._click_relative(*op)
                time.sleep(1.5); self.shell.SendKeys("{ENTER}"); time.sleep(0.5)

        # 3. 알람 출력
        if self._click(main_hwnd, ID_SURVEILLANCE_PANE, right_click=True):
            self._click_relative(*COORD_MENU_ALARM); time.sleep(0.3)
            self._click_relative(*COORD_ALARM_ON)
            time.sleep(1.5); self.shell.SendKeys("{ENTER}"); time.sleep(0.5)

        # 4. 클립 카피 (재생 -> 저장 -> 클립복사)
        if self._click(main_hwnd, ID_SURVEILLANCE_PANE, right_click=True):
            self._click_relative(*COORD_MENU_PLAYBACK)
            time.sleep(4.0)
            if self._click(main_hwnd, ID_SAVE_CLIP_BTN):
                time.sleep(1.0)
                self._click_relative(*COORD_CLIP_COPY) # 저장 메뉴 내 상대 좌표
                time.sleep(2.0); self.shell.SendKeys("{ENTER}")
            self._return_to_watch() # 감시 복귀
            
        print("   ✅ Phase 1 완료")
        return True
    
    

    # --- [기능 2] 권한 테스트 (Phase 2) ---
    def run_permission_phase2(self, device_name):
        print("\n🧪 [iRAS] Phase 2: 설정/검색 차단 테스트...")
        
        # 1. 원격 설정 차단 확인
        setup_hwnd = self._enter_setup()
        if setup_hwnd:
            self._input(setup_hwnd, ID_DEV_SEARCH_INPUT, device_name)
            if self._click(setup_hwnd, ID_DEV_LIST, right_click=True, y_offset=25):
                self._click_relative(*COORD_MENU_REMOTE)
                print("   [Wait] 팝업 대기 (5초)...")
                time.sleep(5.0) # 차단 팝업 대기
                self.shell.SendKeys("{ENTER}") # 팝업 닫기
            self._click(setup_hwnd, ID_OK_BTN) # 설정 닫기

        # 2. 녹화 영상 검색(재생) 차단 확인
        main_hwnd = self._get_handle(TITLE_MAIN, force_focus=True)
        if main_hwnd and self._click(main_hwnd, ID_SURVEILLANCE_PANE, right_click=True):
            self._click_relative(*COORD_MENU_PLAYBACK)
            time.sleep(2.0); self.shell.SendKeys("{ENTER}")
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
            time.sleep(3) # 서버 응답 대기
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
    
    # --- [기능 5] 원격 포트 변경 (NEW) ---
    def set_remote_port(self, device_search_key, port_value):
        """iRAS에서 장치의 원격 포트를 변경하고 연결 테스트 수행"""
        print(f"\n🔌 [iRAS] 원격 포트 변경 시작 (Target Port: {port_value})")

        # 1. 설정 및 수정창 진입
        setup_hwnd = self._enter_setup()
        if not setup_hwnd: return False

        self._input(setup_hwnd, ID_DEV_SEARCH_INPUT, device_search_key)
        time.sleep(1.0)
        
        if self._click(setup_hwnd, ID_DEV_LIST, right_click=True, y_offset=25):
            self._click_relative(*COORD_MENU_MODIFY); time.sleep(2.0)
        else:
            print("❌ 장치 리스트 클릭 실패")
            self._click(setup_hwnd, ID_OK_BTN); return False

        modify_hwnd = self._get_handle(TITLE_MODIFY)
        if not modify_hwnd: return False

        # 2. 네트워크 탭 이동 (탭바 오른쪽 클릭 트릭)
        try:
            win = auto.ControlFromHandle(modify_hwnd)
            tab = win.TabItemControl()
            if tab.Exists(maxSearchSeconds=2):
                rect = tab.BoundingRectangle
                cx = rect.left + (rect.right - rect.left) * 1.5 
                cy = (rect.top + rect.bottom) / 2
                win32api.SetCursorPos((int(cx), int(cy)))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(1.0)
        except: pass

        # 3. 포트 입력 (더블클릭 -> 입력)
        print(f"   [iRAS] 포트 값 입력: {port_value}")
        
        # 확실한 포커스를 위해 더블클릭 수행
        if self._double_click(modify_hwnd, ID_PORT_INPUT):
            time.sleep(0.5)
            # 값 입력 (Ctrl+A -> Del -> Paste)
            self.shell.SendKeys("^a{BACKSPACE}"); time.sleep(0.1)
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(str(port_value), win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                self.shell.SendKeys("^v")
            except: 
                print("⚠️ 클립보드 복사 실패, 직접 입력 시도")
                self.shell.SendKeys(str(port_value))
        else:
            print("❌ 포트 입력 필드(1201)를 찾을 수 없습니다.")
            self._click(modify_hwnd, ID_OK_BTN)
            self._click(setup_hwnd, ID_OK_BTN)
            return False
        
        # 4. 연결 테스트
        print("   [iRAS] 연결 테스트 실행...")
        if self._click(modify_hwnd, ID_TEST_BTN):
            print("   -> 테스트 진행 중 (5초 대기)...")
            time.sleep(5.0) # 포트 변경은 시간이 좀 더 걸릴 수 있음
            self.shell.SendKeys("{ENTER}"); time.sleep(0.5)

        # 5. 저장 및 종료
        print("   [iRAS] 설정 저장 완료")
        self._click(modify_hwnd, ID_OK_BTN); time.sleep(1.5)
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

def run_port_change_process(device_name_to_search, new_port):
    """원격 포트 변경 프로세스 실행 (network_test.py에서 호출)"""
    controller = IRASController()
    if not controller.set_remote_port(device_name_to_search, new_port):
        print("🔥 [iRAS] 포트 변경 중 오류 발생")
        return False
    print(f"🎉 [iRAS] 포트 변경 성공 -> {new_port}")
    return True

def wait_for_connection():
    controller = IRASController()
    return controller.wait_for_video_attachment()

if __name__ == "__main__":
    
    run_fen_verification("TcpDirectExternal")