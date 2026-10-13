"""Content of the installation manual (DOC-002), Slovak."""
from __future__ import annotations

from pathlib import Path

from manuals.kit import Manual

VERSION = "0.6.0"


def build(screens: Path, out: Path) -> None:
    m = Manual("Inštalačná príručka",
               "Inštalácia, prvé spustenie, zálohovanie a riešenie problémov",
               VERSION, "ArgusGrid – Inštalačná príručka", "správcov systému a prevádzkovateľov")
    S = lambda name: screens / f"{name}.png"  # noqa: E731

    m.h(1, "1. Prehľad")
    m.p("Táto príručka popisuje inštaláciu balíka ArgusGrid na Windows, prvé spustenie, základnú konfiguráciu, "
        "zálohovanie a riešenie problémov. Ovládanie aplikácie opisuje samostatná používateľská príručka.")
    m.h(2, "1.1 Typy balíkov")
    m.table(["Balík", "Obsah", "Použitie"], [
        ["production", "aplikácia bez ukážkových údajov a bez simulátora", "ostrá prevádzka"],
        ["demo", "aplikácia, ukážkový objekt „Kestrel Ridge Energy Complex“ a simulátor útoku", "ukážky, školenie, overenie"],
    ], [3.0, 9.0, 5.0])
    m.p("Názov súboru obsahuje verziu, typ balíka a profil nasadenia, napríklad "
        "`ArgusGrid-0.6.0-production-civil.zip`. Profil **civil** je štandardný; profil **defense** vynúti "
        "iba offline spravodajstvo, zobrazí označenie nasadenia a predĺži uchovávanie telemetrie na 90 dní.")
    m.h(2, "1.2 Čo musíte mať pripravené")
    m.table(["Požiadavka", "Podrobnosti"], [
        ["Operačný systém", "Windows 10/11 alebo Windows Server s PowerShell 5.1 (overené na Windows 11)"],
        ["Python", "3.12 alebo novší; setup si ho nenainštaluje"],
        ["PostgreSQL", "verzia 16, prázdna databáza a rola, ktorá je jej vlastníkom"],
        ["Sieť", "pri setupe prístup k balíčkom Python (pip) alebo interné zrkadlo; za behu aplikácia "
                 "internet nepotrebuje, ak sú vypnuté online zdroje spravodajstva"],
        ["Prehliadač", "aktuálny Chrome, Edge alebo Firefox; overené v Chromium"],
        ["Čas", "presné systémové hodiny (NTP); podpisy požiadaviek zariadení a platnosť hesiel závisia od času"],
    ], [4.0, 13.0])
    m.note("Overenie na čistom stroji nebolo súčasťou tohto vydania: inštalácia bola overená na vývojovom "
           "stroji, kde už Python a PostgreSQL boli. Prvú ostrú inštaláciu preto spravte najprv na skúšobnom serveri.")

    m.h(1, "2. Príprava")
    m.h(2, "2.1 Overenie balíka")
    m.p("K archívu patrí súbor `.zip.sha256`. Skontrolujte, že kontrolný súčet súhlasí:")
    m.code("certutil -hashfile ArgusGrid-0.6.0-production-civil.zip SHA256")
    m.p("Hodnota musí byť rovnaká ako v súbore `.sha256`. Archív nie je digitálne podpísaný; kontrolný súčet "
        "chráni pred poškodením pri prenose, nie pred cieleným podvrhom. Preberajte ho preto cez dôveryhodný kanál.")
    m.h(2, "2.2 Rozbalenie")
    m.p("Rozbaľte archív do prázdneho priečinka, napríklad `C:\\ArgusGrid`. Priečinok musí byť zapisovateľný "
        "účtom, pod ktorým bude aplikácia bežať, a ostatní používatelia doň nemajú mať prístup. "
        "Obsah balíka:")
    m.table(["Cesta", "Obsah"], [
        ["setup.bat, setup.ps1", "inštalácia; po úspešnom dokončení sa samy vymažú"],
        ["start.bat, stop.bat", "spustenie a zastavenie"],
        ["backend\\app", "aplikácia"],
        ["backend\\migrations", "schéma databázy"],
        ["backend\\config", "šablóna konfigurácie `app.env.template` a ďalšie konfiguračné súbory"],
        ["frontend\\dist", "zostavené webové rozhranie"],
        ["INSTALL.txt", "stručné pokyny"],
    ], [5.0, 12.0], mono_cols=(0,))
    m.h(2, "2.3 Databáza")
    m.p("V PostgreSQL 16 vytvorte rolu a prázdnu databázu (príkazy spustite ako správca databázy, napríklad v `psql`):")
    m.code("""CREATE ROLE argusgrid LOGIN PASSWORD '<silné-heslo>';
CREATE DATABASE argusgrid OWNER argusgrid;""")
    m.p("Adresa pre setup má tvar:")
    m.code("postgresql+psycopg://argusgrid:<heslo>@localhost:5432/argusgrid")
    m.h(2, "2.4 Balík demo: vlastná databáza a Python")
    m.p("Balík **demo** obsahuje aj súbor `bootstrap.ps1`. Ak pri spustení `setup.bat` nezadáte `-DatabaseUrl`, "
        "setup nainštaluje PostgreSQL 16 do priečinka `runtime\\` (stiahne približne 311 MB; z archívu sa rozbalí iba "
        "server, bez správcovského nástroja) a, ak nie je nainštalovaný Python 3.12 alebo zadáte `-EmbeddedPython`, "
        "aj vložený Python. Databáza počúva iba na adrese 127.0.0.1 a jej heslá sú náhodné.")
    m.bullets([
        "Súbory sa preberajú z pevných adries (python.org, files.pythonhosted.org, get.enterprisedb.com) a akceptujú "
        "sa iba vtedy, ak sa ich SHA-256 zhoduje s hodnotou zapísanou v `bootstrap.ps1`; inak sa zmažú a setup sa zastaví.",
        "Bez prístupu na internet vložte súbory do `runtime\\cache` alebo zadajte `-LocalCache <priečinok>`. "
        "Inštalácia požiadaviek aplikácie (pip) však stále potrebuje index balíkov Pythonu.",
        "`start.bat` spustí aj databázu tohto priečinka, `stop.bat` ju zastaví (voľba `-KeepDatabase` ju ponechá bežať). "
        "Externá databáza sa nikdy nezastavuje.",
        "Produkčný balík toto neobsahuje: databázu a Python poskytuje prevádzkovateľ.",
    ])

    m.h(1, "3. Inštalácia")
    m.p("Otvorte PowerShell alebo príkazový riadok v priečinku balíka a spustite:")
    m.code('setup.bat -DatabaseUrl "postgresql+psycopg://argusgrid:<heslo>@localhost:5432/argusgrid"')
    m.table(["Voľba", "Účinok"], [
        ["-CheckOnly", "iba skontroluje predpoklady a nahlási ich; nič nemení"],
        ["-DryRun", "vypíše, čo by urobil; nič nemení"],
        ["-AssumeYes", "bez otázok (adresu databázy treba zadať)"],
        ["-DatabaseUrl <adresa>", "adresa databázy; bez nej sa setup opýta (balík demo ponúkne vlastnú databázu)"],
        ["-WithDemo", "načíta ukážkový objekt (iba balík demo)"],
        ["-EmbeddedPython", "iba balík demo: použije stiahnutý vložený Python aj vtedy, keď je Python nainštalovaný"],
        ["-LocalCache <priečinok>", "iba balík demo: priečinok s už stiahnutými súbormi (inštalácia bez internetu)"],
    ], [5.0, 12.0], mono_cols=(0,))
    m.p("Odporúčaný postup je spustiť najprv `-CheckOnly`, potom vlastnú inštaláciu. Setup:")
    m.numbered([
        "skontroluje Python 3.12+ a adresu databázy a vypíše plán,",
        "vytvorí priečinok `.venv` a nainštaluje požiadavky,",
        "uloží adresu databázy do `backend\\data\\database.url` (súbor je prístupný iba aktuálnemu používateľovi),",
        "vytvorí schému, roly a východiskové nastavenia,",
        "vytvorí účet **sysadmin** s náhodným heslom,",
        "po úspešnom dokončení vymaže `setup.bat` a `setup.ps1`.",
    ])
    m.note("Počiatočné heslo účtu **sysadmin** sa vypíše raz v konzole a uloží do `backend\\data\\accounts.txt`. "
           "Prečítajte si ho, prihláste sa a súbor potom presuňte mimo priečinka alebo ho zmažte. Heslo nie je "
           "uvedené nikde v zdrojoch ani v dokumentácii.", warning=True)
    m.p("Setup je opakovateľný: pri zlyhaní nič nemaže a po oprave príčiny ho môžete spustiť znova. Existujúce "
        "účty ani údaje neprepíše. Po úspešnom dokončení sa samo odstráni; ak ho chcete spustiť znova, "
        "stiahnite balík znova.")

    m.h(1, "4. Konfigurácia")
    m.p("Nastavenia sú v súbore `backend\\config\\app.env` (riadky `KLÚČ=hodnota`). Zmeny sa prejavia po "
        "ďalšom spustení.")
    m.table(["Kľúč", "Hodnoty", "Význam"], [
        ["ARGUS_PROFILE", "civil | defense", "profil nasadenia; definuje sa pri vydaní balíka"],
        ["ARGUS_MARKING", "text (najviac 64 znakov)", "označenie nasadenia (pruh na obrazovkách, prvý riadok exportov); "
                                                       "pri defense predvolene RESTRICTED – nahraďte ho"],
        ["ARGUS_BIND_HOST", "adresa", "na akej adrese server počúva; predvolene 127.0.0.1 (iba lokálne)"],
        ["ARGUS_SECURE_COOKIES", "0 | 1", "1, ak sa pristupuje cez HTTPS"],
        ["ARGUS_WORKERS", "0 | 1", "spúšťa pozadové úlohy (pošta, spravodajstvo, retencia); nechajte 1"],
        ["ARGUS_ENV", "production", "režim prevádzky; v ostrej prevádzke nemeňte"],
    ], [4.2, 4.0, 8.8], mono_cols=(0,))
    m.h(2, "4.1 Prístup zo siete a HTTPS")
    m.p("Aplikácia sama nešifruje spojenie. Ak k nej majú pristupovať iné počítače, nastavte "
        "`ARGUS_BIND_HOST` na adresu rozhrania a umiestnite pred ňu reverzný proxy server s HTTPS (napríklad "
        "IIS alebo nginx), ktorý podporuje aj WebSocket (cesta `/api/v1/stream`). Potom nastavte "
        "`ARGUS_SECURE_COOKIES=1`.")
    m.note("Neotvárajte aplikáciu do internetu bez HTTPS a bez obmedzenia prístupu na sieť, ktorá ju má "
           "používať. Prihlásenie je chránené zamykaním účtov, ale odporúča sa aj sieťové obmedzenie.", warning=True)
    m.h(2, "4.2 Poznámky k viac inštanciám")
    m.p("Ochrana pred opakovaním podpísaných požiadaviek zariadení a obmedzenie počtu požiadaviek sú vedené "
        "v pamäti jedného procesu. Prevádzkujte preto **jednu** inštanciu servera.")

    m.h(1, "5. Spustenie a zastavenie")
    m.table(["Príkaz", "Účinok"], [
        ["start.bat", "pripraví databázu (prípadné aktualizácie schémy), spustí server na pozadí, počká na jeho "
                      "pripravenosť a otvorí prehliadač"],
        ["start.bat -Port 8080", "iný port (štandardne 8000)"],
        ["start.bat -NoBrowser", "neotvorí prehliadač"],
        ["stop.bat", "zastaví iba server tohto priečinka; databázu nikdy"],
    ], [5.0, 12.0], mono_cols=(0,))
    m.p("Server beží ako skrytý proces; jeho záznamy sú v `backend\\data\\logs`. Číslo procesu je v "
        "`backend\\data\\server.pid`. Stop skontroluje, že proces je naozaj server tohto priečinka, a ak nie, "
        "nič nezastaví.")
    m.h(2, "5.1 Spustenie pri štarte počítača")
    m.p("Balík neinštaluje službu Windows. Spúšťať `start.bat -NoBrowser` pri štarte môžete cez Plánovač úloh "
        "(Task Scheduler) pod vyhradeným účtom.")

    m.h(1, "6. Prvé prihlásenie a základné nastavenie")
    m.numbered([
        "Otvorte `http://127.0.0.1:8000` (alebo adresu z kapitoly 4.1).",
        "Prihláste sa ako **sysadmin** s prideleným heslom z `accounts.txt` a podľa výzvy zvoľte nové heslo.",
        "Na stránke **E-mail** nastavte SMTP server a overte ho testovacou správou; nastavte **Adresu "
        "aplikácie**, ktorá sa uvádza v správach.",
        "Skontrolujte **Zložitosť hesiel**, **Zamykanie účtov** a **Relácie** podľa vašich pravidiel.",
        "Vytvorte používateľov a prideľte im roly (kapitola 9 používateľskej príručky).",
        "V **Aktívach** vyplňte register, najmä fyzickú expozíciu a softvérový inventár.",
        "Pre senzory vytvorte poverenia zariadení a kľúče vložte do ich konfigurácie.",
        "Na stránke **Spravodajstvo o hrozbách** zapnite zdroje (civil) alebo importujte podpísaný balík a "
        "pridajte dôveryhodné kľúče (defense).",
    ])
    m.figure(S("04-operatorsky-panel"), "Operátorský panel po inštalácii balíka demo a spustení simulátora", 15.0)
    m.h(2, "6.1 Simulátor (iba balík demo)")
    m.p("Simulátor odosiela cez skutočné rozhranie API podpísané udalosti jedného dronu a jedného kybernetického "
        "poplachu na ukážkovom objekte. Z priečinka `backend` spustite:")
    m.code("..\\.venv\\Scripts\\python.exe -m app.simulator --speed 15")
    m.p("Voľba `--speed` určuje počet simulovaných sekúnd za sekundu, `--base-url` adresu servera (ak nie je "
        "štandardná) a `--loop` opakuje scenár. Kľúče simulátor číta zo súboru `backend\\data\\demo-devices.txt`, "
        "ktorý vznikol pri načítaní ukážkových údajov.")

    m.h(1, "7. Zálohovanie a obnova")
    m.p("Stav aplikácie tvoria **databáza** a **dva súbory**. Zálohujte všetko spolu.")
    m.table(["Čo", "Kde", "Poznámka"], [
        ["Databáza", "PostgreSQL", "`pg_dump -Fc argusgrid > argusgrid.dump`"],
        ["Šifrovací kľúč", "backend\\data\\secret.key", "bez neho sa uložené heslo SMTP a čakajúce správy nedajú "
                                                         "prečítať; chráňte ho ako heslo"],
        ["Konfigurácia", "backend\\config", "`app.env` a ďalšie konfiguračné súbory"],
        ["Adresa databázy", "backend\\data\\database.url", "obsahuje heslo databázy"],
    ], [3.5, 5.5, 8.0], mono_cols=(1,))
    m.p("Obnova: nainštalujte rovnakú alebo novšiu verziu, obnovte databázu (`pg_restore`), vráťte "
        "`secret.key`, `config` a `database.url`, spustite `start.bat`. Na stránke **Auditný záznam** potom "
        "použite **Overiť integritu**, aby ste sa presvedčili, že zreťazenie záznamov je neporušené.")
    m.note("Zálohy obsahujú citlivé údaje (auditný záznam, adresy, šifrovací kľúč). Uchovávajte ich šifrované a s "
           "obmedzeným prístupom. Obnovu aspoň raz vyskúšajte na skúšobnom stroji.", warning=True)
    m.h(2, "7.1 Uchovávanie telemetrie")
    m.p("Udalosti senzorov sa ukladajú do denných oddielov. Oddiely staršie než doba uchovávania sa zahadzujú "
        "naraz: štandardne 30 dní (civil) a 90 dní (defense). Auditný záznam sa nemaže.")

    m.h(1, "8. Aktualizácia a odinštalovanie")
    m.h(2, "8.1 Aktualizácia")
    m.p("Aktualizácia zatiaľ nebola vyskúšaná na živej inštalácii. Odporúčaný postup: urobte úplnú zálohu "
        "(kapitola 7), zastavte aplikáciu, rozbaľte nový balík do **nového** priečinka, prekopírujte "
        "`backend\\data` a `backend\\config\\app.env`, spustite setup (nič nepreberie ani neprepíše) a potom "
        "`start.bat`, ktorý pri štarte aktualizuje schému databázy. Najprv to vyskúšajte na kópii.")
    m.h(2, "8.2 Odinštalovanie")
    m.p("Zastavte aplikáciu `stop.bat`, zmažte priečinok a v PostgreSQL zrušte databázu a rolu. Prípadné "
        "naplánované úlohy odstráňte ručne.")

    m.h(1, "9. Riešenie problémov")
    m.table(["Príznak", "Príčina a postup"], [
        ["Setup: Python 3.12 or newer: MISSING", "Nainštalujte Python 3.12+ (python.org) a spustite setup znova."],
        ["Setup: Database URL: MISSING", "Zadajte voľbu -DatabaseUrl s adresou v tvare postgresql+psycopg://…"],
        ["Setup zlyhal pri príprave databázy", "Skontrolujte, že databáza existuje, je prázdna a rola je jej "
                                                 "vlastníkom; skontrolujte `pg_hba.conf`. Setup je bezpečné opakovať."],
        ["Setup zlyhal pri inštalácii požiadaviek", "Chýba prístup k balíčkom Python. Nastavte proxy alebo interné "
                                                    "zrkadlo pip a spustite znova."],
        ["start.bat: The application is not set up", "Setup sa nedokončil. Spustite ho znova (alebo stiahnite "
                                                      "balík, ak sa po úspešnom behu už zmazal)."],
        ["Server nebol pripravený", "Pozrite `backend\\data\\logs\\server.err.log`. Najčastejšie: nedostupná "
                                    "databáza alebo obsadený port; použite `start.bat -Port <iný>`."],
        ["Prehliadač sa nepripojí", "Server počúva na `ARGUS_BIND_HOST`; pri 127.0.0.1 je dostupný len lokálne. "
                                    "Skontrolujte bránu firewall a adresu."],
        ["Stránka sa načíta, ale zostáva prázdna", "Reverzný proxy neprepúšťa cestu `/static` alebo blokuje "
                                                    "WebSocket `/api/v1/stream`."],
        ["E-maily neodchádzajú", "Stránka E-mail > Odchádzajúca pošta ukáže stav a chybu každej správy; overte "
                                 "SMTP server a odošlite testovaciu správu."],
        ["Zariadenie dostáva odmietnutie", "Kľúč mohol vypršať alebo byť zrušený; adresa zariadenia nie je v "
                                           "povolených sieťach; hodiny zariadenia sa líšia; rovnaká požiadavka "
                                           "sa v tej istej sekunde zopakovala (ochrana pred opakovaním)."],
        ["Prístup správcu sa stratil", "Obráťte sa na dodávateľa podľa servisnej zmluvy."],
    ], [5.5, 11.5])

    m.save(out)
