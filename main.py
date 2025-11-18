import time
from playwright.sync_api import sync_playwright

# 1. 실행할 테스트 케이스가 있는 파일들을 import
try:
    from system_tests import run_setup_roundtrip_test
    from language_test import run_all_languages_test
except ImportError:
    print("오류: 'common_actions.py', 'system_tests.py', 'language_test.py' 파일이 같은 폴더에 있는지 확인하세요.")
    exit()

# --- 전역 설정값 ---
CAMERA_IP = "10.0.131.105" 
CAMERA_URL = f"http://{CAMERA_IP}/setup"
USERNAME = "admin"
PASSWORD = "qwerty0-" 

def main():
    """
    메인 테스트 실행기.
    브라우저 설정, 로그인, 테스트 케이스 호출, 브라우저 종료를 담당.
    """
    with sync_playwright() as p:
        print("Chrome 브라우저를 실행합니다...")
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(
            http_credentials={
                'username': USERNAME,
                'password': PASSWORD
            }
        )
        page = context.new_page()
        
        try:
            # 0. 공통 준비 단계: 로그인
            print("[메인] 로그인 시도...")
            page.goto(CAMERA_URL)
            print("[메인] 로그인 성공 확인 중 (메뉴 ID 대기)...")
            page.wait_for_selector("#Page200_id", timeout=10000)
            
            # ----------------------------------------------------
            # ⭐️ 테스트 케이스 실행 (원하는 테스트의 주석(#)을 해제)
            # ----------------------------------------------------
            
            # --- [테스트 1: 설정 내보내기/불러오기] ---
            # print("\n--- [메인] '시스템' 테스트 케이스 실행 ---")
            # success, message = run_setup_roundtrip_test(page, CAMERA_IP)
            # if not success:
            #     raise Exception(f"시스템 테스트 실패: {message}")
            # print(f"\n🎉 [메인] {message}")
            

            # --- [테스트 2: 전체 언어 변경] ---
            print("\n--- [메인] '언어' 테스트 케이스 실행 ---")
            success, message = run_all_languages_test(page, CAMERA_IP)
            if not success:
                raise Exception(f"언어 테스트 실패: {message}")
            print(f"\n🎉 [메인] {message}")

            # ----------------------------------------------------

            print("\n===============================================")
            print("✅ 선택된 테스트 케이스가 성공적으로 완료되었습니다.")
            print("===============================================")
            time.sleep(5)

        except Exception as e:
            print(f"\n🔥 [메인] 테스트 실행 중 오류 발생: {e}")
            time.sleep(10)
        
        finally:
            print("[메인] 브라우저를 닫습니다.")
            browser.close()

if __name__ == "__main__":
    main()