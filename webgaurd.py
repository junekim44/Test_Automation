import time
import ctypes
import win32gui
import win32com.client
import win32api
import win32con
import win32clipboard
import uiautomation as auto

# ---------------------------------------------------------
# ⚙️ [설정]
# ---------------------------------------------------------
TITLE_WEBGUARD = "WebGuard" # 창 제목 (실행 환경에 따라 'IDIS WebGuard' 일 수도 있음 확인 필요)

# UI Automation ID
ID_WG_USER = "loginUserId"
ID_WG_PASS = "loginPassword"

try: ctypes.windll.user32.SetProcessDPIAware()
except: pass

# ---------------------------------------------------------
# 🛡️ [Class] WebGuard 컨트롤러
# ---------------------------------------------------------
class WebGuardController:
    def __init__(self):
        self.shell = win32com.client.Dispatch("WScript.Shell")

    # --- [Win32/UIA 헬퍼 메소드] ---
    def _get_handle(self, title_keyword):
        """창 제목에 키워드가 포함된 창 핸들 찾기"""
        found_hwnd = None
        def callback(hwnd, _):
            nonlocal found_hwnd
            if win32gui.IsWindowVisible(hwnd):
                txt = win32gui.GetWindowText(hwnd)
                if title_keyword in txt:
                    found_hwnd = hwnd
                    return False # Stop enumeration
            return True
        
        try: win32gui.EnumWindows(callback, None)
        except: pass
        
        if found_hwnd:
            try:
                # 최소화 상태면 복구
                if win32gui.IsIconic(found_hwnd):
                    win32gui.ShowWindow(found_hwnd, win32con.SW_RESTORE)
                # 포커스 강제 (Alt 키 트릭)
                self.shell.SendKeys('%')
                win32gui.SetForegroundWindow(found_hwnd)
            except: pass
        return found_hwnd

    def _click(self, hwnd, auto_id):
        try:
            win = auto.ControlFromHandle(hwnd)
            elem = win.Control(AutomationId=auto_id)
            if not elem.Exists(maxSearchSeconds=3): return False
            
            rect = elem.BoundingRectangle
            cx, cy = int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2)
            
            win32api.SetCursorPos((cx, cy)); time.sleep(0.2)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.1)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except: return False

    def _input(self, hwnd, auto_id, text):
        if self._click(hwnd, auto_id):
            time.sleep(0.3)
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

    # --- [기능] 로그인 ---
    def login(self, user_id, user_pw):
        print("\n🔐 [WebGuard] 로그인 자동화 시도...")
        
        # 창 대기 (최대 20초)
        hwnd = None
        for i in range(20):
            hwnd = self._get_handle(TITLE_WEBGUARD)
            if hwnd: break
            time.sleep(1)
            if i % 3 == 0: print(f"   -> '{TITLE_WEBGUARD}' 창 대기 중... ({i+1}s)")
            
        if not hwnd:
            print("❌ WebGuard 창을 찾을 수 없습니다.")
            return False
            
        print(f"   -> 아이디 입력: {user_id}")
        if not self._input(hwnd, ID_WG_USER, user_id):
            print("❌ 아이디 입력 실패")
            return False
            
        print("   -> 비밀번호 입력...")
        if not self._input(hwnd, ID_WG_PASS, user_pw):
            print("❌ 비밀번호 입력 실패")
            return False
            
        print("   -> 로그인 (Enter)")
        self.shell.SendKeys("{ENTER}")
        return True

# ---------------------------------------------------------
# 🚀 외부 호출 함수
# ---------------------------------------------------------
def run_login(user_id, user_pw):
    controller = WebGuardController()
    return controller.login(user_id, user_pw)

if __name__ == "__main__":
    # 테스트
    run_login("admin", "password")