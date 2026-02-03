"""
설정값 중앙 관리 모듈
모든 하드코딩된 설정값을 한 곳에서 관리합니다.
"""

# ===========================================================
# 📋 카메라 기본 설정
# ===========================================================
CAMERA_IP = "10.0.131.112"
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
IRAS_DEVICE_NAME = "112_Y8D11"  # iRAS 테스트용 장치 이름

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
    "menu_playback": (50, 150),     # 녹화 영상 검색
    "menu_ptz": (50, 175),          # PTZ 제어
    "menu_color": (50, 225),        # 컬러 제어
    "menu_alarm": (50, 300),        # 알람 출력 제어
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
    "right_click_top": 15,         # 우클릭 상단 오프셋         # 우클릭 중간 오프셋
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
FEN_NAME = IRAS_DEVICE_NAME
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

# 1. Easy Video Setting (Self Adjust)
VIDEO_PRESET_MODES = {
    "1": "Natural (자연스러운)",
    "2": "Vivid (선명한)",
    "3": "Denoise (노이즈 감소)"
}

VIDEO_PARAM_RANGES = {
    "Sharpness": ["0", "3"],
    "Contrast": ["0", "2"],
    "Brightness": ["0", "2"],
    "Colors": ["0", "2"]
}

VIDEO_DEFAULT_CUSTOM_PARAMS = {
    "easyDayType": "0", "easyNightType": "0",
    "easyDaySharpness": "1", "easyDayContrast": "1", "easyDayBrightness": "1", "easyDayColors": "1",
    "easyNightSharpness": "1", "easyNightGamma": "1", "easyNightBrightness": "1"
}

# 2. Video Image (Mirroring/Pivot)
VIDEO_MIRRORING_OPTS = ["off", "horizontal", "vertical", "both"]
VIDEO_PIVOT_OPTS = ["off", "clockwise", "counterclockwise"]

# 3. White Balance
VIDEO_WB_MODES = {
    "auto": "Auto",
    "incandescent": "Incandescent",
    "fluorescent_warm": "Fluorescent Warm",
    "manual": "Manual"
}
VIDEO_WB_GAIN_TEST_VALUES = ["10", "500"]

# 4. Exposure (노출)
VIDEO_SHUTTER_TEST_CASES = [
    ("30", "1/30s (Bright)"), 
    ("8000", "1/8000s (Dark)") 
]
VIDEO_TARGET_GAIN_VALUES = ["-10", "10"]
VIDEO_WDR_MODES = ["off", "on"]

# 5. Day & Night
# 스케줄 문자열 생성 (7일 * 24시간)
# 1시간 = 8비트 = 2 Hex Char. 24시간 = 48 Hex Char.
# 0(00) = Day/Off, 5(0101) = Night/On (15분 단위 설정)
VIDEO_DAY_SCHEDULE_STR = "_".join(["0" * 48] * 7)  # 일주일 내내 주간
VIDEO_NIGHT_SCHEDULE_STR = "_".join(["5" * 48] * 7)  # 일주일 내내 야간 (5555...)

# 6. Miscellaneous (EIS)
VIDEO_EIS_MODES = ["off", "on"]

# 7. Streaming Test
VIDEO_STREAMING_TARGET_STREAM = "1"  # 주로 1번 스트림 테스트
VIDEO_STREAMING_CODECS = ["h265", "h264"]
VIDEO_STREAMING_RESOLUTIONS = ["1920x1080", "1280x720"]
VIDEO_STREAMING_IPS_VALUES = ["30", "5"]  # Max, Min
VIDEO_STREAMING_BITRATE_MODES = ["cbr", "vbr"]
VIDEO_STREAMING_BASE_SETTINGS = {
    "codec": "h265",
    "resolution": "1920x1080",
    "framerate": "30",
    "quality": "veryHigh"
}

# 8. MAT (Motion Adaptive Transmission) Test
VIDEO_MAT_SENSITIVITY = "3"  # 민감도 (1~5)
VIDEO_MAT_INACTIVITY_PERIOD = "10"  # 비활성 감지 시간 (초, 1~60)
VIDEO_MAT_TARGET_FRAMERATE = "5"  # 비활성 시 목표 프레임레이트 (1~15)
VIDEO_MAT_TARGET_IPS = 5.0  # 검증용 목표 IPS 값
VIDEO_MAT_WAIT_TIME = 20  # IPS 감소 대기 시간 (초)

# 9. Privacy Mask Test
VIDEO_PRIVACY_ZONE_COUNT = 8  # 테스트할 Zone 개수 (최대 8 또는 16, 카메라 그룹별 다름)
VIDEO_PRIVACY_GRID_COLS = 4  # 그리드 열 개수 (2x4 그리드)
VIDEO_PRIVACY_GRID_ROWS = 2  # 그리드 행 개수 (2x4 그리드)
VIDEO_PRIVACY_ZONE_NAME_PREFIX = "TestZone"  # Zone 이름 접두사

# 10. OSD (On-Screen Display) Test
# OSD Text
VIDEO_OSD_TEXT_STRING = "IDIS Camera Test 12345"  # 표시할 텍스트
VIDEO_OSD_TEXT_SIZES = ["0", "2", "4"]  # 테스트할 텍스트 크기 (0=최소, 4=최대)
VIDEO_OSD_TEXT_COLORS = ["ffffff", "ff0000", "00ff00"]  # 테스트할 색상 (흰색, 빨강, 초록)
VIDEO_OSD_TEXT_TRANSPARENCIES = ["255", "145", "40"]  # 투명도 (255=불투명, 40=투명)
VIDEO_OSD_TEXT_POSITION = {"x": "50", "y": "10"}  # 기본 위치 (중앙 상단)

# OSD DateTime
VIDEO_OSD_DATETIME_DATE_FORMATS = ["YYYY/MM/DD", "MM/DD/YYYY", "DD/MM/YYYY"]  # 날짜 형식
VIDEO_OSD_DATETIME_TIME_FORMATS = ["HH:MM:SS", "II:MM:SS_PP", "PP_II:MM:SS"]  # 시간 형식
VIDEO_OSD_DATETIME_TEXT_SIZE = "2"  # DateTime 텍스트 크기
VIDEO_OSD_DATETIME_TEXT_COLOR = "ffffff"  # DateTime 텍스트 색상
VIDEO_OSD_DATETIME_TEXT_TRANSPARENCY = "255"  # DateTime 투명도
VIDEO_OSD_DATETIME_POSITION = {"x": "5", "y": "5"}  # DateTime 위치 (좌상단)

# ===========================================================
# 📝 테스트 데이터
# ===========================================================
TEST_GROUP_A = "아이디스_A"
TEST_GROUP_B = "아이디스_B"
TEST_USER_ID = "testuser1"
TEST_USER_PW = "qwerty0-"
