import time
from playwright.sync_api import sync_playwright

# 각 모듈에서 테스트 함수 import
try:
    from system_tests import run_default_setup_test, run_setup_roundtrip_test
    from language_test import run_all_languages_test # 필요시 주석 해제
    from datetime_test import run_datetime_tests
    from user_group_tests import run_user_group_test
except ImportError as e:
    print(f"오류: 파일이나 함수를 찾을 수 없습니다. {e}")
    exit()

# --- 전역 설정값 ---
CAMERA_IP = "10.0.131.104" 
CAMERA_URL = f"http://{CAMERA_IP}/setup"
USERNAME = "admin"
PASSWORD = "qwerty0-" 

def main():
    with sync_playwright() as p:
        print("Chrome 브라우저를 실행합니다...")
        # slow_mo=1000 : 모든 클릭/입력 동작마다 1초(1000ms)씩 텀을 둡니다. (속도 조절)
        browser = p.chromium.launch(channel="chrome", headless=False, slow_mo=1000) 
        
        
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
            
            # # 시스템 초기화 및 복구 (가장 먼저 실행하여 Clean State 확보)
            # success, msg = run_default_setup_test(page, CAMERA_IP)
            # if not success: raise Exception(f"초기화 테스트 실패: {msg}")
            # print(f"🎉 [성공] {msg}")

            # # 설정 내보내기/불러오기
            # success, msg = run_setup_roundtrip_test(page, CAMERA_IP)
            # if not success: raise Exception(f"설정파일 테스트 실패: {msg}")
            # print(f"🎉 [성공] {msg}")

            # # 다국어 변경 테스트
            # success, msg = run_all_languages_test(page, CAMERA_IP)
            # if not success: raise Exception(f"설정파일 테스트 실패: {msg}")
            # print(f"🎉 [성공] {msg}")

            # # 날짜/시간 테스트 (NTP, Timezone, Format)

            # success, msg = run_datetime_tests(page, CAMERA_IP)
            # if not success: raise Exception(msg)
            # print(f"🎉 [성공] {msg}")

            # --- [사용자/그룹 테스트] ---
            success, msg = run_user_group_test(page, CAMERA_IP, USERNAME, PASSWORD)
            if not success: raise Exception(msg)
            print(f"🎉 [최종 성공] {msg}")

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