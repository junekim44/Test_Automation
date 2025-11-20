import time

import subprocess

import win32gui

import win32com.client

import requests

from appium import webdriver

from typing import Any, Dict

from selenium.webdriver.common.by import By

from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.remote.webelement import WebElement

from appium.options.common import AppiumOptions

from appium.webdriver.common.appiumby import AppiumBy

import uiautomation as auto

import win32con

import win32com.client as win32

import win32api



# ---------------------------------------------------------

# [설정] WinAppDriver 경로 및 주소

# ---------------------------------------------------------

WAD_PATH = r"C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe"

WAD_URL = "http://127.0.0.1:4723"



# 창 이름 설정

MAIN_WINDOW_TITLE = "IDIS Center Remote Administration System"

SETUP_WINDOW_TITLE = "IDIS Center 설정"

TARGET_DEVICE = "105_T6831"



# ---------------------------------------------------------

# 🛠️ [핵심 1] WinAppDriver 호환용 커스텀 드라이버

# ---------------------------------------------------------

class LegacyWinAppDriver(webdriver.Remote):

    def start_session(self, capabilities: Dict[str, Any], browser_profile=None) -> None:

        print(f"   [Driver] WinAppDriver에 호환 모드(JSONWP)로 연결 시도...")

        clean_caps = {k.split(':')[-1]: v for k, v in capabilities.items()}

        payload = {"desiredCapabilities": clean_caps}

       

        try:

            response = requests.post(f"{WAD_URL}/session", json=payload)

            if response.status_code != 200:

                raise Exception(f"HTTP {response.status_code}: {response.text}")

           

            data = response.json()

            self.session_id = data.get('sessionId')

            self.w3c = False

            self.command_executor._url = WAD_URL

            print(f"   [Driver] 연결 성공! Session ID: {self.session_id}")

        except Exception as e:

            raise Exception(f"WinAppDriver 연결 실패: {e}")



# ---------------------------------------------------------

# 🛠️ [핵심 2] 요소 안전 변환 (dict -> WebElement)

# ---------------------------------------------------------

def ensure_element(driver, element_or_dict):

    if isinstance(element_or_dict, dict):

        try:

            elem_id = element_or_dict.get('ELEMENT') or list(element_or_dict.values())[0]

            return WebElement(driver, elem_id)

        except:

            return element_or_dict

    return element_or_dict



# ---------------------------------------------------------

# 🛠️ [핵심 3] 윈도우 네이티브 키보드 입력 함수

# ---------------------------------------------------------

def send_native_keys(keys):

    """Appium을 거치지 않고 Windows OS에게 직접 키 입력을 명령"""

    shell = win32com.client.Dispatch("WScript.Shell")

    shell.SendKeys(keys)



def native_mouse_right_click_by_automation(element_name: str):

    """

    WinAppDriver 대신 UIAutomation으로 요소 화면 좌표를 직접 검출 후 우클릭

    """

    try:

        control = auto.Control(Name=element_name)

        if not control.Exists():

            print(f"❌ UIA: 요소 '{element_name}' 찾기 실패")

            return False

       

        rect = control.BoundingRectangle

        x = int((rect.left + rect.right) / 2)

        y = int((rect.top + rect.bottom) / 2)



        print(f"   [UIA] 요소 좌표: ({x}, {y})")



        win32api.SetCursorPos((x, y))

        time.sleep(0.3)



        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, x, y, 0, 0)

        time.sleep(0.1)

        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, x, y, 0, 0)



        print("   → 우클릭 완료 (UIAutomation)")

        return True



    except Exception as e:

        print(f"❌ UIA 우클릭 실패: {e}")

        return False



# ---------------------------------------------------------

# [함수] 창 핸들 찾기 및 연결

# ---------------------------------------------------------

def attach_to_window(window_name):

    print(f"[System] '{window_name}' 창 찾는 중...")

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



    if not hwnd:

        print(f"❌ '{window_name}' 창을 찾을 수 없습니다.")

        return None



    try:

        if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, 9)

        win32gui.SetForegroundWindow(hwnd)

    except: pass



    hwnd_hex = hex(hwnd)

    print(f"✅ 창 핸들 획득: {hwnd_hex}")



    options = AppiumOptions()

    options.set_capability("appTopLevelWindow", hwnd_hex)

    options.set_capability("platformName", "Windows")

    options.set_capability("deviceName", "WindowsPC")



    try:

        return LegacyWinAppDriver(command_executor=WAD_URL, options=options)

    except Exception as e:

        print(f"❌ 연결 오류: {e}")

        return None



def run_iras_automation():

    try:

        subprocess.Popen([WAD_PATH], shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE)

    except: pass

    time.sleep(2)



    # [Step 1] 메인 화면 키보드 진입

    driver = attach_to_window(MAIN_WINDOW_TITLE)

    if not driver: return



    try:

        print("[Step 1] 윈도우 키보드 명령 전송 (Alt+s -> i -> Enter)...")

        send_native_keys("%s") # Alt+s

        time.sleep(1.0)

        send_native_keys("i")

        time.sleep(1.0)

        send_native_keys("{ENTER}")

        time.sleep(1.0)

        send_native_keys("{ENTER}")

        time.sleep(1.0)

        print("✅ 키보드 입력 완료. 팝업 대기...")

    except Exception as e:

        print(f"❌ 키보드 입력 오류: {e}")

    finally:

        try: driver.quit()

        except: pass



    print("[System] 팝업 창 로딩 대기 (3초)...")

    time.sleep(3)



    # [Step 2] 설정 팝업창 연결

    driver = attach_to_window(SETUP_WINDOW_TITLE)

    if not driver:

        print("❌ 설정 창이 뜨지 않았습니다.")

        return



    try:

        # ---------------------------------------------------------

        # [Step 3] 검색창 입력 (ID: "101")

        # ---------------------------------------------------------

        print(f"[Step 3] 검색창(ID:101)에 '{TARGET_DEVICE}' 입력...")

       

        raw_search_box = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "101")

        search_box = ensure_element(driver, raw_search_box)

       

        # 1. 클릭해서 포커스 주기 (커서 이동)

        search_box.click()

        time.sleep(0.5)

       

        # 2. ⭐️ [수정됨] Appium send_keys 대신 Native Input 사용

        # 기존 텍스트 제거를 위해 Ctrl+A -> Backspace 입력 (안전장치)

        send_native_keys("^a{BACKSPACE}")

        time.sleep(0.2)

       

        # 실제 장치 이름 타이핑

        send_native_keys(TARGET_DEVICE)

       

        print("   -> 필터링 대기 (2초)...")

        time.sleep(2)



        # ---------------------------------------------------------

        # [Step 4] 장치 선택 및 우클릭 (ID: "1000")

        # ---------------------------------------------------------

        print("[Step 4] 검색된 장치(ID:1000) 찾기...")

       

        # 1. 요소 찾기

        target_item = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "1000")

       

        # 2. ⭐️ [핵심] 윈도우 네이티브 마우스 우클릭 실행

        # ActionChains 대신 직접 마우스를 움직여서 클릭합니다.

        if native_mouse_right_click_by_automation(TARGET_DEVICE):

            print("✅ 우클릭 성공! (컨텍스트 메뉴 확인)")

        else:

            print("❌ 우클릭 실패")



        time.sleep(2)



    except Exception as e:

        print(f"🔥 오류 발생: {e}")

        import traceback

        traceback.print_exc()

    finally:

        try: driver.quit()

        except: pass



if __name__ == "__main__":

    run_iras_automation()