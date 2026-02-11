import time
import os
import re
from playwright.sync_api import Page
from common_actions import parse_api_response

# iRAS 컨트롤러 가져오기 (OSD 텍스트 읽기용)
from iRAS_test import IRASController

# 비디오 테스트 설정값 가져오기
from config import (
    IRAS_TITLES,
    VIDEO_WAIT_TIME,
    VIDEO_PRESET_MODES,
    VIDEO_PARAM_RANGES,
    VIDEO_DEFAULT_CUSTOM_PARAMS,
    VIDEO_MIRRORING_OPTS,
    VIDEO_PIVOT_OPTS,
    VIDEO_WB_MODES,
    VIDEO_WB_GAIN_TEST_VALUES,
    VIDEO_SHUTTER_TEST_CASES,
    VIDEO_TARGET_GAIN_VALUES,
    VIDEO_WDR_MODES,
    VIDEO_DAY_SCHEDULE_STR,
    VIDEO_NIGHT_SCHEDULE_STR,
    VIDEO_EIS_MODES,
    VIDEO_STREAMING_TARGET_STREAM,
    VIDEO_STREAMING_CODECS,
    VIDEO_STREAMING_RESOLUTIONS,
    VIDEO_STREAMING_IPS_VALUES,
    VIDEO_STREAMING_BITRATE_MODES,
    VIDEO_STREAMING_BASE_SETTINGS,
    VIDEO_MAT_SENSITIVITY,
    VIDEO_MAT_INACTIVITY_PERIOD,
    VIDEO_MAT_TARGET_FRAMERATE,
    VIDEO_MAT_TARGET_IPS,
    VIDEO_MAT_WAIT_TIME,
    VIDEO_PRIVACY_ZONE_COUNT,
    VIDEO_PRIVACY_GRID_COLS,
    VIDEO_PRIVACY_GRID_ROWS,
    VIDEO_PRIVACY_ZONE_NAME_PREFIX,
    VIDEO_OSD_TEXT_STRING,
    VIDEO_OSD_TEXT_SIZES,
    VIDEO_OSD_TEXT_COLORS,
    VIDEO_OSD_TEXT_TRANSPARENCIES,
    VIDEO_OSD_TEXT_POSITION,
    VIDEO_OSD_DATETIME_DATE_FORMATS,
    VIDEO_OSD_DATETIME_TIME_FORMATS,
    VIDEO_OSD_DATETIME_TEXT_SIZE,
    VIDEO_OSD_DATETIME_TEXT_COLOR,
    VIDEO_OSD_DATETIME_TEXT_TRANSPARENCY,
    VIDEO_OSD_DATETIME_POSITION,
)

# ===========================================================
# 🖨️ [출력] 표준 출력 함수
# ===========================================================
def print_step(step_num: int, total_steps: int, msg: str):
    """단계 표시"""
    print(f"\n[{step_num}/{total_steps}] {msg}")

def print_action(msg: str):
    """작업 진행 표시"""
    print(f"   → {msg}")

def print_success(msg: str = None):
    """성공 표시"""
    if msg:
        print(f"   ✅ {msg}")
    else:
        print(f"   ✅ 완료")

def print_warning(msg: str):
    """경고 표시"""
    print(f"   ⚠️ {msg}")

def print_error(msg: str):
    """에러 표시"""
    print(f"   ❌ {msg}")

# ===========================================================
# 📸 [Snapshot] API를 통한 스냅샷 캡처 함수
# ===========================================================
def trigger_iras_snapshot(page: Page, camera_ip: str, file_name=None):
    """videoSnapshot API를 사용하여 카메라에서 직접 JPEG 이미지를 받아서 저장"""
    try:
        api_url = f"http://{camera_ip}/cgi-bin/webSetup.cgi?action=videoSnapshot&mode=1&streamIndex=1"
        
        image_base64 = page.evaluate("""async (url) => {
            try {
                const response = await fetch(url);
                if (!response.ok) return null;
                const blob = await response.blob();
                
                return new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.readAsDataURL(blob);
                });
            } catch (e) { 
                return null; 
            }
        }""", api_url)
        
        if not image_base64:
            return
        
        import base64
        image_data = base64.b64decode(image_base64)
        
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        save_folder = os.path.join(desktop_path, "TestCapture")
        
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)

        if file_name is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            file_name = f"snapshot_{timestamp}.jpg"
        
        if not file_name.lower().endswith(('.jpg', '.jpeg')):
            file_name = file_name.rsplit('.', 1)[0] + '.jpg'
        
        full_path = os.path.join(save_folder, file_name)

        with open(full_path, 'wb') as f:
            f.write(image_data)
            
    except Exception:
        pass

# ===========================================================
# ⚙️ [API] 공통 제어 함수 (GET/SET)
# ===========================================================

def _api_get(page, ip, action, channel=None):
    """API GET 요청"""
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action={action}&mode=1"
    if channel is not None:
        api_url += f"&channel={channel}"
    
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
        else:
            return None
    except Exception:
        return None

def _api_set(page, ip, action, params, channel=None):
    """API SET 요청"""
    query_str = "&".join([f"{k}={v}" for k, v in params.items()])
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action={action}&mode=0"
    if channel is not None:
        api_url += f"&channel={channel}"
    api_url += f"&{query_str}"
    
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
            return False
    except Exception:
        return False

# API 래퍼 함수들
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

def api_get_video_misc(page, ip): return _api_get(page, ip, "videoMisc")
def api_set_video_misc(page, ip, p): return _api_set(page, ip, "videoMisc", p)

def api_get_video_streaming(page, ip): return _api_get(page, ip, "videoStreaming")
def api_set_video_streaming(page, ip, p): return _api_set(page, ip, "videoStreaming", p)

def api_get_video_mat(page, ip): return _api_get(page, ip, "videoMat")
def api_set_video_mat(page, ip, p): return _api_set(page, ip, "videoMat", p)

def api_get_video_privacy(page, ip, channel=1): 
    return _api_get(page, ip, "videoPrivacy", channel=channel)

def api_set_video_privacy(page, ip, p, channel=1): 
    return _api_set(page, ip, "videoPrivacy", p, channel=channel)

def api_get_video_osd_text(page, ip): return _api_get(page, ip, "videoOsdText")
def api_set_video_osd_text(page, ip, p): return _api_set(page, ip, "videoOsdText", p)

def api_get_video_osd_datetime(page, ip): return _api_get(page, ip, "videoOsdDateTime")
def api_set_video_osd_datetime(page, ip, p): return _api_set(page, ip, "videoOsdDateTime", p)

# ===========================================================
# 🛠️ [Helper] iRAS OSD 텍스트 추출 (Right Click + C)
# ===========================================================
def get_iras_clipboard_text():
    """
    iRAS 화면에서 우클릭 후 'c'를 눌러 화면 정보(Debug Info)를 클립보드로 복사하고,
    텍스트를 리턴합니다. (iRAS_test.py의 _copy_debug_info 메서드 사용)
    """
    try:
        import win32clipboard
        ctrl = IRASController()
        main_hwnd = ctrl._get_handle(IRAS_TITLES["main"], force_focus=True, use_alt=False)
        if not main_hwnd:
            return ""
        
        ctrl._clear_clipboard()
        if not ctrl._copy_debug_info(main_hwnd, None):  # None이면 기본 offset 사용
            return ""
        
        # 클립보드에서 텍스트 읽기
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
                    content = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT).decode('utf-8', errors='ignore')
                else:
                    win32clipboard.CloseClipboard()
                    return ""
            except Exception as e:
                win32clipboard.CloseClipboard()
                return ""
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
            
            return content if 'content' in locals() else ""
        except Exception as e:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return ""
    except Exception as e:
        print(f"   ⚠️ 화면 정보 복사 실패: {e}")
        return ""

def parse_stream_info(text):
    """
    클립보드 텍스트에서 해상도, 코덱, FPS, Mbps 파싱
    Sample: 
      [W]{2:1} Fps 30.0 / Ips 30.0 / Mbps 0.59, 0.44
      Res 3520*3520 > 1587*877 ...
      Dec 255/00/390, Thr 2 H265 ...
    """
    info = {}
    
    # 1. Mbps (첫 번째 값 추출) -> "Mbps 0.59, 0.44"
    match_mbps = re.search(r'Mbps\s+([\d\.]+)', text, re.IGNORECASE)
    if match_mbps:
        info['mbps'] = float(match_mbps.group(1))
    
    # 2. IPS (FPS) -> "Ips 30.0"
    match_ips = re.search(r'Ips\s+([\d\.]+)', text, re.IGNORECASE)
    if match_ips:
        info['ips'] = float(match_ips.group(1))

    # 3. Resolution -> "Res 3520*3520" (W*H 형식)
    match_res = re.search(r'Res\s+(\d+)\*(\d+)', text, re.IGNORECASE)
    if match_res:
        info['res_w'] = match_res.group(1)
        info['res_h'] = match_res.group(2)
        info['res_str'] = f"{match_res.group(1)}x{match_res.group(2)}"

    # 4. Codec -> "H264" or "H265" (단순 포함 여부 확인)
    if "H264" in text.upper():
        info['codec'] = "h264"
    elif "H265" in text.upper():
        info['codec'] = "h265"
    elif "JPEG" in text.upper() or "MJPEG" in text.upper():
        info['codec'] = "mjpeg"
        
    return info

# ===========================================================
# 🧪 [Test 1] Self Adjust Mode
# ===========================================================
def run_self_adjust_mode_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 1/10] Self Adjust Mode")
    print("=======================================================")
    trigger_iras_snapshot(page, camera_ip, "기본값") 
    failed_count = 0

    print_step(1, 2, "프리셋 모드 테스트")
    preset_names = {
        "0": "Custom",
        "1": "Natural", 
        "2": "Vivid",
        "3": "Denoise"
    }
    
    for val, name in VIDEO_PRESET_MODES.items():
        preset_name = preset_names.get(val, name)
        print_action(f"모드 변경: {name}")
        if api_set_video_easy_setting(page, camera_ip, {"easyDayType": val, "easyNightType": val}):
            time.sleep(VIDEO_WAIT_TIME)
            trigger_iras_snapshot(page, camera_ip, f"{preset_name}.png")
            curr = api_get_video_easy_setting(page, camera_ip)
            if curr and curr.get("easyDayType") == val:
                print_success(f"{name} 검증 완료")
            else: 
                print_error(f"{name} 검증 실패")
                failed_count += 1
        else:
            failed_count += 1
    
    print_action("Natural 모드로 복구 중...")
    api_set_video_easy_setting(page, camera_ip, {"easyDayType": "1", "easyNightType": "1"})
    time.sleep(2)
    print_success("복구 완료")

    print_step(2, 2, "Custom 모드 테스트")
    print_action("Custom 모드 진입 중...")
    
    curr_set = api_get_video_easy_setting(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        payload.update(VIDEO_DEFAULT_CUSTOM_PARAMS)
        if 'returnCode' in payload: del payload['returnCode']
        
        if not api_set_video_easy_setting(page, camera_ip, payload):
            return False, "Custom 진입 실패"
    else:
        return False, "설정 조회 실패"
    
    time.sleep(2)
    trigger_iras_snapshot(page, camera_ip, "Custom_진입.png")
    print_success("Custom 모드 진입 완료")

    for param, api_key in [("Sharpness","easyDaySharpness"), ("Contrast","easyDayContrast"), 
                           ("Brightness","easyDayBrightness"), ("Colors","easyDayColors")]:
        print(f"\n   [{param}]")
        for val in VIDEO_PARAM_RANGES[param]:
            curr_set = api_get_video_easy_setting(page, camera_ip)
            if not curr_set: continue

            payload = curr_set.copy()
            payload[api_key] = val
            payload["easyDayType"] = "0"
            payload["easyNightType"] = "0"
            if 'returnCode' in payload: del payload['returnCode']

            if api_set_video_easy_setting(page, camera_ip, payload):
                time.sleep(VIDEO_WAIT_TIME)
                trigger_iras_snapshot(page, camera_ip, f"Custom_{param}_{val}.png")
                curr = api_get_video_easy_setting(page, camera_ip)
                if curr and curr.get(api_key) == val: 
                    print(f"      {val}: ✅")
                else: 
                    print(f"      {val}: ❌")
                    failed_count += 1
            else: 
                failed_count += 1
    
    print_action("Natural 모드로 복구 중...")
    api_set_video_easy_setting(page, camera_ip, {"easyDayType": "1", "easyNightType": "1"})
    time.sleep(2)
    print_success("복구 완료")
    
    if failed_count == 0:
        print("\n✅ Self Adjust Mode 테스트 완료")
        return True, "Self Adjust Mode 성공"
    else:
        print(f"\n❌ Self Adjust Mode 테스트 실패 ({failed_count}건)")
        return False, f"Self Adjust Mode 실패 ({failed_count}건)"


# ===========================================================
# 🧪 [Test 2] Video Image
# ===========================================================
def run_video_image_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 2/10] Image Setting")
    print("=======================================================")
    
    base_set = api_get_video_image(page, camera_ip)
    if not base_set: return False, "설정 조회 실패"
    if 'returnCode' in base_set: del base_set['returnCode']
    
    failed_count = 0

    print_step(1, 2, "Mirroring 테스트")
    for mode in VIDEO_MIRRORING_OPTS:
        print(f"\n   👉 Mirroring: {mode}")
        
        curr_set = api_get_video_image(page, camera_ip)
        if not curr_set: continue
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['mirroring'] = mode
        
        if api_set_video_image(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            trigger_iras_snapshot(page, camera_ip, f"Mirroring_{mode}.png")
            curr = api_get_video_image(page, camera_ip)
            if curr and curr.get('mirroring') == mode: 
                print(f"   ✅ Pass")
            else: 
                print("   ❌ Fail")
                failed_count += 1
        else: failed_count += 1
    
    # Step 1 복구: Mirroring을 off로
    print("\n   🔄 Step 1 복구: Mirroring → off")
    curr_set = api_get_video_image(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['mirroring'] = 'off'
        api_set_video_image(page, camera_ip, payload)
        time.sleep(2)
    
    print_step(2, 2, "Pivot 테스트")
    for mode in VIDEO_PIVOT_OPTS:
        print(f"\n   👉 Pivot: {mode}")
        
        curr_set = api_get_video_image(page, camera_ip)
        if not curr_set: continue
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['pivot'] = mode
        
        if api_set_video_image(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            trigger_iras_snapshot(page, camera_ip, f"Pivot_{mode}.png")
            curr = api_get_video_image(page, camera_ip)
            if curr and curr.get('pivot') == mode:
                print(f"   ✅ Pass")
            else: 
                print("   ❌ Fail")
                failed_count += 1
        else: failed_count += 1
    
    # Step 2 복구: Pivot을 off로
    print("\n   🔄 Step 2 복구: Pivot → off")
    curr_set = api_get_video_image(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['pivot'] = 'off'
        api_set_video_image(page, camera_ip, payload)
        time.sleep(2)

    if failed_count == 0: return True, "Video Image 성공"
    else: return False, f"Video Image 실패 ({failed_count}건)"


# ===========================================================
# 🧪 [Test 3] White Balance
# ===========================================================
def run_white_balance_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 3/10] White Balance")
    print("=======================================================")
    trigger_iras_snapshot(page, camera_ip, "WB_기본값.png")
    failed_count = 0

    print_step(1, 3, "Preset Mode 테스트")
    for mode_val, mode_name in VIDEO_WB_MODES.items():
        if mode_val in ["manual", "hold"]: continue  # manual과 hold는 별도 테스트
        print(f"\n   👉 설정: {mode_name} ({mode_val})")
        
        curr_set = api_get_video_wb(page, camera_ip)
        if not curr_set: continue
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['wbMode'] = mode_val
        
        if api_set_video_wb(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            trigger_iras_snapshot(page, camera_ip, f"WB_{mode_name.replace(' ', '_')}.png")
            curr = api_get_video_wb(page, camera_ip)
            if curr and curr.get("wbMode") == mode_val: 
                print("   ✅ Pass")
            else: 
                print(f"   ❌ Fail (기대: {mode_val}, 실제: {curr.get('wbMode') if curr else 'None'})")
                failed_count += 1
        else: 
            print("   ❌ API 설정 실패")
            failed_count += 1
    
    # Step 1 복구: Auto로 복구
    print("\n   🔄 Step 1 복구: WB Mode → auto")
    curr_set = api_get_video_wb(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['wbMode'] = 'auto'
        api_set_video_wb(page, camera_ip, payload)
        time.sleep(2)

    print_step(2, 3, "Hold Mode 테스트")
    if "hold" in VIDEO_WB_MODES:
        print(f"   👉 설정: {VIDEO_WB_MODES['hold']} (hold)")
        
        curr_set = api_get_video_wb(page, camera_ip)
        if not curr_set: 
            print("   ⚠️ 설정 조회 실패")
        else:
            payload = curr_set.copy()
            if 'returnCode' in payload: del payload['returnCode']
            payload['wbMode'] = 'hold'
            
            if api_set_video_wb(page, camera_ip, payload):
                print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
                time.sleep(VIDEO_WAIT_TIME)
                trigger_iras_snapshot(page, camera_ip, f"WB_{VIDEO_WB_MODES['hold'].replace(' ', '_')}.png")
                curr = api_get_video_wb(page, camera_ip)
                if curr and curr.get("wbMode") == 'hold': 
                    print("   ✅ Pass")
                else: 
                    print(f"   ❌ Fail (기대: hold, 실제: {curr.get('wbMode') if curr else 'None'})")
                    failed_count += 1
            else: 
                print("   ❌ API 설정 실패")
                failed_count += 1
    
    # Step 2 복구: Auto로 복구
    print("\n   🔄 Step 2 복구: WB Mode → auto")
    curr_set = api_get_video_wb(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['wbMode'] = 'auto'
        api_set_video_wb(page, camera_ip, payload)
        time.sleep(2)

    print_step(3, 3, "Manual Mode (Gain) 테스트")
    
    curr_set = api_get_video_wb(page, camera_ip)
    if not curr_set: return False, "설정 조회 실패"
    payload = curr_set.copy()
    if 'returnCode' in payload: del payload['returnCode']
    payload['wbMode'] = 'manual'
    
    if not api_set_video_wb(page, camera_ip, payload):
        return False, "Manual 진입 실패"
    
    time.sleep(2)
    trigger_iras_snapshot(page, camera_ip, "WB_Manual_진입.png")
    
    for param, name in [("redGain", "Red"), ("blueGain", "Blue")]:
        print(f"\n   --- [Target: {name}] ---")
        for val in VIDEO_WB_GAIN_TEST_VALUES:
            print(f"   👉 값 변경: {val}")
            
            curr_set = api_get_video_wb(page, camera_ip)
            if not curr_set: continue
            
            payload = curr_set.copy()
            if 'returnCode' in payload: del payload['returnCode']
            payload['wbMode'] = 'manual'
            payload[param] = val
            
            if api_set_video_wb(page, camera_ip, payload):
                print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
                time.sleep(VIDEO_WAIT_TIME)
                trigger_iras_snapshot(page, camera_ip, f"WB_Manual_{name}Gain_{val}.png")
                curr = api_get_video_wb(page, camera_ip)
                if curr and curr.get(param) == val: print(f"   ✅ Pass: {val}")
                else: 
                    print("   ❌ Fail")
                    failed_count += 1
            else: failed_count += 1
    
    # Step 3 복구: Auto로 복구
    print("\n   🔄 Step 3 복구: WB Mode → auto")
    curr_set = api_get_video_wb(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['wbMode'] = 'auto'
        api_set_video_wb(page, camera_ip, payload)
        time.sleep(10)
    
    if failed_count == 0: return True, "WB Test 성공"
    else: return False, f"WB Test 실패 ({failed_count}건)"


# ===========================================================
# 🧪 [Test 4] Exposure (노출)
# ===========================================================
def run_exposure_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 4/10] Exposure")
    print("=======================================================")
    
    trigger_iras_snapshot(page, camera_ip, "Exposure_기본값.png")
    failed_count = 0

    print_step(1, 3, "AE Target Gain 테스트")
    for val in VIDEO_TARGET_GAIN_VALUES:
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
            print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            trigger_iras_snapshot(page, camera_ip, f"Exposure_TargetGain_{val}.png")
            curr = api_get_video_exposure(page, camera_ip)
            if curr and curr.get('targetGain') == val:
                print(f"   ✅ Pass")
            else:
                print(f"   ❌ Fail")
                failed_count += 1
        else: failed_count += 1
    
    # Step 1 복구: Target Gain을 0으로
    print("\n   🔄 Step 1 복구: Target Gain → 0")
    curr_set = api_get_video_exposure(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['targetGain'] = '0'
        api_set_video_exposure(page, camera_ip, payload)
        time.sleep(2)

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
    #         print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
    #         time.sleep(VIDEO_WAIT_TIME)
    #         trigger_iras_snapshot()
            
    #         curr = api_get_video_exposure(page, camera_ip)
    #         if curr and curr.get('upperShutterLimit') == shutter_val:
    #             print(f"   ✅ Pass")
    #         else:
    #             print(f"   ❌ Fail")
    #             failed_count += 1
    #     else: failed_count += 1

    print_step(2, 3, "Slow Shutter 테스트 (Day Mode 고정)")
    
    print("\n" + "="*60)
    print("⚠️  [Action Required]")
    print("    Slow Shutter 동작 확인을 위해 카메라 렌즈를 가리거나,")
    print("    주변 환경을 어둡게 만든 뒤 Enter 키를 눌러주세요.")
    print("="*60)
    input(">> 준비되었으면 Enter를 누르세요...")
    print("   ▶️ 테스트를 계속 진행합니다...\n")

    # Day 모드로 고정
    print("   👉 Day & Night 모드를 Day로 고정")
    daynight_set = api_get_video_daynight(page, camera_ip)
    if daynight_set:
        daynight_payload = daynight_set.copy()
        if 'returnCode' in daynight_payload: del daynight_payload['returnCode']
        daynight_payload['bwMode'] = 'schedule'
        daynight_payload['icrMode'] = 'schedule'
        daynight_payload['schedule'] = VIDEO_DAY_SCHEDULE_STR  # 항상 Day
        api_set_video_daynight(page, camera_ip, daynight_payload)
        time.sleep(2)
    
    # 기준 스냅샷 (Slow Shutter off 상태)
    print("   📸 기준 스냅샷 (Slow Shutter Off)")
    curr_set = api_get_video_exposure(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['manualAeControl'] = 'off'
        payload['wdr'] = 'off'
        payload['slowShutter'] = 'off'
        api_set_video_exposure(page, camera_ip, payload)
        time.sleep(VIDEO_WAIT_TIME)
        trigger_iras_snapshot(page, camera_ip, "Exposure_SlowShutter_Before.png")
    
    # Slow Shutter 설정
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
            # 설정 검증
            curr = api_get_video_exposure(page, camera_ip)
            if curr and curr.get('slowShutter') == slow_shutter_val:
                print(f"   ✅ 설정 적용 확인")
            else:
                print(f"   ❌ 설정 검증 실패")
                failed_count += 1
            
            # IPS가 떨어질 때까지 10초 대기
            print(f"   ⏳ IPS 감소 대기 중 (10초)...")
            time.sleep(10)
            
            # IPS 확인
            print(f"   📊 IPS 확인 중...")
            screen_text = get_iras_clipboard_text()
            info = parse_stream_info(screen_text)
            detected_ips = info.get('ips', -1.0)
            
            # 스냅샷
            trigger_iras_snapshot(page, camera_ip, f"Exposure_SlowShutter_{slow_shutter_val.replace('/', '_')}.png")
            
            # 검증
            if detected_ips > 0:
                print(f"   📊 현재 IPS: {detected_ips}")
                if detected_ips <= 10.0:
                    print(f"   ✅ Pass: IPS가 10 이하로 감소됨 ({detected_ips} ips)")
                else:
                    print(f"   ⚠️ Warning: IPS가 10보다 큼 ({detected_ips} ips)")
                    print(f"   ℹ️  Tip: 환경이 충분히 어둡지 않을 수 있습니다.")
            else:
                print(f"   ⚠️ IPS 값을 읽을 수 없습니다.")
        else: 
            print(f"   ❌ Slow Shutter 설정 실패")
            failed_count += 1
    else: failed_count += 1
    
    # Step 3 복구: Slow Shutter를 off로
    print("\n   🔄 Step 3 복구: Slow Shutter → off")
    curr_set = api_get_video_exposure(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['slowShutter'] = 'off'
        api_set_video_exposure(page, camera_ip, payload)
        time.sleep(2)

    print_step(3, 3, "WDR 테스트")
    for mode in VIDEO_WDR_MODES:
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
            print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            trigger_iras_snapshot(page, camera_ip, f"Exposure_WDR_{mode.upper()}.png")
            curr = api_get_video_exposure(page, camera_ip)
            if curr and curr.get('wdr') == mode:
                print(f"   ✅ Pass")
            else:
                print(f"   ❌ Fail")
                failed_count += 1
        else: failed_count += 1
    
    # Step 4 복구: WDR을 off로
    print("\n   🔄 Step 4 복구: WDR → off")
    curr_set = api_get_video_exposure(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['wdr'] = 'off'
        api_set_video_exposure(page, camera_ip, payload)
        time.sleep(2)
    
    if failed_count == 0: return True, "Exposure Test 성공"
    else: return False, f"Exposure Test 실패 ({failed_count}건)"

# ===========================================================
# 🧪 [Test 5] Day & Night [NEW]
# ===========================================================
def run_daynight_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 5/10] Day & Night")
    print("=======================================================")
    
    failed_count = 0

    print_step(1, 2, "Auto Mode 테스트 (조도 센서 동작 확인)")
    
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
    
    print("   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
    time.sleep(VIDEO_WAIT_TIME)
    trigger_iras_snapshot(page, camera_ip, "DayNight_Auto_Night.png") # 흑백 영상 캡처

    # 3. Day 전환 유도 (사용자 개입)
    print("\n" + "="*60)
    print("⚠️  [Action Required: Day Mode]")
    print("    1. 가림막을 제거하여 밝게 해주세요.")
    print("    2. 컬러(Day)로 돌아오면 Enter를 누르세요.")
    print("="*60)
    input(">> 준비되었으면 Enter를 누르세요...")
    
    print("   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
    time.sleep(VIDEO_WAIT_TIME)
    trigger_iras_snapshot(page, camera_ip, "DayNight_Auto_Day.png") # 컬러 영상 캡처

    print_step(2, 2, "Schedule Mode 테스트")
    
    # 1. Schedule - Always Night (강제 흑백)
    print("   👉 스케줄 설정: Always Night (B&W)")
    
    payload['bwMode'] = 'schedule'
    payload['icrMode'] = 'schedule'
    payload['schedule'] = VIDEO_NIGHT_SCHEDULE_STR # 5555...
    
    if api_set_video_daynight(page, camera_ip, payload):
        print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s) -> 흑백이어야 함")
        time.sleep(VIDEO_WAIT_TIME)
        trigger_iras_snapshot(page, camera_ip, "DayNight_Schedule_Night.png")
        
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
    
    payload['schedule'] = VIDEO_DAY_SCHEDULE_STR # 0000...
    
    if api_set_video_daynight(page, camera_ip, payload):
        print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s) -> 컬러여야 함")
        time.sleep(VIDEO_WAIT_TIME)
        trigger_iras_snapshot(page, camera_ip, "DayNight_Schedule_Day.png")
        print(f"   ✅ 설정 적용 확인")
    else:
        print("   ❌ API 전송 실패")
        failed_count += 1
    
    # Step 2 복구: Auto Mode로 복구
    print("\n   🔄 Step 2 복구: Day&Night Mode → auto")
    curr_set = api_get_video_daynight(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['bwMode'] = 'auto'
        payload['icrMode'] = 'auto'
        api_set_video_daynight(page, camera_ip, payload)
        time.sleep(2)

    if failed_count == 0: return True, "Day&Night Test 성공"
    else: return False, f"Day&Night Test 실패 ({failed_count}건)"

# ===========================================================
# 🧪 [Test 6] Video Misc (EIS) [NEW]
# ===========================================================
def run_video_misc_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 6/10] Miscellaneous (EIS)")
    print("=======================================================")
    
    trigger_iras_snapshot(page, camera_ip, "EIS_기본값.png")
    failed_count = 0

    curr_set = api_get_video_misc(page, camera_ip)
    if not curr_set: return False, "설정 조회 실패"
    
    if 'returnCode' in curr_set: del curr_set['returnCode']

    print_step(1, 1, "EIS 모드 테스트")
    
    for mode in VIDEO_EIS_MODES:
        mode_name = "Off" if mode == "off" else "On"
        print(f"\n   👉 EIS {mode_name}")
        if mode == "on":
            print("   ℹ️  EIS를 켜면 영상 가장자리가 잘려나가 화각이 좁아지는지 확인하세요.")
        
        payload = curr_set.copy()
        payload['imageStabilizer'] = mode
        
        if api_set_video_misc(page, camera_ip, payload):
            print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            trigger_iras_snapshot(page, camera_ip, f"EIS_{mode_name}.png")
            
            curr = api_get_video_misc(page, camera_ip)
            if curr and curr.get('imageStabilizer') == mode:
                print(f"   ✅ 설정 적용 확인 (EIS {mode_name})")
            else:
                print(f"   ❌ 검증 실패")
                failed_count += 1
        else:
            print(f"   ❌ API 전송 실패")
            failed_count += 1
        
        # 각 모드 테스트 후 즉시 off로 복구
        if mode != "off":
            print(f"   🔄 EIS {mode_name} 테스트 후 복구: EIS → off")
            restore_payload = curr_set.copy()
            restore_payload['imageStabilizer'] = 'off'
            api_set_video_misc(page, camera_ip, restore_payload)
            time.sleep(2)

    if failed_count == 0: return True, "Video Misc (EIS) Test 성공"
    else: return False, f"Video Misc (EIS) Test 실패 ({failed_count}건)"



# ===========================================================
# 🧪 [Test 7] Video Streaming Test
# ===========================================================
def run_streaming_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 7/10] Streaming")
    print("=======================================================")
    
    failed_count = 0
    target_stream = VIDEO_STREAMING_TARGET_STREAM
    
    initial_set = api_get_video_streaming(page, camera_ip)
    if not initial_set: return False, "설정 조회 실패"
    if 'returnCode' in initial_set: del initial_set['returnCode']
    
    print_step(1, 5, "스트림 2, 3, 4번 설정")
    print_action("스트림 1번은 이미 활성화되어 있으므로 건너뜀")
    
    curr_set = api_get_video_streaming(page, camera_ip)
    if not curr_set: return False, "설정 조회 실패"
    
    if 'returnCode' in curr_set: del curr_set['returnCode']
    payload = curr_set.copy()
    
    # 스트림 2번: H.264, 1920x1080, standard, vbr, 10ips
    print("   👉 스트림 2: H.264, 1920x1080, standard, vbr, 10ips")
    payload['useStream2'] = 'on'
    payload['codecStream2'] = 'h264'
    payload['resolutionStream2'] = '1920x1080'
    payload['qualityStream2'] = 'standard'
    payload['bitrateControlStream2'] = 'vbr'
    payload['framerateStream2'] = '10'
    
    # 스트림 3번: H.264, 3328x1872, standard, vbr, 15ips
    print("   👉 스트림 3: H.264, 3328x1872, standard, vbr, 15ips")
    payload['useStream3'] = 'on'
    payload['codecStream3'] = 'h264'
    payload['resolutionStream3'] = '3328x1872'
    payload['qualityStream3'] = 'standard'
    payload['bitrateControlStream3'] = 'vbr'
    payload['framerateStream3'] = '15'
    
    # 스트림 4번: H.265, 1920x1080, standard, vbr, 5ips
    print("   👉 스트림 4: H.265, 1920x1080, standard, vbr, 5ips")
    payload['useStream4'] = 'on'
    payload['codecStream4'] = 'h265'
    payload['resolutionStream4'] = '1920x1080'
    payload['qualityStream4'] = 'standard'
    payload['bitrateControlStream4'] = 'vbr'
    payload['framerateStream4'] = '5'

    if api_set_video_streaming(page, camera_ip, payload):
        print("   ✅ 스트림 2, 3, 4번 설정 완료")
        time.sleep(3) 
    else:
        print("   ❌ 스트림 설정 실패")
        failed_count += 1

    print_step(2, 5, "iRAS 스트림 전환 검증")
    
    # 스트림 2, 3, 4 설정 정보
    stream_configs = {
        2: {"codec": "h264", "resolution": "1920x1080", "ips": 10.0},
        3: {"codec": "h264", "resolution": "3328x1872", "ips": 15.0},
        4: {"codec": "h265", "resolution": "1920x1080", "ips": 5.0}
    }
    
    for stream_num, expected in stream_configs.items():
        print(f"\n   👉 스트림 {stream_num}번으로 전환")
        
        ctrl = IRASController()
        if not ctrl.switch_stream(stream_num):
            print(f"   ❌ 스트림 {stream_num} 전환 실패")
            failed_count += 1
            continue
        
        # 클립보드 텍스트에서 스트림 정보 읽기
        print(f"   📊 스트림 {stream_num} 정보 확인 중...")
        screen_text = get_iras_clipboard_text()
        info = parse_stream_info(screen_text)
        
        # 검증
        codec_ok = info.get('codec') == expected['codec']
        res_ok = info.get('res_str') == expected['resolution']
        ips_ok = abs(info.get('ips', -1.0) - expected['ips']) < 1.0
        
        print(f"      코덱: {info.get('codec', 'Unknown')} (기대: {expected['codec']}) {'✅' if codec_ok else '❌'}")
        print(f"      해상도: {info.get('res_str', 'Unknown')} (기대: {expected['resolution']}) {'✅' if res_ok else '❌'}")
        print(f"      IPS: {info.get('ips', 'Unknown')} (기대: {expected['ips']}) {'✅' if ips_ok else '❌'}")
        
        if codec_ok and res_ok and ips_ok:
            print(f"   ✅ 스트림 {stream_num} 검증 성공")
        else:
            print(f"   ❌ 스트림 {stream_num} 검증 실패")
            failed_count += 1
    
    # 스트림 1번으로 복귀
    print(f"\n   👉 스트림 1번으로 복귀")
    ctrl = IRASController()
    if not ctrl.switch_stream(1):
        print(f"   ⚠️ 스트림 1 복귀 실패")
    else:
        print(f"   ✅ 스트림 1 복귀 완료")
        time.sleep(1)

    print_step(3, 5, "코덱 변경 확인 (Stream 1)")
    codecs_to_test = VIDEO_STREAMING_CODECS 
    
    for codec in codecs_to_test:
        print(f"   👉 코덱 변경 요청: {codec.upper()}")
        
        curr_set = api_get_video_streaming(page, camera_ip)
        if not curr_set: continue

        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        
        payload[f'codecStream{target_stream}'] = codec
        
        if api_set_video_streaming(page, camera_ip, payload):
            print(f"   ⏳ 반영 대기 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            
            # 클립보드 텍스트 읽기
            screen_text = get_iras_clipboard_text()
            info = parse_stream_info(screen_text)
            
            # 검증
            detected_codec = info.get('codec', 'Unknown')
            if detected_codec == codec:
                print(f"   ✅ 검증 성공: {detected_codec.upper()}")
            else:
                print(f"   ❌ 검증 실패: 기대값({codec.upper()}) != 실제값({detected_codec.upper()})")
                failed_count += 1
        else:
            failed_count += 1
    
    # Step 2 복구: 코덱을 초기값으로
    print("\n   🔄 Step 2 복구: 코덱 → 초기값")
    curr_set = api_get_video_streaming(page, camera_ip)
    if curr_set and initial_set.get(f'codecStream{target_stream}'):
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload[f'codecStream{target_stream}'] = initial_set[f'codecStream{target_stream}']
        api_set_video_streaming(page, camera_ip, payload)
        time.sleep(2)

    print_step(4, 5, "해상도 변경 확인 (Stream 1)")
    resolutions = ["1920x1080"]  # 1920x1080만 확인 
    
    for res in resolutions:
        print(f"   👉 해상도 변경 요청: {res}")
        
        curr_set = api_get_video_streaming(page, camera_ip)
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        
        payload[f'resolutionStream{target_stream}'] = res
        
        if api_set_video_streaming(page, camera_ip, payload):
            print(f"   ⏳ 반영 대기 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            
            screen_text = get_iras_clipboard_text()
            info = parse_stream_info(screen_text)
            
            # 검증 (API "WxH" == 화면정보 "WxH")
            detected_res = info.get('res_str', 'Unknown')
            if detected_res == res:
                 print(f"   ✅ 검증 성공: {detected_res}")
            else:
                 print(f"   ❌ 검증 실패: 기대값({res}) != 실제값({detected_res})")
                 failed_count += 1
        else:
            failed_count += 1
    
    # Step 3 복구: 해상도를 초기값으로
    print("\n   🔄 Step 3 복구: 해상도 → 초기값")
    curr_set = api_get_video_streaming(page, camera_ip)
    if curr_set and initial_set.get(f'resolutionStream{target_stream}'):
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload[f'resolutionStream{target_stream}'] = initial_set[f'resolutionStream{target_stream}']
        api_set_video_streaming(page, camera_ip, payload)
        time.sleep(2)

    print_step(5, 5, "IPS(FPS) 확인")
    ips_values = VIDEO_STREAMING_IPS_VALUES
    
    for ips in ips_values:
        print(f"   👉 IPS 변경 요청: {ips}")
        
        curr_set = api_get_video_streaming(page, camera_ip)
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        
        payload[f'framerateStream{target_stream}'] = ips
        
        if api_set_video_streaming(page, camera_ip, payload):
            print(f"   ⏳ 반영 대기 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            
            screen_text = get_iras_clipboard_text()
            info = parse_stream_info(screen_text)
            
            detected_ips = info.get('ips', -1.0)
            
            # float 비교 (1.0 오차 허용)
            if abs(detected_ips - float(ips)) < 1.0:
                print(f"   ✅ 검증 성공: {detected_ips} ips")
            else:
                print(f"   ❌ 검증 실패: 기대값({ips}) != 실제값({detected_ips})")
                failed_count += 1
        else:
            failed_count += 1
    
    # Step 4 복구: IPS를 초기값으로
    print("\n   🔄 Step 4 복구: IPS → 초기값")
    curr_set = api_get_video_streaming(page, camera_ip)
    if curr_set and initial_set.get(f'framerateStream{target_stream}'):
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload[f'framerateStream{target_stream}'] = initial_set[f'framerateStream{target_stream}']
        api_set_video_streaming(page, camera_ip, payload)
        time.sleep(2)

    # ---------------------------------------------------------
    # [Step 5] VBR vs CBR 데이터 크기 비교
    # ---------------------------------------------------------
    print("\n[Step 5] VBR vs CBR 데이터 크기 비교")
    
    bitrate_results = {}
    
    # 공정한 비교를 위해 기본 설정 고정
    base_payload = {
        f'codecStream{target_stream}': VIDEO_STREAMING_BASE_SETTINGS['codec'],
        f'resolutionStream{target_stream}': VIDEO_STREAMING_BASE_SETTINGS['resolution'],
        f'framerateStream{target_stream}': VIDEO_STREAMING_BASE_SETTINGS['framerate'],
        f'qualityStream{target_stream}': VIDEO_STREAMING_BASE_SETTINGS['quality']
    }

    # 순서: CBR 먼저 측정 후 VBR 측정
    for mode in VIDEO_STREAMING_BITRATE_MODES:
        print(f"   👉 비트레이트 제어 변경: {mode.upper()}")
        
        curr_set = api_get_video_streaming(page, camera_ip)
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        
        payload.update(base_payload)
        payload[f'bitrateControlStream{target_stream}'] = mode
        
        if api_set_video_streaming(page, camera_ip, payload):
            print(f"   ⏳ 데이터 안정화 대기 ({VIDEO_WAIT_TIME}s)...")
            time.sleep(VIDEO_WAIT_TIME)
            
            screen_text = get_iras_clipboard_text()
            info = parse_stream_info(screen_text)
            mbps = info.get('mbps')
            
            if mbps is not None:
                print(f"      [Measured] {mode.upper()}: {mbps} Mbps")
                bitrate_results[mode] = mbps
            else:
                print(f"   ⚠️ Mbps 값을 화면 정보에서 읽을 수 없습니다.")
        else:
            failed_count += 1

    # 결과 비교
    if "cbr" in bitrate_results and "vbr" in bitrate_results:
        cbr_val = bitrate_results["cbr"]
        vbr_val = bitrate_results["vbr"]
        
        print(f"   📊 비교 결과: VBR({vbr_val}) vs CBR({cbr_val})")
        
        # VBR이 CBR보다 작으면 성공 (정적인 화면 기준)
        if vbr_val < cbr_val:
            print(f"   ✅ Pass: VBR이 CBR보다 효율적입니다. (Diff: {cbr_val - vbr_val:.2f} Mbps)")
        else:
            print(f"   ⚠️ Warning: VBR이 CBR보다 크거나 같습니다. (화면이 동적이거나 설정에 따라 다를 수 있음)")
    else:
        print("   ❌ 데이터 부족으로 비교 불가")
        failed_count += 1
    
    # Step 5 복구: 비트레이트 제어를 초기값으로
    print("\n   🔄 Step 5 복구: 비트레이트 제어 → 초기값")
    curr_set = api_get_video_streaming(page, camera_ip)
    if curr_set and initial_set.get(f'bitrateControlStream{target_stream}'):
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload[f'bitrateControlStream{target_stream}'] = initial_set[f'bitrateControlStream{target_stream}']
        api_set_video_streaming(page, camera_ip, payload)
        time.sleep(2)

    if failed_count == 0: return True, "Streaming Test 성공"
    else: return False, f"Streaming Test 실패 ({failed_count}건)"

# ===========================================================
# 🧪 [Test 8] MAT (Motion Adaptive Transmission) Test
# ===========================================================
def run_video_mat_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 8/10] MAT (Motion Adaptive Transmission)")
    print("=======================================================")
    
    trigger_iras_snapshot(page, camera_ip, "MAT_기본값.png")
    failed_count = 0

    curr_set = api_get_video_mat(page, camera_ip)
    if not curr_set: return False, "설정 조회 실패"
    
    if 'returnCode' in curr_set: del curr_set['returnCode']
    
    # 사용자 확인 - 정적인 화면인지
    print("\n" + "="*60)
    print("⚠️  [Action Required: 정적인 화면 준비]")
    print("    1. 카메라가 움직임이 없는 화면을 촬영하고 있는지 확인해주세요.")
    print("    2. (예: 벽면, 정지된 물체, 고정된 배경)")
    print("    3. 준비되었으면 Enter를 눌러주세요.")
    print("="*60)
    input(">> 준비되었으면 Enter를 누르세요...")
    print("   ▶️ MAT 테스트를 시작합니다...\n")

    print_step(1, 2, "MAT Off (기준 프레임레이트 확인)")
    
    payload = curr_set.copy()
    payload['useMat'] = 'off'
    
    if api_set_video_mat(page, camera_ip, payload):
        print(f"   ⏳ 영상 안정화 대기 (5초)...")
        time.sleep(5)
        trigger_iras_snapshot(page, camera_ip, "MAT_Off.png")
        
        # 현재 IPS 확인
        screen_text = get_iras_clipboard_text()
        info = parse_stream_info(screen_text)
        base_ips = info.get('ips', -1.0)
        
        if base_ips > 0:
            print(f"   📊 현재 IPS (MAT Off): {base_ips}")
        else:
            print(f"   ⚠️ IPS 값을 읽을 수 없습니다.")
            failed_count += 1
    else:
        print(f"   ❌ MAT Off 설정 실패")
        failed_count += 1
    
    # Step 1은 이미 off 상태이므로 복구 불필요

    print_step(2, 2, "MAT On (프레임레이트 감소 확인)")
    print(f"   ℹ️  설정: sensitivity={VIDEO_MAT_SENSITIVITY}, inactivityPeriod={VIDEO_MAT_INACTIVITY_PERIOD}, framerateStream1={VIDEO_MAT_TARGET_FRAMERATE}")
    
    payload['useMat'] = 'on'
    payload['sensitivity'] = VIDEO_MAT_SENSITIVITY
    payload['inactivityPeriod'] = VIDEO_MAT_INACTIVITY_PERIOD
    payload['framerateStream1'] = VIDEO_MAT_TARGET_FRAMERATE
    
    if api_set_video_mat(page, camera_ip, payload):
        print(f"   ✅ MAT 설정 완료")
        
        # 설정 적용 확인
        curr = api_get_video_mat(page, camera_ip)
        if curr and curr.get('useMat') == 'on':
            print(f"   ✅ MAT 활성화 확인")
        else:
            print(f"   ❌ MAT 설정 검증 실패")
            failed_count += 1
        
        # IPS가 떨어지기까지 대기 (inactivityPeriod + 여유 시간)
        print(f"   ⏳ IPS 감소 대기 중 ({VIDEO_MAT_WAIT_TIME}초)...")
        print(f"      (MAT는 움직임이 없으면 {VIDEO_MAT_INACTIVITY_PERIOD}초 후 프레임레이트를 낮춥니다)")
        time.sleep(VIDEO_MAT_WAIT_TIME)
        
        trigger_iras_snapshot(page, camera_ip, "MAT_On_Reduced.png")
        
        # 감소된 IPS 확인
        screen_text = get_iras_clipboard_text()
        info = parse_stream_info(screen_text)
        reduced_ips = info.get('ips', -1.0)
        
        if reduced_ips > 0:
            print(f"   📊 현재 IPS (MAT On): {reduced_ips}")
            
            # 목표 IPS로 떨어졌는지 확인 (±1 오차 허용)
            if abs(reduced_ips - VIDEO_MAT_TARGET_IPS) <= 1.0:
                print(f"   ✅ Pass: IPS가 {VIDEO_MAT_TARGET_IPS}로 감소됨 (실제: {reduced_ips})")
            else:
                print(f"   ❌ Fail: IPS가 목표값으로 감소하지 않음 (목표: {VIDEO_MAT_TARGET_IPS}, 실제: {reduced_ips})")
                print(f"   ℹ️  Tip: 화면에 움직임이 있거나 대기 시간이 부족할 수 있습니다.")
                failed_count += 1
        else:
            print(f"   ⚠️ IPS 값을 읽을 수 없습니다.")
            failed_count += 1
    else:
        print(f"   ❌ MAT On 설정 실패")
        failed_count += 1
    
    # Step 2 복구: MAT를 off로
    print("\n   🔄 Step 2 복구: MAT → off")
    restore_payload = curr_set.copy()
    restore_payload['useMat'] = 'off'
    if api_set_video_mat(page, camera_ip, restore_payload):
        time.sleep(2)
        print("   ✅ 설정 복구 완료")
    else:
        print("   ⚠️ 설정 복구 실패")

    if failed_count == 0: return True, "MAT Test 성공"
    else: return False, f"MAT Test 실패 ({failed_count}건)"

# ===========================================================
# 🧪 [Test 9] Privacy Mask Test
# ===========================================================
def run_privacy_mask_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 9/10] Privacy Mask")
    print("=======================================================")
    
    trigger_iras_snapshot(page, camera_ip, "Privacy_기본값.png")
    failed_count = 0

    curr_set = api_get_video_privacy(page, camera_ip)
    if not curr_set:
        print_error("API 조회 실패: videoPrivacy")
        return False, "설정 조회 실패"
    
    if 'returnCode' in curr_set: del curr_set['returnCode']
    
    max_width = int(curr_set.get('maxWidth', 80))
    max_height = int(curr_set.get('maxHeight', 45))
    print(f"   ℹ️  좌표 시스템: {max_width} x {max_height}")

    print_step(1, 2, "Privacy Mask Off (초기 상태)")
    
    payload = curr_set.copy()
    payload['usePrivacy'] = 'off'
    
    # 모든 Zone 비활성화
    for i in range(1, VIDEO_PRIVACY_ZONE_COUNT + 1):
        payload[f'useZone{i}'] = 'off'
    
    if api_set_video_privacy(page, camera_ip, payload):
        print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
        time.sleep(VIDEO_WAIT_TIME)
        trigger_iras_snapshot(page, camera_ip, "Privacy_Off.png")
        print(f"   ✅ Privacy Mask Off 확인")
    else:
        print(f"   ❌ 설정 실패")
        failed_count += 1

    print_step(2, 2, f"{VIDEO_PRIVACY_ZONE_COUNT}개 Privacy Zone 생성")
    print(f"   ℹ️  그리드: {VIDEO_PRIVACY_GRID_ROWS}x{VIDEO_PRIVACY_GRID_COLS}")
    
    # 화면을 그리드로 나눠서 각각 다른 위치에 마스크 배치
    zones = []
    cell_width = max_width // VIDEO_PRIVACY_GRID_COLS
    cell_height = max_height // VIDEO_PRIVACY_GRID_ROWS
    
    for row in range(VIDEO_PRIVACY_GRID_ROWS):
        for col in range(VIDEO_PRIVACY_GRID_COLS):
            zones.append({
                "left": col * cell_width,
                "top": row * cell_height,
                "right": (col + 1) * cell_width if col < VIDEO_PRIVACY_GRID_COLS - 1 else max_width,
                "bottom": (row + 1) * cell_height if row < VIDEO_PRIVACY_GRID_ROWS - 1 else max_height,
            })
    
    payload['usePrivacy'] = 'on'
    
    for i, zone in enumerate(zones[:VIDEO_PRIVACY_ZONE_COUNT], start=1):
        payload[f'useZone{i}'] = 'on'
        payload[f'nameZone{i}'] = f'{VIDEO_PRIVACY_ZONE_NAME_PREFIX}{i}'
        payload[f'leftZone{i}'] = str(zone['left'])
        payload[f'topZone{i}'] = str(zone['top'])
        payload[f'rightZone{i}'] = str(zone['right'])
        payload[f'bottomZone{i}'] = str(zone['bottom'])
        print(f"   👉 Zone {i}: [{zone['left']},{zone['top']}] ~ [{zone['right']},{zone['bottom']}]")
    
    if api_set_video_privacy(page, camera_ip, payload):
        print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
        time.sleep(VIDEO_WAIT_TIME)
        trigger_iras_snapshot(page, camera_ip, f"Privacy_{VIDEO_PRIVACY_ZONE_COUNT}Zones.png")
        
        # 설정 검증
        curr = api_get_video_privacy(page, camera_ip)
        if curr and curr.get('usePrivacy') == 'on':
            print(f"   ✅ Privacy Mask 활성화 확인")
            
            # Zone 개수 확인
            active_zones = sum(1 for i in range(1, VIDEO_PRIVACY_ZONE_COUNT + 1) if curr.get(f'useZone{i}') == 'on')
            if active_zones == VIDEO_PRIVACY_ZONE_COUNT:
                print(f"   ✅ Pass: {VIDEO_PRIVACY_ZONE_COUNT}개 Zone 모두 활성화됨")
            else:
                print(f"   ❌ Fail: 활성화된 Zone 개수 불일치 (기대: {VIDEO_PRIVACY_ZONE_COUNT}, 실제: {active_zones})")
                failed_count += 1
        else:
            print(f"   ❌ Privacy Mask 설정 검증 실패")
            failed_count += 1
    else:
        print(f"   ❌ 설정 실패")
        failed_count += 1
    
    # Step 2 복구: Privacy Mask를 off로
    print("\n   🔄 Step 2 복구: Privacy Mask → off")
    restore_payload = curr_set.copy()
    restore_payload['usePrivacy'] = 'off'
    
    # 모든 Zone 비활성화
    for i in range(1, VIDEO_PRIVACY_ZONE_COUNT + 1):
        restore_payload[f'useZone{i}'] = 'off'
    
    if api_set_video_privacy(page, camera_ip, restore_payload):
        time.sleep(2)
        print("   ✅ 설정 복구 완료")
    else:
        print("   ⚠️ 설정 복구 실패")

    if failed_count == 0: return True, "Privacy Mask Test 성공"
    else: return False, f"Privacy Mask Test 실패 ({failed_count}건)"

# ===========================================================
# 🧪 [Test 10] OSD (On-Screen Display) Test
# ===========================================================
def run_osd_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🎬 [Video Test 10/10] OSD (On-Screen Display)")
    print("=======================================================")
    
    trigger_iras_snapshot(page, camera_ip, "OSD_기본값.png")
    failed_count = 0

    print("\n" + "="*60)
    print("📝 [Part A] OSD Text Test")
    print("="*60)
    
    curr_text_set = api_get_video_osd_text(page, camera_ip)
    if not curr_text_set: return False, "OSD Text 설정 조회 실패"
    
    if 'returnCode' in curr_text_set: del curr_text_set['returnCode']

    print_step(1, 2, "OSD Text Off")
    
    payload = curr_text_set.copy()
    payload['useOsd'] = 'off'
    
    if api_set_video_osd_text(page, camera_ip, payload):
        time.sleep(2)
        trigger_iras_snapshot(page, camera_ip, "OSD_Text_Off.png")
        
        # API로 실제 적용 확인
        curr = api_get_video_osd_text(page, camera_ip)
        if curr and curr.get('useOsd') == 'off':
            print(f"   ✅ OSD Text Off 확인 (API 검증 완료)")
        else:
            print(f"   ❌ OSD Text Off 검증 실패 (API 값: {curr.get('useOsd') if curr else 'None'})")
            failed_count += 1
    else:
        print(f"   ❌ 설정 실패")
        failed_count += 1

    print_step(2, 2, f"OSD Text On: '{VIDEO_OSD_TEXT_STRING}'")
    
    payload = curr_text_set.copy()
    payload['useOsd'] = 'on'
    payload['text'] = VIDEO_OSD_TEXT_STRING
    payload['textSize'] = VIDEO_OSD_TEXT_SIZES[1]  # 중간 크기
    payload['textColor'] = VIDEO_OSD_TEXT_COLORS[0]  # 흰색
    payload['textTransparency'] = VIDEO_OSD_TEXT_TRANSPARENCIES[0]  # 불투명
    payload['positionX'] = VIDEO_OSD_TEXT_POSITION['x']
    payload['positionY'] = VIDEO_OSD_TEXT_POSITION['y']
    
    if api_set_video_osd_text(page, camera_ip, payload):
        # API로 실제 적용 확인
        curr = api_get_video_osd_text(page, camera_ip)
        if curr and curr.get('useOsd') == 'on':
            print(f"   ✅ OSD Text On 확인 (API 검증 완료)")
            print(f"   📝 설정된 텍스트: '{curr.get('text')}'")
        else:
            print(f"   ❌ OSD Text On 검증 실패 (API 값: {curr.get('useOsd') if curr else 'None'})")
            failed_count += 1
        
        # 스냅샷 촬영
        print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
        time.sleep(VIDEO_WAIT_TIME)
        trigger_iras_snapshot(page, camera_ip, "OSD_Text_On.png")
        
        # API 검증만 수행 (스냅샷 없이)
        print(f"\n   --- [속성 검증] ---")
        
        # 크기 검증
        for size in VIDEO_OSD_TEXT_SIZES:
            payload['textSize'] = size
            if api_set_video_osd_text(page, camera_ip, payload):
                time.sleep(1)
                curr = api_get_video_osd_text(page, camera_ip)
                if curr and curr.get('textSize') == size:
                    print(f"   ✅ 크기 {size}: Pass")
                else:
                    print(f"   ❌ 크기 {size}: Fail")
                    failed_count += 1
            else:
                failed_count += 1
        
        # 색상 검증
        payload['textSize'] = VIDEO_OSD_TEXT_SIZES[1]  # 중간 크기로 복구
        for color in VIDEO_OSD_TEXT_COLORS:
            payload['textColor'] = color
            if api_set_video_osd_text(page, camera_ip, payload):
                time.sleep(1)
                curr = api_get_video_osd_text(page, camera_ip)
                if curr and curr.get('textColor') == color:
                    print(f"   ✅ 색상 {color}: Pass")
                else:
                    print(f"   ❌ 색상 {color}: Fail")
                    failed_count += 1
            else:
                failed_count += 1
        
        # 투명도 검증
        payload['textColor'] = VIDEO_OSD_TEXT_COLORS[0]  # 흰색으로 복구
        for transp in VIDEO_OSD_TEXT_TRANSPARENCIES:
            payload['textTransparency'] = transp
            if api_set_video_osd_text(page, camera_ip, payload):
                time.sleep(1)
                curr = api_get_video_osd_text(page, camera_ip)
                if curr and curr.get('textTransparency') == transp:
                    print(f"   ✅ 투명도 {transp}: Pass")
                else:
                    print(f"   ❌ 투명도 {transp}: Fail")
                    failed_count += 1
            else:
                failed_count += 1
    else:
        print(f"   ❌ 설정 실패")
        failed_count += 1

    # Part A 복구: OSD Text를 off로
    print("\n   🔄 Part A 복구: OSD Text → off")
    curr_set = api_get_video_osd_text(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['useOsd'] = 'off'
        if api_set_video_osd_text(page, camera_ip, payload):
            time.sleep(2)
            # 복구 검증
            verify = api_get_video_osd_text(page, camera_ip)
            if verify and verify.get('useOsd') == 'off':
                print("   ✅ 설정 복구 완료 (API 검증 완료)")
            else:
                print(f"   ⚠️ 설정 복구 검증 실패 (API 값: {verify.get('useOsd') if verify else 'None'})")
        else:
            print("   ⚠️ 설정 복구 실패")

    print("\n" + "="*60)
    print("📅 [Part B] OSD DateTime Test")
    print("="*60)
    
    curr_datetime_set = api_get_video_osd_datetime(page, camera_ip)
    if not curr_datetime_set: return False, "OSD DateTime 설정 조회 실패"
    
    if 'returnCode' in curr_datetime_set: del curr_datetime_set['returnCode']

    print_step(1, 2, "OSD DateTime Off")
    
    payload = curr_datetime_set.copy()
    payload['useOsd'] = 'off'
    
    if api_set_video_osd_datetime(page, camera_ip, payload):
        time.sleep(2)
        trigger_iras_snapshot(page, camera_ip, "OSD_DateTime_Off.png")
        
        # API로 실제 적용 확인
        curr = api_get_video_osd_datetime(page, camera_ip)
        if curr and curr.get('useOsd') == 'off':
            print(f"   ✅ OSD DateTime Off 확인 (API 검증 완료)")
        else:
            print(f"   ❌ OSD DateTime Off 검증 실패 (API 값: {curr.get('useOsd') if curr else 'None'})")
            failed_count += 1
    else:
        print(f"   ❌ 설정 실패")
        failed_count += 1

    print_step(2, 2, "OSD DateTime On")
    
    payload = curr_datetime_set.copy()
    payload['useOsd'] = 'on'
    payload['dateFormat'] = VIDEO_OSD_DATETIME_DATE_FORMATS[0]
    payload['timeFormat'] = VIDEO_OSD_DATETIME_TIME_FORMATS[0]
    payload['textSize'] = VIDEO_OSD_DATETIME_TEXT_SIZE
    payload['textColor'] = VIDEO_OSD_DATETIME_TEXT_COLOR
    payload['textTransparency'] = VIDEO_OSD_DATETIME_TEXT_TRANSPARENCY
    payload['positionX'] = VIDEO_OSD_DATETIME_POSITION['x']
    payload['positionY'] = VIDEO_OSD_DATETIME_POSITION['y']
    
    if api_set_video_osd_datetime(page, camera_ip, payload):
        # API로 실제 적용 확인
        curr = api_get_video_osd_datetime(page, camera_ip)
        if curr and curr.get('useOsd') == 'on':
            print(f"   ✅ OSD DateTime On 확인 (API 검증 완료)")
            print(f"   📝 날짜형식: {curr.get('dateFormat')}, 시간형식: {curr.get('timeFormat')}")
        else:
            print(f"   ❌ OSD DateTime On 검증 실패 (API 값: {curr.get('useOsd') if curr else 'None'})")
            failed_count += 1
        
        # 스냅샷 촬영
        print(f"   ⏳ 영상 확인 ({VIDEO_WAIT_TIME}s)...")
        time.sleep(VIDEO_WAIT_TIME)
        trigger_iras_snapshot(page, camera_ip, "OSD_DateTime_On.png")
        
        # 형식 검증만 수행 (스냅샷 없이)
        print(f"\n   --- [형식 검증] ---")
        
        # 날짜 형식 검증
        for date_format in VIDEO_OSD_DATETIME_DATE_FORMATS:
            payload['dateFormat'] = date_format
            if api_set_video_osd_datetime(page, camera_ip, payload):
                time.sleep(1)
                curr = api_get_video_osd_datetime(page, camera_ip)
                if curr and curr.get('dateFormat') == date_format:
                    print(f"   ✅ 날짜형식 {date_format}: Pass")
                else:
                    print(f"   ❌ 날짜형식 {date_format}: Fail")
                    failed_count += 1
            else:
                failed_count += 1
        
        # 시간 형식 검증
        payload['dateFormat'] = VIDEO_OSD_DATETIME_DATE_FORMATS[0]  # 첫 번째 날짜 형식으로 복구
        for time_format in VIDEO_OSD_DATETIME_TIME_FORMATS:
            payload['timeFormat'] = time_format
            if api_set_video_osd_datetime(page, camera_ip, payload):
                time.sleep(1)
                curr = api_get_video_osd_datetime(page, camera_ip)
                if curr and curr.get('timeFormat') == time_format:
                    print(f"   ✅ 시간형식 {time_format}: Pass")
                else:
                    print(f"   ❌ 시간형식 {time_format}: Fail")
                    failed_count += 1
            else:
                failed_count += 1
    else:
        print(f"   ❌ 설정 실패")
        failed_count += 1

    # Part B 복구: OSD DateTime을 off로
    print("\n   🔄 Part B 복구: OSD DateTime → off")
    curr_set = api_get_video_osd_datetime(page, camera_ip)
    if curr_set:
        payload = curr_set.copy()
        if 'returnCode' in payload: del payload['returnCode']
        payload['useOsd'] = 'off'
        if api_set_video_osd_datetime(page, camera_ip, payload):
            time.sleep(2)
            # 복구 검증
            verify = api_get_video_osd_datetime(page, camera_ip)
            if verify and verify.get('useOsd') == 'off':
                print("   ✅ 설정 복구 완료 (API 검증 완료)")
            else:
                print(f"   ⚠️ 설정 복구 검증 실패 (API 값: {verify.get('useOsd') if verify else 'None'})")
        else:
            print("   ⚠️ 설정 복구 실패")

    # =========================================================
    # 최종 결과
    # =========================================================
    if failed_count == 0: return True, "OSD Test 성공"
    else: return False, f"OSD Test 실패 ({failed_count}건)"