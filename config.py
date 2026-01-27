"""
설정값 중앙 관리 모듈
모든 하드코딩된 설정값을 한 곳에서 관리합니다.
"""

# ===========================================================
# 📋 카메라 기본 설정
# ===========================================================
CAMERA_IP = "10.0.131.104"
CAMERA_PORT = "80"
CAMERA_URL = f"http://{CAMERA_IP}/setup"
USERNAME = "admin"
PASSWORD = "qwerty0-"

# ===========================================================
# 🌐 네트워크 설정
# ===========================================================
INTERFACE_NAME = "이더넷"  # 본인 PC 환경에 맞게 수정 (예: "Ethernet" or "Wi-Fi")

# PC 네트워크 설정
PC_STATIC_IP = "10.0.131.102"
PC_SUBNET = "255.255.0.0"
PC_GW = "10.0.0.1"
PC_AUTO_IP = "169.254.100.100"
AUTO_SUBNET = "255.255.0.0"

# 스캔 범위
SCAN_NET = "10.0.131.0/24"
SCAN_AUTO_NET = "169.254.0.0/16"

# ===========================================================
# 🖥️ iRAS 설정
# ===========================================================
IRAS_DEVICE_NAME = "104_T6631"  # iRAS 테스트용 장치 이름

# iRAS 창 제목
IRAS_TITLES = {
    "main": "IDIS Center Remote Administration System",
    "setup": "IDIS Center 설정",
    "modify": "장치 수정",
    "search": "장치 검색",
    "port_setting": "포트 설정",
}

# iRAS UI 요소 Automation ID
IRAS_IDS = {
    "dev_search_input": "101",      # 설정창 > 장치 검색
    "dev_list": "1000",             # 설정창 > 장치 리스트
    "user_id_input": "22043",       # 수정창 > 사용자 ID
    "user_pw_input": "22045",       # 수정창 > 사용자 PW
    "addr_type_combo": "1195",      # 수정창 > 주소 타입 콤보박스
    "fen_input": "22047",           # 수정창 > FEN 이름 입력
    "port_input": "1201",           # 수정창 > 원격 포트 입력
    "test_btn": "22132",            # 수정창 > 연결 테스트 버튼
    "ok_btn": "1",                  # 확인 버튼 (공통)
    "surveillance_pane": "59648",   # 감시 화면 Pane
    "save_clip_btn": "2005",        # 재생 화면 > 저장 버튼
    "plus_btn": "22023",            # 설정창 > '+' 버튼 (장치 검색)
    "port_btn": "22034",            # 장치 검색 > '포트...' 버튼
    "port_edit": "26468",           # 포트 설정 > 포트 입력
    "search_start_btn": "22031",    # 장치 검색 > '검색 시작' 버튼
    "search_result_text": "1194",  # 장치 검색 > 결과 텍스트
}

# iRAS 마우스 상대 좌표 (우클릭 메뉴 위치)
IRAS_COORDS = {
    "menu_modify": (50, 20),        # 장치 수정
    "menu_remote": (50, 45),        # 원격 설정
    "menu_fw_up": (50, 70),         # 펌웨어 업그레이드
    "menu_playback": (50, 100),     # 녹화 영상 검색
    "menu_ptz": (50, 125),          # PTZ 제어
    "menu_color": (50, 175),        # 컬러 제어
    "menu_alarm": (50, 250),        # 알람 출력 제어
    "alarm_on": (150, 0),           # 알람 > 켜기 (상대좌표)
    "clip_copy": (30, 0),           # 클립 복사 메뉴
}

# 피시아이 iRAS 마우스 상대 좌표 (우클릭 메뉴 위치)
Fisheye_IRAS_COORDS = {
    "menu_modify": (50, 20),        # 장치 수정
    "menu_remote": (50, 45),        # 원격 설정
    "menu_fw_up": (50, 70),         # 펌웨어 업그레이드
    "menu_playback": (50, 125),     # 녹화 영상 검색
    "menu_ptz": (50, 150),          # PTZ 제어
    "menu_color": (50, 200),        # 컬러 제어
    "menu_alarm": (50, 275),        # 알람 출력 제어
    "alarm_on": (150, 0),           # 알람 > 켜기 (상대좌표)
    "clip_copy": (30, 0),           # 클립 복사 메뉴
}

# iRAS 탭 설정
IRAS_TABS = {
    "network_name": "네트워크",      # 네트워크 탭 이름
    "network_offset_x": 100,        # 네트워크 탭 클릭 오프셋 X
    "network_offset_y": 15,         # 네트워크 탭 클릭 오프셋 Y
}

# iRAS 대기 시간 (초)
IRAS_DELAYS = {
    "click": 0.3,                   # 클릭 후 대기
    "input": 0.2,                   # 입력 후 대기
    "key": 0.1,                     # 키 입력 후 대기
    "focus": 0.2,                   # 포커스 전환 후 대기
    "window_open": 2.0,             # 창 열림 대기
    "window_close": 1.5,            # 창 닫힘 대기
    "menu_navigate": 0.5,           # 메뉴 이동 대기
    "tab_switch": 1.5,              # 탭 전환 대기
    "combo_select": 0.5,            # 콤보박스 선택 대기
    "test_response": 5.0,           # 연결 테스트 응답 대기
    "test_popup": 3.0,              # 테스트 팝업 닫기 대기
    "playback_load": 5.0,           # 재생창 로딩 대기
    "clipboard_copy": 1.0,          # 클립보드 복사 대기
    "device_search": 1.5,            # 장치 검색 입력 후 대기
    "device_modify": 2.0,           # 장치 수정 창 열림 대기
    "block_popup": 8.0,             # 차단 팝업 대기
    "permission_action": 2.0,        # 권한 테스트 액션 후 대기
    "permission_result": 1.0,       # 권한 테스트 결과 대기
    "stabilize": 2.0,               # 안정화 대기
    "search_result": 1.0,           # 검색 결과 확인 대기
    "search_timeout": 10,           # 검색 타임아웃 (초)
}

# iRAS 감시 화면 클릭 오프셋
IRAS_SURVEILLANCE_OFFSETS = {
    "right_click_top": 100,         # 우클릭 상단 오프셋
    "right_click_mid": 50,          # 우클릭 중간 오프셋
    "device_list": 25,             # 장치 리스트 클릭 오프셋
}

# iRAS 키 입력 코드
IRAS_KEYS = {
    "ctrl": 0x11,
    "s": 0x53,
    "c": 0x43,
}

# ===========================================================
# 🌍 FEN 설정
# ===========================================================
FEN_SERVER = "qa1.idis.co.kr"
FEN_NAME = "FEN테스트"
FEN_PORT = "10088"

# ===========================================================
# ⏱️ 타임아웃 및 대기 시간 설정
# ===========================================================
TIMEOUTS = {
    "page_load": 15000,      # 페이지 로드 대기 (ms)
    "selector": 10000,       # 셀렉터 대기 (ms)
    "api_request": 10,       # API 요청 타임아웃 (초)
    "video_stabilize": 5,    # 영상 안정화 대기 (초)
    "network_change": 5,     # 네트워크 변경 대기 (초)
    "popup": 5000,           # 팝업 대기 (ms)
    "retry_delay": 2,        # 재시도 간격 (초)
    "max_retries": 3,        # 최대 재시도 횟수
    "video_connection": 180, # 영상 연결 대기 (초)
}

# ===========================================================
# 🎬 비디오 테스트 설정
# ===========================================================
VIDEO_WAIT_TIME = 5  # iRAS 영상 변화 관찰 대기 시간 (초)

# ===========================================================
# 📝 테스트 데이터
# ===========================================================
TEST_GROUP_A = "아이디스_A"
TEST_GROUP_B = "아이디스_B"
TEST_USER_ID = "testuser1"
TEST_USER_PW = "qwerty0-"
