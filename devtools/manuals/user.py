"""Content of the user manual (DOC-003), Slovak. Built from the real screens of a clean install."""
from __future__ import annotations

from pathlib import Path

from manuals.kit import Manual

VERSION = "0.6.0"


def build(screens: Path, out: Path) -> None:
    m = Manual("Používateľská príručka",
               "Ochrana energetickej infraštruktúry pred hybridnými hrozbami",
               VERSION, "ArgusGrid – Používateľská príručka",
               "operátorov, analytikov, správcov a audítorov")
    S = lambda name: screens / f"{name}.png"  # noqa: E731

    # ------------------------------------------------------------------------------------------------
    m.h(1, "1. Úvod")
    m.h(2, "1.1 Na čo ArgusGrid slúži")
    m.p("ArgusGrid je prototyp bezpečnostného modulu na ochranu energetickej infraštruktúry pred hybridnými "
        "hrozbami. Spája dva svety, ktoré sa dnes sledujú oddelene: **fyzický** (napríklad dron, ktorý sa "
        "približuje k objektu) a **kybernetický** (napríklad zraniteľnosť alebo poplach na riadiacom serveri). "
        "Keď spolu súvisia, vznikne jeden **hybridný incident** s ohodnotením, mapou dopadu na zariadenia a "
        "odporúčanými krokmi.")
    m.p("Na jednej obrazovke vidíte vľavo **mapu objektu** s dronom a ohrozeným sektorom a vpravo "
        "**topologický graf**, ktorý ukazuje, ako sa môže porucha šíriť od fyzickej udalosti cez riadiaci server "
        "až na jednotlivé PLC (tzv. dominový efekt).")
    m.note("ArgusGrid iba **zisťuje, prepája a odporúča**. Sám nevykonáva žiadny zásah, nič nevypína ani "
           "neblokuje a neobsahuje žiadne protidronové účinkovače. Rozhodnutie a vykonanie ostáva na ľuďoch.")
    m.h(2, "1.2 Komu je príručka určená")
    m.p("Príručka popisuje každú obrazovku a každú stránku nastavení. Nie každý používateľ vidí všetky "
        "obrazovky: čo vidíte, závisí od vašej **roly** (kapitola 11). Ak v menu položku nevidíte, vaša rola "
        "k nej nemá oprávnenie.")
    m.h(2, "1.3 Konvencie")
    m.bullets([
        "Názvy tlačidiel, položiek menu a polí sú v texte uvedené tak, ako sa zobrazujú v slovenskom rozhraní.",
        "Obrázky pochádzajú z čistej inštalácie s ukážkovými údajmi o fiktívnom objekte "
        "„Kestrel Ridge Energy Complex“. Všetky názvy, adresy a zraniteľnosti v ňom sú vymyslené.",
        "Texty, ktoré prichádzajú zo senzorov a z externých zdrojov (napríklad opis poplachu alebo názov "
        "zraniteľnosti), sa zobrazujú tak, ako prišli, preto môžu byť v angličtine.",
    ])

    # ------------------------------------------------------------------------------------------------
    m.h(1, "2. Prvé kroky")
    m.h(2, "2.1 Prihlásenie")
    m.p("Otvorte adresu aplikácie v prehliadači. Zadajte **Používateľské meno** a **Heslo** a stlačte "
        "**Prihlásiť sa**. Prihlasovacie údaje vám pridelil správca. Ak sa prihlásenie nepodarí, aplikácia vždy "
        "zobrazí tú istú správu „Používateľské meno alebo heslo nie je správne.“ – zámerne neprezrádza, či "
        "neexistuje účet, alebo je zlé heslo.")
    m.figure(S("01-prihlasenie"), "Prihlasovacia stránka", 14.5)
    m.h(2, "2.2 Prvé prihlásenie: povinná zmena hesla")
    m.p("Pri prvom prihlásení a po každom obnovení hesla správcom musíte hneď zvoliť nové heslo. Okno "
        "**Nastavte nové heslo** sa nedá zatvoriť, kým heslo nezmeníte.")
    m.numbered([
        "Zadajte súčasné (pridelené) heslo.",
        "Aplikácia vám predvolene **vygeneruje** silné nové heslo. Môžete ho prijať a uložiť do správcu hesiel, "
        "alebo tlačidlom **Vygenerovať nové** získať iné.",
        "Ak chcete vlastné heslo, zapnite **Vlastné heslo**. Zobrazia sa polia **Nové heslo** a "
        "**Potvrdenie hesla**; heslá sa musia zhodovať.",
        "Pod poľom sa priebežne odškrtávajú splnené pravidlá hesla. Tlačidlo **Zmeniť heslo** sa sprístupní, "
        "keď sú všetky splnené.",
    ])
    m.figure(S("02-prva-zmena-hesla"), "Povinná zmena hesla pri prvom prihlásení (polia hesiel sú v obrázku zakryté)", 14.5)
    m.figure(S("03-vlastne-heslo"), "Vlastné heslo: nové heslo a jeho potvrdenie so zoznamom pravidiel", 14.5)
    m.note("Heslo, ktoré vám prišlo e-mailom alebo ktoré ste dostali od správcu, je **dočasné**. Po zmene už "
           "nefunguje. Nikomu svoje heslo nepovedzte; správca ho nikdy nepotrebuje.", warning=True)
    m.h(2, "2.3 Pravidlá hesla")
    m.p("Pravidlá nastavuje správca (kapitola 10.1). Štandardné nastavenie je:")
    m.table(["Pravidlo", "Štandardná hodnota"], [
        ["Dĺžka", "12 až 128 znakov (heslo sa nikdy neskracuje)"],
        ["Zloženie", "veľké písmeno, malé písmeno, číslica a špeciálny znak"],
        ["Používateľské meno", "heslo ho nesmie obsahovať"],
        ["Bežné heslá", "najčastejšie používané heslá sa odmietnu"],
        ["História", "nové heslo sa nesmie zhodovať so 5 predchádzajúcimi"],
        ["Najmenší vek", "dobrovoľne zmeniť heslo možno najskôr po 48 hodinách (povinná zmena to ignoruje)"],
        ["Platnosť", "6 mesiacov; 14 dní vopred príde upozornenie e-mailom"],
        ["Zobrazenie hesla", "tlačidlo s okom heslo ukáže a po 5 sekundách ho znova skryje"],
    ], [4.5, 12.5])
    m.h(2, "2.4 Uzamknutie účtu")
    m.p("Po viacerých neúspešných pokusoch sa účet dočasne uzamkne, aby sa nedal heslo uhádnuť. "
        "Štandardné správanie je:")
    m.table(["Skupina", "Čo sa stane"], [
        ["Bežní používatelia", "po 5 neúspešných pokusoch za 15 minút sa účet uzamkne na 15 minút. Po treťom "
                                "takom uzamknutí ostane uzamknutý, kým ho nikto neodomkne."],
        ["Administrátori", "po 5 neúspešných pokusoch za 15 minút sa účet uzamkne postupne na 1, 2, 5, 10 a "
                           "15 minút. Iný administrátor ho môže okamžite odomknúť. Po odomknutí musí zmeniť heslo."],
    ], [4.5, 12.5])
    m.p("Okrem toho je z jednej adresy povolených 20 prihlásení za minútu. Pri prekročení sa zobrazí "
        "„Príliš veľa pokusov. Počkajte minútu a skúste znova.“ Správca môže hodnoty zmeniť (kapitola 10.2); "
        "platné hodnoty vždy vidíte na stránke **Zamykanie účtov** v časti **Skutočné správanie**.")
    m.h(2, "2.5 Relácia a odhlásenie")
    m.p("Ak sa v aplikácii 30 minút nič nedeje, relácia skončí a musíte sa prihlásiť znova. Najdlhšie trvá "
        "relácia 12 hodín. Odhlásiť sa môžete kedykoľvek tlačidlom **Odhlásiť sa** vpravo hore. Hodnoty "
        "nastavuje správca na stránke **Relácie**.")

    # ------------------------------------------------------------------------------------------------
    m.h(1, "3. Rozhranie aplikácie")
    m.h(2, "3.1 Rozloženie")
    m.p("Hlavička obsahuje názov aplikácie, voľbu **jazyka** (SK/EN), prepínač **témy**, vaše meno a tlačidlá "
        "**Zmeniť heslo** a **Odhlásiť sa**. Vľavo je hlavné menu:")
    m.table(["Skupina", "Položka", "Na čo slúži"], [
        ["Hlavné menu", "Prehľad", "operátorský panel: mapa a graf topológie s aktuálnymi incidentmi"],
        ["", "Incidenty", "zoznam všetkých incidentov, filtre, pracovný postup"],
        ["", "Operačná mapa", "mapa objektu s dronmi, senzormi a zónami"],
        ["", "Aktíva", "register zariadení, softvéru a vzťahov"],
        ["", "Spravodajstvo o hrozbách", "zraniteľnosti, nálezy na vašich aktívach, zdroje"],
        ["Správa", "Používatelia, Roly, Auditný záznam, E-mail", "správa účtov, oprávnení, auditu a pošty"],
        ["Nastavenia", "Zložitosť hesiel, Zamykanie účtov, Relácie", "bezpečnostné politiky"],
    ], [3.0, 5.5, 8.5])
    m.h(2, "3.2 Jazyk a téma")
    m.p("Rozhranie je v slovenčine a angličtine; voľba sa pamätá v prehliadači. **Tmavá téma** je vhodná do "
        "riadiacich miestností, **Svetlá téma** na tlač a do svetlých miestností. Obrázky v tejto príručke sú "
        "vo svetlej téme.")
    m.h(2, "3.3 Tablet a telefón")
    m.p("Rozhranie sa prispôsobí šírke obrazovky. Na tablete sa mapa a graf zobrazia pod sebou s posuvným "
        "oddeľovačom. Na telefóne sa prepínajú záložkami **Mapa**, **Graf** a **Incident**; menu je pri dolnom "
        "okraji. Ovládacie prvky majú aspoň 44 px, aby sa dali stlačiť prstom.")
    m.figure(S("24-mobil-panel"), "Operátorský panel na telefóne: záložky Mapa, Graf a Incident", 6.0)
    m.h(2, "3.4 Označenie nasadenia")
    m.p("V nasadení s **obranným profilom** sa navrchu a naspodku každej obrazovky (aj prihlasovacej) zobrazuje "
        "pruh s označením, ktoré určil prevádzkovateľ. Rovnaké označenie je v prvom riadku každého exportu "
        "auditu. Obranný profil navyše používa iba offline spravodajstvo (kapitola 8.5) a niektoré názvy majú "
        "iné znenie (napríklad „Operačná miestnosť“ namiesto „Prehľad“).")

    # ------------------------------------------------------------------------------------------------
    m.h(1, "4. Operátorský panel (Prehľad)")
    m.p("Panel je hlavná pracovná obrazovka operátora. Skladá sa z troch častí:")
    m.bullets([
        "**Pás incidentov** navrchu: stav spojenia (**Naživo**, **Pripájanie**, **Odpojené**), ohrozené zóny "
        "(napríklad „Z2 · Kritické“) a tlačidlo pre každý aktívny incident s jeho závažnosťou, kódom, zónou a "
        "stavom. Kliknutím incident vyberiete.",
        "**Rozdelená obrazovka**: vľavo mapa, vpravo graf topológie vybraného incidentu. Oddeľovač medzi nimi "
        "môžete ťahať myšou, alebo ho po zaostrení posúvať klávesmi so šípkami.",
        "**Podrobnosti incidentu** pod nimi (kapitola 5).",
    ])
    m.figure(S("04-operatorsky-panel"), "Operátorský panel: mapa vľavo, graf topológie vpravo, pod nimi podrobnosti incidentu", 16.5)
    m.h(2, "4.1 Mapa")
    m.p("Mapa zobrazuje pôdorys objektu v metroch. **Zóny** sú farebné plochy podľa kritickosti; zóna, nad ktorou "
        "dron je, sa zvýrazní hrubým červeným okrajom. Prerušované kruhy sú kruhy vzdušného priestoru "
        "(poplachový 1 500 m, varovný 600 m, kritický 150 m). Dron je ružová značka so šípkou smeru a prerušovanou "
        "stopou za sebou; po prejdení myšou vidíte jeho označenie a výšku. Zelené body sú senzory, ktoré "
        "nedávno hlásili údaje. Ružová prerušovaná čiara spája dron s aktívami, ktoré sú v jeho dosahu a "
        "súvisia s incidentom.")
    m.h(2, "4.2 Graf topológie")
    m.p("Graf ukazuje, ako sa udalosť šíri. Zhora nadol:")
    m.table(["Úroveň", "Význam", "Ako je vyznačená"], [
        ["Fyzická udalosť", "dron (hviezda)", "ružová hviezda"],
        ["Exponované aktívum", "zariadenie, ktoré je dron schopný dosiahnuť (bezdrôtovo, signálom GNSS…)", "ružový okraj"],
        ["Cesta", "aktíva, cez ktoré vedie závislosť k napadnutému aktívu", "fialový okraj"],
        ["Napadnuté aktívum", "zariadenie s kybernetickým signálom (poplach alebo zneužívaná zraniteľnosť)", "červený hrubý okraj"],
        ["Ohrozené aktíva", "zariadenia, ktoré od neho závisia, podľa počtu skokov", "prerušovaný okraj"],
    ], [3.6, 8.4, 5.0])
    m.p("Tvar uzla hovorí o type zariadenia: šesťuholník je PLC/RTU/IED, zaoblený obdĺžnik server, kosoštvorec "
        "sieťový prvok (firewall, brána, prepínač), kruh koncové zariadenie alebo senzor. Význam teda nikdy "
        "nenesie iba farba. Prerušovaná ružová čiara je **hybridná väzba** medzi fyzickou udalosťou a aktívom.")
    m.p("Kliknutím na uzol ho zvýrazníte; rovnaké aktívum môžete vybrať aj v zozname dosahu dopadu pod grafom.")

    # ------------------------------------------------------------------------------------------------
    m.h(1, "5. Incidenty")
    m.h(2, "5.1 Ako incident vzniká")
    m.p("ArgusGrid porovnáva dráhy dronov z radarov, RF detektorov a kamier so stavom kybernetických aktív. "
        "**Hybridný incident** vznikne, keď:")
    m.bullets([
        "dron je blízko aktíva, ku ktorému sa dá dostať zvonku – v dosahu 150 m pri bezdrôtovom prístupe, 300 m "
        "pri signáli GNSS a priamej viditeľnosti, 100 m pri elektromagnetickom a 40 m pri fyzickom prístupe – a",
        "toto aktívum je závislosťou (najviac 3 skoky) prepojené s aktívom, ktoré hlási kybernetický signál: "
        "poplach alebo zneužívanú zraniteľnosť, alebo",
        "dron je v zóne napadnutého aktíva (slabšia väzba).",
    ])
    m.p("Pre jednu dráhu dronu vzniká jeden incident; ostatné dotknuté aktíva sa vypíšu v dôkazoch. Ak je k "
        "dispozícii iba fyzická alebo iba kybernetická časť, vznikne **fyzický** alebo **kybernetický** incident s "
        "nižším maximálnym skóre, takže hybridný incident je vždy zreteľne vyššie.")
    m.h(2, "5.2 Skóre a závažnosť")
    m.p("Skóre je číslo 0 až 100: 35 % tvorí sila fyzickej väzby (blízkosť a dĺžka závislosti), 35 % zneužiteľnosť "
        "kybernetického signálu a 30 % kritickosť aktíva; ak existuje poplach aj zraniteľnosť naraz, pripočíta sa "
        "10 bodov. Závažnosť: **kritická** od 80, **vysoká** od 60, **stredná** od 40, inak **nízka**.")
    m.note("Váhy a dosahy sú prvý návrh pre prototyp. Overujú sa s prevádzkovateľom a nie sú vyladené na "
           "skutočnej prevádzke. Skóre berte ako pomoc pri poradí, nie ako dôkaz.")
    m.h(2, "5.3 Podrobnosti incidentu")
    m.figure(S("05-incident-detail"), "Podrobnosti incidentu: dôkazy, dosah dopadu, odporúčané kroky a časová os", 16.0)
    m.table(["Časť", "Obsah"], [
        ["Hlavička", "kód (HYB- hybridný), názov, závažnosť, stav, typ, skóre"],
        ["Fyzické dôkazy", "dráha, zóna, kruh vzdušného priestoru, výška, vzdialenosť od exponovaného aktíva"],
        ["Kybernetické dôkazy", "poplachy a zraniteľnosti s triedou (Zero-day, Zero-hour, Bežná)"],
        ["Dosah dopadu", "zoradený zoznam aktív podľa skoku a dôsledku; kliknutím aktívum zvýrazníte v grafe"],
        ["Odporúčané kroky", "napríklad vyslať ochranku, vypnúť bezdrôtové rozhranie, izolovať aktívum, "
                              "overiť integritu regulátorov, informovať vedenie alebo dispečing"],
        ["Časová os", "vytvorenie, upozornenia, zmeny stavu, poznámky a eskalácie s časom a autorom"],
    ], [4.0, 13.0])
    m.p("Odporúčané kroky sú iba odporúčania; nič z nich sa nevykoná automaticky.")
    m.h(2, "5.4 Pracovný postup")
    m.p("Incident prechádza stavmi **Nový**, **Roztriedený**, **Vyšetrovaný**, **Zadržaný** a **Uzavretý**. "
        "Zobrazia sa iba tlačidlá prechodov, ktoré sú povolené:")
    m.table(["Zo stavu", "Možno prejsť do"], [
        ["Nový", "Roztriedený, Vyšetrovaný, Uzavretý"],
        ["Roztriedený", "Vyšetrovaný, Zadržaný, Uzavretý"],
        ["Vyšetrovaný", "Zadržaný, Uzavretý"],
        ["Zadržaný", "Vyšetrovaný, Uzavretý"],
        ["Uzavretý", "žiadny (nový signál po 30 minútach vytvorí nový incident)"],
    ], [4.5, 12.5])
    m.numbered([
        "Vyberte incident a stlačte tlačidlo prechodu, napríklad **Označiť ako roztriedený**.",
        "V okne môžete doplniť poznámku (najviac 500 znakov) a potvrdiť **Uložiť**.",
        "**Pridať poznámku** pridá záznam na časovú os bez zmeny stavu (najviac 1 000 znakov).",
        "**Eskalovať** zvýši závažnosť o jeden stupeň, označí incident ako eskalovaný a upozorní e-mailom "
        "osoby, ktoré môžu incidenty uzatvárať. Eskalovať možno raz.",
    ])
    m.figure(S("06-incident-zmena-stavu"), "Zmena stavu incidentu s poznámkou", 14.5)
    m.p("Uzavrieť incident môže iba rola s oprávnením `incident.close`. Každá zmena, poznámka a "
        "eskalácia sa zapíše na časovú os aj do auditného záznamu.")
    m.h(2, "5.5 Upozornenia e-mailom")
    m.p("Pri vzniku incidentu so závažnosťou vysoká alebo kritická sa raz odošle e-mail osobám, ktoré môžu "
        "incidenty triediť. Znenie upravuje správca v šablóne **Hybrid incident** (kapitola 9.4).")
    m.h(2, "5.6 Zoznam incidentov")
    m.p("Stránka **Incidenty** zobrazuje všetky incidenty so stĺpcami názov, závažnosť, stav, typ, zóna, aktívum, "
        "skóre a čas aktualizácie. Filtrovať možno podľa stavu, závažnosti a typu. Kód incidentu otvorí podrobnosti "
        "priamo pod tabuľkou; odkaz **Panel** ho otvorí v operátorskom paneli.")
    m.figure(S("07-incidenty"), "Zoznam incidentov s filtrami", 16.0)

    # ------------------------------------------------------------------------------------------------
    m.h(1, "6. Operačná mapa")
    m.p("Stránka **Operačná mapa** ukazuje tú istú mapu ako panel, na celú šírku, s ovládaním vrstiev. "
        "Zapínať a vypínať môžete: **Zóny**, **Budovy**, **Kruhy vzdušného priestoru**, **Senzory**, "
        "**Kybernetické aktíva** a **Stopy**. Napravo sú zoznamy **Ohrozené sektory**, **Dráhy** (aktuálne "
        "sledované drony so zónou, kruhom, výškou, rýchlosťou a časom poslednej aktualizácie) a **Poplachy**.")
    m.p("Dráha, ktorá sa 90 sekúnd neozve, sa považuje za neaktívnu a zmizne zo zoznamu ohrozených sektorov. "
        "Ak je spojenie s aplikáciou prerušené, v hornej časti sa zobrazí **Odpojené**; po obnovení sa "
        "údaje načítajú znova. Stav sa navyše sám obnovuje každých 30 sekúnd.")
    m.figure(S("08-mapa"), "Operačná mapa s vrstvami, ohrozenými sektormi, dráhami a poplachmi", 16.0)

    # ------------------------------------------------------------------------------------------------
    m.h(1, "7. Aktíva")
    m.h(2, "7.1 Register aktív")
    m.p("**Aktíva** je register všetkých zariadení: servery, pracovné stanice, HMI, PLC, RTU, ochranné relé, "
        "senzory, prepínače, smerovače, firewally, brány a bezdrôtové prístupové body. Zoznam sa dá "
        "vyhľadávať a filtrovať podľa typu a stavu. Tlačidlom **Vytvoriť aktívum** pridáte nové.")
    m.figure(S("09-aktiva"), "Register aktív", 16.0)
    m.h(2, "7.2 Detail aktíva")
    m.p("Detail má štyri záložky:")
    m.table(["Záložka", "Obsah"], [
        ["Prehľad", "kód, názov, typ, stav, úroveň Purdue, zóna, kritickosť, umiestnenie, výrobca, model, "
                    "firmvér, adresy, protokoly, poloha v objekte a **fyzická expozícia**"],
        ["Softvér", "inventár softvéru a verzií; porovnáva sa s informáciami o zraniteľnostiach"],
        ["Vzťahy", "od čoho aktívum závisí a z čoho je dosiahnuteľné (riadenie, vzdialený prístup, operátorská "
                   "relácia, replikácia, tok dát, bezdrôtové spojenie)"],
        ["Poverenia zariadenia", "kľúče senzorov a brán (kapitola 7.4)"],
    ], [4.0, 13.0])
    m.figure(S("10-detail-aktiva"), "Detail aktíva (záložka Prehľad)", 15.0)
    m.h(2, "7.3 Fyzická expozícia")
    m.p("Pole **Fyzická expozícia** hovorí, ako sa k aktívu môže dostať osoba alebo zariadenie v jeho blízkosti: "
        "bezdrôtovo, priamou viditeľnosťou, signálom GNSS, fyzickým prístupom (USB, konzola) alebo "
        "elektromagneticky. Práve tieto údaje používa korelácia na rozhodnutie, že dron v blízkosti súvisí s "
        "kybernetickým aktívom. Správne vyplnená expozícia je preto dôležitá.")
    m.h(2, "7.4 Poverenia zariadení (kľúče)")
    m.p("Každý senzor a brána má vlastný kľúč. Požiadavky zariadenia sú podpísané, obmedzené na povolené siete "
        "(zápis CIDR, napríklad 10.20.50.0/24) a rozsahy a majú obmedzenú platnosť.")
    m.bullets([
        "**Vytvoriť poverenie** vydá kľúč. Jeho **tajomstvo sa zobrazí iba raz**; uložte si ho hneď, potom ho "
        "už nemožno znova zobraziť. Okno zatvoríte až po potvrdení „Tajomstvo som uložil“.",
        "**Vymeniť** vydá nový kľúč a starý prestane okamžite fungovať. Zariadenie treba aktualizovať.",
        "**Zrušiť** kľúč zneplatní okamžite. Vyradenie aktíva zruší všetky jeho kľúče.",
        "Stĺpce **Vyprší** a **Naposledy použité** ukazujú, či kľúč zariadenie používa.",
    ])
    m.h(2, "7.5 Životný cyklus")
    m.p("Aktívum je **Plánované**, **Aktívne**, **Údržba** alebo **Vyradené**. Vyradené je konečné a iba "
        "z tohto stavu (alebo z plánovaného) sa aktívum zmaže; záznamy auditu ostávajú.")

    # ------------------------------------------------------------------------------------------------
    m.h(1, "8. Spravodajstvo o hrozbách")
    m.p("Táto stránka zbiera informácie o zraniteľnostiach z externých zdrojov a porovnáva ich so softvérom na "
        "vašich aktívach. Výsledkom sú **nálezy**.")
    m.h(2, "8.1 Zero-day a zero-hour")
    m.table(["Trieda", "Kedy sa používa"], [
        ["Zero-day", "zraniteľnosť sa zneužíva (je vo verejnom zozname zneužívaných zraniteľností alebo má vysoké "
                     "skóre EPSS) a **neexistuje oprava** od výrobcu"],
        ["Zero-hour", "zraniteľnosť sa zneužíva a bola zverejnená v posledných **72 hodinách**"],
        ["Bežná", "ostatné zraniteľnosti"],
    ], [3.5, 13.5])
    m.p("Trieda sa počíta pri každom zobrazení, takže zero-hour po uplynutí okna sám prejde na bežnú. Hranice "
        "(72 hodín a prah EPSS 0,5) nastavuje správca.")
    m.h(2, "8.2 Nálezy")
    m.p("Záložka **Nálezy** ukazuje, ktoré aktívum je dotknuté ktorou zraniteľnosťou, s triedou, závažnosťou, "
        "stavom opravy a mierou zhody (zhoda produktu a verzie alebo iba produktu). Počty tried sú navrchu. "
        "Nález môže mať stav **Otvorený**, **Potvrdený**, **Zmiernený** alebo **Falošný poplach**; stav "
        "zmeníte tlačidlom **Upraviť** s poznámkou, zmena sa zapíše do auditu.")
    m.figure(S("11-hrozby-nalezy"), "Nálezy na aktívach (zero-day nahor)", 16.0)
    m.h(2, "8.3 Zraniteľnosti")
    m.p("Záložka **Zraniteľnosti** je katalóg všetkých známych záznamov s popisom, zdrojmi, dotknutými verziami a "
        "dotknutými aktívami.")
    m.figure(S("12-hrozby-zranitelnosti"), "Katalóg zraniteľností", 15.0)
    m.h(2, "8.4 Zdroje")
    m.p("Záložka **Zdroje** zobrazuje zdroje (zoznam zneužívaných zraniteľností, EPSS, NVD, poradenstvá CSAF), "
        "ich stav (**Nespustené**, **V poriadku**, **Chyba**) a interval. Správca ich zapína a tlačidlom "
        "**Spustiť teraz** ich spustí hneď. Zdroje sú predvolene vypnuté.")
    m.figure(S("13-hrozby-zdroje"), "Zdroje spravodajstva", 15.0)
    m.h(2, "8.5 Politika, dôvera a offline balíky")
    m.p("Záložka **Politika a dôvera** obsahuje okno zero-hour, prah EPSS, od akej závažnosti sa posiela "
        "upozornenie a voľbu **Iba offline**. V obrannom profile je táto voľba zapnutá natrvalo: aplikácia "
        "sa nikdy nepripája na internet a spravodajstvo prijíma iba z **podpísaných balíkov**.")
    m.p("Balík sa importuje tlačidlom **Importovať spravodajstvo** a prijme sa iba vtedy, ak je podpísaný "
        "kľúčom zo zoznamu **Dôveryhodné kľúče balíkov**. Zmenený alebo nepodpísaný balík sa odmietne.")
    m.figure(S("14-hrozby-politika"), "Politika spravodajstva a dôveryhodné kľúče", 15.0)

    # ------------------------------------------------------------------------------------------------
    m.h(1, "9. Správa")
    m.h(2, "9.1 Používatelia")
    m.p("Stránka **Používatelia** (rola s oprávnením zobraziť používateľov) obsahuje zoznam s vyhľadávaním a "
        "filtrom rolí. Účty administrátorov vidia iba administrátori.")
    m.figure(S("15-pouzivatelia"), "Zoznam používateľov", 16.0)
    m.p("**Vytvoriť používateľa** otvorí formulár:")
    m.table(["Pole", "Poznámka"], [
        ["Používateľské meno", "3 až 64 znakov: písmená, číslice, bodka, pomlčka, podčiarkovník"],
        ["E-mail", "adresa, na ktorú príde správa s prihlasovacími údajmi"],
        ["Celé meno", "voliteľné"],
        ["Rola", "iba roly, ktoré môžete prideliť (nie vyššie ako vaša)"],
        ["Jazyk", "jazyk rozhrania a e-mailov používateľa"],
        ["Počiatočné heslo", "vygenerované, alebo po zapnutí Vlastné heslo vlastné; platia pravidlá hesla"],
        ["Poslať prihlasovacie údaje e-mailom", "zapnuté predvolene; vyžaduje nastavený SMTP server"],
    ], [5.0, 12.0])
    m.figure(S("16-novy-pouzivatel"), "Vytvorenie používateľa (pole hesla je v obrázku zakryté)", 14.5)
    m.p("Nový používateľ musí pri prvom prihlásení zmeniť heslo. Pri zozname používateľa sú tlačidlá "
        "**Upraviť**, **Obnoviť heslo**, **Zamknúť** / **Odomknúť** a **Zmazať**:")
    m.bullets([
        "**Obnoviť heslo** nastaví nové dočasné heslo a ukončí aktívne relácie používateľa.",
        "**Zamknúť** používateľa okamžite odhlási a zabráni prihláseniu, kým ho niekto neodomkne.",
        "**Odomknúť** vykoná nastavenú akciu po odomknutí (nič, vyžiadať zmenu hesla, alebo obnoviť na nové "
        "heslo odoslané e-mailom).",
        "Nemôžete zamknúť, zmazať ani deaktivovať vlastný účet ani zmeniť vlastnú rolu a nemožno odobrať "
        "posledného aktívneho administrátora.",
    ])
    m.h(2, "9.2 Roly")
    m.p("Roly a ich oprávnenia sú uložené v databáze a dajú sa meniť za behu. Na stránke **Roly** vyberiete rolu "
        "a zaškrtnete oprávnenia po skupinách (Používatelia, Roly, Politiky, Nastavenia, Audit, Aktíva, "
        "Spravodajstvo, Incidenty, Simulácia). Rola smie spravovať iba používateľov a roly pod svojou **úrovňou "
        "zabezpečenia**. Oprávnenia sa zobrazujú pod technickými názvami, napríklad `asset.view` alebo `incident.close`. Rola Administrator má vždy všetko a nedá sa zmeniť. Zúženie roly ukončí relácie jej "
        "používateľov.")
    m.figure(S("17-roly"), "Roly a ich oprávnenia", 16.0)
    m.h(2, "9.3 Auditný záznam")
    m.p("Každá zmena a každé prihlásenie sa zapisuje do auditného záznamu, ktorý sa nedá upravovať ani mazať. "
        "Záznamy sú navzájom zreťazené, takže pozmenenie by sa prezradilo.")
    m.table(["Stĺpec", "Význam"], [
        ["Kedy", "čas (UTC) udalosti"],
        ["Kto", "používateľ alebo „System“ a jeho rola"],
        ["Čo", "vykonaná akcia, napríklad vytvorenie používateľa alebo zmena politiky"],
        ["Objekt", "čoho sa akcia týkala"],
        ["Ako", "cesta: rozhranie, rozhranie API, služba, plánovač; adresa, odkiaľ prišla"],
        ["Výsledok", "úspech alebo zlyhanie"],
        ["Pôvodné a nové hodnoty", "rozdiel zmenených polí; heslá, tajomstvá a tokeny sa nikdy nezapisujú"],
    ], [4.5, 12.5])
    m.p("Filtrovať možno podľa času, osoby, skupiny akcií, výsledku a textu. **Exportovať CSV** (oprávnenie "
        "`audit.export`) stiahne výber; v obrannom profile má súbor v prvom riadku označenie nasadenia. "
        "**Overiť integritu** skontroluje zreťazenie a zobrazí, či je neporušené.")
    m.figure(S("18-audit"), "Auditný záznam s filtrami", 16.0)
    m.h(2, "9.4 E-mail a šablóny")
    m.p("Stránka **E-mail** má tri záložky.")
    m.table(["Záložka", "Obsah"], [
        ["Server", "zapnutie odosielania, SMTP server a port, šifrovanie, používateľ a heslo, adresa a meno "
                   "odosielateľa, adresa aplikácie, testovacia správa"],
        ["Šablóny", "znenie e-mailov (nižšie)"],
        ["Odchádzajúca pošta", "zoznam správ a ich stav: Čaká, Odoslané, Zlyhalo, Preskočené"],
    ], [4.5, 12.5])
    m.p("Heslo SMTP sa ukladá šifrovane a nikdy sa nezobrazuje; pole nechajte prázdne, ak ho nemeníte. "
        "Tlačidlom **Odoslať test** overíte nastavenie. Správy sa odosielajú na pozadí s opakovaním, takže "
        "výpadok pošty nezablokuje prácu v aplikácii.")
    m.figure(S("19-email-server"), "Nastavenie SMTP servera", 15.0)
    m.p("Na záložke **Šablóny** sa upravujú tieto správy:")
    m.table(["Šablóna", "Kedy sa odošle"], [
        ["User created (user.created)", "vytvorenie používateľa – dočasné prihlasovacie údaje"],
        ["Password reset (user.password_reset)", "obnovenie hesla správcom"],
        ["Account unlocked (user.unlocked)", "odomknutie s obnovením hesla"],
        ["Password changed (user.password_changed)", "oznámenie o zmene hesla (bez hesla)"],
        ["Account locked (user.locked)", "uzamknutie účtu"],
        ["Account locked – notice to administrators (admin.user_locked)", "upozornenie administrátorom"],
        ["Password expiring (password.expiring)", "blížiace sa vypršanie hesla"],
        ["Critical vulnerability alert (alert.critical)", "zero-day alebo zero-hour nález s vysokou závažnosťou"],
        ["Hybrid incident (incident.hybrid)", "vznik alebo eskalácia incidentu"],
        ["Test message (system.test)", "testovacia správa"],
    ], [8.0, 9.0])
    m.p("Pre každú šablónu a jazyk upravíte **Predmet**, **Textové telo** a voliteľne **HTML telo**. Povolené "
        "premenné sú vypísané nad poľom; neznáma premenná sa pri uložení odmietne. **Náhľad** ukáže výsledok, "
        "**Obnoviť predvolený text** vráti pôvodné znenie a **História verzií** uchováva predchádzajúce verzie. "
        "Premenná s dočasným heslom existuje iba v šablónach s prihlasovacími údajmi.")
    m.figure(S("20-email-sablony"), "Editor šablón e-mailov", 15.5)

    # ------------------------------------------------------------------------------------------------
    m.h(1, "10. Nastavenia")
    m.h(2, "10.1 Zložitosť hesiel")
    m.p("Stránka určuje pravidlá hesiel (tabuľka v kapitole 2.3): dĺžku, druhy znakov, platnosť, upozornenie "
        "pred vypršaním, históriu, minimálny vek, zobrazenie hesla a odmietanie používateľského mena a bežných "
        "hesiel. Zmena sa týka iba nových hesiel. Aplikácia odmietne nastavenia, ktoré si odporujú (napríklad "
        "minimálny vek dlhší než platnosť) a pomenuje dotknuté polia.")
    m.figure(S("21-politika-hesiel"), "Zložitosť hesiel", 15.0)
    m.h(2, "10.2 Zamykanie účtov")
    m.p("Stránka najprv v časti **Skutočné správanie** vlastnými slovami opíše, čo sa naozaj stane. Pod ňou sa "
        "nastavuje: nezamykanie posledného administrátora, počet prihlásení za minútu z jednej adresy a "
        "politika pre všetky roly, prípadne vlastná politika pre vybranú rolu.")
    m.table(["Pole", "Význam"], [
        ["Režim zámku", "automatické odomknutie po čase, stupňované oneskorenia, alebo zamknuté, kým niekto neodomkne"],
        ["Neúspešné pokusy do zamknutia", "počet pokusov v okne počítania"],
        ["Okno počítania", "za aký čas sa pokusy sčítavajú (minúty)"],
        ["Dĺžky zámku", "minúty; pri stupňovanom režime jedna hodnota na cyklus, hodnoty musia rásť"],
        ["Cykly do trvalého zámku", "po koľkých zámkoch ostane účet zamknutý natrvalo; prázdne = nikdy"],
        ["Kto môže odomknúť", "roly, ktoré smú účet odomknúť"],
        ["Po odomknutí", "nič, vyžiadať zmenu hesla, alebo obnoviť na vygenerované heslo"],
        ["Ukončiť relácie", "pri zamknutí a odomknutí skončia aktívne relácie"],
        ["Upozorniť pri zamknutí", "odošle e-mail o zamknutí"],
    ], [5.5, 11.5])
    m.figure(S("22-zamykanie"), "Zamykanie účtov", 15.0)
    m.h(2, "10.3 Relácie")
    m.p("Nastavuje **časový limit nečinnosti** (štandardne 30 minút) a **absolútnu dĺžku relácie** (štandardne "
        "12 hodín). Limit nečinnosti nemôže byť dlhší ako absolútna dĺžka.")
    m.figure(S("23-relacie"), "Politika relácií", 15.0)

    # ------------------------------------------------------------------------------------------------
    m.h(1, "11. Roly a oprávnenia")
    m.p("Pri inštalácii sa vytvorí týchto sedem rolí. Správca ich môže upraviť a pridať ďalšie.")
    m.table(["Rola", "Určenie", "Hlavné oprávnenia"], [
        ["Administrator", "správa systému", "všetko (okrem oprávnení určených iba zariadeniam)"],
        ["SOC Manager", "vedie SOC", "používatelia (zobraziť, vytvoriť, upraviť, odomknúť), zobrazenie rolí, politík, "
                                      "auditu a e-mailu, aktíva, spravodajstvo vrátane potvrdzovania, incidenty "
                                      "vrátane eskalácie a uzatvárania, simulácia"],
        ["SOC Analyst", "vyšetruje incidenty", "aktíva, spravodajstvo vrátane potvrdzovania, incidenty: triedenie a eskalácia"],
        ["SOC Operator", "sleduje panel", "aktíva, spravodajstvo (zobrazenie), incidenty: zobrazenie a triedenie"],
        ["OT Asset Engineer", "spravuje register aktív", "aktíva: zobrazenie, vytváranie, úprava, mazanie, výmena kľúčov; "
                                                          "spravodajstvo a incidenty iba zobrazenie"],
        ["Auditor", "iba na čítanie", "používatelia, audit vrátane exportu, politiky, e-mail, aktíva, spravodajstvo "
                                      "a incidenty iba zobrazenie"],
        ["Device Agent", "účet senzora alebo brány", "iba odosielanie udalostí vlastného zariadenia; nie je to účet pre človeka"],
    ], [3.4, 4.0, 9.6])
    m.note("Presné oprávnenia vašej roly uvidíte na stránke **Roly**, ak ju máte povolenú. Server kontroluje "
           "oprávnenie pri každej požiadavke; skrytie tlačidla v rozhraní nie je jediná ochrana.")

    # ------------------------------------------------------------------------------------------------
    m.h(1, "12. Správy a ich význam")
    m.table(["Správa", "Význam a čo urobiť"], [
        ["Používateľské meno alebo heslo nie je správne.", "Prihlásenie zlyhalo. Skontrolujte údaje; po opakovaných "
         "pokusoch sa účet uzamkne (kapitola 2.4)."],
        ["Príliš veľa pokusov. Počkajte minútu a skúste znova.", "Z vašej adresy prišlo príliš veľa prihlásení "
         "za minútu. Počkajte."],
        ["Heslo je príliš krátke / musí obsahovať…", "Nové heslo nespĺňa pravidlo; pozrite zoznam pravidiel pod poľom."],
        ["Toto heslo je príliš bežné.", "Heslo je na zozname najčastejších hesiel. Zvoľte iné alebo nechajte "
         "vygenerovať."],
        ["Toto heslo sa už použilo.", "Heslo ste už nedávno používali (história hesiel). Zvoľte nové."],
        ["Heslo bolo zmenené príliš nedávno.", "Dobrovoľnú zmenu možno najskôr po minimálnom veku hesla (štandardne "
         "48 hodín). Ak ste heslo zabudli, požiadajte správcu o obnovenie."],
        ["Na túto akciu nemáte oprávnenie.", "Vaša rola akciu nepovoľuje. Obráťte sa na správcu."],
        ["Požiadavka bola zamietnutá. Načítajte stránku znova…", "Relácia alebo ochranný token vypršal. Obnovte "
         "stránku a zopakujte akciu."],
        ["Server nie je dostupný.", "Aplikácia sa nedá dosiahnuť. Skontrolujte sieť; ak trvá, informujte správcu."],
        ["Toto je posledný aktívny administrátor.", "Posledného administrátora nemožno zmazať ani deaktivovať."],
        ["Obranný profil povoľuje iba offline balíky; toto nemožno vypnúť.", "Voľba Iba offline je v obrannom "
         "nasadení pevná."],
        ["Odpojené (nad mapou)", "Živé spojenie sa prerušilo; aplikácia sa pripája znova a stav sa načíta aj "
         "periodicky každých 30 sekúnd."],
    ], [6.5, 10.5])

    # ------------------------------------------------------------------------------------------------
    m.h(1, "13. Riešenie problémov")
    m.table(["Problém", "Možná príčina a postup"], [
        ["Neviem sa prihlásiť", "Skontrolujte meno a heslo. Ak je účet uzamknutý, počkajte na uplynutie času alebo "
                                "požiadajte správcu o odomknutie. Heslo sa rozlišuje podľa veľkosti písmen."],
        ["Pri prihlásení musím meniť heslo", "Je to očakávané pri prvom prihlásení a po obnovení hesla správcom."],
        ["V menu chýba položka", "Vaša rola nemá oprávnenie. Požiadajte správcu o rolu, ktorá ju obsahuje."],
        ["Nepríde e-mail s údajmi", "Skontrolujte stránku E-mail: zapnuté odosielanie, správny server a stav správy "
                                    "v zozname Odchádzajúca pošta (Čaká, Odoslané, Zlyhalo). Skontrolujte priečinok "
                                    "so spamom."],
        ["Na mape nie je žiadny dron", "Žiadna aktívna dráha: senzory nehlásia, alebo je dráha staršia ako 90 "
                                       "sekúnd. Skontrolujte, že senzory sú zelené a že indikátor ukazuje Naživo."],
        ["Mapa je prázdna alebo zle vycentrovaná", "Skúste Obnoviť stránku; v nasadení bez zón sa mapa prispôsobí "
                                                   "rozsahu definovaných zón."],
        ["Incident nevznikol, hoci je dron blízko", "Aktívum nemá vyplnenú fyzickú expozíciu, alebo nemá "
                                                    "kybernetický signál (poplach alebo zneužívanú zraniteľnosť), "
                                                    "alebo je dron mimo dosahu (kapitola 5.1)."],
        ["Nález chýba pri známej zraniteľnosti", "V inventári softvéru aktíva chýba produkt alebo verzia, alebo je "
                                                 "zdroj spravodajstva vypnutý. Doplňte softvér a spustite zdroj."],
        ["Zdroj spravodajstva hlási Chyba", "Pozrite text chyby pri zdroji. V obrannom profile online zdroje "
                                            "nefungujú; použite podpísaný balík."],
        ["Stránka je pomalá alebo „Odpojené“", "Skontrolujte sieťové spojenie. Aplikácia sa pripojí sama; stav "
                                               "dopočíta aj pri načítaní stránky."],
    ], [5.0, 12.0])

    # ------------------------------------------------------------------------------------------------
    m.h(1, "14. Slovník pojmov")
    m.table(["Pojem", "Vysvetlenie"], [
        ["Aktívum", "zariadenie alebo uzol v sieti objektu evidovaný v registri"],
        ["Audit", "nemenný záznam o tom, kto, kedy, čo a ako urobil"],
        ["Blast radius / dosah dopadu", "aktíva, ktoré môže ovplyvniť porucha jedného aktíva, podľa počtu skokov"],
        ["Dominový efekt", "šírenie poruchy po závislostiach od jedného zariadenia na ďalšie"],
        ["EPSS", "odhad pravdepodobnosti, že sa zraniteľnosť začne zneužívať (0 až 1)"],
        ["Expozícia", "spôsob, akým sa k aktívu možno dostať fyzicky zvonku"],
        ["Hybridný incident", "incident, v ktorom súvisí fyzická udalosť s kybernetickým signálom"],
        ["Nález", "zhoda zraniteľnosti s konkrétnym aktívom"],
        ["Purdue úroveň", "vrstva v modeli priemyselných sietí (od regulátorov po podnikové IT)"],
        ["Relácia", "obdobie od prihlásenia po odhlásenie alebo vypršanie"],
        ["Zero-day / Zero-hour", "zneužívaná zraniteľnosť bez opravy / čerstvo zverejnená zneužívaná zraniteľnosť"],
        ["Zóna", "pomenovaná oblasť objektu s vlastnou kritickosťou"],
    ], [4.5, 12.5])

    m.save(out)
