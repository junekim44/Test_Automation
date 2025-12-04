import time
from playwright.sync_api import Page
from common_actions import parse_api_response

# 💡 iRAS 컨트롤러 및 타이틀 상수 가져오기
from iRAS_test import IRASController, TITLE_MAIN

# ===========================================================
# ⚙️ [설정] 테스트 상수
# ===========================================================
WAIT_TIME = 5  # iRAS 영상 변화 관찰 대기 시간

PRESET_MODES = {
    "1": "Natural (자연스러운)",
    "2": "Vivid (선명한)",
    "3": "Denoise (노이즈 감소)"
}

PARAM_RANGES = {
    "Sharpness": ["0", "3"],
    "Contrast": ["0", "1", "2"],
    "Brightness": ["0", "2"],
    "Colors": ["0", "2"]
}

# 🌟 [핵심 수정] Custom 모드(0) 진입 시 필수인 '모든' 파라미터 정의
# API는 Custom 모드일 때 이 값들이 모두 포함되어 있어야만 301 에러를 내지 않습니다.
DEFAULT_CUSTOM_PARAMS = {
    "easyDayType": "0",
    "easyNightType": "0",
    "easyDaySharpness": "1",
    "easyDayContrast": "1",
    "easyDayBrightness": "1",
    "easyDayColors": "1",
    "easyNightSharpness": "1",
    "easyNightGamma": "1",      # Night는 Contrast 대신 Gamma 사용
    "easyNightBrightness": "1"
}

# ===========================================================
# 📸 [Snapshot] 스크린샷 캡처 함수
# ===========================================================
def trigger_iras_snapshot():
    """
    iRAS 창을 찾아 포커스한 뒤 Ctrl+S를 전송하여 스냅샷을 저장합니다.
    저장 경로: C:\\IDIS-Center\\Client\\save\\still\\admin
    """
    try:
        ctrl = IRASController()
        # iRAS 창 핸들을 찾고 포커스 (키 입력을 받기 위해 필수)
        if ctrl._get_handle(TITLE_MAIN, force_focus=True, use_alt=False):
            time.sleep(0.5) # 포커스 전환 안정화 대기
            ctrl.save_snapshot()
            print("   📸 [Snapshot] 스크린샷 저장 (Ctrl+S)")
            time.sleep(1) # 저장 완료 대기
        else:
            print("   ⚠️ iRAS 창을 찾을 수 없어 스크린샷을 건너뜁니다.")
    except Exception as e:
        print(f"   ⚠️ 스크린샷 시도 중 오류: {e}")


# ===========================================================
# ⚙️ [API] 제어 함수
# ===========================================================

def api_get_video_easy_setting(page: Page, ip: str):
    """[Read] 현재 설정 조회"""
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=videoEasySetting&mode=1"
    try:
        response_text = page.evaluate("""async (url) => {
            try {
                const response = await fetch(url);
                if (!response.ok) return `Error: ${response.status}`;
                return await response.text();
            } catch (e) { return `Error: ${e.message}`; }
        }""", api_url)

        if response_text and not response_text.startswith("Error"):
            return parse_api_response(response_text)
        return None
    except: return None

def api_set_video_easy_setting(page: Page, ip: str, params: dict):
    """[Write] 설정 변경"""
    query_str = "&".join([f"{k}={v}" for k, v in params.items()])
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=videoEasySetting&mode=0&{query_str}"
    
    # 디버깅용: 전송되는 파라미터 확인
    # print(f"   📡 [API Write] {params}")
    
    try:
        response_text = page.evaluate("""async (url) => {
            try {
                const response = await fetch(url, { method: 'POST' });
                if (!response.ok) return `Error: ${response.status}`;
                return await response.text();
            } catch (e) { return `Error: ${e.message}`; }
        }""", api_url)

        if "returnCode=0" in response_text:
            return True
        else:
            # 실패 시 어떤 파라미터가 문제였는지 확인하기 위해 로그 출력
            print(f"   ❌ [API Fail] 요청: {params}")
            print(f"   ❌ [API Fail] 응답: {response_text.strip()}")
            return False
    except Exception as e:
        print(f"   🔥 [API Error] {e}")
        return False

# ===========================================================
# 🧪 [Main Module] Self Adjust Mode 테스트 시나리오
# ===========================================================

def run_self_adjust_mode_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video] Self Adjust Mode (Easy Video Setting) Test")
    print("=======================================================")

    # 시작 전 iRAS 포커싱 한 번 수행
    trigger_iras_snapshot() 
    
    failed_count = 0

    # ---------------------------------------------------------
    # [Scenario 1] 프리셋 모드 순차 변경
    # ---------------------------------------------------------
    print("\n[Step 1] 프리셋 모드(Preset) 전체 순회 테스트")
    for val, name in PRESET_MODES.items():
        print(f"\n   👉 설정 변경: {name} (Value: {val})")
        
        # Preset 모드는 Day/Night Type만 보내도 됨
        target_params = {"easyDayType": val, "easyNightType": val}
        
        if api_set_video_easy_setting(page, camera_ip, target_params):
            print(f"   ⏳ 영상 확인 대기 ({WAIT_TIME}초)...")
            time.sleep(WAIT_TIME)
            
            trigger_iras_snapshot()
            
            curr_data = api_get_video_easy_setting(page, camera_ip)
            if curr_data and curr_data.get("easyDayType") == val:
                print(f"   ✅ 검증 성공: {name}")
            else:
                print(f"   ❌ 검증 실패: {name}")
                failed_count += 1
        else:
            print("   ❌ API 전송 실패")
            failed_count += 1

    # ---------------------------------------------------------
    # [Scenario 2] Custom 모드 및 세부 파라미터 테스트
    # ---------------------------------------------------------
    print("\n[Step 2] Custom 모드 세부 파라미터 전체 순회 테스트")
    print("   👉 모드 변경: Custom (사용자 설정) 진입")

    # 1. 초기 진입: 모든 필수 파라미터가 포함된 DEFAULT_CUSTOM_PARAMS 사용
    if api_set_video_easy_setting(page, camera_ip, DEFAULT_CUSTOM_PARAMS):
        time.sleep(2)
        trigger_iras_snapshot()
    else:
        return False, "Custom 진입 실패 (API 오류)"

    test_targets = [
        ("Sharpness", "easyDaySharpness"),
        ("Contrast", "easyDayContrast"),
        ("Brightness", "easyDayBrightness"),
        ("Colors", "easyDayColors")
    ]

    for param_name, api_key in test_targets:
        print(f"\n   --- [Test Target: {param_name}] ---")
        for val in PARAM_RANGES[param_name]:
            print(f"   👉 {param_name} 변경: {val}")

            # 💡 [핵심 수정] 완전한 파라미터 구성을 위해 기본값에서 복사 후 수정
            payload = DEFAULT_CUSTOM_PARAMS.copy()
            payload[api_key] = val
            
            if api_set_video_easy_setting(page, camera_ip, payload):
                print(f"   ⏳ 영상 확인 대기 ({WAIT_TIME}초)...")
                time.sleep(WAIT_TIME)
                
                trigger_iras_snapshot()

                curr = api_get_video_easy_setting(page, camera_ip)
                if curr and curr.get(api_key) == val:
                    print(f"   ✅ {param_name}={val} 적용 확인")
                else:
                    actual = curr.get(api_key) if curr else "None"
                    print(f"   ❌ 실패: 기대({val}) != 실제({actual})")
                    failed_count += 1
            else:
                print("   ❌ API 전송 실패")
                failed_count += 1

    # ---------------------------------------------------------
    # [Scenario 3] 복구
    # ---------------------------------------------------------
    print("\n[Step 3] 설정 초기화 (Natural 모드로 복구)")
    if api_set_video_easy_setting(page, camera_ip, {"easyDayType": "1", "easyNightType": "1"}):
        time.sleep(2)
        trigger_iras_snapshot()
        print("   ✅ 설정 복구 완료")
    else:
        print("   ⚠️ 설정 복구 실패")

    if failed_count == 0:
        return True, "테스트 성공"
    else:
        return False, f"실패 항목 {failed_count}건"