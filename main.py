import time
import sys
import ctypes
import subprocess
from playwright.sync_api import sync_playwright


# if not ctypes.windll.shell32.IsUserAnAdmin():
#     print("🔒 관리자 권한으로 재실행합니다...")
#     # 현재 스크립트를 관리자 권한('runas')으로 다시 실행
#     ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
#     sys.exit()

# 각 모듈에서 테스트 함수 import
try:
    from system_tests import run_default_setup_test, run_setup_roundtrip_test
    from language_test import run_all_languages_test # 필요시 주석 해제
    from datetime_test import run_datetime_tests
    from user_group_tests import run_user_group_test
    from video_test import run_self_adjust_mode_test, run_video_image_test, run_white_balance_test, run_exposure_test
except ImportError as e:
    print(f"오류: 파일이나 함수를 찾을 수 없습니다. {e}")
    exit()

# --- 전역 설정값 ---
CAMERA_IP = "10.0.131.104" 
CAMERA_URL = f"http://{CAMERA_IP}/setup"
USERNAME = "admin"
PASSWORD = "qwerty0-"
INTERFACE_NAME = "이더넷" # 본인 PC 환경에 맞게 수정 (예: "Ethernet" or "Wi-Fi")

def main():
    
    # -----------------------------------------------------------
    # 🖥️ [새 창 실행 로직]
    # --new-console 인자가 없으면, 새 콘솔을 열어 자신을 재실행합니다.
    # -----------------------------------------------------------
    if "--new-console" not in sys.argv:
        print("🖥️  테스트 가시성을 위해 새 터미널 창을 엽니다...")
        
        # 현재 실행된 파이썬과 동일한 인자로 새 프로세스 실행 (CREATE_NEW_CONSOLE 플래그 사용)
        # Windows 전용 플래그입니다.
        CREATE_NEW_CONSOLE = 0x00000010
        subprocess.Popen([sys.executable] + sys.argv + ["--new-console"], 
                         creationflags=CREATE_NEW_CONSOLE)
        return # 현재 프로세스는 종료

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

            print("\n📡 네트워크 통합 테스트를 별도 프로세스로 시작합니다...")
            print("   (브라우저 세션 충돌 방지를 위해 독립적으로 실행됩니다)\n")
            
            # 현재 실행 중인 파이썬 인터프리터 경로
            python_exe = sys.executable 
            
            # subprocess로 실행할 명령어 구성
            cmd = [
                python_exe, "network_test.py",
                "--ip", CAMERA_IP,
                "--id", USERNAME,
                "--pw", PASSWORD,
                "--iface", INTERFACE_NAME
            ]
            
            # 실행 (check=True는 실패 시 예외 발생시킴)
            # 💡 브라우저는 닫을 필요 없음 (서로 다른 프로세스라 영향 없음)
            try:
                subprocess.run(cmd, check=True)
                print("\n🎉 [최종 성공] 네트워크 테스트 프로세스가 정상 종료되었습니다.")
            except subprocess.CalledProcessError:
                raise Exception("네트워크 테스트 프로세스가 실패 코드를 반환했습니다.")
            
            # [Video] Self Adjust Mode (Easy Video Setting) 테스트
            success, msg = run_self_adjust_mode_test(page, CAMERA_IP)
            if not success: raise Exception(msg)
            print(f"🎉 [성공] {msg}")

            # --- [Test 2] Video - Image (Mirroring/Pivot) ---
            print("\n🎥 [Video] Image Setting (Mirroring/Pivot) 테스트 시작...")
            success, msg = run_video_image_test(page, CAMERA_IP)
            if not success: raise Exception(msg)
            print(f"🎉 [성공] {msg}")

            # --- [Test 3] White Balance ---
            print("\n🎥 [Video] White Balance 테스트 시작...")
            success, msg = run_white_balance_test(page, CAMERA_IP)
            if not success: raise Exception(msg)
            print(f"🎉 [성공] {msg}")

            print("\n🎥 [Video] Exposure 테스트 시작...")
            success, msg = run_exposure_test(page, CAMERA_IP)
            if not success: raise Exception(msg)
            print(f"🎉 [성공] {msg}")

            # ----------------------------------------------------
            print("\n✅ 모든 테스트가 성공적으로 완료되었습니다.")
            time.sleep(3)

        except Exception as e:
            print(f"\n🔥 [실패] 테스트 중단됨: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(10) # 에러 확인용 대기
        finally:
            browser.close()

if __name__ == "__main__":
    main()