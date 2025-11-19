import time
from playwright.sync_api import sync_playwright

# 각 모듈에서 테스트 함수 import
try:
    from system_tests import run_default_setup_test, run_setup_roundtrip_test
    # from datetime_tests import run_ntp_test, run_timezone_test, run_format_test
    from language_test import run_all_languages_test # 필요시 주석 해제
except ImportError as e:
    print(f"오류: 파일이나 함수를 찾을 수 없습니다. {e}")
    exit()

# --- 전역 설정값 ---
CAMERA_IP = "10.0.131.105" 
CAMERA_URL = f"http://{CAMERA_IP}/setup"
USERNAME = "admin"
PASSWORD = "qwerty0-" 

def main():
    with sync_playwright() as p:
        print("Chrome 브라우저를 실행합니다...")
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(
            http_credentials={'username': USERNAME, 'password': PASSWORD}
        )
        page = context.new_page()
        
        try:
            print("[메인] 로그인 및 페이지 로드...")
            page.goto(CAMERA_URL)
            page.wait_for_selector("#Page200_id", timeout=10000)
            
            # ----------------------------------------------------
            # 🧪 테스트 실행 (순서: 초기화 -> 기능테스트 -> 기타)
            # ----------------------------------------------------
            
            # # 1. 시스템 초기화 및 복구 (가장 먼저 실행하여 Clean State 확보)
            # success, msg = run_default_setup_test(page, CAMERA_IP)
            # if not success: raise Exception(f"초기화 테스트 실패: {msg}")
            # print(f"🎉 [성공] {msg}")

            # # 2. 설정 내보내기/불러오기
            # success, msg = run_setup_roundtrip_test(page, CAMERA_IP)
            # if not success: raise Exception(f"설정파일 테스트 실패: {msg}")
            # print(f"🎉 [성공] {msg}")

            success, msg = run_all_languages_test(page, CAMERA_IP)
            if not success: raise Exception(f"설정파일 테스트 실패: {msg}")
            print(f"🎉 [성공] {msg}")

            # # 3. 날짜/시간 테스트 (NTP, Timezone, Format)
            # success, msg = run_ntp_test(page, CAMERA_IP)
            # if not success: raise Exception(f"NTP 테스트 실패: {msg}")
            # print(f"🎉 [성공] {msg}")

            # success, msg = run_timezone_test(page, CAMERA_IP)
            # if not success: raise Exception(f"시간대 테스트 실패: {msg}")
            # print(f"🎉 [성공] {msg}")

            # success, msg = run_format_test(page, CAMERA_IP)
            # if not success: raise Exception(f"포맷 테스트 실패: {msg}")
            # print(f"🎉 [성공] {msg}")

            # ----------------------------------------------------
            print("\n✅ 모든 테스트가 성공적으로 완료되었습니다.")
            time.sleep(3)

        except Exception as e:
            print(f"\n🔥 [실패] 테스트 중단됨: {e}")
            time.sleep(10) # 에러 확인용 대기
        finally:
            browser.close()

if __name__ == "__main__":
    main()