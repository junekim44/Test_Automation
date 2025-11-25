import time
import subprocess
import sys
import ctypes
import socket
import uuid
from scapy.all import ARP, Ether, srp, conf
from playwright.sync_api import sync_playwright

# ==========================================
# 🛡️ 관리자 권한 획득
# ==========================================
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

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

    # [PC Auto IP 대역]
    "PC_AUTO_IP": "169.254.100.100",
    
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
# 1. 시스템 관리자 (IP 대기 로직 강화)
# ==========================================
class SystemManager:
    def run_command(self, cmd):
        try:
            subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except: return False

    def set_pc_static(self, ip, subnet, gateway=None):
        print(f"💻 [System] PC IP 변경 -> {ip} (Static)...")
        cmd = f'netsh interface ip set address name="{CONFIG["INTERFACE_NAME"]}" static {ip} {subnet}'
        if gateway: cmd += f" {gateway}"
        self.run_command(cmd)
        time.sleep(4) 

    def set_pc_dhcp(self):
        print("💻 [System] PC IP 변경 -> DHCP 모드...")
        self.run_command(f'netsh interface ip set address name="{CONFIG["INTERFACE_NAME"]}" source=dhcp')
        self.run_command(f'netsh interface ip set dns name="{CONFIG["INTERFACE_NAME"]}" source=dhcp')

    def flush_arp(self):
        self.run_command("arp -d *")
        time.sleep(1)

    def renew_ip_and_wait(self, expected_prefix="10."):
        """
        DHCP 갱신 요청 후, 실제로 IP가 들어올 때까지 루프 돌며 대기
        """
        print("💻 [System] IP 갱신 요청 (ipconfig /renew)...")
        # 1. 갱신 명령 (비동기적으로 됨)
        subprocess.call("ipconfig /renew", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print(f"⏳ [Wait] 사내망 IP({expected_prefix}x.x) 할당 대기 중...", end="")
        
        # 2. IP가 들어올 때까지 최대 60초 대기
        for _ in range(30):
            try:
                # ipconfig 출력 확인
                output = subprocess.check_output("ipconfig", shell=True, encoding='cp949', errors='ignore')
                
                # 정규식이나 문자열로 IP 찾기 (간단히 문자열 포함 여부 확인)
                # 실제로는 인터페이스 별로 파싱해야 정확하지만, 
                # 여기서는 'IPv4 주소 . . . : 10.' 패턴이 보이는지로 판단
                if f": {expected_prefix}" in output:
                    print(" 성공! ✅")
                    time.sleep(2) # 안정화 대기
                    return True
            except: pass
            
            print(".", end="", flush=True)
            time.sleep(2)
        
        print(" 실패 ❌ (시간 초과)")
        return False

# ==========================================
# 2. 하이브리드 스캐너
# ==========================================
class HybridScanner:
    def trigger_discovery(self):
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
            <e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>
        </e:Envelope>'''
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.settimeout(0.5)
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

    def find_ip(self, target_mac, scan_range=None, timeout=60, use_probe=False):
        print(f"🔍 [Scanner] MAC [{target_mac}] 추적 시작 ({timeout}s)", end="")
        
        # [중요] Scapy 라우팅 테이블 갱신 (PC IP 변경 후 필수)
        try:
            conf.iface = CONFIG["INTERFACE_NAME"]
            conf.route.resync()
        except: pass

        start_time = time.time()
        while time.time() - start_time < timeout:
            print(".", end="", flush=True)
            if use_probe: self.trigger_discovery()

            found_ip = self.get_ip_from_arp_table(target_mac)
            if found_ip:
                if scan_range and "169.254" not in scan_range and found_ip.startswith("169.254"):
                    pass 
                else:
                    print("")
                    return found_ip

            if scan_range and "169.254" not in scan_range:
                try:
                    # verbose=0으로 에러 숨김
                    ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=scan_range), timeout=0.5, verbose=0, iface=CONFIG["INTERFACE_NAME"])
                    for _, received in ans:
                        if received.hwsrc.lower().replace("-", ":") == target_mac.lower().replace("-", ":"):
                            print("")
                            return received.psrc
                except: pass
            
            time.sleep(1)
            
        print("")
        return None

# ==========================================
# 3. 웹 컨트롤러
# ==========================================
class WebController:
    def __init__(self, page):
        self.page = page

    def _click_menu(self, selector):
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=5000)
            self.page.click(selector, force=True)
            time.sleep(1)
            return True
        except: return False

    def _handle_popup(self):
        try:
            self.page.once("dialog", lambda dialog: dialog.accept())
            time.sleep(1)
            if self.page.locator(".ui-dialog:visible").count() > 0:
                print("   [Pop] 팝업 확인")
                self.page.locator(".ui-dialog:visible").locator("button").filter(has_text="확인").click()
                time.sleep(1)
        except: pass

    def get_mac(self, ip):
        try:
            url = f"http://{ip}:{CONFIG['HTTP_PORT']}/setup/setup.html"
            print(f"🌐 [UI] 접속 시도: {url}")
            self.page.goto(url, timeout=20000)
            self.page.wait_for_load_state("domcontentloaded")
            if self._click_menu("#Page200_id"): self._click_menu("#Page201_id")
            
            self.page.wait_for_selector("#mac-addressInfo", state="visible", timeout=5000)
            mac = self.page.input_value("#mac-addressInfo").strip()
            print(f"✅ [UI] MAC 확보: {mac}")
            return mac
        except: return None

    def enable_link_local(self):
        print("🖱️ [UI] Link-Local Only '켜기' 시도...")
        try:
            if self._click_menu("#Page300_id"): self._click_menu("#Page301_id")
            
            if not self.page.is_checked("#use-linklocal-only"):
                self.page.click("label[for='use-linklocal-only']", force=True)
                print("   -> 체크박스 ON (V)")
            
            self._handle_popup()
            self.page.click("text=저장", force=True)
            print("💾 [UI] 저장 완료 (카메라 재부팅/네트워크 재설정 대기)")
            time.sleep(5)
            return True
        except Exception as e:
            print(f"❌ 설정 실패: {e}"); return False

    def disable_link_local_and_set_dhcp(self):
        print("🖱️ [UI] Link-Local 해제 및 DHCP 설정...")
        try:
            if self._click_menu("#Page300_id"): self._click_menu("#Page301_id")
            
            if self.page.is_checked("#use-linklocal-only"):
                self.page.click("label[for='use-linklocal-only']", force=True)
                print("   -> Link-Local 체크 해제")
                self._handle_popup()
                time.sleep(1)

            print("   -> DHCP 선택")
            self.page.select_option("#ip-type", value="1") 
            
            self._handle_popup()
            self.page.click("text=저장", force=True)
            print("💾 [UI] 저장 완료")
            time.sleep(2)
            return True
        except Exception as e:
            print(f"❌ 설정 실패: {e}"); return False

    def configure_fen(self, ip, fen_name):
        print(f"🚀 [FEN] 설정 시작 ({ip})...")
        try:
            if not self.page.is_visible("#Page302_id"): self._click_menu("#Page300_id")
            self._click_menu("#Page302_id")
            
            if not self.page.is_checked("#use-fen"): self.page.click("label[for='use-fen']")
            
            self.page.fill("#fen-server", CONFIG["FEN_SERVER"])
            self.page.fill("#cam-name", fen_name)
            self.page.click("#check-cam-name")
            time.sleep(3)
            self._handle_popup()

            self.page.click("text=저장", force=True)
            time.sleep(2)
            self._handle_popup()
            print("✅ [FEN] 설정 완료!")
            return True
        except Exception as e:
            print(f"❌ FEN 설정 실패: {e}"); return False

# ==========================================
# 🚀 메인 시나리오
# ==========================================
def main():
    sys_mgr = SystemManager()
    scanner = HybridScanner()

    # [Step 1]
    print("\n>>> [Step 1] Link-Local 모드 활성화 (Software)")
    sys_mgr.set_pc_static(CONFIG["PC_STATIC_IP"], CONFIG["PC_SUBNET"], CONFIG["PC_GATEWAY"])
    
    target_mac = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(http_credentials={"username": CONFIG["USER_ID"], "password": CONFIG["USER_PW"]})
        ui = WebController(context.new_page())
        target_mac = ui.get_mac(CONFIG["TARGET_CAMERA_IP"])
        if target_mac: ui.enable_link_local()
        browser.close()

    if not target_mac: print("❌ 테스트 중단"); return

    # [Step 2]
    print("\n>>> [Step 2] 169.254 대역 접속 검증")
    sys_mgr.set_pc_static(CONFIG["PC_AUTO_IP"], CONFIG["PC_SUBNET"]) 
    sys_mgr.flush_arp()

    link_local_ip = scanner.find_ip(target_mac, timeout=60, use_probe=True)
    
    if link_local_ip and link_local_ip.startswith("169.254"):
        print(f"🎉 [SUCCESS] Link-Local IP 확인: {link_local_ip}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(http_credentials={"username": CONFIG["USER_ID"], "password": CONFIG["USER_PW"]})
            ui = WebController(context.new_page())
            try:
                ui.page.goto(f"http://{link_local_ip}:{CONFIG['HTTP_PORT']}/setup/setup.html", timeout=20000)
                ui.disable_link_local_and_set_dhcp()
            except Exception as e: print(f"❌ 설정 변경 중 에러: {e}")
            browser.close()
    else:
        print(f"❌ Link-Local IP 발견 실패. (IP: {link_local_ip})"); return

    # [Step 3]
    print("\n" + "="*50)
    print("🚨 [ACTION] '물리적' 테스트: 사내망 랜선 뽑고, 카메라 재연결 후 y")
    print("="*50)
    input(">> y 입력: ")

    sys_mgr.set_pc_dhcp() 
    sys_mgr.flush_arp()
    
    auto_ip = scanner.find_ip(target_mac, timeout=90, use_probe=True)
    if auto_ip and auto_ip.startswith("169.254"):
        print(f"🎉 [SUCCESS] 물리적 단절 시 Auto-IP 동작 확인: {auto_ip}")
    else:
        print(f"⚠️ Auto-IP 확인 실패. IP: {auto_ip}")

    # [Step 4]
    print("\n" + "="*50)
    print("🚨 [ACTION] 사내망 랜선을 다시 연결하세요 (DHCP 환경 복구). -> y")
    print("="*50)
    input(">> y 입력: ")

    # [핵심 수정] IP 갱신하고 "10." 대역을 받을 때까지 기다림
    # 사내망 IP가 10.x.x.x 가 아니라면 인자값 수정 필요 (예: "192.168.")
    if sys_mgr.renew_ip_and_wait(expected_prefix="10."):
        sys_mgr.flush_arp()
        
        # PC가 10번대 IP를 받았으므로 이제 Scapy가 10번대 라우팅을 할 수 있음
        dhcp_ip = scanner.find_ip(target_mac, CONFIG["COMPANY_DHCP_NETWORK"], use_probe=True)
        
        if dhcp_ip and dhcp_ip.startswith("10.0.17"):
            print(f"🎉 [SUCCESS] 사내 DHCP 발견: {dhcp_ip}")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, slow_mo=1000)
                context = browser.new_context(http_credentials={"username": CONFIG["USER_ID"], "password": CONFIG["USER_PW"]})
                ui = WebController(context.new_page())
                try:
                    ui.page.goto(f"http://{dhcp_ip}:{CONFIG['HTTP_PORT']}/setup/setup.html", timeout=30000)
                    ui.configure_fen(dhcp_ip, CONFIG["FEN_NAME"])
                    print("✅ 테스트 완료. 엔터키로 종료.")
                    input()
                except: pass
                browser.close()
        else:
            print("❌ 사내망 IP 발견 실패")
    else:
        print("❌ PC가 사내망 IP를 할당받지 못했습니다. 랜선을 확인하세요.")

if __name__ == "__main__":
    main()