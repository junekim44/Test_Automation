import time
from playwright.sync_api import Page
from common_actions import parse_api_response
from iRAS_test import IRASController

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
            return None
    except Exception:
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
            return False
    except Exception:
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

def api_get_action_ftp(page, ip): 
    """FTP 설정 조회"""
    return _api_get(page, ip, "actionFtp")

def api_set_action_ftp(page, ip, p): 
    """FTP 설정 변경"""
    return _api_set(page, ip, "actionFtp", p)

def api_get_action_record(page, ip): 
    """SD Recording 설정 조회"""
    return _api_get(page, ip, "actionRecord")

def api_set_action_record(page, ip, p): 
    """SD Recording 설정 변경"""
    return _api_set(page, ip, "actionRecord", p)

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
    
    print("\n[사전 준비] Alarm In 이벤트를 Alarm Out과 연동")
    
    alarmin_initial_set = api_get_event_alarmin(page, camera_ip)
    if not alarmin_initial_set:
        print_warning("Alarm In 이벤트 설정 조회 실패 (카메라가 지원하지 않을 수 있음)")
        return False, "Alarm In 이벤트 설정 조회 실패"
    
    if 'returnCode' in alarmin_initial_set: 
        del alarmin_initial_set['returnCode']
    
    alarmin_payload = alarmin_initial_set.copy()
    alarmin_payload['useAlarmIn'] = 'on'
    alarmin_payload['alarmType'] = 'no'
    alarmin_payload['actionAlarmOut'] = 'on'
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print_success("Alarm In 이벤트 연동 완료 (alarmType=no, actionAlarmOut=on)")
    else:
        print_error("Alarm In 이벤트 연동 실패")
        return False, "Alarm In 이벤트 연동 실패"
    
    time.sleep(2)
    
    alarmout_initial_set = api_get_action_alarmout(page, camera_ip)
    if not alarmout_initial_set:
        print_warning("Alarm Out 설정 조회 실패")
        return False, "Alarm Out 설정 조회 실패"
    
    if 'returnCode' in alarmout_initial_set: 
        del alarmout_initial_set['returnCode']
    
    print_step(1, 2, "Dwell Time 테스트 (5초)")
    print("\n" + "="*60)
    print("⚠️  [iRAS Status 창으로 이동]")
    print("    준비되었으면 Enter를 누르세요.")
    print("="*60)
    input(">> 준비되었으면 Enter를 누르세요...")
    
    payload = alarmout_initial_set.copy()
    payload['useAlarmOut'] = 'on'
    payload['dwellTime'] = '5'
    payload['scheduleStart'] = '00:00'
    payload['scheduleEnd'] = '24:00'
    
    if api_set_action_alarmout(page, camera_ip, payload):
        print_success("Alarm Out 설정 완료 (Dwell Time: 5초)")
        
        curr = api_get_action_alarmout(page, camera_ip)
        if curr and curr.get('dwellTime') == '5':
            print_success(f"설정 검증 완료: dwellTime={curr.get('dwellTime')}초")
        else:
            print_error(f"설정 검증 실패")
            failed_count += 1
    else:
        print_error("Alarm Out 설정 실패")
        failed_count += 1
        return False, "Alarm Out 설정 실패"
    
    time.sleep(2)
    
    print_action("Alarm In을 NC로 변경 (이벤트 발생)")
    alarmin_payload = alarmin_initial_set.copy()
    alarmin_payload['useAlarmIn'] = 'on'
    alarmin_payload['alarmType'] = 'nc'
    alarmin_payload['actionAlarmOut'] = 'on'
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print_success("Alarm In NC 변경 완료")
        print("   ℹ️  Status 창에서 'Alarm Out' 표시등이 5초간 켜지는지 확인하세요")
        
        print_action("Alarm Out 동작 대기 중 (5초)...")
        time.sleep(5)
        
        print("\n   ℹ️  Alarm Out이 5초 동안 켜졌다가 꺼졌나요?")
        print("      - 예 (Y): 정상 동작")
        print("      - 아니오 (N): 비정상 동작")
        user_confirm = input("   >> (Y/N): ").strip().upper()
        
        if user_confirm == 'Y':
            print_success("Dwell Time 5초 동작 확인됨")
        else:
            print_error("Dwell Time 5초 동작 확인 실패")
            failed_count += 1
    else:
        print_error("Alarm In NC 변경 실패")
        failed_count += 1
    
    print_action("Alarm In을 NO로 복구 중...")
    alarmin_payload['alarmType'] = 'no'
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print_success("Alarm In NO 복구 완료")
        time.sleep(2)
    else:
        print_warning("Alarm In NO 복구 실패")
    
    print_step(2, 2, "Schedule 테스트 (시간대별 동작 확인)")
    print("   ℹ️  스케줄: 12:00 ~ 11:45 (11:45~12:00는 비활성)")
    
    datetime_initial_set = api_get_system_datetime(page, camera_ip)
    if not datetime_initial_set:
        print_warning("시스템 시간 조회 실패 - Schedule 테스트를 건너뜁니다")
    else:
        if 'returnCode' in datetime_initial_set: 
            del datetime_initial_set['returnCode']
        
        payload = alarmout_initial_set.copy()
        payload['useAlarmOut'] = 'on'
        payload['dwellTime'] = '5'
        payload['scheduleStart'] = '12:00'
        payload['scheduleEnd'] = '11:45'
        
        if api_set_action_alarmout(page, camera_ip, payload):
            print_success("Alarm Out 스케줄 설정 완료 (12:00 ~ 11:45)")
            
            curr = api_get_action_alarmout(page, camera_ip)
            if curr and curr.get('scheduleStart') == '12:00' and curr.get('scheduleEnd') == '11:45':
                print_success(f"설정 검증 완료: {curr.get('scheduleStart')} ~ {curr.get('scheduleEnd')}")
            else:
                print_error("설정 검증 실패")
                failed_count += 1
        else:
            print_error("Alarm Out 스케줄 설정 실패")
            failed_count += 1
        
        print("\n   [Step 2-1] 비활성 시간대 테스트 (11:50)")
        
        datetime_payload = datetime_initial_set.copy()
        
        if 'dateTime' in datetime_payload:
            current_datetime = datetime_payload['dateTime']
            date_part = current_datetime.split()[0] if ' ' in current_datetime else '2024-01-01'
            datetime_payload['dateTime'] = f"{date_part} 11:50:00"
        else:
            datetime_payload['hour'] = '11'
            datetime_payload['minute'] = '50'
            datetime_payload['second'] = '00'
        
        if api_set_system_datetime(page, camera_ip, datetime_payload):
            print_success("시스템 시간 변경 완료 (11:50)")
            time.sleep(2)
            
            print_action("Alarm In을 NC로 변경 (이벤트 발생 시도)")
            alarmin_payload = alarmin_initial_set.copy()
            alarmin_payload['useAlarmIn'] = 'on'
            alarmin_payload['alarmType'] = 'nc'
            alarmin_payload['actionAlarmOut'] = 'on'
            
            if api_set_event_alarmin(page, camera_ip, alarmin_payload):
                print_success("Alarm In NC 변경 완료")
                print("   ℹ️  Status 창에서 Alarm Out이 켜지지 않는지 확인하세요 (비활성 시간대)")
                
                time.sleep(3)
                
                print("\n   ℹ️  Alarm Out이 동작하지 않았나요?")
                print("      - 예 (Y): 정상 동작 (비활성 시간대)")
                print("      - 아니오 (N): 비정상 동작 (켜졌음)")
                user_confirm = input("   >> (Y/N): ").strip().upper()
                
                if user_confirm == 'Y':
                    print_success("비활성 시간대에서 Alarm Out 동작하지 않음")
                else:
                    print_error("비활성 시간대에서 Alarm Out이 동작함")
                    failed_count += 1
            else:
                print_error("Alarm In NC 변경 실패")
                failed_count += 1
            
            print_action("Alarm In을 NO로 복구 중...")
            alarmin_payload['alarmType'] = 'no'
            if api_set_event_alarmin(page, camera_ip, alarmin_payload):
                print_success("Alarm In NO 복구 완료")
                time.sleep(2)
            else:
                print_warning("Alarm In NO 복구 실패")
        else:
            print_error("시스템 시간 변경 실패")
            failed_count += 1
        
        print_action("시스템 시간 복구 중...")
        if api_set_system_datetime(page, camera_ip, datetime_initial_set):
            print_success("시스템 시간 복구 완료")
            time.sleep(2)
        else:
            print_warning("시스템 시간 복구 실패 (수동으로 확인 필요)")
    
    print("\n[최종 복구] Alarm Out 및 Alarm In 설정 복구")
    
    if api_set_action_alarmout(page, camera_ip, alarmout_initial_set):
        print_success("Alarm Out 설정 복구 완료")
    else:
        print_warning("Alarm Out 설정 복구 실패")
    
    if api_set_event_alarmin(page, camera_ip, alarmin_initial_set):
        print_success("Alarm In 이벤트 설정 복구 완료")
    else:
        print_warning("Alarm In 이벤트 설정 복구 실패")
    
    time.sleep(2)
    
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
    
    print("\n[사전 준비] Email 설정 정보 입력")
    print("   ℹ️  SMTP 서버: gw.idis.co.kr, 포트: 25, SSL/STARTTLS: 사용 안 함")
    print("")
    
    smtp_id = input("   👉 SMTP 인증 ID를 입력하세요: ").strip()
    smtp_pw = input("   👉 SMTP 인증 PW를 입력하세요: ").strip()
    sender = input("   👉 보내는 사람을 입력하세요: ").strip()
    recipient_email = input("   👉 받는 사람 이메일을 입력하세요: ").strip()
    
    if not smtp_id or not smtp_pw or not sender or not recipient_email:
        print_error("필수 정보가 입력되지 않았습니다")
        return False, "Email 설정 정보 입력 실패"
    
    print(f"\n")
    print_success(f"입력 완료 - SMTP ID: {smtp_id}, 보내는 사람: {sender}, 받는 사람: {recipient_email}")
    
    print_step(1, 3, "Email 설정 구성")
    
    email_initial_set = api_get_action_email(page, camera_ip)
    if not email_initial_set:
        print_warning("Email 설정 조회 실패")
        return False, "Email 설정 조회 실패"
    
    if 'returnCode' in email_initial_set: 
        del email_initial_set['returnCode']
    
    email_payload = email_initial_set.copy()
    email_payload['useEmail'] = 'on'
    email_payload['smtpServer'] = 'gw.idis.co.kr'
    email_payload['smtpPort'] = '25'
    email_payload['useSSLTLS'] = 'off'
    email_payload['id'] = smtp_id
    email_payload['password'] = smtp_pw
    email_payload['sender'] = sender
    email_payload['recipientList'] = recipient_email
    
    if api_set_action_email(page, camera_ip, email_payload):
        print_success("Email 설정 완료")
        
        curr = api_get_action_email(page, camera_ip)
        if curr and curr.get('useEmail') == 'on':
            print_success(f"설정 검증 완료: {curr.get('smtpServer')}:{curr.get('smtpPort')}")
        else:
            print_error("설정 검증 실패")
            failed_count += 1
    else:
        print_error("Email 설정 실패")
        failed_count += 1
        return False, "Email 설정 실패"
    
    time.sleep(2)
    
    print_step(2, 3, "Alarm In 이벤트와 Email 액션 연동")
    
    alarmin_initial_set = api_get_event_alarmin(page, camera_ip)
    if not alarmin_initial_set:
        print_warning("Alarm In 이벤트 설정 조회 실패")
        return False, "Alarm In 이벤트 설정 조회 실패"
    
    if 'returnCode' in alarmin_initial_set: 
        del alarmin_initial_set['returnCode']
    
    alarmin_payload = alarmin_initial_set.copy()
    alarmin_payload['useAlarmIn'] = 'on'
    alarmin_payload['alarmType'] = 'no'
    alarmin_payload['actionEmail'] = 'on'
    alarmin_payload['actionEmailAttachImage'] = 'off'
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print_success("Alarm In 이벤트 연동 완료 (alarmType=no, actionEmail=on)")
    else:
        print_error("Alarm In 이벤트 연동 실패")
        failed_count += 1
        return False, "Alarm In 이벤트 연동 실패"
    
    time.sleep(2)
    
    print_step(3, 3, "Email 전송 테스트")
    
    print_action("Alarm In을 NC로 변경 (이벤트 발생 → Email 전송)")
    alarmin_payload['alarmType'] = 'nc'
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print_success("Alarm In NC 변경 완료")
        print(f"   ℹ️  이메일이 {recipient_email}로 전송되었을 것입니다")
        
        print_action("이메일 전송 대기 중 (5초)...")
        time.sleep(5)
        
        print(f"\n   ℹ️  이메일을 받으셨나요? (받는 사람: {recipient_email}, 보낸 사람: {sender})")
        print("      - 예 (Y): 정상 동작")
        print("      - 아니오 (N): 비정상 동작")
        user_confirm = input("   >> (Y/N): ").strip().upper()
        
        if user_confirm == 'Y':
            print_success("Email 전송 성공")
        else:
            print_error("Email 전송 실패 (Tip: SMTP 설정/스팸 폴더 확인)")
            failed_count += 1
    else:
        print_error("Alarm In NC 변경 실패")
        failed_count += 1
    
    print_action("Alarm In을 NO로 복구 중...")
    alarmin_payload['alarmType'] = 'no'
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print_success("Alarm In NO 복구 완료")
        time.sleep(2)
    else:
        print_warning("Alarm In NO 복구 실패")
    
    print("\n[최종 복구] Email 및 Alarm In 설정 복구")
    
    if api_set_action_email(page, camera_ip, email_initial_set):
        print_success("Email 설정 복구 완료")
    else:
        print_warning("Email 설정 복구 실패")
    
    if api_set_event_alarmin(page, camera_ip, alarmin_initial_set):
        print_success("Alarm In 이벤트 설정 복구 완료")
    else:
        print_warning("Alarm In 이벤트 설정 복구 실패")
    
    time.sleep(2)
    
    if failed_count == 0: 
        return True, "Email Test 성공"
    else: 
        return False, f"Email Test 실패 ({failed_count}건)"

# ===========================================================
# 🧪 [Test] Event Action - FTP Upload
# ===========================================================
def run_ftp_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"📁 [Event Action] FTP Upload Test")
    print("=======================================================")
    
    failed_count = 0
    
    print("\n[사전 준비] FTP 설정 정보 입력")
    print("   ℹ️  포트: 21, 업로드 타입: event")
    print("")
    
    ftp_server = input("   👉 FTP 서버 주소를 입력하세요: ").strip()
    ftp_path = input("   👉 업로드 경로를 입력하세요 (예: /upload/camera1): ").strip()
    ftp_user = input("   👉 FTP 사용자 ID를 입력하세요: ").strip()
    ftp_password = input("   👉 FTP 비밀번호를 입력하세요: ").strip()
    
    if not ftp_server or not ftp_path or not ftp_user or not ftp_password:
        print_error("필수 정보가 입력되지 않았습니다")
        return False, "FTP 설정 정보 입력 실패"
    
    print(f"\n")
    print_success(f"입력 완료 - FTP: {ftp_server}, 경로: {ftp_path}, ID: {ftp_user}")
    
    print_step(1, 3, "FTP 설정 구성")
    
    # FTP 초기 설정 백업
    ftp_initial_set = api_get_action_ftp(page, camera_ip)
    if not ftp_initial_set:
        print("   ⚠️ FTP 설정 조회 실패")
        return False, "FTP 설정 조회 실패"
    
    if 'returnCode' in ftp_initial_set: 
        del ftp_initial_set['returnCode']
    
    print(f"   ℹ️  현재 FTP 설정: {ftp_initial_set}")
    
    # FTP 설정 변경
    ftp_payload = ftp_initial_set.copy()
    ftp_payload['useFTP'] = 'on'
    ftp_payload['ftpServer1'] = ftp_server
    ftp_payload['uploadPath1'] = ftp_path
    ftp_payload['port1'] = '21'
    ftp_payload['userID1'] = ftp_user
    ftp_payload['password1'] = ftp_password
    ftp_payload['uploadType'] = 'event'
    ftp_payload['uploadFrequency'] = '1s'  # 이벤트 타입: 1초마다
    ftp_payload['duration'] = '5sec'  # 5초 동안 업로드
    ftp_payload['resolution'] = '352x240'  # 기본 해상도
    ftp_payload['quality'] = 'standard'  # 표준 품질
    ftp_payload['prefix'] = 'event_image'  # 파일 접두어
    ftp_payload['namingType'] = 'datetime'  # 날짜시간 형식
    
    if api_set_action_ftp(page, camera_ip, ftp_payload):
        print("   ✅ FTP 설정 완료")
        
        # 설정 검증
        curr = api_get_action_ftp(page, camera_ip)
        if curr and curr.get('useFTP') == 'on':
            print(f"   ✅ 설정 검증 완료: useFTP={curr.get('useFTP')}")
            print(f"      - FTP 서버: {curr.get('ftpServer1')}")
            print(f"      - 업로드 경로: {curr.get('uploadPath1')}")
            print(f"      - 포트: {curr.get('port1')}")
            print(f"      - 업로드 타입: {curr.get('uploadType')}")
            print(f"      - Duration: {curr.get('duration')}")
        else:
            print(f"   ❌ 설정 검증 실패: useFTP={curr.get('useFTP') if curr else 'None'}")
            failed_count += 1
    else:
        print("   ❌ FTP 설정 실패")
        failed_count += 1
        return False, "FTP 설정 실패"
    
    time.sleep(2)
    
    print_step(2, 3, "Alarm In 이벤트와 FTP 액션 연동")
    
    # Alarm In 이벤트 설정 백업
    alarmin_initial_set = api_get_event_alarmin(page, camera_ip)
    if not alarmin_initial_set:
        print("   ⚠️ Alarm In 이벤트 설정 조회 실패")
        return False, "Alarm In 이벤트 설정 조회 실패"
    
    if 'returnCode' in alarmin_initial_set: 
        del alarmin_initial_set['returnCode']
    
    # Alarm In 이벤트 활성화 및 FTP 액션 연동 (NO 상태로 시작)
    alarmin_payload = alarmin_initial_set.copy()
    alarmin_payload['useAlarmIn'] = 'on'
    alarmin_payload['alarmType'] = 'no'   # NO (Normally Open) 상태
    alarmin_payload['actionFTPupload'] = 'on'  # FTP 액션 연동
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In 이벤트 연동 완료 (alarmType=no, actionFTPupload=on)")
    else:
        print("   ❌ Alarm In 이벤트 연동 실패")
        failed_count += 1
        return False, "Alarm In 이벤트 연동 실패"
    
    time.sleep(2)
    
    print_step(3, 3, "FTP 업로드 테스트")
    print("   ℹ️  Alarm In을 NC로 변경하여 이벤트를 발생시키고 FTP 업로드를 시작합니다.")
    
    # Alarm In을 NC로 변경하여 이벤트 발생
    print("\n   👉 Alarm In을 NC로 변경 (이벤트 발생 → FTP 업로드)")
    alarmin_payload['alarmType'] = 'nc'  # NC로 변경 → 이벤트 발생
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In을 NC로 변경 완료")
        print(f"   ℹ️  FTP 서버로 이미지가 업로드되고 있습니다.")
        print(f"      - 서버: {ftp_server}")
        print(f"      - 경로: {ftp_path}")
        print(f"      - Duration: 5초 동안 1초마다 업로드")
        
        # FTP 업로드 대기 (duration=5sec)
        print("\n   ⏳ FTP 업로드 대기 중 (5초)...")
        time.sleep(5)
        
        # 추가 대기 (업로드 완료 확인)
        print("   ⏳ 업로드 완료 대기 중 (2초 추가)...")
        time.sleep(2)
        
        print("\n   ℹ️  FTP 서버에서 파일을 확인해주세요.")
        print(f"      - 경로: {ftp_path}")
        print(f"      - 파일명 형식: event_image_YYYYMMDD_HHMMSS.jpg")
        print("\n   ℹ️  FTP 서버에 파일이 업로드되었나요?")
        print("      - 예 (Y): 정상 동작")
        print("      - 아니오 (N): 비정상 동작")
        user_confirm = input("   >> (Y/N): ").strip().upper()
        
        if user_confirm == 'Y':
            print("   ✅ Pass: FTP 업로드 성공")
        else:
            print("   ❌ Fail: FTP 업로드 실패")
            print("   ℹ️  Tip: FTP 서버 설정, 경로, 권한을 확인해보세요.")
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
    # [최종 복구] FTP 및 Alarm In 설정 복구
    # ---------------------------------------------------------
    print("\n   🔄 최종 복구: FTP 및 Alarm In 설정 복구")
    
    # FTP 복구
    if api_set_action_ftp(page, camera_ip, ftp_initial_set):
        print("   ✅ FTP 설정 복구 완료")
    else:
        print("   ⚠️ FTP 설정 복구 실패")
    
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
        return True, "FTP Test 성공"
    else: 
        return False, f"FTP Test 실패 ({failed_count}건)"

# ===========================================================
# 🛠️ [Helper] 스케줄 문자열 생성 함수
# ===========================================================
def create_schedule_string(start_hour, end_hour, mode='1'):
    """
    7일 * 24시간 * 4(15분 단위) = 672자 스케줄 문자열 생성
    mode: '0'=off, '1'=event, '2'=timelapse, '3'=event+timelapse
    start_hour: 시작 시간 (0-23)
    end_hour: 종료 시간 (0-23), start_hour보다 크거나 같아야 함
    """
    # 672자 (7일 * 96블록(24시간 * 4)) 전체를 '0'으로 초기화
    schedule = ['0'] * 672
    
    # 매일 같은 시간대에 적용 (7일 반복)
    for day in range(7):  # 0=일요일, 1=월요일, ..., 6=토요일
        day_offset = day * 96  # 하루는 96블록 (24시간 * 4)
        
        # 시작 시간부터 종료 시간까지 mode로 설정
        start_block = start_hour * 4  # 시간당 4블록 (15분 단위)
        end_block = (end_hour + 1) * 4  # 종료 시간의 끝까지 포함
        
        for block in range(start_block, min(end_block, 96)):
            schedule[day_offset + block] = mode
    
    return ''.join(schedule)

# ===========================================================
# 🧪 [Test] Event Action - SD Recording
# ===========================================================
def run_recording_test(page: Page, camera_ip: str):
    print("\n=======================================================")
    print(f"💾 [Event Action] SD Recording Test")
    print("=======================================================")
    
    failed_count = 0
    
    print("\n[사전 준비] 이벤트 녹화 시간대 설정")
    print("   ℹ️  녹화 타입: event, 스케줄: schedule (14:00~15:00)")
    print("")
    
    # 이벤트 녹화 구간 설정 (14:00 ~ 15:00)
    event_start_hour = 14
    event_end_hour = 14  # 15:00까지이므로 14시대만 설정
    event_schedule = create_schedule_string(event_start_hour, event_end_hour, mode='1')
    
    print(f"   ℹ️  스케줄 생성 완료 (672자)")
    print(f"   ℹ️  이벤트 녹화 활성 시간: {event_start_hour}:00 ~ {event_end_hour+1}:00")
    
    print_step(1, 4, "SD Recording 설정 구성")
    
    # Recording 초기 설정 백업
    record_initial_set = api_get_action_record(page, camera_ip)
    if not record_initial_set:
        print("   ⚠️ SD Recording 설정 조회 실패")
        return False, "SD Recording 설정 조회 실패"
    
    if 'returnCode' in record_initial_set: 
        del record_initial_set['returnCode']
    
    print(f"   ℹ️  현재 Recording 설정: {record_initial_set}")
    
    # Recording 설정 변경
    record_payload = record_initial_set.copy()
    record_payload['useRecord'] = 'on'
    record_payload['recordAudio'] = 'on'
    record_payload['scheduleMode'] = 'schedule'  # 커스텀 스케줄
    record_payload['preEventDuration'] = '10'  # 이벤트 전 10초
    record_payload['postEventDuration'] = '10'  # 이벤트 후 10초
    record_payload['schedule'] = event_schedule  # 14:00 ~ 15:00 이벤트 녹화
    record_payload['eventRecordingStream'] = 'primary'  # 이벤트 녹화 스트림
    record_payload['timelapseRecordingStream'] = 'secondary'  # 타임랩스 스트림
    record_payload['recordingPreference'] = 'none'
    record_payload['networkRecordingFailover'] = 'off'
    
    if api_set_action_record(page, camera_ip, record_payload):
        print("   ✅ SD Recording 설정 완료")
        
        # 설정 검증
        curr = api_get_action_record(page, camera_ip)
        if curr and curr.get('useRecord') == 'on':
            print(f"   ✅ 설정 검증 완료: useRecord={curr.get('useRecord')}")
            print(f"      - 스케줄 모드: {curr.get('scheduleMode')}")
            print(f"      - Pre-Event: {curr.get('preEventDuration')}초")
            print(f"      - Post-Event: {curr.get('postEventDuration')}초")
            print(f"      - 이벤트 녹화 구간: 14:00 ~ 15:00")
        else:
            print(f"   ❌ 설정 검증 실패: useRecord={curr.get('useRecord') if curr else 'None'}")
            failed_count += 1
    else:
        print("   ❌ SD Recording 설정 실패")
        failed_count += 1
        return False, "SD Recording 설정 실패"
    
    time.sleep(2)
    
    print_step(2, 4, "시스템 시간을 이벤트 녹화 구간으로 변경")
    
    # 현재 시스템 시간 백업
    datetime_initial_set = api_get_system_datetime(page, camera_ip)
    if not datetime_initial_set:
        print("   ⚠️ 시스템 시간 조회 실패")
        print("   ℹ️  시간 변경 없이 테스트를 계속 진행합니다.")
        datetime_initial_set = None
    else:
        if 'returnCode' in datetime_initial_set: 
            del datetime_initial_set['returnCode']
        
        print(f"   ℹ️  현재 시스템 시간: {datetime_initial_set.get('dateTime', 'Unknown')}")
        
        # 시스템 시간을 14:30으로 변경 (이벤트 녹화 구간 내)
        datetime_payload = datetime_initial_set.copy()
        
        if 'dateTime' in datetime_payload:
            current_datetime = datetime_payload['dateTime']
            date_part = current_datetime.split()[0] if ' ' in current_datetime else '2024-01-01'
            datetime_payload['dateTime'] = f"{date_part} 14:30:00"
        else:
            datetime_payload['hour'] = '14'
            datetime_payload['minute'] = '30'
            datetime_payload['second'] = '00'
        
        if api_set_system_datetime(page, camera_ip, datetime_payload):
            print("   ✅ 시스템 시간 변경 완료 (14:30) - 이벤트 녹화 구간 내")
            time.sleep(2)
        else:
            print("   ❌ 시스템 시간 변경 실패")
            failed_count += 1
    
    print_step(3, 4, "Alarm In 이벤트와 SD Recording 액션 연동")
    
    # Alarm In 이벤트 설정 백업
    alarmin_initial_set = api_get_event_alarmin(page, camera_ip)
    if not alarmin_initial_set:
        print("   ⚠️ Alarm In 이벤트 설정 조회 실패")
        return False, "Alarm In 이벤트 설정 조회 실패"
    
    if 'returnCode' in alarmin_initial_set: 
        del alarmin_initial_set['returnCode']
    
    # Alarm In 이벤트 활성화 및 Recording 액션 연동 (NO 상태로 시작)
    alarmin_payload = alarmin_initial_set.copy()
    alarmin_payload['useAlarmIn'] = 'on'
    alarmin_payload['alarmType'] = 'no'   # NO (Normally Open) 상태
    alarmin_payload['actionRecord'] = 'on'  # SD Recording 액션 연동
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In 이벤트 연동 완료 (alarmType=no, actionRecord=on)")
    else:
        print("   ❌ Alarm In 이벤트 연동 실패")
        failed_count += 1
        return False, "Alarm In 이벤트 연동 실패"
    
    time.sleep(2)
    
    print_step(4, 4, "이벤트 녹화 테스트")
    print("   ℹ️  Alarm In을 NC로 변경하여 이벤트를 발생시키고 SD 녹화를 시작합니다.")
    
    # Alarm In을 NC로 변경하여 이벤트 발생
    print("\n   👉 Alarm In을 NC로 변경 (이벤트 발생 → SD 녹화 시작)")
    alarmin_payload['alarmType'] = 'nc'  # NC로 변경 → 이벤트 발생
    
    if api_set_event_alarmin(page, camera_ip, alarmin_payload):
        print("   ✅ Alarm In을 NC로 변경 완료")
        print(f"   ℹ️  SD 카드에 이벤트 녹화가 시작되었습니다.")
        print(f"      - 녹화 시간: Pre-Event 10초 + 이벤트 중 + Post-Event 10초")
        print(f"      - 녹화 스트림: primary")
        
        # 이벤트 녹화 대기 (Pre + Event + Post)
        print("\n   ⏳ 이벤트 녹화 대기 중 (15초)...")
        time.sleep(15)
        
        print("\n   ℹ️  SD 카드에서 녹화 파일을 확인해주세요.")
        print(f"      - 녹화 시간: 14:30 경")
        print(f"      - 녹화 타입: Event Recording")
        print("\n   ℹ️  SD 카드에 이벤트 녹화 파일이 생성되었나요?")
        print("      (카메라 웹 UI 또는 SD 카드를 직접 확인)")
        print("      - 예 (Y): 정상 동작")
        print("      - 아니오 (N): 비정상 동작")
        user_confirm = input("   >> (Y/N): ").strip().upper()
        
        if user_confirm == 'Y':
            print("   ✅ Pass: 이벤트 녹화 성공")
        else:
            print("   ❌ Fail: 이벤트 녹화 실패")
            print("   ℹ️  Tip: SD 카드 상태, 스케줄 설정, 시스템 시간을 확인해보세요.")
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
    # [최종 복구] 시스템 시간, Recording, Alarm In 설정 복구
    # ---------------------------------------------------------
    print("\n   🔄 최종 복구: 모든 설정 복구")
    
    # 시스템 시간 복구
    if datetime_initial_set:
        print("   🔄 시스템 시간 복구")
        if api_set_system_datetime(page, camera_ip, datetime_initial_set):
            print("   ✅ 시스템 시간 복구 완료")
            time.sleep(2)
        else:
            print("   ⚠️ 시스템 시간 복구 실패 (수동으로 확인 필요)")
    
    # Recording 복구
    if api_set_action_record(page, camera_ip, record_initial_set):
        print("   ✅ SD Recording 설정 복구 완료")
    else:
        print("   ⚠️ SD Recording 설정 복구 실패")
    
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
        return True, "SD Recording Test 성공"
    else: 
        return False, f"SD Recording Test 실패 ({failed_count}건)"
