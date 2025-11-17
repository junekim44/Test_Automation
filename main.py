import time
from playwright.sync_api import sync_playwright

# 1. 👈 'system_tests.py' 파일에서 실행할 테스트 케이스 함수를 import
try:
    from system_tests import run_setup_roundtrip_test
    # ⭐️ 나중에 date_tests.py 만들면 여기에 추가:
    # from date_tests import run_ntp_server_test 
except ImportError:
    print("오류: 'system_tests.py' 또는 'date_tests.py' 파일을 찾을 수 없습니다.")
    exit()

# --- 전역 설정값 ---
CAMERA_IP = "10.0.131.108" 
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
            page.wait_for_selector("text=시스템", timeout=10000)
            print("✅ [메인] 로그인 성공!")
            
            # ----------------------------------------------------
            # ⭐️ 테스트 케이스 호출 ⭐️
            # ----------------------------------------------------
            
            # 1. '시스템' 메뉴 테스트 실행
            success, message = run_setup_roundtrip_test(page, CAMERA_IP)
            if not success:
                raise Exception(f"시스템 테스트 실패: {message}")
            print(f"\n🎉 [메인] {message}")
            
            # 2. '날짜/시간' 메뉴 테스트 실행 (예시)
            # print("\n--- [TC 2] 날짜/시간 테스트 시작 ---")
            # success, msg = run_ntp_server_test(page, CAMERA_IP) 
            # if not success:
            #     raise Exception(f"날짜/시간 테스트 실패: {msg}")

            # ----------------------------------------------------

            print("\n===============================================")
            print("✅ 모든 테스트 케이스가 성공적으로 완료되었습니다.")
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