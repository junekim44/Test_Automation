import time
from playwright.sync_api import Page
from common_actions import parse_api_response
from iRAS_test import IRASController

# ===========================================================
# ⚙️ [API] 공통 제어 함수 (GET/SET)
# ===========================================================

def _api_get(page, ip, action):
    """API GET 요청"""
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
        else:
            if response_text:
                print(f"   ⚠️ [API GET Error] action={action}, 응답: {response_text[:200]}")
            return None
    except Exception as e:
        print(f"   🔥 [API GET Exception] action={action}, 오류: {e}")
        return None

def _api_set(page, ip, action, params):
    """API SET 요청"""
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
def api_get_action_alarmout(page, ip): 
    """Alarm Out 설정 조회"""
    return _api_get(page, ip, "actionAlarmout")

def api_set_action_alarmout(page, ip, p): 
    """Alarm Out 설정 변경"""
    return _api_set(page, ip, "actionAlarmout", p)

def api_get_action_email(page, ip): 
    """Email 설정 조회"""
    return _api_get(page, ip, "actionEmail")

def api_set_action_email(page, ip, p): 
    """Email 설정 변경"""
    return _api_set(page, ip, "actionEmail", p)

def api_get_event_alarmin(page, ip): 
    """Alarm In 이벤트 설정 조회"""
    return _api_get(page, ip, "eventAlarmin")

def api_set_event_alarmin(page, ip, p): 
    """Alarm In 이벤트 설정 변경"""
    return _api_set(page, ip, "eventAlarmin", p)

def api_get_system_datetime(page, ip): 
    """시스템 시간 조회"""
    return _api_get(page, ip, "dateTime")

def api_set_system_datetime(page, ip, p): 
    """시스템 시간 변경"""
    return _api_set(page, ip, "dateTime", p)

# ===========================================================
# 🧪 [Test] Event Action - Alarm Out
# ===========================================================
def run_alarm_out_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"🚨 [Event Action] Alarm Out Test")
    print("=======================================================")
    
    failed_count = 0
    
    # ---------------------------------------------------------
    # [사전 준비] Alarm In 이벤트 연동 설정
    # ---------------------------------------------------------
    print("\n[사전 준비] Alarm In 이벤트를 Alarm Out과 연동")
    print("   ℹ️  Alarm In 이벤트가 발생하면 Alarm Out이 동작하도록 설정합니다.")
    
    # Alarm In 이벤트 설정 백업
    alarmin_initial_set = api_get_event_alarmin(page, camera_ip)
    if not alarmin_initial_set:
        print("   ⚠️ Alarm In 이벤트 설정 조회 실패")
        print("   ℹ️  카메라가 Alarm In을 지원하지 않을 수 있습니다.")
        return False, "Alarm In 이벤트 설정 조회 실패"
    
    if 'returnCode' in alarmin_initial_set: 
        del alarmin_initial_set['returnCode']
    
    print(f"   ℹ️  현재 Alarm In 설정: {alarmin_initial_set}")
    
    # Alarm In 이벤트 활성화 및 Alarm Out 액션 연동 (NO 상태로 시작)
    alarmin_payload = alarmin_initial_set.copy()
    alarmin_payload['useAlarmIn'] = 'on'  # Alarm In 활성화
    alarmin_payload['alarmType'] = 'no'   # NO (Normally Open) 상태 - 이벤트 미발생
    alarmin_payload['actionAlarmOut'] = 'on'  # Alarm Out 액션 연동
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In 이벤트 연동 완료 (alarmType=no, actionAlarmOut=on)")
    else:
        print("   ❌ Alarm In 이벤트 연동 실패")
        return False, "Alarm In 이벤트 연동 실패"
    
    time.sleep(2)
    
    # Alarm Out 초기 설정 백업
    alarmout_initial_set = api_get_action_alarmout(page, camera_ip)
    if not alarmout_initial_set:
        print("   ⚠️ Alarm Out 설정 조회 실패")
        return False, "Alarm Out 설정 조회 실패"
    
    if 'returnCode' in alarmout_initial_set: 
        del alarmout_initial_set['returnCode']
    
    print(f"   ℹ️  현재 Alarm Out 설정: {alarmout_initial_set}")
    
    # ---------------------------------------------------------
    # [Step 1] Dwell Time 테스트 (5초 동작 확인)
    # ---------------------------------------------------------
    print("\n[Step 1] Dwell Time 테스트 (5초)")
    print("\n" + "="*60)
    print("⚠️  [iRAS Status 창으로 이동]")
    print("    준비되었으면 Enter를 누르세요.")
    print("="*60)
    input(">> 준비되었으면 Enter를 누르세요...")
    print("   ▶️ Dwell Time 테스트를 시작합니다...\n")
    
    # Alarm Out 설정: Dwell Time 5초
    payload = alarmout_initial_set.copy()
    payload['useAlarmOut'] = 'on'
    payload['dwellTime'] = '5'  # 5초
    payload['scheduleStart'] = '00:00'  # 항상 동작
    payload['scheduleEnd'] = '24:00'
    
    if api_set_action_alarmout(page, camera_ip, payload):
        print("   ✅ Alarm Out 설정 완료 (Dwell Time: 5초)")
        
        # 설정 검증
        curr = api_get_action_alarmout(page, camera_ip)
        if curr and curr.get('dwellTime') == '5':
            print(f"   ✅ 설정 검증 완료: dwellTime={curr.get('dwellTime')}초")
        else:
            print(f"   ❌ 설정 검증 실패: dwellTime={curr.get('dwellTime') if curr else 'None'}")
            failed_count += 1
    else:
        print("   ❌ Alarm Out 설정 실패")
        failed_count += 1
        return False, "Alarm Out 설정 실패"
    
    time.sleep(2)
    
    # Alarm In을 NC로 변경하여 이벤트 발생 (API로 제어)
    print("\n   👉 Alarm In을 NC로 변경 (이벤트 발생)")
    alarmin_payload = alarmin_initial_set.copy()
    alarmin_payload['useAlarmIn'] = 'on'
    alarmin_payload['alarmType'] = 'nc'  # NC로 변경 → 이벤트 발생
    alarmin_payload['actionAlarmOut'] = 'on'
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In을 NC로 변경 완료")
        print("   ℹ️  Status 창에서 'Alarm Out' 표시등이 켜지는지 확인하세요.")
        print("   ℹ️  5초 후 자동으로 꺼지는지 확인하세요.")
        
        # 5초 대기 (Dwell Time)
        print("\n   ⏳ Alarm Out 동작 대기 중 (5초)...")
        time.sleep(5)
        
        print("\n   ℹ️  Alarm Out이 5초 동안 켜졌다가 꺼졌나요?")
        print("      - 예 (Y): 정상 동작")
        print("      - 아니오 (N): 비정상 동작")
        user_confirm = input("   >> (Y/N): ").strip().upper()
        
        if user_confirm == 'Y':
            print("   ✅ Pass: Dwell Time 5초 동작 확인됨")
        else:
            print("   ❌ Fail: Dwell Time 5초 동작 확인 실패")
            failed_count += 1
    else:
        print("   ❌ Alarm In NC 변경 실패")
        failed_count += 1
    
    # Alarm In을 NO로 복구
    print("\n   🔄 Alarm In을 NO로 복구 (이벤트 해제)")
    alarmin_payload['alarmType'] = 'no'
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In NO 복구 완료")
        time.sleep(2)
    else:
        print("   ⚠️ Alarm In NO 복구 실패")
    
    # ---------------------------------------------------------
    # [Step 2] Schedule 테스트 (시간대별 동작 확인)
    # ---------------------------------------------------------
    print("\n[Step 2] Schedule 테스트 (시간대별 동작 확인)")
    print("   ℹ️  시작 시간: 12:00 (PM), 종료 시간: 11:45 (AM)")
    print("   ℹ️  → 11:45 ~ 12:00 사이에는 Alarm Out이 동작하지 않아야 합니다.")
    
    # 현재 시스템 시간 백업
    datetime_initial_set = api_get_system_datetime(page, camera_ip)
    if not datetime_initial_set:
        print("   ⚠️ 시스템 시간 조회 실패")
        print("   ℹ️  Schedule 테스트를 건너뜁니다.")
    else:
        if 'returnCode' in datetime_initial_set: 
            del datetime_initial_set['returnCode']
        
        print(f"   ℹ️  현재 시스템 시간: {datetime_initial_set.get('dateTime', 'Unknown')}")
        
        # Alarm Out 스케줄 설정
        payload = alarmout_initial_set.copy()
        payload['useAlarmOut'] = 'on'
        payload['dwellTime'] = '5'
        payload['scheduleStart'] = '12:00'  # PM 12:00
        payload['scheduleEnd'] = '11:45'    # AM 11:45
        
        if api_set_action_alarmout(page, camera_ip, payload):
            print("   ✅ Alarm Out 스케줄 설정 완료 (12:00 ~ 11:45)")
            
            # 설정 검증
            curr = api_get_action_alarmout(page, camera_ip)
            if curr and curr.get('scheduleStart') == '12:00' and curr.get('scheduleEnd') == '11:45':
                print(f"   ✅ 설정 검증 완료: {curr.get('scheduleStart')} ~ {curr.get('scheduleEnd')}")
            else:
                print(f"   ❌ 설정 검증 실패")
                failed_count += 1
        else:
            print("   ❌ Alarm Out 스케줄 설정 실패")
            failed_count += 1
        
        # ---------------------------------------------------------
        # [Step 2-1] 비활성 시간대 테스트 (11:45 ~ 12:00)
        # ---------------------------------------------------------
        print("\n   [Step 2-1] 비활성 시간대 테스트 (11:50)")
        print("   ℹ️  장치 시간을 11:50으로 변경하고 Alarm Out이 동작하지 않는지 확인합니다.")
        
        # 시스템 시간을 11:50으로 변경
        datetime_payload = datetime_initial_set.copy()
        
        # dateTime 형식 확인 (예: "2024-02-05 14:30:00")
        if 'dateTime' in datetime_payload:
            # 현재 날짜 유지, 시간만 11:50:00으로 변경
            current_datetime = datetime_payload['dateTime']
            date_part = current_datetime.split()[0] if ' ' in current_datetime else '2024-01-01'
            datetime_payload['dateTime'] = f"{date_part} 11:50:00"
        else:
            # 개별 필드로 설정 (API에 따라 다를 수 있음)
            datetime_payload['hour'] = '11'
            datetime_payload['minute'] = '50'
            datetime_payload['second'] = '00'
        
        if api_set_system_datetime(page, camera_ip, datetime_payload):
            print("   ✅ 시스템 시간 변경 완료 (11:50)")
            time.sleep(2)
            
            # Alarm In을 NC로 변경하여 이벤트 발생 (API로 제어)
            print("\n   👉 Alarm In을 NC로 변경 (이벤트 발생 시도)")
            alarmin_payload = alarmin_initial_set.copy()
            alarmin_payload['useAlarmIn'] = 'on'
            alarmin_payload['alarmType'] = 'nc'  # NC로 변경
            alarmin_payload['actionAlarmOut'] = 'on'
            
            if api_set_event_alarmin(page, camera_ip, alarmin_payload):
                print("   ✅ Alarm In을 NC로 변경 완료")
                print("   ℹ️  Status 창에서 'Alarm Out' 표시등이 켜지지 않는지 확인하세요.")
                print("      (비활성 시간대이므로 동작하지 않아야 합니다)")
                
                # 잠시 대기
                time.sleep(3)
                
                print("\n   ℹ️  Alarm Out이 동작하지 않았나요?")
                print("      - 예 (Y): 정상 동작 (비활성 시간대)")
                print("      - 아니오 (N): 비정상 동작 (켜졌음)")
                user_confirm = input("   >> (Y/N): ").strip().upper()
                
                if user_confirm == 'Y':
                    print("   ✅ Pass: 비활성 시간대에서 Alarm Out 동작하지 않음")
                else:
                    print("   ❌ Fail: 비활성 시간대에서 Alarm Out이 동작함")
                    failed_count += 1
            else:
                print("   ❌ Alarm In NC 변경 실패")
                failed_count += 1
            
            # Alarm In을 NO로 복구
            print("\n   🔄 Alarm In을 NO로 복구")
            alarmin_payload['alarmType'] = 'no'
            if api_set_event_alarmin(page, camera_ip, alarmin_payload):
                print("   ✅ Alarm In NO 복구 완료")
                time.sleep(2)
            else:
                print("   ⚠️ Alarm In NO 복구 실패")
        else:
            print("   ❌ 시스템 시간 변경 실패")
            failed_count += 1
        
        # ---------------------------------------------------------
        # [Step 2 복구] 시스템 시간 복구
        # ---------------------------------------------------------
        print("\n   🔄 Step 2 복구: 시스템 시간 복구")
        if api_set_system_datetime(page, camera_ip, datetime_initial_set):
            print("   ✅ 시스템 시간 복구 완료")
            time.sleep(2)
        else:
            print("   ⚠️ 시스템 시간 복구 실패 (수동으로 확인 필요)")
    
    # ---------------------------------------------------------
    # [최종 복구] Alarm Out 및 Alarm In 설정 복구
    # ---------------------------------------------------------
    print("\n   🔄 최종 복구: Alarm Out 및 Alarm In 설정 복구")
    
    # Alarm Out 복구
    if api_set_action_alarmout(page, camera_ip, alarmout_initial_set):
        print("   ✅ Alarm Out 설정 복구 완료")
    else:
        print("   ⚠️ Alarm Out 설정 복구 실패")
    
    # Alarm In 복구
    if api_set_event_alarmin(page, camera_ip, alarmin_initial_set):
        print("   ✅ Alarm In 이벤트 설정 복구 완료")
    else:
        print("   ⚠️ Alarm In 이벤트 설정 복구 실패")
    
    time.sleep(2)
    
    # ---------------------------------------------------------
    # [최종 결과]
    # ---------------------------------------------------------
    if failed_count == 0: 
        return True, "Alarm Out Test 성공"
    else: 
        return False, f"Alarm Out Test 실패 ({failed_count}건)"

# ===========================================================
# 🧪 [Test] Event Action - Email
# ===========================================================
def run_email_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"📧 [Event Action] Email Test")
    print("=======================================================")
    
    failed_count = 0
    
    # ---------------------------------------------------------
    # [사전 준비] 사용자로부터 Email 설정 정보 입력받기
    # ---------------------------------------------------------
    print("\n[사전 준비] Email 설정 정보 입력")
    print("   ℹ️  SMTP 서버: gw.idis.co.kr (고정)")
    print("   ℹ️  포트: 25 (고정)")
    print("   ℹ️  SSL/STARTTLS: 사용 안 함 (고정)")
    print("")
    
    # 사용자 입력
    smtp_id = input("   👉 SMTP 인증 ID를 입력하세요: ").strip()
    smtp_pw = input("   👉 SMTP 인증 PW를 입력하세요: ").strip()
    sender_email = input("   👉 보내는 사람 이메일을 입력하세요: ").strip()
    recipient_email = input("   👉 받는 사람 이메일을 입력하세요: ").strip()
    
    if not smtp_id or not smtp_pw or not sender_email or not recipient_email:
        print("   ❌ 필수 정보가 입력되지 않았습니다.")
        return False, "Email 설정 정보 입력 실패"
    
    print(f"\n   ✅ 입력 완료:")
    print(f"      - SMTP ID: {smtp_id}")
    print(f"      - SMTP PW: {'*' * len(smtp_pw)}")
    print(f"      - 보내는 사람: {sender_email}")
    print(f"      - 받는 사람: {recipient_email}")
    
    # ---------------------------------------------------------
    # [Step 1] Email 설정 구성
    # ---------------------------------------------------------
    print("\n[Step 1] Email 설정 구성")
    
    # Email 초기 설정 백업
    email_initial_set = api_get_action_email(page, camera_ip)
    if not email_initial_set:
        print("   ⚠️ Email 설정 조회 실패")
        return False, "Email 설정 조회 실패"
    
    if 'returnCode' in email_initial_set: 
        del email_initial_set['returnCode']
    
    print(f"   ℹ️  현재 Email 설정: {email_initial_set}")
    
    # Email 설정 변경
    email_payload = email_initial_set.copy()
    email_payload['useEmail'] = 'on'
    email_payload['smtpServer'] = 'gw.idis.co.kr'
    email_payload['smtpPort'] = '25'
    email_payload['useSSLTLS'] = 'off'
    email_payload['id'] = smtp_id
    email_payload['password'] = smtp_pw
    email_payload['sender'] = sender_email
    email_payload['recipientList'] = recipient_email
    
    if api_set_action_email(page, camera_ip, email_payload):
        print("   ✅ Email 설정 완료")
        
        # 설정 검증
        curr = api_get_action_email(page, camera_ip)
        if curr and curr.get('useEmail') == 'on':
            print(f"   ✅ 설정 검증 완료: useEmail={curr.get('useEmail')}")
            print(f"      - SMTP 서버: {curr.get('smtpServer')}")
            print(f"      - SMTP 포트: {curr.get('smtpPort')}")
            print(f"      - 보내는 사람: {curr.get('sender')}")
            print(f"      - 받는 사람: {curr.get('recipientList')}")
        else:
            print(f"   ❌ 설정 검증 실패: useEmail={curr.get('useEmail') if curr else 'None'}")
            failed_count += 1
    else:
        print("   ❌ Email 설정 실패")
        failed_count += 1
        return False, "Email 설정 실패"
    
    time.sleep(2)
    
    # ---------------------------------------------------------
    # [Step 2] Alarm In 이벤트와 Email 액션 연동
    # ---------------------------------------------------------
    print("\n[Step 2] Alarm In 이벤트와 Email 액션 연동")
    
    # Alarm In 이벤트 설정 백업
    alarmin_initial_set = api_get_event_alarmin(page, camera_ip)
    if not alarmin_initial_set:
        print("   ⚠️ Alarm In 이벤트 설정 조회 실패")
        return False, "Alarm In 이벤트 설정 조회 실패"
    
    if 'returnCode' in alarmin_initial_set: 
        del alarmin_initial_set['returnCode']
    
    # Alarm In 이벤트 활성화 및 Email 액션 연동 (NO 상태로 시작)
    alarmin_payload = alarmin_initial_set.copy()
    alarmin_payload['useAlarmIn'] = 'on'
    alarmin_payload['alarmType'] = 'no'   # NO (Normally Open) 상태
    alarmin_payload['actionEmail'] = 'on'  # Email 액션 연동
    alarmin_payload['actionEmailAttachImage'] = 'off'  # 이미지 첨부는 off (빠른 테스트를 위해)
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In 이벤트 연동 완료 (alarmType=no, actionEmail=on)")
    else:
        print("   ❌ Alarm In 이벤트 연동 실패")
        failed_count += 1
        return False, "Alarm In 이벤트 연동 실패"
    
    time.sleep(2)
    
    # ---------------------------------------------------------
    # [Step 3] Email 전송 테스트 (Alarm In 이벤트 발생)
    # ---------------------------------------------------------
    print("\n[Step 3] Email 전송 테스트")
    print("   ℹ️  Alarm In을 NC로 변경하여 이벤트를 발생시키고 이메일을 전송합니다.")
    
    # Alarm In을 NC로 변경하여 이벤트 발생
    print("\n   👉 Alarm In을 NC로 변경 (이벤트 발생 → Email 전송)")
    alarmin_payload['alarmType'] = 'nc'  # NC로 변경 → 이벤트 발생
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In을 NC로 변경 완료")
        print(f"   ℹ️  이메일이 {recipient_email}로 전송되었을 것입니다.")
        print("   ℹ️  받은 편지함을 확인해주세요.")
        
        # 이메일 전송 대기
        print("\n   ⏳ 이메일 전송 대기 중 (5초)...")
        time.sleep(5)
        
        print("\n   ℹ️  이메일을 받으셨나요?")
        print(f"      - 받는 사람: {recipient_email}")
        print(f"      - 보낸 사람: {sender_email}")
        print("      - 예 (Y): 정상 동작")
        print("      - 아니오 (N): 비정상 동작")
        user_confirm = input("   >> (Y/N): ").strip().upper()
        
        if user_confirm == 'Y':
            print("   ✅ Pass: Email 전송 성공")
        else:
            print("   ❌ Fail: Email 전송 실패")
            print("   ℹ️  Tip: SMTP 설정을 확인하거나 스팸 폴더를 확인해보세요.")
            failed_count += 1
    else:
        print("   ❌ Alarm In NC 변경 실패")
        failed_count += 1
    
    # Alarm In을 NO로 복구
    print("\n   🔄 Alarm In을 NO로 복구 (이벤트 해제)")
    alarmin_payload['alarmType'] = 'no'
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In NO 복구 완료")
        time.sleep(2)
    else:
        print("   ⚠️ Alarm In NO 복구 실패")
    
    # ---------------------------------------------------------
    # [최종 복구] Email 및 Alarm In 설정 복구
    # ---------------------------------------------------------
    print("\n   🔄 최종 복구: Email 및 Alarm In 설정 복구")
    
    # Email 복구
    if api_set_action_email(page, camera_ip, email_initial_set):
        print("   ✅ Email 설정 복구 완료")
    else:
        print("   ⚠️ Email 설정 복구 실패")
    
    # Alarm In 복구
    if api_set_event_alarmin(page, camera_ip, alarmin_initial_set):
        print("   ✅ Alarm In 이벤트 설정 복구 완료")
    else:
        print("   ⚠️ Alarm In 이벤트 설정 복구 실패")
    
    time.sleep(2)
    
    # ---------------------------------------------------------
    # [최종 결과]
    # ---------------------------------------------------------
    if failed_count == 0: 
        return True, "Email Test 성공"
    else: 
        return False, f"Email Test 실패 ({failed_count}건)"
