import time, subprocess, sys, ctypes, socket, requests
from requests.auth import HTTPDigestAuth
from scapy.all import ARP, Ether, srp, conf
from playwright.sync_api import sync_playwright
from common_actions import handle_popup
import iRAS_test

conf.verb = 0  # Scapy 조용히

# 🛠️ 설정
CFG = {
    "IFACE": "이더넷",
    "PC_IP": "10.0.131.102", "SUBNET": "255.255.0.0", "GW": "10.0.0.1",
    "AUTO_IP": "169.254.100.100",
    "CAM_IP": "10.0.131.104", "PORT": "80", "ID": "admin", "PW": "qwerty0-",
    "SCAN_NET": "10.0.17.0/24",
    "FEN_SVR": "qa1.idis.co.kr", "FEN_NAME": "FEN테스트"
}

# 🛡️ 시스템 유틸리티
def run(cmd): 
    try: subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def set_ip(ip, subnet, gw=None):
    print(f"💻 [System] PC IP 변경 -> {ip}")
    cmd = f'netsh interface ip set address name="{CFG["IFACE"]}" static {ip} {subnet}' + (f" {gw}" if gw else "")
    run(cmd); time.sleep(4)

def set_dhcp():
    print("💻 [System] PC IP 변경 -> DHCP")
    run(f'netsh interface ip set address name="{CFG["IFACE"]}" source=dhcp')
    run(f'netsh interface ip set dns name="{CFG["IFACE"]}" source=dhcp')

def wait_for_dhcp(prefix="10."):
    print("💻 [System] IP 갱신 및 할당 대기...")
    run("ipconfig /renew")
    for _ in range(30):
        try:
            if f": {prefix}" in subprocess.check_output("ipconfig", shell=True, encoding='cp949', errors='ignore'):
                print("   -> 할당 완료! ✅"); return True
        except: pass
        time.sleep(2)
    return False
def wait_for_ping(ip, timeout=30):
    print(f"📡 [System] {ip} 통신 대기 중...", end="")
    start = time.time()
    while time.time() - start < timeout:
        # 윈도우 ping 명령어로 확인 (-n 1: 1회, -w 1000: 1초 대기)
        if subprocess.call(f"ping -n 1 -w 1000 {ip}", shell=True, stdout=subprocess.DEVNULL) == 0:
            print(" 연결됨! ✅")
            return True
        print(".", end="", flush=True)
        time.sleep(1)
    print(" 실패 ❌")
    return False

# 📡 스캐너
def find_ip(target_mac, scan_range=None, timeout=60):
    print(f"🔍 [Scanner] {target_mac} 찾는 중...", end="")
    try: conf.iface = CFG["IFACE"]; conf.route.resync()
    except: pass
    
    start = time.time()
    t_mac_norm = target_mac.lower().replace(":", "-")
    
    while time.time() - start < timeout:
        print(".", end="", flush=True)
        try: # Probe
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.sendto(b'<?xml version="1.0" encoding="UTF-8"?><e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" xmlns:dn="http://www.onvif.org/ver10/network/wsdl"><e:Header><w:MessageID>uuid:84ede3de-7dec-11d0-c360-f01234567890</w:MessageID><w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To><w:Action a:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action></e:Header><e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body></e:Envelope>', ('239.255.255.250', 3702))
        except: pass
        
        try: # ARP Table Check
            out = subprocess.check_output("arp -a", shell=True).decode('cp949', errors='ignore')
            for line in out.splitlines():
                if t_mac_norm in line.lower():
                    found = line.split()[0]
                    if scan_range and "169.254" not in scan_range and "169.254" in found: continue
                    print(f" 발견! {found}"); return found
        except: pass

        if scan_range and "169.254" not in scan_range: # Active Scan
            try:
                ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=scan_range), timeout=0.5, verbose=0, iface=CFG["IFACE"])
                for _, rcv in ans:
                    if rcv.hwsrc.lower().replace("-",":") == target_mac.lower().replace("-",":"):
                        print(f" 발견! {rcv.psrc}"); return rcv.psrc
            except: pass
        time.sleep(1)
    return None

# 🕵️ API 검증기 (New!)
class ApiValidator:
    def __init__(self, ip):
        self.url = f"http://{ip}:{CFG['PORT']}/cgi-bin/webSetup.cgi"
        self.auth = HTTPDigestAuth(CFG['ID'], CFG['PW'])

    def _get(self, action):
        try:
            res = requests.get(f"{self.url}?action={action}&mode=1", auth=self.auth, timeout=5)
            if res.status_code == 200:
                # API 응답 파싱 (key=value&key2=value2 형태)
                return dict(item.split("=", 1) for item in res.text.strip().split("&") if "=" in item)
        except Exception as e: print(f"⚠️ API Error: {e}")
        return {}

    def check_dhcp(self):
        print("📡 [API] 네트워크 설정 검증...", end="")
        data = self._get("networkIp") #
        is_dhcp = data.get("type") == "dhcp"
        print(f" DHCP={'✅' if is_dhcp else '❌'} ({data.get('type')})")
        return is_dhcp

    def check_fen(self):
        print("📡 [API] FEN 설정 검증...", end="")
        data = self._get("networkDDNS") #
        use_ddns = data.get("useDDNS") == "on"
        server = data.get("serverAddress") == CFG["FEN_SVR"]
        print(f" 사용={'✅' if use_ddns else '❌'}, 서버={'✅' if server else '❌'}")
        return use_ddns and server

# 🌐 웹 컨트롤
class Web:
    def __init__(self, p):
        self.browser = p.chromium.launch(headless=False)
        self.ctx = self.browser.new_context(http_credentials={"username": CFG["ID"], "password": CFG["PW"]})
        self.page = self.ctx.new_page()

    def close(self): self.browser.close()
    def _click(self, sel): 
        try: self.page.click(sel, force=True, timeout=3000); time.sleep(0.5)
        except: pass

    def get_mac(self, ip):
        try:
            self.page.goto(f"http://{ip}:{CFG['PORT']}/setup/setup.html", timeout=10000)
            self._click("#Page200_id"); self._click("#Page201_id")
            mac = self.page.input_value("#mac-addressInfo", timeout=3000).strip()
            print(f"✅ MAC: {mac}"); return mac
        except: return None

    def set_link_local(self, enable=True):
        print(f"🖱️ [UI] Link-Local {'ON' if enable else 'OFF'} 설정")
        try:
            self._click("#Page300_id"); self._click("#Page301_id")
            chk = self.page.is_checked("#use-linklocal-only")
            if (enable and not chk) or (not enable and chk):
                self.page.click("label[for='use-linklocal-only']"); time.sleep(0.5)
            if not enable: self.page.select_option("#ip-type", value="1") # DHCP
            self.page.once("dialog", lambda d: d.accept())
            self.page.click("text=저장"); time.sleep(3)
        except: pass

    def set_fen(self, ip):
        print(f"🚀 [FEN] 설정: {ip}")
        try:
            self.page.goto(f"http://{ip}:{CFG['PORT']}/setup/setup.html")
            self._click("#Page300_id"); self._click("#Page302_id")
            
            if not self.page.is_checked("#use-fen"): self.page.click("label[for='use-fen']")
            self.page.fill("#fen-server", CFG["FEN_SVR"])
            self.page.fill("#cam-name", CFG["FEN_NAME"])
            
            # 중복 확인 -> 팝업 처리
            self.page.click("#check-cam-name"); time.sleep(1)
            handle_popup(self.page)

            # 저장 -> 팝업 처리
            self.page.click("text=저장"); time.sleep(1)
            handle_popup(self.page)
            
            print("✅ UI 설정 완료")
        except: pass

# 🚀 메인 실행
if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1); sys.exit()

    # # Step 1: Link-Local 켜기
    # print(">>> Step 1: Link-Local 활성화")
    # set_ip(CFG["PC_IP"], CFG["SUBNET"], CFG["GW"])
    # mac = None
    # with sync_playwright() as p:
    #     w = Web(p)
    #     mac = w.get_mac(CFG["CAM_IP"])
    #     if mac: w.set_link_local(True)
    #     w.close()
    
    # if not mac: sys.exit()

    # # Step 2: 169 대역 확인
    # print("\n>>> Step 2: 169.254 검증")
    # set_ip(CFG["AUTO_IP"], CFG["SUBNET"])
    # run("arp -d *")
    
    # ip = find_ip(mac, timeout=40)
    # if ip and "169.254" in ip:
    #     print(f"🎉 성공: {ip}")
    #     with sync_playwright() as p:
    #         w = Web(p); w.page.goto(f"http://{ip}/setup/setup.html")
    #         w.set_link_local(False) # DHCP로 복구
    #         w.close()
    
    # # Step 3: 물리 테스트
    # input("\n🚨 [ACTION] 사내망 뽑고, 카메라 재부팅 후 엔터 >> ")
    # set_dhcp(); run("arp -d *")
    # ip = find_ip(mac, timeout=60)
    # print(f"🎉 Auto-IP: {ip}" if ip and "169.254" in ip else "⚠️ 실패")

    # Step 4: 복구 및 검증 (Web 설정)
    input("\n🚨 [ACTION] 사내망 연결 후 엔터 >> ")
    if wait_for_dhcp("10."):
        # IP 스캔 (MAC 주소 필요, 실제 실행 시엔 위에서 받아와야 함)
        # ip = find_ip(mac, CFG["SCAN_NET"]) 
        ip = CFG["CAM_IP"] # 테스트용 고정 IP 사용 시

        if ip:
            # 1. FEN 설정 (Web UI)
            print("\n>>> Step 4-1: Web에서 FEN 설정")
            with sync_playwright() as p:
                w = Web(p); w.set_fen(ip); w.close()
            
            # 2. API 검증
            print("\n>>> Step 4-2: API 검증")
            validator = ApiValidator(ip)
            if validator.check_dhcp() and validator.check_fen():
                print("   ✅ Web/API 설정 검증 Pass!")
            else:
                print("   ❌ Web/API 설정 검증 Fail!")

            # 3. iRAS FEN 설정 및 연결 테스트 (Step 5)
            print("\n>>> Step 5: iRAS에서 FEN 설정 및 연결 테스트")
            target_device_name = "104_T6631"  # iRAS에 등록된 장치명
            
            # iRAS 자동화 실행
            result = iRAS_test.run_fen_setup_process(target_device_name, CFG["FEN_NAME"])
            
            if result:
                print("\n🎉 [최종 완료] iRAS FEN 설정 및 테스트 성공!")
            else:
                print("\n🔥 [실패] iRAS 자동화 중 오류 발생")
            
            input("종료하려면 엔터...")