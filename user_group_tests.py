import time
from playwright.sync_api import Page
from common_actions import handle_popup, VISIBLE_DIALOG, DIALOG_BUTTONS
import iRAS_test

# ===========================================================
# 📋 [설정] ID 및 API 매핑
# ===========================================================

# 1. 그룹 생성 (Add) 팝업용 ID
ADD_ID_MAP = {
    "NAME_INPUT": "#edit-gid",
    "PERMS": {
        "업그레이드": "#auth-upgrade",
        "설정": "#auth-setup",
        "컬러 조정": "#auth-color",
        "PTZ 제어": "#auth-ptz",
        "알람-아웃 제어": "#auth-alarm",
        "검색": "#auth-search",
        "클립-카피": "#auth-clipcopy"
    }
}

# 2. 그룹 변경 (Edit) 팝업용 ID
EDIT_ID_MAP = {
    "NAME_INPUT": "#edit-auth-gid",
    "PERMS": {
        "업그레이드": "#edit-auth-upgrade",
        "설정": "#edit-auth-setup",
        "컬러 조정": "#edit-auth-color",
        "PTZ 제어": "#edit-auth-ptz",
        "알람-아웃 제어": "#edit-auth-alarm",
        "검색": "#edit-auth-search",
        "클립-카피": "#edit-auth-clipcopy"
    }
}

# 3. API 검증용 매핑
UI_TO_API_MAP = {
    "업그레이드": "upgrade",
    "설정": "setup",
    "컬러 조정": "color",
    "PTZ 제어": "ptz",
    "알람-아웃 제어": "alarmOut",
    "검색": "search",
    "클립-카피": "clipCopy"
}

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
# 📡 [API] 검증 함수 (권한 확인 / 삭제 확인)
# ===========================================================

def get_api_data(page: Page, ip: str):
    """API 데이터를 가져와서 딕셔너리로 반환"""
    api_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=groupSetup&mode=1"
    try:
        resp_text = page.evaluate(f"fetch('{api_url}').then(r => r.text())")
        return dict(item.split("=", 1) for item in resp_text.strip().split("&") if "=" in item)
    except Exception as e:
        print(f"   🔥 [API] Fetch 실패: {e}")
        return {}

def verify_permissions_via_api(page: Page, ip: str, group_name: str, expected_perms: dict):
    """API를 통해 실제 권한이 적용되었는지 교차 검증"""
    print(f"   📡 [API] '{group_name}' 권한 실제 적용 여부 확인 중...")
    data = get_api_data(page, ip)
    
    count = int(data.get("groupCount", 0))
    target_idx = -1
    for i in range(1, count + 1):
        if data.get(f"groupName{i}") == group_name:
            target_idx = i
            break
    
    if target_idx == -1:
        print(f"   ❌ [API] 그룹 '{group_name}'을 찾을 수 없습니다.")
        return False

    auth_str = data.get(f"authorities{target_idx}", "")
    current_apis = auth_str.split("|") if auth_str else []
    
    is_valid = True
    for ui_name, should_have in expected_perms.items():
        api_name = UI_TO_API_MAP.get(ui_name)
        if not api_name: continue
        
        has_perm = api_name in current_apis
        if should_have != has_perm:
            print(f"   ❌ [Mismatch] {ui_name}({api_name}) -> 기대: {should_have}, 실제: {has_perm}")
            is_valid = False
            
    if is_valid:
        print(f"   ✅ [API] 권한 검증 통과 (API: {auth_str})")
        return True
    return False

def verify_group_absence_via_api(page: Page, ip: str, group_name: str):
    """API를 통해 그룹이 실제로 삭제되었는지 확인 (Absence Check)"""
    print(f"   📡 [API] '{group_name}' 삭제 여부 확인 중...")
    data = get_api_data(page, ip)
    
    count = int(data.get("groupCount", 0))
    found = False
    for i in range(1, count + 1):
        if data.get(f"groupName{i}") == group_name:
            found = True
            break
            
    if found:
        print(f"   ❌ [API] 그룹 '{group_name}'이(가) 여전히 존재합니다!")
        return False
    else:
        print(f"   ✅ [API] 그룹 삭제 확인 완료 (목록에 없음)")
        return True

# ===========================================================
# ⚙️ [Helper] UI 제어
# ===========================================================
def toggle_permissions(popup, id_map, target_state, page):
    for perm_name, should_check in target_state.items():
        target_id = id_map.get(perm_name)
        if not target_id: continue
        checkbox = popup.locator(target_id)
        if checkbox.is_visible():
            if checkbox.is_checked() != should_check:
                page.wait_for_timeout(300) 
                if should_check:
                    checkbox.check()
                    print(f"   -> [체크] {perm_name}")
                else:
                    checkbox.uncheck()
                    print(f"   -> [해제] {perm_name}")
                page.wait_for_timeout(300)

def select_group_in_tree(page: Page, group_name: str):
    """좌측 트리에서 그룹 선택"""
    try:
        node = page.locator(f"a.dynatree-title:text-is('{group_name}')")
        if node.count() == 0: return False
        node.click(force=True)
        page.wait_for_timeout(500) 
        return True
    except: return False

def select_user(page: Page, uid: str):
    """사용자 선택 (트리 노드 우선 검색)"""
    # 1. 트리 노드 (a.dynatree-title)에서 검색
    user_tree_node = page.locator(f"a.dynatree-title:text-is('{uid}')")
    
    try:
        # 트리 노드가 보이면 클릭
        if user_tree_node.is_visible():
            print(f"   -> [Tree] 트리에서 사용자 '{uid}' 발견 및 클릭")
            user_tree_node.click()
            page.wait_for_timeout(300)
            return True
        
        # 2. 우측 리스트 (td)에서 검색 (Fallback)
        user_cell = page.locator(f"td:text-is('{uid}')")
        if user_cell.is_visible():
            print(f"   -> [List] 리스트에서 사용자 '{uid}' 발견 및 클릭")
            user_cell.click()
            page.wait_for_timeout(300)
            return True
            
    except Exception as e:
        print(f"⚠️ 사용자 선택 중 예외 발생: {e}")
        
    return False

# ===========================================================
# 🛠️ [기능] 생성 / 이동 / 삭제
# ===========================================================

def create_group_only(page: Page, group_name: str):
    """그룹만 생성"""
    if select_group_in_tree(page, group_name):
        print(f"ℹ️ 그룹 '{group_name}' 이미 존재.")
        return True
        
    print(f"[UI] 그룹 '{group_name}' 생성...")
    
    page.locator("#add-group-btn").click()
    input_id = ADD_ID_MAP["NAME_INPUT"]
    try:
        page.wait_for_selector(input_id, state="visible", timeout=3000)
    except:
        print("❌ 그룹 생성 팝업 안 뜸")
        return False

    group_dialog = page.locator(".ui-dialog").filter(has=page.locator(input_id))
    page.locator(input_id).fill(group_name)
    toggle_permissions(group_dialog, ADD_ID_MAP["PERMS"], INITIAL_PERMS, page)

    group_dialog.locator(".ui-dialog-buttonset button").first.click()
    page.locator(input_id).wait_for(state="hidden")
    page.wait_for_timeout(1000)
    
    # 저장
    page.locator("#setup-apply").click()
    handle_popup(page)
    time.sleep(1)
    return True

def create_group_and_user(page: Page, group_name: str, uid: str, upw: str):
    """그룹 및 사용자 생성"""
    try:
        print(f"[UI] 계정 생성 프로세스 시작 ({group_name})...")
        
        # 1. 그룹 생성
        create_group_only(page, group_name)

        # 2. 사용자 생성
        select_group_in_tree(page, group_name)
        print(f"[UI] 사용자 '{uid}' 생성 시도...")
        page.locator("#add-user-btn").click()
        page.wait_for_selector("#add-user-edit-uid", state="visible", timeout=3000)
        
        user_dialog = page.locator(".ui-dialog").filter(has=page.locator("#add-user-edit-uid"))
        page.locator("#add-user-edit-uid").fill(uid)
        page.locator("#add-user-edit-passwd1").fill(upw)
        page.locator("#add-user-edit-passwd2").fill(upw)
        
        # 이메일 없음 체크
        user_dialog.locator("#add-email_not_use").check()
        page.wait_for_timeout(1000) 
        
        # [Fix] 방해하는 팝업 처리
        blocking_msg = page.locator(".ui-dialog[aria-describedby='msg-dialog-ok']:visible")
        if blocking_msg.count() > 0:
            print("   -> [Popup] 메시지 경고창 발견. 닫기.")
            blocking_msg.locator(".ui-dialog-buttonset button").first.click()
            page.wait_for_timeout(500)
            
        elif page.locator(".ui-dialog:visible").count() > 1:
            top_dlg = page.locator(".ui-dialog:visible").last
            if top_dlg.locator("#add-user-edit-uid").count() == 0:
                print("   -> [Popup] 알 수 없는 상단 팝업 발견. 닫기.")
                btn = top_dlg.locator(".ui-dialog-buttonset button").first
                if btn.is_visible(): btn.click(force=True)
                else: top_dlg.locator("button").first.click(force=True)
                page.wait_for_timeout(500)

        # 사용자 생성 확인
        user_confirm_btn = user_dialog.locator(".ui-dialog-buttonset button").first
        if user_confirm_btn.is_enabled():
            user_confirm_btn.click()
            page.locator("#add-user-edit-uid").wait_for(state="hidden")
        else:
            print(f"ℹ️ 사용자 중복/오류. 취소.")
            user_dialog.locator(".ui-dialog-buttonset button").last.click()

        print("[UI] 설정 저장...")
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(2)
        return True
    except Exception as e:
        print(f"❌ 생성 오류: {e}")
        return False

def move_user_to_group(page: Page, uid: str, current_group: str, target_group: str):
    """사용자 소속 그룹 이동"""
    print(f"\n📦 [Move] 사용자 '{uid}' 이동: {current_group} -> {target_group}")
    try:
        # 1. 사용자 바로 선택
        print(f"   -> 사용자 '{uid}' 바로 선택 시도...")
        page.wait_for_timeout(1000)
        
        if not select_user(page, uid):
            print(f"❌ 사용자 '{uid}' 찾을 수 없음 (트리/목록 모두 확인)")
            return False
            
        # 2. 수정 버튼 클릭
        page.locator("#edit-user-btn").click()

        target_selector = "#edit-user-edit-ugroup"
        
        try:
            page.wait_for_selector(target_selector, state="visible", timeout=3000)
        except:
            print(f"❌ 사용자 수정 팝업 요소를 찾을 수 없음 ({target_selector})")
            return False
            
        edit_dialog = page.locator(".ui-dialog").filter(has=page.locator(target_selector))
        
        # 3. 그룹 변경
        try:
            # [Fix] 중복 ID 문제 해결: .first 사용
            group_select = edit_dialog.locator(target_selector).first 
            group_select.select_option(label=target_group)
            print(f"   -> 그룹 드롭다운 변경 완료 ({target_group})")
            
        except Exception as e:
            print(f"❌ 그룹 선택 실패: {e}")
            edit_dialog.locator(".ui-dialog-buttonset button").last.click() # 취소
            return False

        # 4. 저장
        edit_dialog.locator(".ui-dialog-buttonset button").first.click() # 확인
        
        # 사라짐 대기 (타겟 요소 기준)
        page.locator(target_selector).first.wait_for(state="hidden")
        
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(2)
        return True
        
    except Exception as e:
        print(f"❌ 이동 오류: {e}")
        return False

def delete_group_and_user(page: Page, group_name: str, uid: str = None):
    """그룹 및 (선택적) 사용자 삭제"""
    try:
        print(f"\n🗑️ [Delete] 그룹 '{group_name}' 삭제 시도...")
        
        # 삭제 시에는 그룹을 먼저 선택해야 함 (트리에서)
        if not select_group_in_tree(page, group_name):
            print("ℹ️ 삭제할 그룹이 이미 없습니다.")
            return True

        # 사용자가 지정되었다면 사용자 먼저 삭제
        if uid:
            page.wait_for_timeout(1000)
            if select_user(page, uid):
                print(f"   -> 사용자 '{uid}' 삭제 중...")
                # [수정] ID 변경: #del-user-btn -> #remove-user-btn
                page.locator("#remove-user-btn").click()
                handle_popup(page) # '삭제하시겠습니까?' 확인
                page.wait_for_timeout(500)
            else:
                print(f"ℹ️ 사용자 '{uid}' 없음 (이미 삭제됨?)")

        # 그룹 삭제
        print(f"   -> 그룹 '{group_name}' 삭제 중...")
        select_group_in_tree(page, group_name) # 포커스 확인
        page.locator("#remove-user-btn").click()
        
        # 그룹 삭제 확인 팝업
        handle_popup(page) 
        
        # 저장
        print("   -> 변경사항 적용 중...")
        page.locator("#setup-apply").click()
        handle_popup(page)
        time.sleep(2)
        
        return True
    except Exception as e:
        print(f"❌ 삭제 실패: {e}")
        return False

# ===========================================================
# 🚀 [메인 테스트 케이스]
# ===========================================================

def run_user_group_test(page: Page, camera_ip: str, admin_id: str, admin_pw: str):
    GROUP_A = "아이디스_A"
    GROUP_B = "아이디스_B"
    UID = "testuser1"
    UPW = "qwerty0-"
    DEVICE = "105_T6831"

    print("\n=== [통합 테스트] 그룹/사용자 관리 및 API 검증 Start ===")
    
    # 설정 메뉴 진입
    page.locator("#Page200_id").click()
    page.wait_for_timeout(500)
    page.locator("#Page203_id").click()
    page.wait_for_timeout(1000)

    # 1. 그룹 A 및 사용자 생성
    if not create_group_and_user(page, GROUP_A, UID, UPW):
        return False, "그룹A/사용자 생성 실패"
    
    # 2. 그룹 B 생성 (빈 그룹)
    if not create_group_only(page, GROUP_B):
        return False, "그룹B 생성 실패"

    # ⭐️ [API 검증 1] 그룹 A, B 존재 확인
    if not verify_permissions_via_api(page, camera_ip, GROUP_A, INITIAL_PERMS):
        return False, "그룹 A API 검증 실패"

    # -------------------------------------------------------
    # 🔄 [Refresh] UI 갱신 (사용자 목록 노출 보장)
    # -------------------------------------------------------
    print("\n🔄 [Refresh] UI 동기화를 위해 페이지 새로고침...")
    page.reload()
    page.wait_for_timeout(2000)

    print("   -> 사용자/그룹 설정 메뉴 재진입...")
    try:
        # 설정 메뉴 -> 사용자/그룹 메뉴 클릭
        page.locator("#Page200_id").wait_for(state="visible", timeout=5000)
        page.locator("#Page200_id").click()
        page.wait_for_timeout(500)
        page.locator("#Page203_id").click()
        page.wait_for_timeout(1500)
    except Exception as e:
        return False, f"메뉴 재진입 실패: {e}"

    # 3. [Move] 사용자 이동 (A -> B)
    if not move_user_to_group(page, UID, GROUP_A, GROUP_B):
        return False, "사용자 이동 실패"
    
    # 4. [Delete] 빈 그룹 A 삭제
    # 사용자가 이동했으므로 A는 비어있어야 함 (uid=None으로 그룹만 삭제 시도)
    if not delete_group_and_user(page, GROUP_A, uid=None):
        return False, "빈 그룹 A 삭제 실패"

    # ⭐️ [API 검증 2] 그룹 A 삭제 확인 (Absence Check)
    if not verify_group_absence_via_api(page, camera_ip, GROUP_A):
        return False, "그룹 A 삭제 API 검증 실패 (여전히 존재함)"

    # 5. [iRAS] 이동된 사용자로 로그인 테스트 (선택 사항, 여기선 Phase 1만 수행)
    print("\n🖥️ [iRAS] 이동된 사용자 로그인 테스트...")
    success_p1, msg_p1 = iRAS_test.run_iras_permission_check(DEVICE, UID, UPW, phase=1)
    if not success_p1: 
        print(f"⚠️ iRAS 로그인 실패: {msg_p1}")
        # 실패해도 삭제 로직은 수행
    else:
        print(f"✅ iRAS 로그인 성공: {msg_p1}")

    # 6. [Cleanup] 그룹 B 및 사용자 삭제
    print("\n🧹 [Cleanup] 테스트 데이터 정리...")
    if not delete_group_and_user(page, GROUP_B, UID):
        return False, "Cleanup(그룹B) 실패"

    # ⭐️ [API 검증 3] 그룹 B 삭제 확인
    if not verify_group_absence_via_api(page, camera_ip, GROUP_B):
        return False, "Cleanup API 검증 실패 (그룹B 잔존)"

    # 🔄 [Final] 관리자 로그인 복구
    print("\n🔄 [Final] 관리자 로그인 복구 수행...")
    if iRAS_test.restore_admin_login(DEVICE, admin_id, admin_pw):
        print("✅ 복구 완료")
    else:
        print("⚠️ 복구 실패")

    return True, "그룹/사용자 관리 시나리오 성공"