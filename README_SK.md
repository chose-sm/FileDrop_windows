# AirDrop pre Windows

[English](README.md) | **Slovenčina**

Posielanie súborov medzi Windows PC a iPhonom cez domácu Wi-Fi. Na iPhone sa nič neinštaluje, stačí Safari.

## Spustenie

1. Dvojklik na `start.bat` (alebo `python airdrop.py`). Potrebuješ Python 3.8 alebo novší, nič ďalšie netreba inštalovať.
2. Keď sa Windows pri prvom spustení opýta na bránu firewall, povoľ prístup pre **súkromné siete**.
3. V prehliadači na PC sa otvorí okno s QR kódom. Naskenuj ho fotoaparátom iPhonu.
4. Odporúčam: na iPhone v Safari ťukni na **Zdieľať → Pridať na plochu**. Potom AirDrop otvoríš ako aplikáciu, bez skenovania.

### Voliteľné: prenosná verzia (bez Pythonu)

Ak nemáš nainštalovaný Python, stiahni si **[AirDrop-Windows.zip](https://github.com/chose-sm/AirDrop_windows/releases/latest/download/AirDrop-Windows.zip)**. Odkaz vždy vedie na najnovšiu verziu (prehľad zmien nájdeš v sekcii [Releases](https://github.com/chose-sm/AirDrop_windows/releases)). Obsahuje oficiálny prenosný Python z python.org, digitálne podpísaný organizáciou Python Software Foundation, takže netreba nič inštalovať. ZIP rozbaľ kamkoľvek a dvakrát klikni na `start.bat`. Ostatné kroky vyššie zostávajú rovnaké. Firewall sa pri prvom spustení opýta na `python.exe`; povoľ mu súkromné siete.

## Použitie

| Smer | Ako |
|---|---|
| PC → iPhone | Pretiahni súbory do okna na PC (alebo Ctrl+V). Na iPhone ich potom stiahneš cez **Stiahnuť** (uloží sa do Súborov), fotky a videá cez **Otvoriť** a podržanie prsta → **Pridať do Fotiek**. |
| iPhone → PC | Ťukni na **Poslať do PC** a vyber fotky alebo súbory. |

Súbory sú v priečinku AirDrop, predvolene `Stiahnuté\AirDrop` (presnú cestu vidíš hore v okne na PC):
- `Prijate` obsahuje súbory z iPhonu,
- `Odoslane` obsahuje súbory pripravené pre iPhone.

### Vlastný priečinok

Súbory si môžeš ukladať kamkoľvek. Vedľa `airdrop.py` vytvor textový súbor `airdrop_folder.txt` a do prvého riadku napíš cestu k priečinku, napríklad:

```
D:\AirDrop
```

Potom AirDrop reštartuj. Ak priečinok neexistuje, vytvorí sa automaticky.

## Nastavenia (premenné prostredia)

- `AIRDROP_PORT` je port, predvolene `8765`.
- `AIRDROP_DIR` je priečinok so súbormi a má prednosť pred `airdrop_folder.txt`.
- Spustenie s `--no-browser` neotvorí prehliadač.

## Bezpečnosť

Prístup chráni náhodný kľúč v QR kóde, uložený v súbore `.token` v priečinku AirDrop. Keď ho zmažeš, vygeneruje sa nový a starý odkaz prestane fungovať. Prenos ide nešifrovane cez HTTP v lokálnej sieti, preto ho používaj len doma alebo na dôveryhodnej Wi-Fi.

Ďalšia ochrana:
- Webové stránky otvorené v prehliadači na PC nemôžu AirDrop ovládať (ochrana proti CSRF a DNS rebinding).
- Súbory prijaté z mobilu sú označené ako stiahnuté z internetu, takže Windows pred ich otvorením varuje. Spustiteľné súbory (`.exe`, `.bat`, `.ps1`, …) tlačidlo **Otvoriť** nikdy nespustí, len ich označí v Prieskumníkovi.
- Prenášané súbory sa zobrazujú v izolovanom režime (sandbox), takže HTML alebo SVG súbor nemôže v aplikácii spustiť skript.
- Všetky časti aplikácie vrátane knižnice pre QR kód sú priložené; nič sa nenačítava z internetu.

## Riešenie problémov

- **iPhone sa nepripojí:** obe zariadenia musia byť na rovnakej Wi-Fi a sieť vo Windows musí byť nastavená ako *Súkromná*. Pravidlo firewallu môžeš pridať aj ručne (PowerShell ako správca):
  ```
  New-NetFirewallRule -DisplayName "AirDrop pre Windows" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow -Profile Private
  ```
- **Viac sieťových adries (VPN, Hyper-V):** pod QR kódom vyber správnu adresu.
- **Fotky prídu ako .HEIC:** v iPhone nastav *Nastavenia → Fotoaparát → Formáty → Najkompatibilnejšie*.

## Jazyk

Rozhranie je v slovenčine a angličtine. Prepneš ho prepínačom vedľa nápisu AirDrop. Každé zariadenie (PC aj iPhone) si pamätá svoju voľbu a pri prvom spustení sa jazyk zvolí podľa nastavenia zariadenia.

## Zostavenie balíka (pre vývojárov)

Bežný používateľ toto nepotrebuje. Stačí mu stiahnuť ZIP cez odkaz vyššie.

Prenosný balík zo zdrojového kódu zostavíš v priečinku projektu príkazom:

```
powershell -ExecutionPolicy Bypass -File build_release.ps1 -Version 1.1.0
```

- Výsledok je `dist\AirDrop-Windows.zip`. Nahraj ho do nového vydania na GitHube presne pod týmto názvom, aby odkaz na stiahnutie v tomto návode stále viedol na najnovšiu verziu.
- `-Version` určuje len číslo verzie v názve priečinka vo vnútri ZIP-u (napr. `AirDrop-Windows-v1.1.0`).
- Skript stiahne oficiálny prenosný Python z python.org (`-PythonVersion`, predvolene `3.14.8`) a overí digitálne podpisy všetkých jeho súborov.
