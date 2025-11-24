import time
import subprocess
import sys
import ctypes
import socket
import uuid
from scapy.all import ARP, Ether, srp
from playwright.sync_api import sync_playwright

# ==========================================
# 🛡️ 관리자 권한 획득
# ==========================================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
    sys.exit()

# ==========================================
# 🛠️ 설정값
# ==========================================
CONFIG = {
    "INTERFACE_NAME": "이더넷",
    
    # [PC 초기 고정 IP]
    "PC_STATIC_IP": "10.0.131.102",
    "PC_SUBNET": "255.255.0.0",
    "PC_GATEWAY": "10.0.0.1",
    
    # [타겟 카메라 정보]
    "TARGET_CAMERA_IP": "10.0.131.104",
    "HTTP_PORT": "80",
    "USER_ID": "admin",
    "USER_PW": "qwerty0-",
    
    # [스캔 범위 - 사내망용]
    "COMPANY_DHCP_NETWORK": "10.0.17.0/24",
    
    # [FEN 설정]
    "FEN_SERVER": "qa1.idis.co.kr",
    "FEN_NAME": "AUTO_TEST_CAM"
}

# ==========================================
# 1. 시스템 관리자
# ==========================================
class SystemManager:
    def run_command(self, cmd):
        try:
            subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except: return False

    def set_pc_static(self):
        print(f"💻 [System] PC 고정 IP 설정 ({CONFIG['PC_STATIC_IP']})...")
        cmd = f'netsh interface ip set address name="{CONFIG["INTERFACE_NAME"]}" static {CONFIG["PC_STATIC_IP"]} {CONFIG["PC_SUBNET"]} {CONFIG["PC_GATEWAY"]}'
        self.run_command(cmd)
        time.sleep(3)

    def set_pc_dhcp(self):
        print("💻 [System] PC DHCP 모드 변경 (Auto IP 할당 대기)...")
        cmd_ip = f'netsh interface ip set address name="{CONFIG["INTERFACE_NAME"]}" source=dhcp'
        cmd_dns = f'netsh interface ip set dns name="{CONFIG["INTERFACE_NAME"]}" source=dhcp'
        self.run_command(cmd_ip)
        self.run_command(cmd_dns)
        print("   -> PC 네트워크 재설정 대기 (IP 할당까지 약 20초 소요)...")
        time.sleep(20) 

    def flush_arp(self):
        self.run_command("arp -d *")
        time.sleep(1)

    def renew_ip(self):
        print("💻 [System] IP 갱신 (ipconfig /renew)...")
        self.run_command("ipconfig /renew")
        time.sleep(10) # 사내망 DHCP 할당 시간 충분히 대기

# ==========================================
# 2. 하이브리드 스캐너 (로그 간소화)
# ==========================================
class HybridScanner:
    def trigger_discovery(self):
        """ONVIF Probe 패킷 전송 (INIT 역할)"""
        # 로그 대신 '+' 기호만 출력하여 진행상황 표시
        print("+", end="", flush=True)
        
        msg = f'''<?xml version="1.0" encoding="UTF-8"?>
        <e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
                    xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
                    xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
                    xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
            <e:Header>
                <w:MessageID>uuid:{uuid.uuid4()}</w:MessageID>
                <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
                <w:Action a:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
            </e:Header>
            <e:Body>
                <d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe>
            </e:Body>
        </e:Envelope>'''

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.settimeout(1)
            sock.sendto(msg.encode(), ('239.255.255.250', 3702))
            sock.close()
        except: pass

    def get_ip_from_arp_table(self, target_mac):
        target_mac_norm = target_mac.lower().replace(":", "-")
        try:
            output = subprocess.check_output("arp -a", shell=True).decode('cp949', errors='ignore')
            for line in output.splitlines():
                if target_mac_norm in line.lower():
                    return line.split()[0]
        except: pass
        return None

    def find_ip(self, target_mac, scan_range=None, timeout=120, use_probe=False):
        print(f"🔍 [Scanner] MAC [{target_mac}] 추적 시작 ({timeout}s)", end="")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 진행 표시 (점 찍기)
            print(".", end="", flush=True)

            # 1. INIT 처럼 깨우기
            if use_probe:
                self.trigger_discovery()

            # 2. ARP 테이블 조회
            found_ip = self.get_ip_from_arp_table(target_mac)
            if found_ip:
                # Auto IP 모드일 때 169.254 대역인지 확인
                if use_probe and not found_ip.startswith("169.254") and not scan_range:
                    pass 
                elif scan_range and found_ip.startswith("169.254") and "169.254" not in scan_range:
                    pass # 사내망 찾는데 Auto IP 나오면 무시
                else:
                    print("") # 줄바꿈
                    return found_ip

            # 3. Scapy 스캔 (사내망 DHCP용)
            if scan_range and "169.254" not in scan_range:
                try:
                    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=scan_range), timeout=0.5, verbose=0)
                    for sent, received in ans:
                        if received.hwsrc.lower().replace("-", ":") == target_mac.lower().replace("-", ":"):
                            print("") # 줄바꿈
                            return received.psrc
                except: pass
            
            time.sleep(1.5)
            
        print("") # 줄바꿈
        return None

# ==========================================
# 3. 웹 컨트롤러 (속도 조절 및 유지)
# ==========================================
class WebController:
    def __init__(self, page):
        self.page = page

    def _click_menu(self, selector):
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=5000)
            self.page.click(selector, force=True)
            time.sleep(1) # 메뉴 이동 천천히
            return True
        except: return False

    def _handle_popup(self):
        try:
            self.page.once("dialog", lambda dialog: dialog.accept())
            time.sleep(1)
            # 화면상 팝업 처리
            if self.page.locator(".ui-dialog:visible").count() > 0:
                print("   [Pop] 팝업 확인 클릭")
                self.page.locator(".ui-dialog:visible").locator("button").filter(has_text="확인").click()
                time.sleep(1)
        except: pass

    def get_mac(self, ip):
        try:
            url = f"http://{ip}:{CONFIG['HTTP_PORT']}/setup/setup.html"
            print(f"🌐 [UI] 접속 시도: {url}")
            self.page.goto(url, timeout=20000)
            self.page.wait_for_load_state("domcontentloaded")
            
            if self._click_menu("#Page200_id"): # 시스템
                self._click_menu("#Page201_id") # 일반
            
            self.page.wait_for_selector("#mac-addressInfo", state="visible", timeout=5000)
            mac = self.page.input_value("#mac-addressInfo").strip()
            print(f"✅ [UI] MAC 확보: {mac}")
            return mac
        except: return None

    def set_dhcp(self):
        print("🖱️ [UI] 카메라 설정 -> DHCP 변경")
        try:
            if self._click_menu("#Page300_id"): # 네트워크
                self._click_menu("#Page301_id") # IP주소
            
            self.page.wait_for_selector("#ip-type", state="visible")
            self.page.select_option("#ip-type", value="1") # DHCP
            
            self._handle_popup()
            self.page.click("text=저장", force=True)
            print("✅ [UI] 저장 완료.")
            return True
        except: return False

    def configure_fen(self, ip, fen_name):
        print(f"🚀 [FEN] 설정 시작 ({ip})... 천천히 진행합니다.")
        try:
            if not self.page.is_visible("#Page302_id"):
                self._click_menu("#Page300_id")
            self._click_menu("#Page302_id") # FEN
            
            self.page.wait_for_selector("#use-fen", state="visible", timeout=5000)
            
            # 1. FEN 체크
            if not self.page.is_checked("#use-fen"):
                self.page.click("label[for='use-fen']")
                print("   -> FEN 사용 V")
            time.sleep(2) # 육안 확인용 대기

            # 2. 정보 입력
            self.page.fill("#fen-server", CONFIG["FEN_SERVER"])
            time.sleep(1)
            self.page.fill("#cam-name", fen_name)
            print(f"   -> 정보 입력 완료")
            time.sleep(2)

            # 3. 중복 확인
            print("   -> 중복 확인 클릭")
            self.page.click("#check-cam-name")
            time.sleep(3) # 서버 통신 대기
            self._handle_popup() # 사용가능 팝업

            # 4. 저장
            print("💾 [FEN] 최종 저장")
            self.page.click("text=저장", force=True)
            time.sleep(2)
            self._handle_popup()
            
            print("✅ [FEN] 설정이 완료되었습니다.")
            return True
        except Exception as e:
            print(f"❌ FEN 설정 실패: {e}")
            return False

# ==========================================
# 🚀 메인 시나리오
# ==========================================
def main():
    sys_mgr = SystemManager()
    scanner = HybridScanner()

    # [Step 1] 초기 설정
    sys_mgr.set_pc_static()
    
    target_mac = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(http_credentials={"username": CONFIG["USER_ID"], "password": CONFIG["USER_PW"]})
        ui = WebController(context.new_page())

        target_mac = ui.get_mac(CONFIG["TARGET_CAMERA_IP"])
        if target_mac:
            ui.set_dhcp()
        browser.close()

    if not target_mac: 
        print("❌ 테스트 중단"); return

    # [Step 2] Auto IP 테스트
    print("\n" + "="*50)
    print("🚨 [ACTION] 허브에서 '사내망 랜선' 뽑고, '카메라 랜선' 뺐다 꽂으세요.")
    print("   -> 완료 후 y 입력")
    print("="*50)
    input(">> y 입력: ")

    sys_mgr.set_pc_dhcp()
    sys_mgr.flush_arp()
    
    # Auto IP 찾기 (로그: . + . + )
    auto_ip = scanner.find_ip(target_mac, timeout=120, use_probe=True)
    
    if auto_ip and auto_ip.startswith("169.254"):
        print(f"🎉 [SUCCESS] Auto IP 발견: {auto_ip}")
    else:
        print(f"❌ 발견 실패. (스캔된 IP: {auto_ip})")

    # [Step 3] Company DHCP & FEN
    print("\n" + "="*50)
    print("🚨 [ACTION] '사내망 랜선'을 다시 연결하세요.")
    print("   -> 완료 후 y 입력")
    print("="*50)
    input(">> y 입력: ")

    sys_mgr.renew_ip()
    sys_mgr.flush_arp()
    
    dhcp_ip = scanner.find_ip(target_mac, CONFIG["COMPANY_DHCP_NETWORK"], use_probe=True)
    
    if dhcp_ip and dhcp_ip.startswith("10.0.17"):
        print(f"🎉 [SUCCESS] 사내 DHCP 발견: {dhcp_ip}")
        
        # FEN 설정 진행
        print("\n>>> FEN 설정을 위해 브라우저를 엽니다...")
        with sync_playwright() as p:
            # slow_mo를 1000ms(1초)로 설정하여 천천히 동작
            browser = p.chromium.launch(headless=False, slow_mo=1000)
            context = browser.new_context(http_credentials={"username": CONFIG["USER_ID"], "password": CONFIG["USER_PW"]})
            ui = WebController(context.new_page())
            
            try:
                ui.page.goto(f"http://{dhcp_ip}:{CONFIG['HTTP_PORT']}/setup/setup.html", timeout=30000)
                ui.configure_fen(dhcp_ip, CONFIG["FEN_NAME"])
                
                # 브라우저 유지
                print("\n" + "="*50)
                print("✅ FEN 설정이 완료되었습니다. 화면을 확인하세요.")
                input("🔴 브라우저를 닫고 종료하려면 Enter를 누르세요...")
                print("="*50)
                
            except Exception as e:
                print(f"❌ FEN 단계 에러: {e}")
            
            browser.close()
    else:
        print("❌ 사내망 IP 발견 실패")

    print("[System] 종료.")

if __name__ == "__main__":
    main()