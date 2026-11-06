import os
import sys
import time
import ctypes
import socket
import subprocess
import pyautogui
import traceback
import winsound
from datetime import datetime
from pycaw.pycaw import AudioUtilities

# --- KNIŽNICE PRE IKONU ---
import pystray
from PIL import Image, ImageDraw, ImageFont

# =====================================================================
#               POUŽÍVATEĽSKÁ KONFIGURÁCIA (UPRAVTE TU)
# =====================================================================

VERZIA_SKRIPTU = "1.25"

# 1. Nastavenia domácej siete (skript je aktívny len doma, na cudzích sieťach spí)
HOME_SSIDS = ["Moja_Domaca_WiFi_2.4G", "Moja_Domaca_WiFi_5G"]
HOME_IP_PREFIX = "192.168.100."
# IP adresa zariadenia, ktoré odpovedá na ping LEN DOMA (napr. domáci router, NAS, smart reproduktor)
DOMACE_ZARIADENIE_IP = "192.168.100.1"

# 2. Časové limity (v sekundách)
LIMIT_NECINNOSTI = 900     # 900 = 15 minút nečinnosti a ticha pred spustením príkazov
OCHRANA_PO_VYPNUTI = 10.0  # 10 sekúnd ochrana po odoslaní príkazov

# 3. Príkazy pre Google Assistant Unofficial Desktop Client
# Príkazy odoslané po uplynutí limitu nečinnosti (napr. vypnutie zásuviek, svetiel, LED pásov, reproduktorov)
ZOZNAM_VYPNUTIE = [
    "turn off pc",
    "stop studio mini",
    "turn off left and right",
    "turn off up and down"
]

# Príkazy pri návrate k PC (vykonajú sa vždy pri pohnutí myšou)
ZOZNAM_ZAPNUTIE_ZAKLAD = [
    "turn on pc"
]

# Príkazy pri návrate k PC, ktoré sa pridajú iba vtedy, keď je vonku tma (napr. smart svetlá a LED pásy)
ZOZNAM_ZAPNUTIE_TMA = [
    "turn on left and right",
    "turn on down"
]

# 4. Nastavenia a časovanie pre Google Assistant Unofficial Desktop Client (v sekundách)
NAZOV_OKNA = "Google Assistant Unofficial Client"
CESTA_K_ASISTENTOVI = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Google Assistant\Google Assistant.exe")

DELAY_START_POZADIE = 8.0
DELAY_VYKRESLENIE = 5.0
DELAY_PREBUDENIE = 4.0
DELAY_MEDZI_PRIKAZMI = 2.6
DELAY_PISANIE = 0.04

# 5. Zobrazenie ladiacej konzoly (True = skrytá na pozadí, False = viditeľné okno CMD)
SKRYT_KONZOLU = True

# 6. Časy východu a západu slnka podľa mesiacov (1 až 12) - predvolené pre Bratislavu (upravte podľa vášho mesta)
SLNKO_KALENDAR = {
    1:  ((7, 22), (16,  7)), 2:  ((6, 42), (16, 55)), 3:  ((5, 45), (17, 42)),
    4:  ((5, 42), (19, 32)), 5:  ((5,  2), (20, 17)), 6:  ((4, 52), (20, 45)),
    7:  ((5, 12), (20, 35)), 8:  ((5, 52), (19, 52)), 9:  ((6, 37), (18, 52)),
    10: ((6, 55), (17, 50)), 11: ((7, 10), (16, 40)), 12: ((7, 37), (16,  2))
}
# =====================================================================

pyautogui.FAILSAFE = True
CREATE_NO_WINDOW = 0x08000000 if SKRYT_KONZOLU else 0

if SKRYT_KONZOLU:
    def print(*args, **kwargs):
        pass

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

# Nastavenie neznamienkového 32-bitového typu pre GetTickCount (prevencia pretečenia)
ctypes.windll.kernel32.GetTickCount.restype = ctypes.c_uint

def riadenie_konzoly():
    if not SKRYT_KONZOLU:
        ctypes.windll.kernel32.AllocConsole()
        sys.stdout = open('CONOUT$', 'w', encoding='utf-8')
        sys.stderr = open('CONOUT$', 'w', encoding='utf-8')

# --- DETEKCIA SPÁNKU A PREBUDENIA NOTEBOOKU ---
prebieha_prebudenie_zo_spanku = False
cas_resetu_necinnosti = time.time()
zariadenia_vypnute = False
varovanie_pipnute = False

CMPOWERNOTIFY_CALLBACK = ctypes.WINFUNCTYPE(
    ctypes.c_ulong,
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_void_p
)

class DEVICE_NOTIFY_SUBSCRIBE_PARAMETERS(ctypes.Structure):
    _fields_ = [
        ("Callback", CMPOWERNOTIFY_CALLBACK),
        ("Context", ctypes.c_void_p)
    ]

_power_callback_ref = None
_power_params_ref = None
_power_handle_ref = ctypes.c_void_p()

def _power_notify_callback(context, event_type, setting):
    global prebieha_prebudenie_zo_spanku, zariadenia_vypnute, varovanie_pipnute, cas_resetu_necinnosti
    if event_type == 0x0004:  # PBT_APMSUSPEND (Uspanie PC/notebooku)
        prebieha_prebudenie_zo_spanku = True
        cas_resetu_necinnosti = time.time()
        varovanie_pipnute = False
        print("\n[P] Systém prechádza do spánku. Nulujem časovač nečinnosti.")
    elif event_type in (0x0007, 0x0012):  # PBT_APMRESUMESUSPEND / PBT_APMRESUMEAUTOMATIC (Prebudenie)
        prebieha_prebudenie_zo_spanku = True
        zariadenia_vypnute = False
        cas_resetu_necinnosti = time.time()
        varovanie_pipnute = False
        print("\n[P] Systém sa prebudil zo spánku. Časovač nečinnosti začína od 0.")
    return 0

def registruj_sledovanie_spanku():
    global _power_callback_ref, _power_params_ref, _power_handle_ref
    try:
        _power_callback_ref = CMPOWERNOTIFY_CALLBACK(_power_notify_callback)
        _power_params_ref = DEVICE_NOTIFY_SUBSCRIBE_PARAMETERS(_power_callback_ref, None)
        ctypes.windll.powrprof.PowerRegisterSuspendResumeNotification(
            2,  # DEVICE_NOTIFY_CALLBACK
            ctypes.byref(_power_params_ref),
            ctypes.byref(_power_handle_ref)
        )
    except Exception:
        pass

def je_prihlasovacia_obrazovka():
    """Vráti True iba vtedy, ak je aktívna prihlasovacia/zamknutá obrazovka Windowsu (Winlogon)."""
    try:
        h_desk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
        if h_desk == 0:
            return True
        ctypes.windll.user32.CloseDesktop(h_desk)
        return False
    except Exception:
        return False

def nastav_rezim_napajania(drzat_bdele):
    """Zabráni predčasnému uspaniu obrazovky/notebooku počas odpočtu pred vypnutím zariadení."""
    try:
        if drzat_bdele:
            # ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001) | ES_DISPLAY_REQUIRED (0x00000002)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
        else:
            # ES_CONTINUOUS (0x80000000) - uvoľnenie, štandardný spánok povolený
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    except Exception:
        pass

# --- DETEKCIA SIETE A UDALOSTÍ ---
def get_wifi_ssid():
    try:
        output = subprocess.check_output("netsh wlan show interfaces", shell=True, creationflags=CREATE_NO_WINDOW).decode('utf-8', errors='ignore')
        for line in output.splitlines():
            if "SSID" in line and "BSSID" not in line:
                return line.split(":")[1].strip()
    except Exception:
        pass
    return None

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

def is_on_home_network():
    ssid = get_wifi_ssid()
    if ssid and ssid in HOME_SSIDS:
        return True
    
    ip = get_local_ip()
    if ip and ip.startswith(HOME_IP_PREFIX):
        try:
            res = subprocess.run(
                f"ping -n 1 -w 300 {DOMACE_ZARIADENIE_IP}", 
                shell=True, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW
            )
            return res.returncode == 0
        except Exception:
            return False
        
    return False

# --- INTEGROVANÝ SYSTÉM PRE ZACHYTÁVANIE CHÝB ---
def spracuj_a_zaloguj_chybu(titulok_chyby, detail_chyby=None, zobraziť_okno=True):
    try:
        priecinok = os.path.dirname(os.path.abspath(__file__))
        if not priecinok:
            priecinok = os.getcwd()
            
        cesta_k_logu = os.path.join(priecinok, "chyba_assistant_automation.txt")
        cas_chyby = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(cesta_k_logu, "a", encoding="utf-8") as f:
            f.write(f"=== CHYBA DETEGOVANÁ: {cas_chyby} ===\n")
            f.write(f"Kontext: {titulok_chyby}\n")
            if detail_chyby:
                f.write(f"Detaily: {detail_chyby}\n")
            f.write(traceback.format_exc())
            f.write("\n" + "="*40 + "\n\n")
        
        if zobraziť_okno:
            kliknute = ctypes.windll.user32.MessageBoxW(
                None,
                f"V skripte PC Google Assistant Automation nastala chyba:\n{titulok_chyby}\n\nChcete otvoriť textový súbor s logom chýb?",
                "Chyba aplikácie - PC Google Assistant Automation",
                0x4 | 0x10
            )
            if kliknute == 6:
                os.startfile(cesta_k_logu)
            
    except Exception:
        pass

# --- LOGIKA PRE GRAFICKÉ IKONY (SYSTEM TRAY) ---
def vytvor_ikonu_blesku():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    body_blesku = [(35, 5), (15, 35), (32, 35), (25, 60), (48, 25), (30, 25)]
    draw.polygon(body_blesku, fill=(255, 215, 0, 255))
    return img

def vytvor_ikonu_zzz():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    try:
        font_V = ImageFont.truetype("arialbd.ttf", 38)
        font_M = ImageFont.truetype("arialbd.ttf", 26)
        font_S = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font_V = font_M = font_S = ImageFont.load_default()
    
    c1 = (0, 119, 182, 255)
    c2 = (0, 150, 199, 255)
    c3 = (72, 202, 228, 255)
    
    draw.text((28, 2), "Z", fill=c1, font=font_V)
    draw.text((14, 24), "z", fill=c2, font=font_M)
    draw.text((2, 44), "z", fill=c3, font=font_S)
    
    return img

IKONA_BLESK = vytvor_ikonu_blesku()
IKONA_ZZZ = vytvor_ikonu_zzz()

systemova_ikona = None
manualna_pauza = False
aktualny_typ_ikony = "blesk"

def nastav_ikonu(typ):
    global aktualny_typ_ikony
    if systemova_ikona and aktualny_typ_ikony != typ:
        systemova_ikona.icon = IKONA_ZZZ if typ == "zzz" else IKONA_BLESK
        aktualny_typ_ikony = typ

def ukonci_skript(icon, item):
    nastav_rezim_napajania(False)
    icon.stop()
    os._exit(0)

def restartuj_skript(icon, item):
    print("\n[R] Reštartujem skript...")
    nastav_rezim_napajania(False)
    try:
        icon.stop()
    except Exception:
        pass
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__)] + sys.argv[1:],
        creationflags=CREATE_NO_WINDOW
    )
    os._exit(0)

def prepni_pauzu(icon, item):
    global manualna_pauza, cas_resetu_necinnosti, varovanie_pipnute
    manualna_pauza = not manualna_pauza
    cas_resetu_necinnosti = time.time()
    varovanie_pipnute = False
    if manualna_pauza:
        print("\n[M] Manuálna pauza AKTIVOVANÁ. Automatizácia je pozastavené.")
        nastav_rezim_napajania(False)
        nastav_ikonu("zzz")
    else:
        print("\n[M] Manuálna pauza DEAKTIVOVANÁ. Automatizácia opäť beží.")

def spustis_systémovú_lištu():
    global systemova_ikona, aktualny_typ_ikony
    try:
        na_domacej = is_on_home_network()
        startovacia_ikona = IKONA_BLESK if na_domacej else IKONA_ZZZ
        aktualny_typ_ikony = "blesk" if na_domacej else "zzz"

        menu = pystray.Menu(
            pystray.MenuItem('Google Assistant Automatizácia', lambda: None, enabled=False),
            pystray.MenuItem('Pozastaviť (Spiaci režim)', prepni_pauzu, checked=lambda item: manualna_pauza),
            pystray.MenuItem('Reštartovať skript', restartuj_skript),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Ukončiť skript', ukonci_skript),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f'Verzia: {VERZIA_SKRIPTU}', lambda: None, enabled=False)
        )
        systemova_ikona = pystray.Icon("AssistantAutomation", startovacia_ikona, f"PC Google Assistant Automation (v{VERZIA_SKRIPTU})", menu)
        systemova_ikona.run_detached()
    except Exception as e:
        spracuj_a_zaloguj_chybu("Zlyhala inicializácia ikony v lište (System Tray)", str(e))

def get_idle_time():
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        aktualny_tick = ctypes.windll.kernel32.GetTickCount()
        millis = (aktualny_tick - lii.dwTime) & 0xFFFFFFFF
        return millis / 1000.0
    except Exception as e:
        spracuj_a_zaloguj_chybu("Chyba pri zisťovaní času nečinnosti systému", str(e))
        return 0.0

def is_audio_playing():
    try:
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.State == 1:
                if session.Process and session.Process.name() != "System Interrupts":
                    return True
        return False
    except Exception:
        return False

def is_assistant_running():
    try:
        output = subprocess.check_output("tasklist", shell=True, text=True, creationflags=CREATE_NO_WINDOW)
        return "Google Assistant.exe" in output
    except Exception:
        return False

def je_tma():
    try:
        teraz = datetime.now()
        mesiac = teraz.month
        if mesiac not in SLNKO_KALENDAR:
            return True
        (vychod_h, vychod_m), (zapad_h, zapad_m) = SLNKO_KALENDAR[mesiac]
        aktualne_minuty = teraz.hour * 60 + teraz.minute
        minuty_vychod = vychod_h * 60 + vychod_m
        minuty_zapad = zapad_h * 60 + zapad_m
        return aktualne_minuty < minuty_vychod or aktualne_minuty > minuty_zapad
    except Exception as e:
        spracuj_a_zaloguj_chybu("Chyba pri výpočte svetelných podmienok", str(e))
        return True

def posli_sekvenciu_prikazov(prikazy):
    try:
        if not is_on_home_network():
            print("[!] PC nie je na domácej sieti. Príkazy do asistenta sa preskakujú.")
            return

        if not os.path.exists(CESTA_K_ASISTENTOVI):
            spracuj_a_zaloguj_chybu("Google Assistant nebol nájdený na zadanej ceste", CESTA_K_ASISTENTOVI, zobraziť_okno=False)
            return

        # Kontrola výhradne bodu (0, 0), plne kompatibilná aj s viacerými monitormi nad sebou
        mx, my = pyautogui.position()
        if mx == 0 and my == 0:
            pyautogui.moveTo(200, 200)

        if not is_assistant_running():
            print("Google Assistant je úplne vypnutý. Spúšťam Fázu 1 (Štart na pozadí)...")
            subprocess.Popen(CESTA_K_ASISTENTOVI, creationflags=CREATE_NO_WINDOW)
            print(f"Čakám {DELAY_START_POZADIE} sekúnd na načítanie do systémovej lišty...")
            time.sleep(DELAY_START_POZADIE)
            
            print("Spúšťam Fázu 2 (Otvorenie grafického okna)...")
            subprocess.Popen(CESTA_K_ASISTENTOVI, creationflags=CREATE_NO_WINDOW)
            print(f"Čakám {DELAY_VYKRESLENIE} sekúnd na vykreslenie okna...")
            time.sleep(DELAY_VYKRESLENIE)
        else:
            print("Google Assistant beží na pozadí. Prebúdzam okno...")
            subprocess.Popen(CESTA_K_ASISTENTOVI, creationflags=CREATE_NO_WINDOW)
            print(f"Čakám {DELAY_PREBUDENIE} sekundy na otvorenie okna...")
            time.sleep(DELAY_PREBUDENIE)
        
        # Počkáme, kým sa okno Asistenta reálne objaví (ak bolo po dlhej nečinnosti odložené v swape)
        hwnd = 0
        for _ in range(16):
            hwnd = ctypes.windll.user32.FindWindowW(None, NAZOV_OKNA)
            if hwnd and ctypes.windll.user32.IsWindowVisible(hwnd):
                break
            time.sleep(0.5)

        if not hwnd:
            print("[!] Nenašiel som okno podľa názvu. Prerušujem proces.")
            return

        print("Zameriavam okno Asistenta...")
        for pokus in range(3):
            pyautogui.press('alt')
            time.sleep(0.2)
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.6)
            if ctypes.windll.user32.GetForegroundWindow() == hwnd:
                break
        
        for index, prikaz in enumerate(prikazy, 1):
            aktualne_hwnd = ctypes.windll.user32.GetForegroundWindow()
            if aktualne_hwnd != hwnd:
                print("[!] Okno Asistenta stratilo fokus. Zastavujem písanie.")
                break
            
            print(f"[{index}/{len(prikazy)}] Píšem príkaz: {prikaz}")
            pyautogui.write(prikaz, interval=DELAY_PISANIE)
            pyautogui.press('enter')
            
            print(f"Čakám {DELAY_MEDZI_PRIKAZMI} sekundy na vykonanie...")
            time.sleep(DELAY_MEDZI_PRIKAZMI)
        
        print("Zatváram grafické okno aplikácie (Alt+F4)...")
        aktualne_hwnd = ctypes.windll.user32.GetForegroundWindow()
        if aktualne_hwnd == hwnd:
            pyautogui.hotkey('alt', 'f4')
            print("Všetky príkazy odoslané, okno upratané.")
            
    except pyautogui.FailSafeException:
        print("[!] Aktivovaná záchranná brzda PyAutoGUI. Prerušujem odosielanie.")
    except Exception as e:
        spracuj_a_zaloguj_chybu("Chyba počas simulácie stláčania kláves", str(e))

# Štart prostredia
riadenie_konzoly()
registruj_sledovanie_spanku()
spustis_systémovú_lištu()
print(f"PC Google Assistant Automation (v{VERZIA_SKRIPTU}) s ikonou v lište spustený...")

mimo_domova_rezim = False
pocet_zlyhani_siete = 0
cas_posledneho_vypnutia = 0.0
cas_resetu_necinnosti = time.time()
last_loop_time = time.time()

try:
    while True:
        current_time = time.time()
        time_diff = current_time - last_loop_time
        
        # 1. Detekcia dlhého spánku notebooku (> 15 sekúnd zamrznutia cyklu)
        if time_diff > 15.0:
            print(f"\n[!] Detegované prebudenie zo spánku (pauza {int(time_diff)}s). Nulujem časovač nečinnosti.")
            prebieha_prebudenie_zo_spanku = True
            zariadenia_vypnute = False
            varovanie_pipnute = False
            cas_resetu_necinnosti = time.time()
            last_loop_time = time.time()
            time.sleep(1)
            continue
            
        last_loop_time = current_time

        # 2. Ak sa PC práve prebudil zo spánku a používateľ je ešte na prihlasovacej obrazovke, držíme časovač na 0
        if prebieha_prebudenie_zo_spanku:
            if je_prihlasovacia_obrazovka():
                cas_resetu_necinnosti = time.time()
                varovanie_pipnute = False
                time.sleep(1)
                last_loop_time = time.time()
                continue
            else:
                # Používateľ sa práve prihlásil na pracovnú plochu -> spúšťame čistý odpočet od 0s
                prebieha_prebudenie_zo_spanku = False
                zariadenia_vypnute = False
                varovanie_pipnute = False
                cas_resetu_necinnosti = time.time()

        # 3. Manuálna pauza cez ikonu v lište
        if manualna_pauza:
            nastav_rezim_napajania(False)
            nastav_ikonu("zzz")
            cas_resetu_necinnosti = time.time()
            varovanie_pipnute = False
            time.sleep(1)
            last_loop_time = time.time()
            continue

        # 4. Kontrola domácej siete (s toleranciou voči krátkemu výpadku Wi-Fi)
        if not is_on_home_network():
            pocet_zlyhani_siete += 1
            if not mimo_domova_rezim and pocet_zlyhani_siete >= 3:
                print("\n[i] Zistená cudzia sieť / mimo domova. Prepínam do spánkového režimu.")
                mimo_domova_rezim = True
            
            if mimo_domova_rezim:
                nastav_rezim_napajania(False)
                nastav_ikonu("zzz")
                cas_resetu_necinnosti = time.time()
                zariadenia_vypnute = False
                varovanie_pipnute = False
                time.sleep(5)
                last_loop_time = time.time()
                continue
        else:
            pocet_zlyhani_siete = 0
            if mimo_domova_rezim:
                print("\n[*] Návrat na domácu sieť! Obnovujem aktívne sledovanie od 0s...")
                mimo_domova_rezim = False
                zariadenia_vypnute = False
                varovanie_pipnute = False
                cas_resetu_necinnosti = time.time()
                nastav_ikonu("blesk")
            
        raw_idle_sec = get_idle_time()
        audio_active = is_audio_playing()

        # Efektívny čas nečinnosti: menšia hodnota z fyzickej nečinnosti myši/klávesnice a času od pripojenia/prebudenia
        idle_sec = min(raw_idle_sec, time.time() - cas_resetu_necinnosti)
        
        if not zariadenia_vypnute:
            nastav_ikonu("blesk")
            # Počas aktívneho sledovania doma nedovolíme, aby zhasnutie obrazovky predčasne uspalo skript pred limitom
            nastav_rezim_napajania(True)
            
            # --- ZVUKOVÉ UPOZORNENIE (1 MINÚTU PRED SPUSTENÍM PRÍKAZOV) ---
            CAS_VAROVANIA = max(5, LIMIT_NECINNOSTI - 60)
            
            if idle_sec >= CAS_VAROVANIA and idle_sec < LIMIT_NECINNOSTI and not audio_active:
                if not varovanie_pipnute:
                    winsound.Beep(1000, 200)
                    time.sleep(0.1)
                    winsound.Beep(1200, 300)
                    varovanie_pipnute = True
                    print("\n[!] Upozornenie: O 1 minútu sa spustí sekvencia príkazov pri nečinnosti.")
            
            if idle_sec < CAS_VAROVANIA:
                varovanie_pipnute = False

            # --- SPUSTENIE PRÍKAZOV PO DOSIAHNUTÍ LIMITU NEČINNOSTI ---
            if idle_sec >= LIMIT_NECINNOSTI and not audio_active:
                print(f"\n[!] Zistená nečinnosť ({int(idle_sec)}s) a ticho. Odosielam príkazy do Google Assistant...")
                posli_sekvenciu_prikazov(ZOZNAM_VYPNUTIE)
                
                zariadenia_vypnute = True
                varovanie_pipnute = False
                cas_resetu_necinnosti = time.time()
                cas_posledneho_vypnutia = time.time()
                last_loop_time = time.time()
                # Po odoslaní vypínacích príkazov uvoľníme režim napájania, aby mohol monitor/notebook bežne zhasnúť
                nastav_rezim_napajania(False)
                print("-> Príkazy pri nečinnosti odoslané. Čakám na návrat k PC...")
                
        else:
            nastav_ikonu("blesk")
            nastav_rezim_napajania(False)
            varovanie_pipnute = False
            
            # Kontrola: Po vypršaní 10-sekundovej ochrannej lehoty od vypnutia reaguj na pohyb myšou
            if (time.time() - cas_posledneho_vypnutia) > OCHRANA_PO_VYPNUTI:
                if raw_idle_sec < 3.0: 
                    print("\n[*] Detegovaný návrat k PC! Skladám príkazy na zapnutie...")
                    print("[~] Čakám 3 sekundy na prebudenie grafického prostredia Windowsu...")
                    
                    for _ in range(3):
                        time.sleep(1)
                        last_loop_time = time.time()
                    
                    prikazy_zapnutie = list(ZOZNAM_ZAPNUTIE_ZAKLAD)
                    
                    if je_tma():
                        print("[~] Podľa kalendára je vonku tma. Pridávam príkazy pre nočný režim / osvetlenie.")
                        prikazy_zapnutie.extend(ZOZNAM_ZAPNUTIE_TMA)
                    else:
                        print("[~] Podľa kalendára je vonku svetlo. Príkazy pre tmu vynechávam.")
                        
                    posli_sekvenciu_prikazov(prikazy_zapnutie)
                    
                    zariadenia_vypnute = False
                    cas_resetu_necinnosti = time.time()
                    last_loop_time = time.time()
                    print("-> Zariadenia sú opäť zapnuté. Prepínam na sledovanie nečinnosti...")
                    
                    for _ in range(3):
                        time.sleep(1)
                        last_loop_time = time.time()
                
        time.sleep(1)

except Exception as e:
    nastav_rezim_napajania(False)
    spracuj_a_zaloguj_chybu("Kritická chyba hlavného monitorovacieho cyklu.", str(e))
    os._exit(1)