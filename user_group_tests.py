import time
from playwright.sync_api import Page
from common_actions import parse_api_response, handle_popup, VISIBLE_DIALOG, DIALOG_BUTTONS
import iRAS_test

# ===========================================================
# ⚙️ [내부 액션 함수] 사용자/그룹 전용
# ===========================================================

def api_get_users_groups(page: Page, ip: str):
    """API로 현재 그룹 및 사용자 목록 조회"""
    group_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=groupSetup&mode=1"
    user_url = f"http://{ip}/cgi-bin/webSetup.cgi?action=userSetup&mode=1"
    
    result = {"groups": [], "users": []}
    
    try:
        resp_text = page.evaluate(f"fetch('{group_url}').then(r => r.text())")
        data = parse_api_response(resp_text)
        cnt = int(data.get("groupCount", 0))
        for i in range(1, cnt + 1):
            result["groups"].append(data.get(f"groupName{i}"))
    except: pass

    try:
        resp_text = page.evaluate(f"fetch('{user_url}').then(r => r.text())")
        data = parse_api_response(resp_text)
        cnt = int(data.get("userCount", 0))
        for i in range(1, cnt + 1):
            result["users"].append({
                "name": data.get(f"user{i}Name"),
                "group": data.get(f"user{i}Group")
            })
    except: pass
    
    return result

def ui_add_group(page: Page, group_name: str):
    """그룹 추가 (모든 권한 해제)"""
    try:
        page.locator("#Page200_id").click() # 시스템
        page.locator("#Page203_id").click() # 사용자/그룹
        page.wait_for_timeout(1000) 

        page.locator("#add-group-btn").click()
        
        # 팝업 대기
        page.wait_for_selector("#edit-gid", state="visible", timeout=5000)

        # 그룹명 입력
        page.locator("#edit-gid").fill(group_name)
        
        # 팝업 컨테이너 찾기 (체크박스 제어를 위해)
        popup = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#edit-gid"))
        
        # 모든 체크박스 해제
        checkboxes = popup.locator("input[type='checkbox']")
        count = checkboxes.count()
        for i in range(count):
            if checkboxes.nth(i).is_checked():
                checkboxes.nth(i).uncheck()
        
        # 확인 버튼 클릭
        popup.locator(DIALOG_BUTTONS).first.click()
        
        # 팝업 닫힘 확인
        page.locator("#edit-gid").wait_for(state="hidden", timeout=3000)
        return True
    except Exception as e:
        print(f"❌ 그룹 추가 실패: {e}")
        return False

def ui_select_group_node(page: Page, group_name: str):
    """트리에서 특정 그룹 이름 클릭"""
    try:
        # 트리 노드 찾기 (a 태그 텍스트 매칭)
        node = page.locator(f"a.dynatree-title:text-is('{group_name}')")
        node.wait_for(state="visible", timeout=5000)
        
        # 강제 클릭
        node.click(force=True)
        page.wait_for_timeout(1000) 
        return True
    except Exception as e:
        print(f"❌ 그룹 선택 실패 ({group_name}): {e}")
        return False

def ui_add_user(page: Page, user_id: str, password: str):
    """사용자 추가 (수정된 ID 적용)"""
    try:
        # 사용자 추가 버튼 클릭
        print("[UI] '사용자 추가' 버튼 클릭...")
        page.locator("#add-user-btn").click()
        
        # ⭐️ [수정됨] 올바른 ID(#add-user-edit-uid)로 대기
        try:
            page.wait_for_selector("#add-user-edit-uid", state="visible", timeout=3000)
        except:
            if handle_popup(page, button_index=0):
                print("⚠️ [UI] 경고창이 떠서 닫았습니다. (그룹 미선택 등)")
                return False
            else:
                print("❌ [UI] 사용자 추가 팝업이 뜨지 않았습니다.")
                return False

        print(f"[UI] 사용자 정보 입력 ({user_id})...")
        
        # ⭐️ [수정됨] HTML 소스 기반 정확한 ID 사용
        page.locator("#add-user-edit-uid").fill(user_id)
        page.locator("#add-user-edit-passwd1").fill(password)
        page.locator("#add-user-edit-passwd2").fill(password)
        
        # 이메일 사용 안함 체크 (ID: add-email_not_use)
        page.locator("#add-email_not_use").check()
        
        # 이메일 경고 팝업 처리 (최상단 팝업 OK 클릭)
        try:
            if page.locator(VISIBLE_DIALOG).count() > 1:
                warning = page.locator(VISIBLE_DIALOG).last
                warning.locator(DIALOG_BUTTONS).first.click()
                warning.wait_for(state="hidden", timeout=2000)
        except: pass
        
        # 확인 버튼 클릭 (사용자 추가 팝업의 OK)
        # #add-user-edit-uid가 있는 팝업의 버튼을 찾음
        add_user_popup = page.locator(VISIBLE_DIALOG).filter(has=page.locator("#add-user-edit-uid"))
        add_user_popup.locator(DIALOG_BUTTONS).first.click()
        
        # 팝업 닫힘 대기
        page.locator("#add-user-edit-uid").wait_for(state="hidden", timeout=3000)
        
        # 저장 버튼 클릭 (최종 반영)
        print("[UI] 최종 저장...")
        page.locator("#setup-apply").click()
        handle_popup(page)
        
        return True
    except Exception as e:
        print(f"❌ 사용자 추가 실패: {e}")
        return False

# ===========================================================
# ⚙️ [테스트 케이스]
# ===========================================================

def run_user_group_test(page: Page, camera_ip: str):
    """
    1. 웹 Admin 접속 -> 그룹/사용자 생성
    2. 생성 성공 시 -> iRAS 데스크톱 앱 실행 -> 생성된 계정으로 로그인/동작 수행
    """
    
    # 테스트 데이터
    GROUP_NAME = "아이디스"
    USER_ID = "admin123"
    USER_PW = "qwerty0-"
    TARGET_DEVICE_NAME = "105_T6831" # iRAS에서 검색할 장치명

    print(f"\n==================================================")
    print(f"   [통합 테스트] 사용자 생성(Web) + 로그인 검증(iRAS)")
    print(f"==================================================\n")
    
    # -------------------------------------------------------
    # [Phase 1] 웹 브라우저 자동화 (계정 생성)
    # -------------------------------------------------------
    print(f"🌐 [Web] 그룹/사용자 생성 시작...")
    
    # 1. 그룹 추가
    if not ui_add_group(page, GROUP_NAME): 
        return False, "Web: 그룹 추가 실패"
    
    # 2. 그룹 선택
    if not ui_select_group_node(page, GROUP_NAME): 
        return False, "Web: 그룹 선택 실패"
    
    # 3. 사용자 추가
    if not ui_add_user(page, USER_ID, USER_PW): 
        return False, "Web: 사용자 추가 실패"
    
    print(f"✅ [Web] 계정 생성 완료 ({USER_ID} / {USER_PW})")
    time.sleep(2) # 저장 반영 대기

    # -------------------------------------------------------
    # [Phase 2] iRAS 데스크톱 자동화 (권한/로그인 검증)
    # -------------------------------------------------------
    print(f"\n🖥️ [System] iRAS 연동 테스트로 진입합니다...")
    
    # iRAS 모듈의 함수 호출 (장치명, 아이디, 비번 전달)
    iras_success, iras_msg = iRAS_test.run_iras_permission_check(
        TARGET_DEVICE_NAME, 
        USER_ID, 
        USER_PW
    )

    if iras_success:
        return True, f"통합 테스트 성공: {iras_msg}"
    else:
        return False, f"iRAS 테스트 실패: {iras_msg}"