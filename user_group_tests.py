import time
from playwright.sync_api import Page
from common_actions import handle_popup, VISIBLE_DIALOG, DIALOG_BUTTONS
import iRAS_test

# ===========================================================
# 📋 [매핑] UI ID & API 권한명 매핑
# ===========================================================

# 1. UI 체크박스 제어용 ID
PERM_ID_MAP = {
    "업그레이드": "#edit-auth-upgrade",
    "설정": "#edit-auth-setup",
    "컬러 조정": "#edit-auth-color",
    "PTZ 제어": "#edit-auth-ptz",
    "알람-아웃 제어": "#edit-auth-alarm",
    "검색": "#edit-auth-search",
    "클립-카피": "#edit-auth-clipcopy"
}

# 2. API 검증용 권한명 매핑 (UI 한글 -> API 영문)
# API Doc: upgrade | setup | color | ptz | alarmOut | search | clipCopy | systemCheck
UI_TO_API_MAP = {
    "업그레이드": "upgrade",
    "설정": "setup",
    "컬러 조정": "color",
    "PTZ 제어": "ptz",
    "알람-아웃 제어": "alarmOut",
    "검색": "search",
    "클립-카피": "clipCopy"
}

# -----------------------------------------------------------
# [초기 권한 설정]
# -----------------------------------------------------------
INITIAL_PERMS = {
    "설정": True,         
    "검색": True,         
    "업그레이드": False,  
    "컬러 조정": False,   
    "PTZ 제어": False,    
    "알람-아웃 제어": False, 
    "클립-카피": False    
}

# ===========================================================
# 📡 [API] 권한 검증 함수 (신규 추가)
# ===========================================================
def verify_permissions_via_api(page: Page, ip: str, group_name: str, expected_perms_dict: dict):
    """
    API를 호출하여 특정 그룹의 실제 권한이 기대값과 일치하는지 검증합니다.
    """
    print(f"   📡 [API] '{group_name}' 권한 검증 수행 중...")
    
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=groupSetup&mode=1"
    
    try:
        # 브라우저 컨텍스트를 이용해 fetch 실행 (세션 쿠키 자동 사용)
        resp_text = page.evaluate(f"""
            fetch('{api_url}').then(response => response.text())
        """)
        
        # 응답 파싱 (Query String 형태 -> Dict)
        # 예: returnCode=0&groupCount=2&groupName1=admin...
        data = dict(item.split("=", 1) for item in resp_text.strip().split("&") if "=" in item)
        
        # 1. 그룹 찾기
        target_index = -1
        count = int(data.get("groupCount", 0))
        
        for i in range(1, count + 1):
            name_key = f"groupName{i}"
            if data.get(name_key) == group_name:
                target_index = i
                break
        
        if target_index == -1:
            print(f"   ❌ [API Fail] 그룹 '{group_name}'을 찾을 수 없습니다.")
            return False

        # 2. 권한 파싱 (pipe separated string)
        # 예: "setup|search"
        auth_str = data.get(f"authorities{target_index}", "")
        current_api_perms = auth_str.split("|") if auth_str else []
        
        # 3. 비교 검증
        is_valid = True
        for ui_name, should_have in expected_perms_dict.items():
            api_name = UI_TO_API_MAP.get(ui_name)
            if not api_name: continue
            
            has_perm = api_name in current_api_perms
            
            if should_have != has_perm:
                print(f"   ❌ [Mismatch] '{ui_name}'({api_name}) -> 기대: {should_have}, 실제: {has_perm}")
                is_valid = False
        
        if is_valid:
            print(f"   ✅ [API OK] 권한 설정이 서버에 올바르게 반영되었습니다.")
            return True
        else:
            return False

    except Exception as e:
        print(f"   🔥 [API Error] 검증 중 예외 발생: {e}")
        return False

# ===========================================================
# ⚙️ [UI 제어 함수] (기존 코드 유지)
# ===========================================================

def select_group_in_tree(page: Page, group_name: str):
    try:
        node = page.locator(f"a.dynatree-title:text-is('{group_name}')")
        if node.count() == 0: return False
        node.click(force=True)
        page.wait_for_timeout(500) 
        return True
    except: return False

def create_group_and_user(page: Page, group_name: str, uid: str, upw: str):
    try:
        print(f"[UI] 계정 생성 프로세스 시작 ({group_name})...")
        page.locator("#Page200_id").click()
        page.locator("#Page203_id").click()
        page.wait_for_timeout(1500)

        # 1. 그룹 생성
        if select_group_in_tree(page, group_name):
            print(f"ℹ️ 그룹 '{group_name}' 존재. 생성 스킵.")
        else:
            print(f"[UI] 새 그룹 '{group_name}' 생성...")
            page.locator("#add-group-btn").click()
            page.wait_for_selector("#edit-gid", state="visible")
            page.wait_for_timeout(1000)
            
            # 팝업 및 입력
            group_dialog = page.locator(".ui-dialog").filter(has=page.locator("#edit-gid"))
            page.locator("#edit-gid").fill(group_name)
            page.wait_for_timeout(500)
            
            # 초기 권한 설정
            print("   -> 초기 권한 설정 중...")
            toggle_permissions(page, group_dialog, INITIAL_PERMS)

            # 확인
            confirm_btn = group_dialog.locator(".ui-dialog-buttonset button").first
            if confirm_btn.is_enabled():
                confirm_btn.click()
                page.locator("#edit-gid").wait_for(state="hidden")
                page.wait_for_timeout(1000)
            else:
                print("🔥 그룹 생성 불가(중복 등). 취소.")
                group_dialog.locator(".ui-dialog-buttonset button").last.click()
                return False

        # 2. 사용자 생성
        select_group_in_tree(page, group_name)
        print(f"[UI] 사용자 '{uid}' 생성 시도...")
        page.locator("#add-user-btn").click()
        page.wait_for_selector("#add-user-edit-uid", state="visible")
        page.wait_for_timeout(1000)
        
        user_dialog = page.locator(".ui-dialog").filter(has=page.locator("#add-user-edit-uid"))
        page.locator("#add-user-edit-uid").fill(uid)
        page.locator("#add-user-edit-passwd1").fill(upw)
        page.locator("#add-user-edit-passwd2").fill(upw)
        user_dialog.locator("#add-email_not_use").check()
        page.wait_for_timeout(1000)
        
        # 경고창 처리
        if page.locator(VISIBLE_DIALOG).count() > 1:
            top_dialog = page.locator(".ui-dialog:visible").last
            if top_dialog.locator("#add-user-edit-uid").count() == 0:
                print("   -> 경고창 닫기")
                btn = top_dialog.locator(".ui-dialog-buttonset button").first
                if btn.is_visible(): btn.click(force=True)
                else: top_dialog.locator("button").first.click(force=True)
                page.wait_for_timeout(1000)

        # 확인
        user_confirm_btn = user_dialog.locator(".ui-dialog-buttonset button").first
        if user_confirm_btn.is_enabled():
            user_confirm_btn.click()
            page.locator("#add-user-edit-uid").wait_for(state="hidden")
        else:
            print(f"ℹ️ 사용자 중복. 취소.")
            user_dialog.locator(".ui-dialog-buttonset button").last.click()
        
        # 저장
        print("[UI] 설정 저장...")
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(3)
        return True

    except Exception as e:
        print(f"❌ 생성 오류: {e}")
        return False

def toggle_permissions(page, popup, target_state):
    """체크박스 제어 Helper"""
    for perm_name, should_check in target_state.items():
        # ID 매핑 조회
        target_id = PERM_ID_MAP.get(perm_name)
        if not target_id: continue

        # 체크박스 찾기 (매핑된 ID 사용)
        checkbox = popup.locator(target_id)
        
        if checkbox.is_visible():
            if checkbox.is_checked() != should_check:
                if should_check:
                    checkbox.check()
                    print(f"   -> [체크] {perm_name}")
                else:
                    checkbox.uncheck()
                    print(f"   -> [해제] {perm_name}")
                page.wait_for_timeout(300)
        else:
            # ID 매핑이 틀렸거나(그룹추가 vs 그룹변경) 안보일 때 Fallback
            # 원래 '그룹 추가' 팝업은 ID가 다를 수 있으나, 현재 제공된 ID(#edit-auth-...)로 통일됨 가정
            print(f"⚠️ 요소 안 보임: {perm_name} ({target_id})")

def set_permissions_state(page: Page, group_name: str, target_state: dict):
    """그룹 권한 변경"""
    try:
        print(f"[UI] '{group_name}' 권한 변경 시작...")
        
        if not select_group_in_tree(page, group_name): return False
        
        page.locator("#edit-user-btn").click()
        
        try:
            page.wait_for_selector("#edit-group-diag", state="visible", timeout=5000)
        except:
            print("🔥 그룹 변경 팝업 미발견")
            return False

        popup = page.locator(".ui-dialog").filter(has=page.locator("#edit-group-diag"))
        page.wait_for_timeout(1000)

        toggle_permissions(page, popup, target_state)

        confirm_btn = popup.locator(".ui-dialog-buttonset button").first
        page.wait_for_timeout(500)
        
        if confirm_btn.is_enabled():
            confirm_btn.click()
            page.locator("#edit-group-diag").wait_for(state="hidden")
        else:
            print("⚠️ 변경사항 없음. 취소.")
            popup.locator(".ui-dialog-buttonset button").last.click()
        
        page.wait_for_timeout(1000)
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(3)
        return True

    except Exception as e:
        print(f"❌ 권한 설정 오류: {e}")
        return False

# ===========================================================
# 🚀 [메인 테스트 케이스]
# ===========================================================

def run_user_group_test(page: Page, camera_ip: str):
    GROUP = "아이디스"
    UID = "admin123"
    UPW = "qwerty0-"
    DEVICE = "105_T6831"

    print("\n=== [통합 테스트] 권한 제어 시나리오 Start ===")

    # 1. 계정 생성 (생성 시 INITIAL_PERMS 적용됨)
    if not create_group_and_user(page, GROUP, UID, UPW):
        return False, "계정 생성 실패"

    # ⭐️ [API 검증 1] 초기 권한 확인 (Phase 1과 동일해야 함)
    if not verify_permissions_via_api(page, camera_ip, GROUP, INITIAL_PERMS):
        return False, "초기 권한 API 검증 실패"

    # 2. [Phase 1] iRAS 검증
    print("\n🖥️ [Phase 1] iRAS 검증 시작...")
    success_p1, msg_p1 = iRAS_test.run_iras_permission_check(DEVICE, UID, UPW, phase=1)
    if not success_p1: return False, f"Phase 1 iRAS 실패: {msg_p1}"
    print(f"✅ Phase 1 통과: {msg_p1}")

    # 3. [Phase 2] 권한 변경 (설정, 검색 해제)
    print("\n🌐 [Phase 2] 권한 변경 (설정/검색 OFF)...")
    phase2_perms = {
        "클립-카피": False,
        "검색": False,
        "설정": False
    }
    
    if not set_permissions_state(page, GROUP, phase2_perms):
        return False, "Phase 2 권한 설정 실패"

    # ⭐️ [API 검증 2] 변경된 권한 확인
    # Phase 2에서 설정한 권한들이 모두 False(해제)인지 확인
    # (기존에 꺼져있던 업그레이드 등도 여전히 꺼져있어야 하므로 전체 검증 권장)
    full_phase2_perms = INITIAL_PERMS.copy()
    full_phase2_perms.update(phase2_perms) # 설정, 검색 등을 False로 덮어씀
    
    if not verify_permissions_via_api(page, camera_ip, GROUP, full_phase2_perms):
        return False, "Phase 2 권한 API 검증 실패"

    # 4. [Phase 2] iRAS 검증
    success_p2, msg_p2 = iRAS_test.run_iras_permission_check(DEVICE, UID, UPW, phase=2)
    if not success_p2: return False, f"Phase 2 iRAS 실패: {msg_p2}"
    print(f"✅ Phase 2 통과: {msg_p2}")

    return True, "모든 권한 테스트 성공"