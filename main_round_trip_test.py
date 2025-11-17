import time
from playwright.sync_api import sync_playwright

# 1. 모듈 4개를 모두 import
try:
    from camera_actions import (
        export_and_verify_settings, 
        import_settings_and_reboot, 
        api_get_note, 
        ui_set_note
    )
except ImportError:
    print("오류: 'camera_actions.py' 파일이 같은 폴더에 있는지 확인하세요.")
    exit()

# --- 설정값 ---
CAMERA_IP = "10.0.131.104" # URL이 아닌 IP만
CAMERA_URL = f"http://{CAMERA_IP}/setup"
USERNAME = "admin"
PASSWORD = "qwerty"
HTTP_AUTH = (USERNAME, PASSWORD) # API 요청용 인증 튜플

EXPORT_FILE = "registry_test.dat" # 테스트용 파일 이름
TEST_NOTE_VALUE = "AUTOMATION_TEST_VALUE_12345" # 검증용 특수 문자열
CONTAMINATE_VALUE = "DIRTY_VALUE_999" # 오염용 문자열

def run_full_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(
            http_credentials={
                'username': USERNAME,
                'password': PASSWORD
            }
        )
        page = context.new_page()
        
        try:
            # 0. 로그인
            print("[메인] 로그인 시도...")
            page.goto(CAMERA_URL)
            page.wait_for_selector("text=시스템", timeout=10000)
            print("✅ [메인] 로그인 성공!")
            
            # --- 테스트 시나리오 시작 ---

            # 1. (준비) 테스트 값으로 설정 변경
            print("\n[메인] 1. '설명' 값을 테스트 값으로 변경합니다...")
            if not ui_set_note(page, TEST_NOTE_VALUE):
                raise Exception("'설명' 값 설정(UI) 실패")
            
            # 2. (내보내기) 이 설정이 담긴 파일 내보내기
            print(f"\n[메인] 2. '{TEST_NOTE_VALUE}' 값이 담긴 설정을 내보냅니다...")
            success, msg = export_and_verify_settings(page, EXPORT_FILE)
            if not success:
                raise Exception(f"'설정 내보내기' 실패: {msg}")
            print(f"✅ [메인] 설정 파일 '{EXPORT_FILE}' 내보내기 성공.")
            
            # 3. (오염) 값을 엉뚱한 값으로 다시 변경 (불러오기 검증을 위해)
            print("\n[메인] 3. '설명' 값을 '오염' 값으로 덮어씁니다...")
            if not ui_set_note(page, CONTAMINATE_VALUE):
                raise Exception("'설명' 값 오염(UI) 실패")
            
            # API로 오염되었는지 확인
            note_check = api_get_note(CAMERA_IP, HTTP_AUTH)
            if note_check != CONTAMINATE_VALUE:
                 raise Exception(f"값 오염 실패! (현재 값: {note_check})")
            print(f"✅ [메인] 값 오염 완료 (현재 'note' = {CONTAMINATE_VALUE})")

            # 4. (불러오기) 2번에서 내보낸 파일 불러오기 -> 카메라 재부팅됨
            print(f"\n[메인] 4. '{EXPORT_FILE}' 파일을 '불러오기' 합니다...")
            success, msg = import_settings_and_reboot(page, EXPORT_FILE)
            if not success:
                raise Exception(f"'설정 불러오기' 실패: {msg}")
            print("✅ [메인] 설정 불러오기 및 재부팅 대기 완료.")
            
            # 5. (최종 검증)
            print("\n[메인] 5. API로 최종 'note' 값을 검증합니다...")
            # 재부팅되었으므로 페이지를 새로고침/재방문해야 세션이 복구됨
            print("[메인] 재부팅 후 페이지 재접속...")
            page.goto(CAMERA_AURL) 
            page.wait_for_selector("text=시스템", timeout=15000) # 재부팅 후 로딩 시간
            
            final_note_value = api_get_note(CAMERA_IP, HTTP_AUTH)
            
            if final_note_value == TEST_NOTE_VALUE:
                print("\n===============================================")
                print(f"🎉 테스트 성공! 🎉")
                print(f"   'note' 값이 '{TEST_NOTE_VALUE}'로 완벽히 복원되었습니다!")
                print("===============================================")
            else:
                print("\n===============================================")
                print(f"🔥 테스트 실패! 🔥")
                print(f"   예상 값: {TEST_NOTE_VALUE}")
                print(f"   실제 값: {final_note_value}")
                print("===============================================")

            time.sleep(5)

        except Exception as e:
            print(f"\n🔥 [메인] 테스트 중 심각한 오류 발생: {e}")
            time.sleep(10)
        
        finally:
            browser.close()

if __name__ == "__main__":
    # requests 라이브러리 설치 확인
    try:
        import requests
    except ImportError:
        print(" 'requests' 라이브러리가 필요합니다. 'pip install requests'를 실행하세요.")
        exit()
        
    run_full_test()