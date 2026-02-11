import time
import sys
import ctypes
import subprocess
import os  
from playwright.sync_api import sync_playwright

# 각 모듈에서 테스트 함수 import
try:
    from system_tests import run_default_setup_test, run_setup_roundtrip_test
    from language_test import run_all_languages_test
    from datetime_test import run_datetime_tests
    from user_group_tests import run_user_group_test
    from video_test import (
        run_self_adjust_mode_test, run_video_image_test, run_white_balance_test, 
        run_exposure_test, run_daynight_test, run_video_misc_test, run_streaming_test, 
        run_video_mat_test, run_privacy_mask_test, run_osd_test
    )
    from event_action import (
        run_alarm_out_test, run_email_test, run_ftp_test, run_recording_test
    )
    from api_client import CameraApiClient
    import config
except ImportError as e:
    print(f"❌ 오류: 필요한 모듈을 찾을 수 없습니다.\n{e}")
    input("엔터 키를 누르면 종료합니다...") 
    sys.exit(1)

# ===========================================================
# 📋 테스트 카테고리 정의
# ===========================================================
TEST_CATEGORIES = {
    "system": {
        "name": "🔧 시스템 테스트",
        "tests": [
            ("default_setup", "초기화 및 기본 설정 복구", run_default_setup_test, True),
            ("setup_roundtrip", "설정 내보내기/불러오기", run_setup_roundtrip_test, True),
            ("language", "다국어 지원", run_all_languages_test, True),
            ("datetime", "날짜/시간 설정", run_datetime_tests, True),
            ("user_group", "사용자/그룹 관리", run_user_group_test, True),
        ]
    },
    "network": {
        "name": "📡 네트워크 테스트",
        "tests": [
            ("network_full", "네트워크 통합 테스트 (별도 프로세스)", None, False),
        ],
        "special": "subprocess"  # 특수 실행 방식 표시
    },
    "video": {
        "name": "🎥 비디오 테스트",
        "tests": [
            ("self_adjust", "Self Adjust Mode", run_self_adjust_mode_test, False),
            ("image", "Image Setting (Mirroring/Pivot)", run_video_image_test, False),
            ("white_balance", "White Balance", run_white_balance_test, False),
            ("exposure", "Exposure (Gain/Shutter/WDR)", run_exposure_test, False),
            ("daynight", "Day & Night", run_daynight_test, False),
            ("misc", "Misc (EIS)", run_video_misc_test, False),
            ("streaming", "Streaming", run_streaming_test, False),
            ("mat", "MAT (Motion Adaptive Transmission)", run_video_mat_test, False),
            ("privacy", "Privacy Mask", run_privacy_mask_test, False),
            ("osd", "OSD (On-Screen Display)", run_osd_test, False),
        ]
    },
    "event": {
        "name": "🚨 이벤트/액션 테스트",
        "tests": [
            ("alarm_out", "Alarm Out", run_alarm_out_test, False),
            ("email", "Email 전송", run_email_test, False),
            ("ftp", "FTP 업로드", run_ftp_test, False),
            ("recording", "SD Recording", run_recording_test, False),
        ]
    }
}

def get_user_input():
    """사용자로부터 테스트에 필요한 정보를 입력받습니다."""
    print("\n" + "="*60)
    print("🎥 카메라 자동 테스트 프로그램")
    print("="*60)
    print("테스트에 필요한 정보를 입력해주세요.\n")
    
    # 카메라 IP
    camera_ip = input("📍 카메라 IP 주소 (예: 10.0.131.104): ").strip()
    if not camera_ip:
        print("❌ 카메라 IP는 필수입니다.")
        input("엔터 키를 누르면 종료합니다...")
        sys.exit(1)
    
    # 사용자 이름
    username = input("👤 카메라 사용자 이름 (기본값: admin): ").strip()
    if not username:
        username = "admin"
    
    # 비밀번호
    password = input("🔑 카메라 비밀번호: ").strip()
    if not password:
        print("❌ 비밀번호는 필수입니다.")
        input("엔터 키를 누르면 종료합니다...")
        sys.exit(1)
    
    # 네트워크 인터페이스 이름
    print("\n💡 네트워크 인터페이스 이름을 입력하세요.")
    print("   (Windows 설정 > 네트워크 > 어댑터 옵션 변경에서 확인)")
    print("   예: 이더넷, Ethernet, Wi-Fi")
    interface_name = input("🌐 네트워크 인터페이스 이름 (기본값: 이더넷): ").strip()
    if not interface_name:
        interface_name = "이더넷"
    
    # iRAS 장치 이름
    print("\n💡 iRAS에 등록할 장치 이름을 입력하세요.")
    iras_device_name = input("🖥️  iRAS 장치 이름 (예: 104_T6631): ").strip()
    if not iras_device_name:
        print("❌ iRAS 장치 이름은 필수입니다.")
        input("엔터 키를 누르면 종료합니다...")
        sys.exit(1)
    
    # PC 고정 IP
    print("\n💡 네트워크 테스트를 위한 PC의 고정 IP를 입력하세요.")
    print(f"   (카메라와 같은 네트워크 대역: {camera_ip.rsplit('.', 1)[0]}.xxx)")
    pc_static_ip = input(f"💻 PC 고정 IP (예: {camera_ip.rsplit('.', 1)[0]}.102): ").strip()
    if not pc_static_ip:
        pc_static_ip = f"{camera_ip.rsplit('.', 1)[0]}.102"
        print(f"   기본값 사용: {pc_static_ip}")
    
    print("\n" + "="*60)
    print("📋 입력된 정보:")
    print("="*60)
    print(f"카메라 IP:           {camera_ip}")
    print(f"사용자 이름:         {username}")
    print(f"비밀번호:            {'*' * len(password)}")
    print(f"네트워크 인터페이스: {interface_name}")
    print(f"iRAS 장치 이름:      {iras_device_name}")
    print(f"PC 고정 IP:          {pc_static_ip}")
    print("="*60)
    
    confirm = input("\n✅ 이 정보로 테스트를 시작하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        print("테스트를 취소합니다.")
        sys.exit(0)
    
    return camera_ip, username, password, interface_name, iras_device_name, pc_static_ip

def show_test_menu():
    """테스트 선택 메뉴를 표시합니다."""
    print("\n" + "="*60)
    print("📋 테스트 카테고리 선택")
    print("="*60)
    
    categories = list(TEST_CATEGORIES.keys())
    for i, cat_key in enumerate(categories, 1):
        cat = TEST_CATEGORIES[cat_key]
        print(f"{i}. {cat['name']} ({len(cat['tests'])}개)")
    
    print(f"{len(categories)+1}. 🎯 전체 테스트 실행")
    print("0. ❌ 종료")
    print("="*60)
    
    while True:
        choice = input("\n선택 (번호 입력): ").strip()
        if choice.isdigit():
            choice_num = int(choice)
            if choice_num == 0:
                print("프로그램을 종료합니다.")
                sys.exit(0)
            elif 1 <= choice_num <= len(categories):
                return categories[choice_num - 1]
            elif choice_num == len(categories) + 1:
                return "all"
        print("❌ 올바른 번호를 입력하세요.")

def run_tests_with_browser(tests_to_run, camera_ip, username, password):
    """브라우저가 필요한 테스트 실행"""
    with sync_playwright() as p:
        print("\n🌐 Chrome 브라우저를 실행합니다...")
        browser = p.chromium.launch(channel="chrome", headless=False, slow_mo=500)
        context = browser.new_context(
            http_credentials={'username': username, 'password': password}
        )
        page = context.new_page()
        
        try:
            print("   카메라 웹 페이지 접속 중...")
            page.goto(config.CAMERA_URL)
            page.wait_for_selector("#Page200_id", timeout=10000)
            print("   ✅ 로그인 성공\n")
            
            api_client = CameraApiClient(page, camera_ip)
            
            # 테스트 실행
            passed = 0
            failed = 0
            
            for test_id, test_name, test_func, needs_browser in tests_to_run:
                print(f"\n{'='*60}")
                print(f"🧪 [{passed+failed+1}/{len(tests_to_run)}] {test_name}")
                print(f"{'='*60}")
                
                try:
                    # 테스트 함수의 시그니처에 따라 인자 전달
                    if test_id in ["default_setup", "setup_roundtrip", "language", "datetime"]:
                        success, msg = test_func(page, api_client)
                    elif test_id == "user_group":
                        success, msg = test_func(page, camera_ip, username, password)
                    else:
                        success, msg = test_func(page, camera_ip)
                    
                    if success:
                        print(f"✅ 성공: {msg}")
                        passed += 1
                    else:
                        print(f"❌ 실패: {msg}")
                        failed += 1
                        
                except Exception as e:
                    print(f"❌ 예외 발생: {e}")
                    failed += 1
            
            # 최종 결과
            print(f"\n{'='*60}")
            print(f"📊 테스트 결과")
            print(f"{'='*60}")
            print(f"✅ 성공: {passed}/{len(tests_to_run)}")
            print(f"❌ 실패: {failed}/{len(tests_to_run)}")
            print(f"{'='*60}")
            
            if failed > 0:
                print(f"\n⚠️  {failed}개의 테스트가 실패했습니다.")
            else:
                print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
            
        except Exception as e:
            print(f"\n🔥 [치명적 오류] {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()
            print("\n브라우저를 종료했습니다.")

def run_tests_without_browser(tests_to_run, camera_ip, username, password):
    """브라우저 없이 API만으로 실행 가능한 테스트"""
    with sync_playwright() as p:
        print("\n🔧 백그라운드 세션 초기화 중...")
        # headless 모드로 실행 (화면 없음)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            http_credentials={'username': username, 'password': password}
        )
        page = context.new_page()
        
        try:
            # 최소한의 인증만 수행
            page.goto(config.CAMERA_URL, wait_until="domcontentloaded")
            print("   ✅ 인증 완료\n")
            
            # 테스트 실행
            passed = 0
            failed = 0
            
            for test_id, test_name, test_func, needs_browser in tests_to_run:
                print(f"\n{'='*60}")
                print(f"🧪 [{passed+failed+1}/{len(tests_to_run)}] {test_name}")
                print(f"{'='*60}")
                
                try:
                    success, msg = test_func(page, camera_ip)
                    
                    if success:
                        print(f"✅ 성공: {msg}")
                        passed += 1
                    else:
                        print(f"❌ 실패: {msg}")
                        failed += 1
                        
                except Exception as e:
                    print(f"❌ 예외 발생: {e}")
                    failed += 1
            
            # 최종 결과
            print(f"\n{'='*60}")
            print(f"📊 테스트 결과")
            print(f"{'='*60}")
            print(f"✅ 성공: {passed}/{len(tests_to_run)}")
            print(f"❌ 실패: {failed}/{len(tests_to_run)}")
            print(f"{'='*60}")
            
            if failed > 0:
                print(f"\n⚠️  {failed}개의 테스트가 실패했습니다.")
            else:
                print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
            
        except Exception as e:
            print(f"\n🔥 [치명적 오류] {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

def run_network_test(camera_ip, username, password, interface_name):
    """네트워크 테스트를 별도 프로세스로 실행 (브라우저 충돌 방지)"""
    print("\n" + "="*60)
    print("📡 네트워크 통합 테스트")
    print("="*60)
    print("   ℹ️  브라우저 세션 충돌 방지를 위해 별도 프로세스로 실행합니다.\n")
    
    # subprocess로 실행할 명령어 구성
    cmd = [
        sys.executable, "network_test.py",
        "--ip", camera_ip,
        "--id", username,
        "--pw", password,
        "--iface", interface_name
    ]
    
    try:
        # 별도 프로세스로 실행 (현재 콘솔에서)
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print("\n✅ 네트워크 테스트가 정상 종료되었습니다.")
            return True
        else:
            print(f"\n⚠️  네트워크 테스트가 코드 {result.returncode}를 반환했습니다.")
            return False
            
    except FileNotFoundError:
        print(f"\n❌ [오류] network_test.py 파일을 찾을 수 없습니다.")
        return False
    except Exception as e:
        print(f"\n🔥 [실패] 네트워크 테스트 실행 중 오류: {e}")
        return False

def main():
    # -----------------------------------------------------------
    # 🔐 관리자 권한 체크
    # -----------------------------------------------------------
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("🔒 관리자 권한으로 재실행합니다...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()
    
    # -----------------------------------------------------------
    # 📋 사용자 입력 받기
    # -----------------------------------------------------------
    camera_ip, username, password, interface_name, iras_device_name, pc_static_ip = get_user_input()
    
    # config 모듈 업데이트
    config.update_config(camera_ip, username, password, interface_name, iras_device_name, pc_static_ip)
    
    # -----------------------------------------------------------
    # 📋 테스트 선택
    # -----------------------------------------------------------
    selected_category = show_test_menu()
    
    # -----------------------------------------------------------
    # 📡 네트워크 테스트는 별도 처리
    # -----------------------------------------------------------
    if selected_category == "network":
        print("\n✅ 설정 완료. 네트워크 테스트를 시작합니다...\n")
        time.sleep(1)
        run_network_test(camera_ip, username, password, interface_name)
        return
    
    # -----------------------------------------------------------
    # 🧪 일반 테스트 실행
    # -----------------------------------------------------------
    tests_to_run = []
    needs_browser = False
    run_network_after = False
    
    if selected_category == "all":
        # 모든 테스트 실행 (네트워크 제외)
        for cat_key in TEST_CATEGORIES:
            if cat_key != "network":  # 네트워크는 별도 처리
                tests_to_run.extend(TEST_CATEGORIES[cat_key]["tests"])
        needs_browser = True  # 전체 실행 시 브라우저 필요
        
        # 전체 테스트 후 네트워크 테스트 실행 여부 확인
        print("\n" + "="*60)
        print("📡 네트워크 테스트도 실행하시겠습니까?")
        print("="*60)
        print("   ℹ️  네트워크 테스트는 별도 프로세스로 실행됩니다.")
        confirm = input("   실행 (y/n): ").strip().lower()
        run_network_after = (confirm == 'y')
    else:
        # 선택한 카테고리의 테스트만 실행
        category = TEST_CATEGORIES[selected_category]
        tests_to_run = category["tests"]
        # 하나라도 브라우저가 필요하면 브라우저 모드로 실행
        needs_browser = any(test[3] for test in tests_to_run)
    
    print(f"\n✅ 설정 완료. {len(tests_to_run)}개의 테스트를 시작합니다...\n")
    time.sleep(1)
    
    # 일반 테스트 실행
    if needs_browser:
        run_tests_with_browser(tests_to_run, camera_ip, username, password)
    else:
        run_tests_without_browser(tests_to_run, camera_ip, username, password)
    
    # 전체 테스트 모드에서 네트워크 테스트 실행
    if run_network_after:
        print("\n" + "="*60)
        input("일반 테스트 완료. 네트워크 테스트를 시작하려면 엔터를 누르세요...")
        print("="*60)
        run_network_test(camera_ip, username, password, interface_name)
    
    print("\n\n" + "="*60)
    print("🎉 모든 작업이 완료되었습니다!")
    print("="*60)
    input("\n엔터 키를 누르면 프로그램을 종료합니다...")

if __name__ == "__main__":
    try:
        # 스크립트가 있는 경로로 작업 디렉토리 변경 (관리자 실행 시 경로 꼬임 방지)
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자가 테스트를 중단했습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        input("\n엔터 키를 누르면 종료합니다...")
        sys.exit(1)