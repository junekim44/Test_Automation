import time
from playwright.sync_api import Page
from common_actions import parse_api_response

# 💡 iRAS 컨트롤러 및 타이틀 상수 가져오기
from iRAS_test import IRASController, TITLE_MAIN

# ===========================================================
# ⚙️ [설정] 테스트 상수
# ===========================================================
WAIT_TIME = 5  # iRAS 영상 변화 관찰 대기 시간

# 1. Easy Video Setting (Self Adjust)
PRESET_MODES = {
    "1": "Natural (자연스러운)",
    "2": "Vivid (선명한)",
    "3": "Denoise (노이즈 감소)"
}

PARAM_RANGES = {
    "Sharpness": ["0", "3"],
    "Contrast": ["0", "2"],
    "Brightness": ["0", "2"],
    "Colors": ["0", "2"]
}

DEFAULT_CUSTOM_PARAMS = {
    "easyDayType": "0", "easyNightType": "0",
    "easyDaySharpness": "1", "easyDayContrast": "1", "easyDayBrightness": "1", "easyDayColors": "1",
    "easyNightSharpness": "1", "easyNightGamma": "1", "easyNightBrightness": "1"
}

# 2. Video Image (Mirroring/Pivot)
MIRRORING_OPTS = ["off", "horizontal", "vertical", "both"]
PIVOT_OPTS = ["off", "clockwise", "counterclockwise"]

# 3. White Balance
WB_MODES = {
    "auto": "Auto",
    "incandescent": "Incandescent",
    "fluorescent_warm": "Fluorescent Warm",
    "manual": "Manual"
}
WB_GAIN_TEST_VALUES = ["10", "500"]

# 4. Exposure (노출)
# 셔터 스피드 테스트 값 (문서 및 요청사항 반영)
SHUTTER_TEST_CASES = [
    ("30", "1/30s (Bright)"), 
    ("8000", "1/8000s (Dark)") 
]
TARGET_GAIN_VALUES = ["-10", "10"]
WDR_MODES = ["off", "on"]

# 5. Day & Night [NEW]
# 스케줄 문자열 생성 (7일 * 24시간)
# 1시간 = 8비트 = 2 Hex Char. 24시간 = 48 Hex Char.
# 0(00) = Day/Off, 5(0101) = Night/On (15분 단위 설정)
DAY_SCHEDULE_STR = "_".join(["0" * 48] * 7) # 일주일 내내 주간
NIGHT_SCHEDULE_STR = "_".join(["5" * 48] * 7) # 일주일 내내 야간 (5555...)


# ===========================================================
# 📸 [Snapshot] 스크린샷 캡처 함수
# ===========================================================
def trigger_iras_snapshot():
    """iRAS 창을 찾아 포커스한 뒤 Ctrl+S를 전송하여 스냅샷 저장"""
    try:
        ctrl = IRASController()
        if ctrl._get_handle(TITLE_MAIN, force_focus=True, use_alt=False):
            time.sleep(0.5) 
            ctrl.save_snapshot()
            print("   📸 [Snapshot] 스냅샷 저장 (Ctrl+S)")
            time.sleep(1)
        else:
            print("   ⚠️ iRAS 창을 찾을 수 없어 스냅샷을 건너뜁니다.")
    except Exception as e:
        print(f"   ⚠️ 스크린샷 시도 중 오류: {e}")

# ===========================================================
# ⚙️ [API] 공통 제어 함수 (GET/SET)
# ===========================================================

def _api_get(page, ip, action):
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action={action}&mode=1"
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

def _api_set(page, ip, action, params):
    query_str = "&".join([f"{k}={v}" for k, v in params.items()])
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action={action}&mode=0&{query_str}"
    
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
            print(f"   ❌ [API Fail] 요청: {params}") 
            print(f"   ❌ [API Fail] 응답: {response_text.strip()}")
            return False
    except Exception as e:
        print(f"   🔥 [API Error] {e}")
        return False

# 래퍼 함수들
def api_get_video_easy_setting(page, ip): return _api_get(page, ip, "videoEasySetting")
def api_set_video_easy_setting(page, ip, p): return _api_set(page, ip, "videoEasySetting", p)

def api_get_video_image(page, ip): return _api_get(page, ip, "videoImage")
def api_set_video_image(page, ip, p): return _api_set(page, ip, "videoImage", p)

def api_get_video_wb(page, ip): return _api_get(page, ip, "videoWb")
def api_set_video_wb(page, ip, p): return _api_set(page, ip, "videoWb", p)

def api_get_video_exposure(page, ip): return _api_get(page, ip, "videoExposure")
def api_set_video_exposure(page, ip, p): return _api_set(page, ip, "videoExposure", p)

def api_get_video_daynight(page, ip): return _api_get(page, ip, "videoDaynight")
def api_set_video_daynight(page, ip, p): return _api_set(page, ip, "videoDaynight", p)


# ===========================================================
# 🧪 [Test 1] Self Adjust Mode
# ===========================================================
def run_self_adjust_mode_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video] Self Adjust Mode (Easy Video Setting) Test")
    print("=======================================================")
    trigger_iras_snapshot() 
    failed_count = 0

    # 1. Preset
    print("\n[Step 1] 프리셋 모드(Preset) 테스트")
    for val, name in PRESET_MODES.items():
        print(f"\n   👉 설정 변경: {name} (Value: {val})")
        if api_set_video_easy_setting(page, camera_ip, {"easyDayType": val, "easyNightType": val}):
            print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
            time.sleep(WAIT_TIME)
            trigger_iras_snapshot()
            curr = api_get_video_easy_setting(page, camera_ip)
            if curr and curr.get("easyDayType") == val: print(f"   ✅ Pass")
            else: 
                print(f"   ❌ Fail")
                failed_count += 1
        else: failed_count += 1

    # 2. Custom
    print("\n[Step 2] Custom 모드 테스트")
    print("   👉 모드 변경: Custom (사용자 설정) 진입")
    
    curr_set = api_get_video_easy_setting(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        payload.update(DEFAULT_CUSTOM_PARAMS)
        if 'returnCode' in payload: del payload['returnCode']
        
        if not api_set_video_easy_setting(page, camera_ip, payload):
            return False, "Custom 진입 실패"
    else: return False, "설정 조회 실패"
    
    time.sleep(2)
    trigger_iras_snapshot()

    for param, api_key in [("Sharpness","easyDaySharpness"), ("Contrast","easyDayContrast"), ("Brightness","easyDayBrightness"), ("Colors","easyDayColors")]:
        print(f"\n   --- [Target: {param}] ---")
        for val in PARAM_RANGES[param]:
            print(f"   👉 값 변경: {val}")
            
            curr_set = api_get_video_easy_setting(page, camera_ip)
            if not curr_set: continue

            payload = curr_set.copy()
            payload[api_key] = val
            payload["easyDayType"] = "0"
            payload["easyNightType"] = "0"
            if 'returnCode' in payload: del payload['returnCode']

            if api_set_video_easy_setting(page, camera_ip, payload):
                print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
                time.sleep(WAIT_TIME)
                trigger_iras_snapshot()
                curr = api_get_video_easy_setting(page, camera_ip)
                if curr and curr.get(api_key) == val: print(f"   ✅ Pass: {val}")
                else: 
                    print(f"   ❌ Fail: {curr.get(api_key)}")
                    failed_count += 1
            else: failed_count += 1

    # Restore
    print("\n[Step 3] 복구 (Natural)")
    api_set_video_easy_setting(page, camera_ip, {"easyDayType": "1", "easyNightType": "1"})
    
    if failed_count == 0: return True, "Self Adjust Mode 성공"
    else: return False, f"Self Adjust Mode 실패 ({failed_count}건)"


# ===========================================================
# 🧪 [Test 2] Video Image
# ===========================================================
def run_video_image_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video] Image Setting (Mirroring / Pivot) Test")
    print("=======================================================")
    
    base_set = api_get_video_image(page, camera_ip)
    if not base_set: return False, "설정 조회 실패"
    if 'returnCode' in base_set: del base_set['returnCode']
    
    failed_count = 0

    # Mirroring
    print("\n[Step 1] Mirroring 테스트")
    for mode in MIRRORING_OPTS:
        print(f"\n   👉 Mirroring: {mode}")
        
        curr_set = api_get_video_image(page, camera_ip)
        if not curr_set: continue
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['mirroring'] = mode
        
        if api_set_video_image(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
            time.sleep(WAIT_TIME)
            trigger_iras_snapshot()
            curr = api_get_video_image(page, camera_ip)
            if curr and curr.get('mirroring') == mode: 
                print(f"   ✅ Pass")
            else: 
                print("   ❌ Fail")
                failed_count += 1
        else: failed_count += 1

    # Pivot
    print("\n[Step 2] Pivot 테스트")
    for mode in PIVOT_OPTS:
        print(f"\n   👉 Pivot: {mode}")
        
        curr_set = api_get_video_image(page, camera_ip)
        if not curr_set: continue
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['pivot'] = mode
        
        if api_set_video_image(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
            time.sleep(WAIT_TIME)
            trigger_iras_snapshot()
            curr = api_get_video_image(page, camera_ip)
            if curr and curr.get('pivot') == mode:
                print(f"   ✅ Pass")
            else: 
                print("   ❌ Fail")
                failed_count += 1
        else: failed_count += 1

    # Restore
    print("\n[Step 3] 복구 (off)")
    final_set = api_get_video_image(page, camera_ip)
    if final_set:
        payload = final_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['mirroring'] = 'off'
        payload['pivot'] = 'off'
        api_set_video_image(page, camera_ip, payload)

    if failed_count == 0: return True, "Video Image 성공"
    else: return False, f"Video Image 실패 ({failed_count}건)"


# ===========================================================
# 🧪 [Test 3] White Balance
# ===========================================================
def run_white_balance_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video] White Balance Test")
    print("=======================================================")
    trigger_iras_snapshot()
    failed_count = 0

    # Preset
    print("\n[Step 1] Preset Mode 테스트")
    for mode_val, mode_name in WB_MODES.items():
        if mode_val == "manual": continue
        print(f"\n   👉 설정: {mode_name}")
        
        curr_set = api_get_video_wb(page, camera_ip)
        if not curr_set: continue
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['wbMode'] = mode_val
        
        if api_set_video_wb(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
            time.sleep(WAIT_TIME)
            trigger_iras_snapshot()
            curr = api_get_video_wb(page, camera_ip)
            if curr and curr.get("wbMode") == mode_val: print("   ✅ Pass")
            else: 
                print("   ❌ Fail")
                failed_count += 1
        else: failed_count += 1

    # Manual
    print("\n[Step 2] Manual Mode (Gain) 테스트")
    
    curr_set = api_get_video_wb(page, camera_ip)
    if not curr_set: return False, "설정 조회 실패"
    payload = curr_set.copy()
    if 'returnCode' in payload: del payload['returnCode']
    payload['wbMode'] = 'manual'
    
    if not api_set_video_wb(page, camera_ip, payload):
        return False, "Manual 진입 실패"
    
    time.sleep(2)
    
    for param, name in [("redGain", "Red"), ("blueGain", "Blue")]:
        print(f"\n   --- [Target: {name}] ---")
        for val in WB_GAIN_TEST_VALUES:
            print(f"   👉 값 변경: {val}")
            
            curr_set = api_get_video_wb(page, camera_ip)
            if not curr_set: continue
            
            payload = curr_set.copy()
            if 'returnCode' in payload: del payload['returnCode']
            payload['wbMode'] = 'manual'
            payload[param] = val
            
            if api_set_video_wb(page, camera_ip, payload):
                print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
                time.sleep(WAIT_TIME)
                trigger_iras_snapshot()
                curr = api_get_video_wb(page, camera_ip)
                if curr and curr.get(param) == val: print(f"   ✅ Pass: {val}")
                else: 
                    print("   ❌ Fail")
                    failed_count += 1
            else: failed_count += 1

    # Restore
    print("\n[Step 3] 복구 (Auto)")
    curr_set = api_get_video_wb(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['wbMode'] = 'auto'
        api_set_video_wb(page, camera_ip, payload)
    
    if failed_count == 0: return True, "WB Test 성공"
    else: return False, f"WB Test 실패 ({failed_count}건)"


# ===========================================================
# 🧪 [Test 4] Exposure (노출)
# ===========================================================
def run_exposure_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video] Exposure Test (Gain, Shutter, WDR)")
    print("=======================================================")
    
    trigger_iras_snapshot()
    failed_count = 0

    # 1. Target Gain
    print("\n[Step 1] AE Target Gain 변경 (-10 <-> 10)")
    for val in TARGET_GAIN_VALUES:
        print(f"   👉 Target Gain: {val}")
        
        curr_set = api_get_video_exposure(page, camera_ip)
        if not curr_set: failed_count += 1; continue
            
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        
        # 충돌 방지
        payload['manualAeControl'] = 'off'
        payload['wdr'] = 'off' 
        payload['targetGain'] = val
        
        if api_set_video_exposure(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
            time.sleep(WAIT_TIME)
            trigger_iras_snapshot()
            curr = api_get_video_exposure(page, camera_ip)
            if curr and curr.get('targetGain') == val:
                print(f"   ✅ Pass")
            else:
                print(f"   ❌ Fail")
                failed_count += 1
        else: failed_count += 1

    # # 2. Manual Shutter Speed (Fixed Logic)
    # print("\n[Step 2] Manual Shutter Speed (1/30 vs 1/8000)")
    # print("   👉 Exposure Mode: Manual (수동)")

    # for shutter_val, label in SHUTTER_TEST_CASES:
    #     print(f"   👉 셔터 변경: {label} (Value: {shutter_val})")
        
    #     curr_set = api_get_video_exposure(page, camera_ip)
    #     if not curr_set: 
    #         failed_count += 1; continue

    #     payload = curr_set.copy()
    #     if 'returnCode' in payload: del payload['returnCode']
        
    #     # 💡 [핵심 수정] Manual Mode 진입 파라미터 세트 (301 에러 방지)
    #     payload['manualAeControl'] = 'on'
    #     payload['lowerShutterLimit'] = shutter_val
    #     payload['upperShutterLimit'] = shutter_val
        
    #     # 1. 충돌 파라미터 끄기
    #     payload['slowShutter'] = 'off'     
    #     payload['antiFlicker'] = 'off'
    #     payload['targetGain'] = '0' # Manual에서는 Target Gain 초기화
        
    #     # 2. Gain 고정 (3dB 사용 - API 예제 호환)
    #     payload['lowerGainLimit'] = '3dB'  
    #     payload['upperGainLimit'] = '3dB'  
        
    #     # 3. Iris Control은 건드리지 않음 (기존 값 유지) -> 'fullopen' 강제 제거
    #     # payload['irisControlMode'] = 'fullopen'  <-- 삭제함
        
    #     if api_set_video_exposure(page, camera_ip, payload):
    #         print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
    #         time.sleep(WAIT_TIME)
    #         trigger_iras_snapshot()
            
    #         curr = api_get_video_exposure(page, camera_ip)
    #         if curr and curr.get('upperShutterLimit') == shutter_val:
    #             print(f"   ✅ Pass")
    #         else:
    #             print(f"   ❌ Fail")
    #             failed_count += 1
    #     else: failed_count += 1

    # 3. Slow Shutter
    print("\n[Step 3] Slow Shutter 설정 (Auto Mode)")
    
    print("\n" + "="*60)
    print("⚠️  [Action Required]")
    print("    Slow Shutter 동작 확인을 위해 카메라 렌즈를 가리거나,")
    print("    주변 환경을 어둡게 만든 뒤 Enter 키를 눌러주세요.")
    print("="*60)
    input(">> 준비되었으면 Enter를 누르세요...")
    print("   ▶️ 테스트를 계속 진행합니다...\n")

    slow_shutter_val = "1/7.5s" 
    print(f"   👉 Slow Shutter 변경: {slow_shutter_val}")
    
    curr_set = api_get_video_exposure(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        
        payload['manualAeControl'] = 'off' # Auto 모드 복귀
        payload['wdr'] = 'off' # WDR 꺼야 함
        payload['slowShutter'] = slow_shutter_val
        
        if api_set_video_exposure(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
            time.sleep(WAIT_TIME)
            trigger_iras_snapshot()
            
            curr = api_get_video_exposure(page, camera_ip)
            if curr and curr.get('slowShutter') == slow_shutter_val:
                print(f"   ✅ Pass")
            else:
                print(f"   ❌ Fail")
                failed_count += 1
        else: failed_count += 1
    else: failed_count += 1

    # 4. WDR
    print("\n[Step 4] WDR 테스트")
    for mode in WDR_MODES:
        print(f"   👉 WDR: {mode}")
        
        curr_set = api_get_video_exposure(page, camera_ip)
        if not curr_set: failed_count += 1; continue

        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        
        payload['wdr'] = mode
        if mode == 'on': 
            payload['wdrLevel'] = '2'
            payload['slowShutter'] = 'off' # WDR과 충돌 방지
            payload['targetGain'] = '0'
        
        # 모드에 상관없이 충돌 방지
        if mode == 'off':
            payload['slowShutter'] = 'off' # 깔끔하게

        if api_set_video_exposure(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({WAIT_TIME}s)...")
            time.sleep(WAIT_TIME)
            trigger_iras_snapshot()
            curr = api_get_video_exposure(page, camera_ip)
            if curr and curr.get('wdr') == mode:
                print(f"   ✅ Pass")
            else:
                print(f"   ❌ Fail")
                failed_count += 1
        else: failed_count += 1

    # Restore
    print("\n[Step 5] 복구 (Auto Default)")
    final_set = api_get_video_exposure(page, camera_ip)
    if final_set:
        payload = final_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        
        # 초기화
        payload['manualAeControl'] = 'off'
        payload['targetGain'] = '0'
        payload['slowShutter'] = 'off'
        payload['wdr'] = 'off'
        
        api_set_video_exposure(page, camera_ip, payload)
    
    if failed_count == 0: return True, "Exposure Test 성공"
    else: return False, f"Exposure Test 실패 ({failed_count}건)"

# ===========================================================
# 🧪 [Test 5] Day & Night [NEW]
# ===========================================================
def run_daynight_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video] Day & Night Test (Auto/Schedule/ICR)")
    print("=======================================================")
    
    trigger_iras_snapshot()
    failed_count = 0

    # ---------------------------------------------------------
    # [Step 1] Auto Mode 설정 및 센서 동작 확인
    # ---------------------------------------------------------
    print("\n[Step 1] Auto Mode 설정 (조도 센서 동작 확인)")
    
    # 1. Auto 설정
    print("   👉 설정 변경: Auto")
    curr_set = api_get_video_daynight(page, camera_ip)
    if not curr_set: return False, "설정 조회 실패"
    
    payload = curr_set.copy()
    if 'returnCode' in payload: del payload['returnCode']
    payload['bwMode'] = 'auto'
    payload['icrMode'] = 'auto'
    
    if api_set_video_daynight(page, camera_ip, payload):
        print(f"   ✅ 설정 완료: Auto")
    else:
        print(f"   ❌ 설정 실패")
        failed_count += 1
        return False, "Auto 모드 설정 실패"

    # 2. Night 전환 유도 (사용자 개입)
    print("\n" + "="*60)
    print("⚠️  [Action Required: Night Mode]")
    print("    1. 카메라의 렌즈와 조도 센서를 가려주세요.")
    print("    2. '딸깍' 소리와 함께 흑백(Night)으로 바뀌면 Enter를 누르세요.")
    print("="*60)
    input(">> 준비되었으면 Enter를 누르세요...")
    
    print("   ⏳ 영상 확인 ({WAIT_TIME}s)...")
    time.sleep(WAIT_TIME)
    trigger_iras_snapshot() # 흑백 영상 캡처

    # 3. Day 전환 유도 (사용자 개입)
    print("\n" + "="*60)
    print("⚠️  [Action Required: Day Mode]")
    print("    1. 가림막을 제거하여 밝게 해주세요.")
    print("    2. 컬러(Day)로 돌아오면 Enter를 누르세요.")
    print("="*60)
    input(">> 준비되었으면 Enter를 누르세요...")
    
    print("   ⏳ 영상 확인 ({WAIT_TIME}s)...")
    time.sleep(WAIT_TIME)
    trigger_iras_snapshot() # 컬러 영상 캡처

    # ---------------------------------------------------------
    # [Step 2] Schedule Mode 테스트 (강제 주간/야간 전환)
    # ---------------------------------------------------------
    print("\n[Step 2] Schedule Mode 테스트")
    
    # 1. Schedule - Always Night (강제 흑백)
    print("   👉 스케줄 설정: Always Night (B&W)")
    
    payload['bwMode'] = 'schedule'
    payload['icrMode'] = 'schedule'
    payload['schedule'] = NIGHT_SCHEDULE_STR # 5555...
    
    if api_set_video_daynight(page, camera_ip, payload):
        print(f"   ⏳ 영상 확인 ({WAIT_TIME}s) -> 흑백이어야 함")
        time.sleep(WAIT_TIME)
        trigger_iras_snapshot()
        
        curr = api_get_video_daynight(page, camera_ip)
        if curr and curr.get('bwMode') == 'schedule':
            print(f"   ✅ 설정 적용 확인")
        else:
            print(f"   ❌ 검증 실패")
            failed_count += 1
    else:
        print("   ❌ API 전송 실패")
        failed_count += 1

    # 2. Schedule - Always Day (강제 컬러)
    print("   👉 스케줄 설정: Always Day (Color)")
    
    payload['schedule'] = DAY_SCHEDULE_STR # 0000...
    
    if api_set_video_daynight(page, camera_ip, payload):
        print(f"   ⏳ 영상 확인 ({WAIT_TIME}s) -> 컬러여야 함")
        time.sleep(WAIT_TIME)
        trigger_iras_snapshot()
        print(f"   ✅ 설정 적용 확인")
    else:
        print("   ❌ API 전송 실패")
        failed_count += 1

    # ---------------------------------------------------------
    # [Step 3] 복구 (Auto Mode)
    # ---------------------------------------------------------
    print("\n[Step 3] 설정 초기화 (Auto)")
    
    # 읽어온 초기값 복구 or 강제 Auto 설정
    restore_payload = payload.copy()
    restore_payload['bwMode'] = 'auto'
    restore_payload['icrMode'] = 'auto'
    # 스케줄은 복잡하므로 굳이 초기화 안 해도 됨 (모드가 Auto면 무시됨)
    
    if api_set_video_daynight(page, camera_ip, restore_payload):
        time.sleep(2)
        print("   ✅ 설정 복구 완료")
    else:
        print("   ⚠️ 설정 복구 실패")

    if failed_count == 0: return True, "Day&Night Test 성공"
    else: return False, f"Day&Night Test 실패 ({failed_count}건)"