# ⚡ PC Google Assistant Automation (Windows)

Univerzálny Python skript pre Windows (v1.25), ktorý automaticky ovláda **[Google Assistant Unofficial Desktop Client](https://github.com/Melvin-Abraham/Google-Assistant-Unofficial-Desktop-Client)** a spúšťa vami zvolené príkazy alebo celé scenáre (Routines) vtedy, keď **odídete od počítača (nečinnosť)** a keď sa k nemu **opäť vrátite**.

V predvolenom nastavení slúži na automatické vypínanie zariadení v izbe alebo pracovni (smart svetlá, LED pásy, reproduktory, smart zásuvky) po 15 minútach nečinnosti a ich opätovné zapnutie pri pohnutí myšou – s inteligentným vyhodnotením, či je vonku tma alebo svetlo. **Do skriptu si však môžete zadať akékoľvek vlastné príkazy, časovače, mesto či sieťové podmienky.**

---

## 🎯 Ako to funguje v praxi (príklad použitia)

1. **Pracujete pri PC alebo pozeráte film:** Skript beží ticho v systémovej lište (System Tray) pri hodinách (ikona ⚡). Ak sa hýbe myš, stláča klávesnica alebo na PC hrá akýkoľvek zvuk (hudba, YouTube, hovor), skript nič nevypína.
2. **Odídete od PC:** Po 14 minútach nečinnosti a ticha skript jemne zapípa (upozornenie 1 minútu vopred, aby ste mohli pohnúť myšou, ak ste stále v miestnosti).
3. **Automatické vypnutie (15. minúta):** Ak na upozornenie nereagujete, skript prebudí okno Google Asistenta, odošle sériu príkazov (napr. vypnutie smart zásuvky monitorov, LED pásov, stolových lámp a reproduktora), okno Asistenta zatvorí a uvoľní systém pre bežný spánok obrazovky.
4. **Návrat k PC:** Akonáhle sa vrátite a pohnete myšou, skript okamžite odošle príkazy na zapnutie. Zároveň skontroluje astronomický kalendár – ak je vonku deň, zapne len hlavné zariadenia; ak je už po západe slnka, automaticky rozsvieti aj smart osvetlenie a LED pásy.
5. **Režim mimo domova (Notebooky):** Ak si notebook vezmete do kancelárie alebo na inú Wi-Fi/káblovú sieť, skript to rozpozná, prepne sa do spánku (ikona 💤) a neodosiela žiadne príkazy, kým sa opäť nepripojíte na domácu sieť.

---

## ✨ Hlavné funkcie

* **Ľubovoľné príkazy a scenáre:** Môžete zadať jeden príkaz alebo celú sekvenciu príkazov pre Google Home (ovládanie svetiel, zásuviek, klimatizácie, kúrenia, žalúzií alebo vlastných Google Routines).
* **Detekcia prehrávania zvuku (`pycaw`):** Príkazy pri nečinnosti sa nespustia, ak na PC práve beží video, hudba alebo online hovor.
* **Zvukové varovanie pred spustením:** Pípnutie minútu pred aktiváciou nečinnosti zabráni nechcenému zhasnutiu izby, keď napríklad len čítate dokument bez dotyku myši.
* **Inteligentný kalendár Deň / Noc:** Rozdelenie zapínacích príkazov na tie, ktoré sa majú vykonať vždy, a tie, ktoré sa pridajú len po zotmení (podľa nastaviteľných časov východu a západu slnka pre vaše mesto).
* **Detekcia domácej Wi-Fi a Ethernet kábla:** Rozlíši domácu sieť od cudzej aj v prípade, že firemná sieť používa rovnaký IP rozsah (napr. `192.168.100.x`), pomocou rýchleho pingu na zvolené domáce zariadenie.
* **Podpora Modern Standby (S0), viacmonitorových zostáv a zamknutej obrazovky:** Plne kompatibilné s novšími notebookmi aj zostavami s viacerými monitormi nad sebou alebo vedľa seba. Čas strávený v spánku alebo na prihlasovacej obrazovke Windowsu sa nezapočítava do nečinnosti.
* **System Tray menu:** Rýchle pozastavenie sledovania (Manuálna pauza), reštartovanie skriptu, informácia o verzii (v1.25) a ukončenie pravým kliknutím na ikonu v lište.

---

## 🛠️ Požiadavky

1. **Operačný systém:** Windows 10 / Windows 11
2. **Python:** verzia 3.9 alebo novšia
3. **Google Assistant pre PC:** Nainštalovaný a prihlásený **[Google Assistant Unofficial Desktop Client](https://github.com/Melvin-Abraham/Google-Assistant-Unofficial-Desktop-Client)**
   * Stiahnuť si ho môžete priamo zo sekcie [Releases](https://github.com/Melvin-Abraham/Google-Assistant-Unofficial-Desktop-Client/releases).
   * Predvolená cesta po inštalácii, ktorú skript automaticky hľadá: `%LOCALAPPDATA%\Programs\Google Assistant\Google Assistant.exe`.

---

## 🚀 Inštalácia a prispôsobenie

1. **Stiahnite si tento repozitár:**
   ```bash
   git clone [https://github.com/kozmali/pc-google-assistant-automation.git](https://github.com/kozmali/pc-google-assistant-automation.git)
   cd pc-google-assistant-automation
   ```

2. **Nainštalujte potrebné Python knižnice:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Upravte si premenné podľa seba:**
   Otvorte súbor `pc_google_assistant_automation.pyw` v ľubovoľnom textovom editore a na samom začiatku v sekcii **`POUŽÍVATEĽSKÁ KONFIGURÁCIA`** si nastavte:
   * `HOME_SSIDS`: Názvy vašich domácich Wi-Fi sietí.
   * `HOME_IP_PREFIX` a `DOMACE_ZARIADENIE_IP`: IP prefix vašej siete a IP adresa domáceho routera / smart zariadenia (slúži na overenie, že ste doma, ak pripájate notebook cez Ethernet kábel).
   * `LIMIT_NECINNOSTI`: Po koľkých sekundách nečinnosti sa má aktivovať Google Assistant (predvolené `900` = 15 minút).
   * `ZOZNAM_VYPNUTIE`: Zoznam príkazov, ktoré sa napíšu do Google Asistenta pri odchode od PC.
   * `ZOZNAM_ZAPNUTIE_ZAKLAD`: Príkazy, ktoré sa odošlú pri návrate k PC bez ohľadu na dennú dobu.
   * `ZOZNAM_ZAPNUTIE_TMA`: Príkazy, ktoré sa pri návrate k PC pridajú iba vtedy, keď je vonku tma (napr. zapnutie svetiel a LED pásov).
   * `SLNKO_KALENDAR`: Časy východu a západu slnka pre jednotlivé mesiace (1–12), ktoré si môžete upraviť podľa vášho mesta.

4. **Spustenie:**
   Spustite súbor dvojklikom na `pc_google_assistant_automation.pyw` (prípona `.pyw` zabezpečí tichý beh na pozadí bez okna príkazového riadka).

### Automatické spustenie pri štarte Windows
Stlačte `Win + R`, napíšte `shell:startup`, potvrďte klávesom Enter a do otvoreného priečinka vložte **odkaz (zástupcu)** na súbor `pc_google_assistant_automation.pyw`.

---

## 👤 Autor

**Dominik Kozmáli**
* Web: [kozmali.sk](https://kozmali.sk)
* GitHub: [@kozmali](https://github.com/kozmali)