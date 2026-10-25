# Nutikad Lahendused: Labor 2 — internetipostkontor ja kaks kaamerat

> See on tööleht, mitte valminud süsteemi kirjeldus. Dropleti, võrgu, roboti,
> kaamerate ja AtomS3 päriskatsed on tegemata, kuni nende juures on kirjas
> mõõtmise kuupäev, meetod ja tegelik tulemus.

**Töömaht:** 28 tundi | **Hindamine:** 20 punkti | **Meeskond:** 3 tudengit

**Välja antud:** 07.10.26 | **Tellimise kuupäev:** 16.10.26 | **Esimene kaitsmine:** 29.10.26, veebis

Kaitsmise kuupäev: [õppejõu ajakohane ülesanne](https://github.com/KKallas/Narva-subjects/blob/main/EST/2026-27/Smart%20Solutions/Smart%20Solutions%20%5BLab%202%5D%20EST.md).

## Praegune seis — 23.10.26

**Tarkvara:** valmis on Flask/SQLite postkontor koos autentimise, TTL-i,
järjekorra, `last_seen` ja tulemuste käsitlemisega; kõrgtaseme tööd `letter`
ja `pick_place`; station-adapter (`pick_place` täitmine on ainult mock);
Atomi väljaminev polling ja Wi-Fi recovery; USB/XIAO kaamerate tarkvaraalus;
rõhuanduri UI, kalibratsioonimudel ja NVS-seaded; production-paigalduse
runbook ning software-regressiooni skript `check.sh`.

**Kontrollitud:** 23.10.26 pärast HEALTH_ONLY lisamist Python `541 passed`,
Atom native `57/57` (sh HEALTH_ONLY `14/14`) ja health-build `SUCCESS`;
ELF isolation ja kohaliku CA fingerprint'i kontroll läbisid. Varasemad
BENCH-kontrollid olid Python `480 passed`, Atom native `43/43` ja
`atoms3r` BENCH_MODE=1 puhas build `SUCCESS`. Varasemad XIAO native `6/6`,
deployment-testid `18 passed` ja XIAO build jäävad eraldi tarkvaratulemusteks.
Mõlema töö software E2E läbib tulemusega `done` ja `hardware_used=false`.
Varasemad Atomi lokaalse autentitud HTTP pollingu, reboot-püsivuse ning
Wi-Fi fallback/reconnect/recovery katsed on tehtud päris seadmel. Need
tarkvarakontrollid ei tõenda kogu Lab 2 riistvaravalmidust.

**Asendus-AtomS3R-i BENCH-katse:** seadmesse (ESP32-S3-PICO-1, 8 MB flash)
laaditi 23.10.26 `atoms3r` BENCH_MODE=1. Enne laadimist kontrolliti
Lab 1 täis-flash backup'i suurust ja SHA-256 ning Lab 1 ekraan töötas pärast
backup'i. LCD näitab `BENCH` / `execution disabled`; MacBook ühines kaitstud
`Lab2AtomBench` AP-ga ja Safari avas aadressil `http://192.168.4.1` eestikeelse
read-only lehe. Salvestus- ja postkontori testinupud olid keelatud. Nikita
Teterev kontrollis hiljem samal päeval MacBookist curl'iga üle selle AP:
`POST /settings`, `POST /test/post-office` ja `POST /pressure/settings`
andsid kõik `HTTP/1.1 423`
ning `{"error":"bench_read_only"}`. Päringutes ei olnud paroole ega API-võtmeid.
G5 ilma andurita andis `raw_adc=7`,
`not_calibrated`, voltage/kPa `null`: see on ujuva sisendi vaatlus, mitte
rõhumõõtmine. Reset'i järel taastus BENCH-ekraan; rakenduse serial-teateid
ei salvestatud ega kinnitatud. Production-polling ja station-kanal on bench'is
keelatud. Vana musta ekraaniga seadme rike jääb tõestamata; selle ajalugu on
[`docs/atom_display_diagnostic.md`](docs/atom_display_diagnostic.md) failis.
Piirangud ja bench-juhend: [`firmware/README.md`](firmware/README.md).

**HEALTH_ONLY katse 23.10.26:** Nikita Teterev laadis seejärel eraldi
`atoms3r_health` püsivara ning kontrollis LCD-d ja USB-helper'it. Redmi
telefoni hotspot'i kaudu sai ta `WIFI CONNECTED`, `TLS VERIFIED`,
seejärel `HEALTH ERROR`; helper naasis shell'i. HTTP 200 ega oodatud
`/health` JSON ei ole kinnitatud. Production-pollingut, jobs'i ega station
dispatch'i selles build'is ei ole. Vea täpne HTTP/read/framing põhjus
on lahtine; [diagnostikaplaan](firmware/README.md#health-error-23102026-piiratud-tulemus-ja-järgmine-diagnostika)
ei tähenda paranduse ega eduka korduskatse läbimist. Seadme hilisemat
olekut teiste kursuste katsetes see kanne ei kinnita.

**Droplet:** Nikita Teterev kontrollis 20.10.26 avalikku postkontorit aadressil
`https://narva2.roboarena.org`. Maci väline curl sai `/health` päringule
HTTP/2 200 korrektse TLS-iga; Safari Macis ja Chrome telefonis 5G kaudu
avasid autentitud kasutajaliidese. Ubuntu 24.04.5 LTS serveris uuendati
11 paketti, SSH parooli- ja keyboard-interactive autentimine on keelatud
ning võtmega sõltumatu login pärast UFW aktiveerimist on kontrollitud.
UFW on `active`, sissetulevad TCP 22/80/443 lubatud ja vaikepoliitika
`deny incoming`. Caddy 2.11.7 ja `smart-solutions-lab2` on `active` ning
`enabled`. Aktiivne 1 GiB swap-fail on kirjas `/etc/fstab` failis.

**Production-kontrollid:** `letter A` loodi ja aegus põhjusega `ttl_expired`;
SQLite kirje säilis teenuse restardi järel. Backup oli 24 576 baiti,
`root:root 0600`; eraldi testbaasi taastamisel oli `integrity_check` tulemus
`ok` ja töö kirje taastati. `deploy/verify.sh`: `12 PASS, 0 FAIL, 0 SKIP`.
Atom on avalikus serveris offline ja production pollingut pole testitud.
Kogu dropleti reboot ning füüsiline MG400 integratsioon on kontrollimata.
Kuupäevaga tulemused on päevikus ja [paigaldusjuhendis](deploy/README.md).

**Production UI uuendus:** Nikita uuendas 20.10.26 serveri commit'ilt
`7571582` commit'ile `7d374915f48e9f4cc7e4357e3a2c82df6191f231`
`deploy/update.sh` kaudu. Fast-forward läbis ja SQLite backup'id loodi enne
uuendust. Vahetu kontroll pärast restarti sai lokaalse connection refused
ning avaliku HTTPS 502: Gunicorn polnud veel porti avanud. Pärast Gunicorni
valmisolekut läbis korduv `deploy/verify.sh` kõik 12 kontrolli (`0 FAIL`),
serveri tööpuu oli puhas ja `letter A` kirje säilis (`expired`, `ttl_expired`).
Uus UI, mobiilikaardid ja letter/pick-place väljade vahetus on kontrollitud
Safari Macis ning Chrome Androidis 5G kaudu. Repos lisatud readiness-ootamine
on kohalik parandus; seda versiooni pole veel production'is kontrollitud.

**Atomi production TLS ettevalmistus:** Nikita kontrollis 20.10.26 Macis
serveri TLS-ahelat OpenSSL-iga (`Verify return code: 0 (ok)`). Ta lisas
ametlikust allikast saadud ja fingerprint'i järgi kontrollitud ISRG Root X2
CA lokaalsesse ignoreeritud header'isse. CA-ga Atom build läbis ja
`firmware.bin` sisaldas PEM-sertifikaati; `check.sh` lõpetas teatega
`All software-only regression checks passed.` See on software-only
ettevalmistus. 23.10.26 eraldi HEALTH_ONLY katses kinnitas Atom Wi-Fi ja TLS-i,
kuid `/health` lõppes veaga; edukas HTTP/JSON ja production-polling on TODO.
Üksikasjad: [firmware README](firmware/README.md#production-tls-ettevalmistus--20102026).

**Laboris veel teha:** päris `pick_place` executor ja kalibratsioon, füüsiline
Lab 2 end-to-end, mõlemad päris kaamerad, sensor/op-amp ahel ja Andmehõive
Lab 2 rõhukalibratsioon, tegelikud latency/metrics mõõtmised, production
HTTPS polling, BOM-i ja tellimuse kontroll ning iga liikme isiklik
ohutuskinnitus. Asendus-AtomS3R-i esimene isoleeritud bench-katse on tehtud;
normaalrežiim vajab eraldi luba ja katseplaani. Lõplik tag tehakse alles pärast
kriteeriumide täitmist.

## Eesmärk

Labor 2 lisab Labori 1 lokaalsele Atom → jaam → MG400 ahelale internetis
kättesaadava postkontori. Kasutaja loob autentitud HTTPS-lehel kõrgtaseme
töö. Atom küsib dropletilt töid väljamineva polling-ühendusega ja annab need
Laborist 1 pärit lokaalse kanali kaudu jaamale. Ainult jaam suhtleb MG400-ga.

Lisaks tuleb jaama lehele kaks kohalikku kaamerapilti: laua üldvaade ja
tööriista juures olev lähivaade. Kaameravood ei lähe dropleti postkontorisse.

Smart Solutions Lab 2 ei ava jaama lehte dropleti kaudu ega loo dropleti ja
jaama vahele VPN-i, SSH pöördtunnelit või muud otsejuhtimise teed. Atom küsib
ise dropletilt töid. Otsene kaugjuurdepääs jaamale kuulub Smart Solutions
Lab 3 ulatusse.

Labor 1 jääb muutmata lähtebaasiks:

- `smart-solutions/lab1/src/station.py` sisaldab jaam → MG400 täitmisrada;
- `smart-solutions/lab1/docs/letter_channel.md` kirjeldab Atomi lokaalset
  HTTP/USB kanalit, korduste tuvastamist ja ohutusväravaid;
- Labori 1 Atomi püsivara ning sama seadete/testide leht on edasise töö alus;
- Labori 1 MG400 ohutusreeglid kehtivad täielikult edasi.

Kavandatud ühendused (tervikahel vajab laborikatset):

```text
MG400 <--- Ethernet/TCP ---> station PC
Verbatim AWC-03 <--- USB ---> station PC
AtomS3R <--- USB Serial ---> station PC
AtomS3R --- Wi-Fi/HTTPS ---> droplet <--- HTTPS --- kasutaja brauser
station PC --- kohalik IP-võrk / Wi-Fi / GET /snapshot.jpg ---> XIAO
USB-C toiteallikas (TODO) ---> XIAO
```

Ethernetiga station PC peab jõudma Wi-Fi-s oleva XIAO IP-ni. Alamvõrgud,
marsruutimine ja Wi-Fi client isolation tuleb laboris kontrollida; PC enda
Wi-Fi adapter pole vajalik, kui võrgud lubavad IP-liiklust. XIAO toiteallikas
ja kaablitee on TODO. Droplet ei vahenda videovooge. Täpsemalt: [kaamerad](docs/cameras.md).

![Lab 2 süsteemiarhitektuur](docs/system.svg)

Muudetav skeem: [`docs/system.drawio`](docs/system.drawio). Skeem näitab eraldi
avalikku postkontorit, Atomi väljaminevat pollingut, lokaalset robotirada ja
ainult station'i lehele minevaid kaameravooge.

Täpne protokoll on failis [`docs/server_api.md`](docs/server_api.md).
Kohalik kaamera-arhitektuur ja tulevaste pärismõõtmiste metoodika on failis
[`docs/cameras.md`](docs/cameras.md).

## Püsivara töövoog

AtomS3 püsivara arendatakse, ehitatakse ja laaditakse seadmesse PlatformIO
abil. Lab 2 muudatused peavad jääma reprodutseeritavasse PlatformIO projekti:
`platformio.ini`, lähtekoodipuu ja fikseeritavad sõltuvused. Arduino IDE ei
ole selle repo peamine projektitöövoog.

XIAO ESP32S3 Sense tööriistakaamera on eraldi PlatformIO projektis
`firmware-xiao-camera/`; see ei ole AtomS3 projektiga kokku segatud. Mõlemal on
oma `platformio.ini`, lähtekoodipuu ja native-testid. Lab 2 AtomS3 projekt on
kaustas `firmware/`; Labori 1 püsivara ei ole tervikuna kopeeritud. Mõlema
projekti `pio run` build on tarkvaraliselt kontrollitud. AtomS3R-i Lab 2
püsivara laaditi 12.10.26 PlatformIO-ga seadmesse; Atomi autentitud lokaalne
polling, reboot-persistence ja Wi-Fi reconnect kontrolliti 13.10.26. Selle
repo XIAO Wi-Fi firmware upload ja ülejäänud integratsioonikatsed on TODO.

## Tehtud töö

See jaotis võtab kokku repos tegelikult valminud ja tarkvaraliselt kontrollitud
Lab 2 osad ning 16.10.26 ja 20.10.26 dropleti kontrollid. Roboti ja
kaamerate füüsilised katsed jäävad lahti; Atomi varasemad katsed on eraldi
kuupäevaga kirjas.

### Postkontori server

- Valmis on Flaski ja SQLite'i kasutav postkontor, kus autentitud kasutaja saab
  luua lubatud kõrgtaseme `letter` ja `pick_place` töid. `pick_place` lubab
  ainult eelmääratud routine'i `source_to_finished`.
- Atomil on kasutajaliidesest eraldatud bearer-võtmega polling- ja tulemuse API.
- Server rakendab TTL-i ja aegumist, lubatud tööde whitelist'i, atomaarset
  claim'i ning idempotentset tulemust. Tundmatuid töid, otseliikumiskäske ja
  kasutaja antud trajektoore järjekorda ei lubata.
- SQLite'is säilivad töö, tulemus ja Atomi `last_seen` olek. Sama töö
  kordussaatmine ei käivita kontrollimatut uut täitmist.
- Sama API-ga mock Atom võimaldab serveri töövoogu kontrollida ilma AtomS3R-i,
  station'i või MG400-ta. Serveri käitumine on kaetud Python testidega.
- Nikita paigaldas serveri päris dropletile 16.10.26. Ta kontrollis 20.10.26
  avalikku HTTPS-i, login'it Macis ja telefonis 5G kaudu, `letter A` loomist
  ja aegumist ning kirje säilimist teenuse restardi järel. Atom oli offline;
  robotitöö täitmist selle katsega ei kontrollitud.

### AtomS3R Lab 2 püsivara

- Kaustas `firmware/` on PlatformIO projekt: environment `atoms3r` kasutab
  ühilduvat `m5stack-atoms3` board definition'it.
- Seadete mudel sisaldab serveri URL-i, Atomi privaatvõtit ja polling-intervalli.
  Rakendatud on väljaminev poll/result klient ning production-siht kasutab
  HTTPS-i.
- Aktiivse töö ID ja saatmata terminaltulemus säilitatakse püsivalt. Ühe
  aktiivse töö piir, duplikaadikaitse ja restardi järel ebaselge claim'i
  fail-safe käitumine väldivad automaatset kordustäitmist.
- Atom → station piir säilitab `letter` jaoks Lab 1 väljadega ühilduva
  serial-JSON sõnumi ning saadab `pick_place` jaoks ainult high-level routine'i;
  mõlemal on stabiilne `job_id`. Native-testid ja PlatformIO build läbivad.
- Lab 2 püsivara laaditi 12.10.26 füüsilisse AtomS3R-i pordi
  `/dev/cu.usbmodem101` kaudu. Esimesel katsel leitud NVS `activeId NOT_FOUND`
  kordus ja development-serveri loopback-bind parandati ning kontrolliti sama
  päeva jätkukatses. Setup-AP, settings, autentitud lokaalne polling,
  reboot-persistence ja Wi-Fi reconnect kontrolliti päris seadmel 13.10.26;
  production HTTPS, station/MG400 ja ametlik mid-job katkestus on TODO.

### Station-adapter

- Valmis on station'i Atom-job adapter, mis eristab `letter` ja `pick_place`
  töid, säilitab `session/seq/atom_sent_ms` väljad ning serveri stabiilse
  `job_id`.
- SQLite'i idempotentsus, `session + seq` duplikaadikaitse ja restardi
  `ambiguous_after_restart` fail-safe väldivad ebaselge töö automaatset
  korduskäivitust.
- USB serial transport on eraldi abstraktsioon. Eraldi letter- ja pick-place
  mock executor'id võimaldavad software-only kontrolli; vaikimisi on täitmine
  keelatud.
- Adapter ei loo MG400 ühendust ega impordi robotiklienti. Kohalik software E2E
  läbib kogu server → mock Atom → station → server tulemuse ahela.
- Päris MG400 täitmine on TODO ja vajab eraldi lokaalset ohutuskontrolli.

### Station'i kaamerad

- Valmis on ühine kaameraabstraktsioon, USB OpenCV backend ja XIAO HTTP
  snapshot backend.
- Eraldi `src.camera_server` leht näitab kahte kaamerat ning pakub snapshot- ja
  MJPEG route'e. Vaikebind on `127.0.0.1:5002`, autentimist ei ole. Olemasoleva
  station'i lehega ühendamine ja kaitstud LAN-ligipääs on TODO. Mock-kaamerad
  võimaldavad mõlemat rada riistvarata testida.
- Tarkvaralised loendurid mõõdavad kaadrite arvu, väljastatud baite ning
  arvutatud FPS/Mbit/s väärtusi; need ei ole füüsiliste kaamerate mõõtetulemused.
- Kaamerakiht ja route'id on kaetud testidega. Päris USB- ja XIAO-kaameraid ei
  ole selle Lab 2 töövooga füüsiliselt kontrollitud.

### XIAO ESP32S3 Sense

- Kaustas `firmware-xiao-camera/` on eraldi PlatformIO projekt ametliku
  `seeed_xiao_esp32s3` boardiga.
- Teostatud on camera init alus, toetatud sensori tuvastamine, PSRAM-i arvestav
  seadistus, piiratud Wi-Fi reconnect/backoff ning endpoint'id `/status` ja
  `/snapshot.jpg`.
- HTTP leping sobib station'i XIAO snapshot backendiga. PlatformIO build ja
  native-testid läbivad.
- Lab 2 põhipüsivara on `firmware-xiao-camera/`, kohalik Wi-Fi HTTP
  `GET /snapshot.jpg`. **Selle püsivara upload ja Wi-Fi töö on kinnitamata.**
- [3D Printing Lab 2](https://github.com/Dennel04/3d-printing-course/blob/main/3d-print/lab2/README.md)
  kinnitab 23.10.26 J4 kinnituses XIAO OV3660 ühe JPEG-i `1600 × 1200`
  saamist USB Serial COM5 kaudu. Sealne `tool-camera/firmware/` jääb
  diagnostiliseks varuks, mitte selle Wi-Fi lahenduse kinnituseks.
  J4 paigutus on meeskonna dokumenteeritud variant, mille kohta 3D Printing
  kirjeldab õpetaja suulist luba. Verbatim AWC-03 (49580) on üldvaatekaamerana
  identifitseeritud; lõplik paigaldus, kogu laua FOV ja mõõtmised on TODO.

### Dropleti paigalduse alus

- Valmis on olemasoleva Flaski rakenduse Gunicorn WSGI entrypoint, localhosti
  bind'iga systemd unit ja Caddy HTTPS reverse proxy näidis.
- Lisatud on placeholder'itega env/saladuste muster ning install-, update-,
  verify- ja backup-skriptid. SQLite asub kavandis lähtekoodipuust väljas ning
  backup kasutab SQLite'i turvalist backup API-t.
- Paigalduse staatilised ja lokaalsed testid kontrollivad muu hulgas localhost
  bind'i, fail-closed saladusi, Caddy piiri ja backup'i terviklikkust.
- Nikita käivitas 16.10.26 päris dropletil `deploy/install.sh` ning seejärel
  systemd teenuse käsitsi. Env-faili õigused, SQLite fail, loopback-bind,
  HTTP 200 health ja autentimata HTTP 401 on kontrollitud.
- Nikita kontrollis 20.10.26 Caddy avalikku HTTPS-i, SSH autentimisseadeid,
  UFW-d ja teenuste `enabled/active` olekut. `deploy/verify.sh` andis
  `12 PASS, 0 FAIL, 0 SKIP`; SQLite backup ja taastamine eraldi testbaasi
  läbisid. Kogu dropleti reboot ja täielik taastamine puhtale hostile on TODO.

## Tarkvaralise kontrolli tulemused

Allolev tabel on praeguse tarkvaraseisu koond, mitte varasemate arenduspäeviku
kannete ümberkirjutus. Kontrollid on software-only, kui piirangu veerus ei ole
selgesõnaliselt märgitud päris riistvara.

| Kontroll | Tegelik tulemus | Piirang |
| :--- | :--- | :--- |
| Lab 2 Python `pytest` | 23.10.26 pärast HEALTH_ONLY lisamist: 541 testi läbis | software-only |
| `python -m src.e2e_demo` | `letter` ja `pick_place`: `server_status=done`, sama `job_id` kogu ahelas, `hardware_used=false` | ajutine DB, mock Atom ja mock executor |
| AtomS3R `pio run -e atoms3r` | 23.10.26: BENCH_MODE=1 puhas build SUCCESS | lokaalne build; tavaline postkontoriklient on sellest build'ist väljas |
| AtomS3R `pio test -e native` | 23.10.26: 57/57 testi läbis (43 olemasolevat ja 14 HEALTH_ONLY) | hosti native-testid, mitte seadme test |
| `pio run -e atoms3r_health` ja ELF verifier | SUCCESS; RAM 49 112 B, flash 982 297 B; isolation ja CA PASS | lokaalne build; flash-coredump jääkrisk säilib; päris `/health` katse lõppes veaga |
| XIAO `pio run` | SUCCESS, board `seeed_xiao_esp32s3` | build; upload'i ei tehtud |
| XIAO `pio test -e native` | 6/6 testi läbis | hosti native-testid, mitte kaamerakatse |
| Deployment-testid | 18 testi läbis | lokaalne/static ja mock readiness-kontroll; päris hosti ei kasutatud |
| WSGI import ja deploy shell syntax | läbis | lokaalne/static kontroll |
| `deploy/verify.sh` arendusmasinas | `SKIP` | systemd/Caddy production-kontroll vajab päris Ubuntu dropletit |
| Mock-kaameraserver | HTTP 200 lehel, API-s ning table/tool snapshot'idel | sünteetilised mock-kaadrid, mitte füüsiline mõõtmine |

Tabeli software-only tulemused ise ei tõenda seadme upload'i, MG400 täitmist,
päris kaamerate tööd, internetist kättesaadavat HTTPS-i, SSH hardening'ut ega
tulemüüri olekut. Hilisem osaline AtomS3R upload/boot-katse on eraldi kirjas
12.10.26 arenduspäeviku riistvarakande juures ning asendusseadme isoleeritud
bench-katse 23.10.26 kandes; selle repo XIAO Wi-Fi firmware upload on TODO.

Varasemad testiarvud jäävad kuupäevaga arenduspäeviku kannetes ajalooliseks
tõendiks. Praegune koond ei ole MG400, pumba, rõhuanduri, XIAO ega kaamerate
füüsiline katsetulemus.

## Kontrollnimekiri

Kõik punktid on alguses lahti. Märge tehakse alles pärast kontrollitavat
tulemust; füüsilise katse juurde lisatakse kuupäev, meetod ja failiviide.

### Tarkvaraliselt ettevalmistatav

- [x] Postkontori kasutajaleht ja Atomi API on loogiliselt eraldatud.
- [x] Kohalik kasutajaleht nõuab autentimist; production-siht on endiselt HTTPS.
- [x] Postkontor võtab vastu ainult whitelist'is olevaid kõrgtaseme töid.
- [x] `letter` on lubatud ja tarkvaraliselt teostatud kõrgtaseme robotitöö.
- [x] `pick_place` on teine lubatud high-level töö software-only ahelas;
  ainus routine on `source_to_finished` ning internetist antud koordinaadid,
  kiirus, pumba-/DO-käsud ja trajektoorid lükatakse tagasi. Päris MG400/pumba
  kontroll on endiselt lahti, seega ametlik riistvarakriteerium ei ole täidetud.
- [x] Töödel on TTL; aegunud töö märgitakse `expired` ja seda ei väljastata.
- [x] Vigane või tundmatu töö lükatakse tagasi ega jõua täitmispiirini.
- [x] Stabiilne töö ID, atomaarne claim ja idempotentne tulemus välistavad
  sama töö kontrollimatu kordusväljastuse.
- [x] Atom API on väljamineva pollingu jaoks; droplet ei loo ühendust
  Atomi, jaama ega robotiga.
- [x] Poll uuendab heartbeat-/olekuinfot; leht näitab `last_seen` põhjal
  online/offline olekut, roboti olekut ja polling-intervalli.
  - 25.10.26 parandus: kuni selle päevani näitas leht ainult online/offline
    olekut ja `last_seen` väärtust; roboti olek ja polling-intervall olid
    ainult `/api/status` ja `/api/jobs` JSON-is. Nüüd näitab Atomi paneel ka
    jaama teatatud `robot_state` väärtust ja Atomi `poll_interval_ms` väärtust.
- [x] Sama terminaltulemuse kordussaatmine sama töö ID-ga on serveris idempotentne.
- [x] Postkontori API leping on kirjas failis `docs/server_api.md`.
- [x] Kohalik Flask postkontor, SQLite store ja minimaalne kasutajaleht on teostatud.
- [x] Mock Atom kasutab sama HTTP API-t ja simuleerib lokaalse jaama tulemust,
  kuid ei kasuta AtomS3 ega MG400-t.
- [x] Automaattestid katavad autentimise, valideerimise, TTL-i, claim'i,
  idempotentsuse, tulemused ja `last_seen` oleku.
- [x] Atomi olemasoleva lehe Lab 2 väljad ja testid on kirjeldatud failis
  `docs/atom_page.md`.
- [x] AtomS3 PlatformIO projekt build'ib ning hostitestid katavad töö- ja
  konfiguratsioonivalideerimist ning ühe aktiivse claim'i reeglit.
- [x] Atom pollib millis-ajastusega, valideerib `letter` ja eelmääratud
  `pick_place` töö ning salvestab aktiivse ID ja saatmata terminaltulemuse
  püsivalt enne retry'd.
- [x] AtomS3 minimaalne seadeteleht salvestab serveri URL-i, bearer-võtme ja
  polling-intervalli; saladust ei tagastata ega logita.
- [x] Lab 2 station-adapter valideerib firmware serial-JSON lepingu ja kasutab
  Lab 1 `session + seq` korduskaitset koos stabiilse `job_id` väärtusega.
- [x] Station'i SQLite store säilitab terminaltulemuse ja muudab restardist
  jäänud poolelioleva töö `ambiguous_after_restart` keeldumiseks.
- [x] Mock executor ning lokaalne end-to-end demo kontrollivad server → mock
  Atom → station → server ahelat ilma AtomS3 või MG400-ta.
- [x] Ohutuskokkuleppe mustand on failis `docs/safety.md`.
- [x] BOM-i kontroll-leht on failis `docs/bom.md`.
- [x] Mõõtmiste CSV-mallid sisaldavad ainult päiseid, kuni päris mõõtmised on tehtud.
- [x] Station'i eraldi kohalik kaameraserver näitab kahte jagatud worker'iga
  MJPEG-allikat ning ei lisa kaameraroute'e dropleti postkontorisse.
- [x] Mock table/tool allikad, USB OpenCV backend ja seadistatava URL-iga XIAO
  snapshot backend on automaattestitavad ilma riistvarata.
- [x] Software kaadriloendurid ja väljastatud baitide/FPS/Mbit/s arvutus on
  valmis; need ei ole päris kaameramõõtmised.
- [x] XIAO ESP32S3 Sense tool-camera on eraldi PlatformIO projekt ametliku
  `seeed_xiao_esp32s3` boardiga; build ja native-testid läbivad.
- [x] XIAO `/status` ja `/snapshot.jpg` leping sobib station'i olemasoleva
  snapshot backendiga; Wi-Fi saladused jäävad ignored private header'isse.
- [x] Production-paigalduse tarkvaraalus sisaldab localhost Gunicorn unit'it,
  Caddy HTTPS reverse proxy näidist, kaitstud env-malli, SQLite backup'i ning
  install/update/verify skripte. Dropleti paigaldus, avalik HTTPS ja
  `deploy/verify.sh` on kontrollitud; Atomi production polling on TODO.

### Dropleti paigaldus ja production-kontroll

- [ ] Igal kasutataval arvutil on oma SSH võtmepaar; privaatvõtmeid ei jagata
  ega lisata reposse.
- [x] Nikita sai õppejõult dropleti ligipääsuandmed ja kontrollis võtmega
  SSH login'it 16.10.26.
- [x] Repo on `/opt/smart-solutions-lab2/app`; production-sõltuvused ja
  systemd teenus on paigaldatud, teenus käivitati käsitsi 16.10.26.
- [x] Env-fail on `root:root 0600`, täidetud ning placeholder'iteta;
  veebiparool ja Atomi võti on eraldi paroolihalduris.
- [x] SQLite fail asub püsirajal; Gunicorn kuulas ainult `127.0.0.1:5001`,
  `/health` vastas HTTP 200 ning autentimata `/` HTTP 401 (16.10.26).
- [x] `smart-solutions-lab2` ja Caddy on `enabled` ning `active` (20.10.26).
- [ ] Teenuste käivitumine pärast kogu dropleti reboot'i on kontrollitud.
- [x] SSH: `pubkeyauthentication yes`, `passwordauthentication no`,
  `kbdinteractiveauthentication no`; sõltumatu võtmega login pärast UFW
  aktiveerimist kontrollitud. Ubuntu uuenduses paigaldati 11 paketi uuendused
  (20.10.26).
- [x] UFW on `active`, default `deny incoming`, sissetulevad TCP 22/80/443
  lubatud (20.10.26).
- [x] `https://narva2.roboarena.org` töötab kehtiva TLS-iga; väline Maci curl
  sai `/health` päringule HTTP/2 200 (20.10.26).
- [x] Kasutajalehe autentimine ja UI on Safari Macis ning Chrome telefonis
  5G kaudu kontrollitud (20.10.26).
- [x] Päris serveris loodud `letter A` aegus: `expired`, `ttl_expired`;
  SQLite kirje säilis teenuse restardi järel (20.10.26).
- [x] `deploy/verify.sh`: `12 PASS, 0 FAIL, 0 SKIP` (20.10.26).
- [x] SQLite backup (24 576 baiti, `root:root 0600`) taastati eraldi testbaasi:
  `integrity_check` oli `ok` ja töö kirje taastati (20.10.26).
- [ ] Atom pollib production-hostilt töid ning autentimine toimib seadmesse
  salvestatud võtmega, mida repos ei ole.
- [ ] Dropleti taastamine märkmete järgi on läbi proovitud ja tulemus dokumenteeritud.

### Vajab päris riistvara või laborikatset

- [ ] `letter` töö jõuab postkontorist Atomi ja Labori 1 kohaliku kanali kaudu
  jaama ning käivitab lubatud MG400 täitmisraja.
- [ ] Teine whitelist'i töö on riistvaraga integreeritud ja kontrollitud.
- [ ] 30 sõnumit on mõõdetud kiire polling-intervalliga failis
  `docs/latency_poll_fast.csv`.
- [ ] 30 sõnumit on mõõdetud aeglase polling-intervalliga failis
  `docs/latency_poll_slow.csv`.
- [ ] Mõlema 30 katse seeria keskmine ja maksimum on arvutatud pärisandmetest.
- [ ] Internetiühendus katkestatakse töö ajal kontrollitud katses ning
  kontrollitakse, et station lõpetab juba vastu võetud tervikliku töö lokaalselt,
  Atom säilitab tulemuse ja saadab selle pärast ühenduse taastumist.
- [ ] Katkestuskatse on tehtud ohutult kolm korda enne internetist tööde vastuvõttu.
- [ ] Atom `last_seen`/offline kuvamine on päris katkestusega kontrollitud.
- [ ] Laua UHD-kaamera näitab kogu tööala, ruudustikku servast servani ja robotit.
- [ ] Tööriistakaamera näitab otsikut ning selle all olevat detaili.
- [ ] Mõlemad kaamerapildid on jaama lehel ja sama autentimise taga.
- [ ] Kaameraid ei saa postkontori kaudu ega internetist otse avada; Lab 2
  postkontor ei vahenda kaameravooge.
- [ ] Mõlema kaamera lahutus, viide, FPS ja ribalaius on mõõdetud failis
  `docs/camera_metrics.csv`.
- [ ] Roboti juhtimislatentsus on mõõdetud ilma kaamerata, ühe kaameraga ja kahe
  kaameraga failis `docs/control_latency_cameras.csv`.
- [ ] Rõhuanduri kalibratsioonikonstandid on Andmehõive Lab 2 tulemustest
  lisatud Atomi seadetele.
- [ ] Atomi rõhutest näitab korraga toorest ADC lugemit, pinget ja kPa väärtust.
- [ ] Atomi lehe uued väljad, salvestamine ja testinupp on päris seadmel kontrollitud.
  23.10.26 bench'is avati ainult read-only leht ja prooviti G5 ADC lugemist
  ilma andurita. Nikita kontrollis hiljem kõigi kolme BENCH POST-route'i
  HTTP 423 vastuseid; salvestamise normaalrežiim ja NVS-i säilimine on lahti.
- [ ] Ohutuskokkulepe on kõigil meeskonnaliikmetel päriselt läbi loetud ja
  kinnitused on lisatud `docs/safety.md` faili.
- [ ] Enne tellimist on BOM laboris üle kontrollitud ja tellimus on valmis 16.10.26.
- [ ] Repo ja arenduspäevik on täidetud ning esitamisel on loodud tag
  `smart-solutions-lab2`.

### Enne päris riistvara testi

- [ ] BOM-i füüsiline saadavus on laboris kontrollitud.
- [x] Lab 2 püsivara on AtomS3R-i PlatformIO kaudu üles laaditud 12.10.26.
- [x] Asendus-AtomS3R: isoleeritud BENCH_MODE=1 upload, LCD, kaitstud AP ja
  Safari read-only leht kontrollitud 23.10.26; vaata sama kuupäeva päevikukannet.
- [x] Nikita Teterev: `POST /settings`, `POST /test/post-office` ja
  `POST /pressure/settings` tagastasid päris BENCH Wi-Fi kaudu HTTP 423
  `bench_read_only` (23.10.26).
- [x] AtomS3R ja lokaalne postkontor on koos kontrollitud ilma MG400
  täitmiseta.
- [x] Dropleti ligipääsuandmed on õppejõult saadud ja Nikita võtmega SSH
  login on kontrollitud 16.10.26; avalik HTTPS kontrollitud 20.10.26.
- [x] XIAO olemasolu ja USB Serial diagnostiline JPEG on 3D Printing Lab 2-s
  kinnitatud 23.10.26; Smart Solutions Wi-Fi püsivara kontroll jääb eraldi.
- [ ] Identifitseeritud Verbatim AWC-03 (49580) lõplik paigaldus ja sobivus
  kogu laua üldvaateks on kontrollitud.
- [ ] Andmehõive Lab 2 päris rõhukalibratsioon on kättesaadav.
- [ ] 3D Printing Lab 2 laua- ja tööriistakaamera kinnitused on valmis ning
  füüsiliselt kontrollitud.

## Kavandatud tulemused

| Tulemus | Väärtus või olek |
| :--- | :--- |
| Dropleti host, piirkond ja suurus | `narva2.roboarena.org`; piirkond ja suurus TODO |
| Avalikud pordid ja põhjendus | 20.10.26 UFW `active`, TCP 22 (SSH), 80/443 (Caddy), default `deny incoming`; Gunicorn ainult loopback |
| HTTPS URL | `https://narva2.roboarena.org`; väline `/health` HTTP/2 200 ja korrektne TLS (20.10.26) |
| Kiire polling-intervall | TODO — real test setting required |
| Kiire pollingu latentsus, keskmine / max | TODO — real measurement required |
| Aeglane polling-intervall | TODO — real test setting required |
| Aeglase pollingu latentsus, keskmine / max | TODO — real measurement required |
| Katkestuse tegelik tulemus | TODO — real laboratory test required |
| Atomi offline-piir | TODO — tested poll interval required |
| Lauakaamera lahutus / viide / FPS / ribalaius | TODO — real measurement required |
| Tööriistakaamera lahutus / viide / FPS / ribalaius | TODO — real measurement required |
| Juhtimislatentsus 0 / 1 / 2 kaameraga | TODO — real measurement required |
| Rõhu kalibratsioonikonstandid | TODO — Data Acquisition Lab 2 result required |
| Riistvara olemasolu ja puuduvad osad | TODO — physical inventory required |

## Kohalik postkontor

Kood asub kaustas `server/`. Valitud on Python, Flask ja standardteegi SQLite.
SQLite hoiab töö ID-d, claim-olekut, terminaltulemust ja Atomi `last_seen`
väärtust ka serveri taaskäivituse järel. See annab idempotentsusele püsiva
aluse ilma eraldi production-andmebaasi halduseta.

Tarkvaralised vaikeväärtused on arenduseks, mitte labori lõplikud otsused:

- töö TTL: 60 s, seadistatav `JOB_TTL_SECONDS` abil;
- maksimaalne lubatud TTL: 3600 s, seadistatav `JOB_MAX_TTL_SECONDS` abil;
- stale/offline piirid: 10 s / 30 s, seadistatavad `ATOM_STALE_SECONDS` ja
  `ATOM_OFFLINE_SECONDS` abil;
- final TTL ja online/stale/offline piirid: TODO — real test/decision required.

### Korratav kohalik käivitus

Käivita käsud kaustas `smart-solutions/lab2/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r server/requirements-dev.txt
export ATOM_API_KEY=local-dev-only-atom-key
export POST_OFFICE_USER=dev-user
export POST_OFFICE_PASSWORD=local-dev-only-user-password
python -m server.app
```

Need väärtused on ainult lokaalse arenduse näited, mitte production-saladused.
Ilma `ATOM_API_KEY` või `POST_OFFICE_PASSWORD` muutujata server ei käivitu.
Kasutajaleht avaneb aadressil `http://127.0.0.1:5001/` ja küsib HTTP Basic
kasutajat/parooli. HTTP on lubatud ainult lokaalseks arenduseks.

Füüsilise Atomi samas LAN-is testimiseks tuleb development-server eraldi ja
teadlikult LAN-ile bind'ida:

```bash
export POST_OFFICE_BIND=0.0.0.0  # development LAN test only
python -m server.app
```

Vaikeväärtus jääb `127.0.0.1`. Seda opt-in'i ei kasutata production'is:
systemd/Gunicorn kuulab endiselt ainult `127.0.0.1:5001` ning avalik HTTPS piir
on Caddy.

Loo teises terminalis testtöö:

```bash
curl -u dev-user:local-dev-only-user-password \
  -H 'Content-Type: application/json' \
  -d '{"job":"letter","arg":{"letter":"A"},"ttl_seconds":60}' \
  http://127.0.0.1:5001/api/jobs
```

Polli ja simuleeri Atom → lokaalne station → tulemus piir ilma MG400-ta:

```bash
export ATOM_API_KEY=local-dev-only-atom-key
python -m server.tools.mock_atom --once --outcome done
```

Seejärel vaata tulemust kasutajalehelt või `GET /api/jobs/<id>` kaudu.
Kunstliku pollingu viite jaoks kasuta näiteks `--poll-delay 2`. Keeldumise
simulatsiooniks kasuta `--outcome refused`.

## Kohalik station-adapter

Kood asub kaustas `src/`. `letter` säilitab Lab 1 USB sõnumi väljad;
`pick_place` saadab ainult `job`, `routine`, `session`, `seq`, `atom_sent_ms`
ja `job_id`. Adapter tagastab firmware'ile `post_office_result` JSON rea.
Adapter ei kopeeri Lab 1 Flask UI-d ega motion-koodi: letter mock kontrollib
toetatud tähte Lab 1 `config/letters.json` failist ning pick-place mock ei ava
võrku ega kasuta MG400 või pumpa.

Reaalset porti kasutava software-only mock adapteri näidiskäsk:

```bash
python -m src.station_adapter --port COM4 --baud 115200 --allow-mock-jobs
```

Ilma `--allow-mock-jobs` liputa on lokaalne täitmine keelatud. Ka lipuga
kasutatakse ainult mock executor'it; MG400 klienti ei impordita ega ühendata.
Serial-porti tohib omada ainult üks programm. Porti kadumisel proovib adapter
uuesti ühenduda, vigane üksikrida ei lõpeta protsessi.

Täielik lokaalne tarkvarademo loob ajutise Flask/SQLite postkontori, läbib
eraldi `letter` ja `pick_place` töö mock Atomina, saadab firmware-formaadis
read station-adapterile ning tagastab mõlema sama ID terminaltulemuse serverisse:

```bash
python -m src.e2e_demo
```

Demo kasutab ainult ajutisi placeholder-saladusi ja kustutatavaid SQLite
faile. See ei ava serial-porti, võrguühendust ega MG400 klienti.

## Kohalik kaameraleht

Kaamerakiht asub `src/cameras/` ja eraldi kohalik Flask-rakendus failis
`src/camera_server.py`. Riistvarata demo käivitatakse Lab 2 juurkaustast:

```bash
python -m src.camera_server --mock
```

Leht on aadressil `http://127.0.0.1:5002/`. See näitab kõrvuti Table camera
ja Tool camera mock-pilte, allika olekut, resolutsiooni ning tarkvaralisi
FPS/ribalaiuse loendureid. Demo ei pöördu dropleti, MG400 ega päris kaamera
poole ja ei ava brauserit automaatselt. See on eraldi autentimiseta leht
localhost-bind'iga; olemasoleva station'i lehega ühendamine, kaitstud
LAN-ligipääs, päris USB/XIAO seaded ja mõõtmised on TODO; vt `docs/cameras.md`.

Testid ja import-/süntaksikontroll:

```bash
pytest -q
python -m compileall -q server src tests
```

Kogu software-only regressiooni (Python, E2E ning mõlema PlatformIO projekti
native-testid ja buildid) saab käivitada Lab 2 kaustast või mujalt ühe käsuga:

```bash
smart-solutions/lab2/check.sh
```

Skript ei laadi püsivara seadmesse, ei ava serial-porti, ei ühendu MG400,
kaamerate ega dropletiga ning ei käivita SSH/deployment toiminguid.

## Production-paigalduse alus

Korduvkasutatavad production-mallid ja samm-sammuline värske Ubuntu dropleti
paigaldus-, SSH/tulemüüri-, uuendus-, backup-, taastamis- ning kontrolljuhend
on failis [`deploy/README.md`](deploy/README.md). Kavandatud avalik ahel on:

```text
Internet -> HTTPS Caddy -> 127.0.0.1:5001 Gunicorn/Flask -> SQLite
AtomS3  -> outbound HTTPS polling -> sama Caddy host
```

Gunicorn ei kuula avalikul liidesel ning SQLite, env ja backup'id asuvad Git
checkout'ist väljaspool. Dropletile ei lisata station'i, MG400 ega kaamerate
route'e, proxy't, VPN-i või tunnelit. Nikita kontrollis 16.10.26 esmast
paigaldust ning 20.10.26 avalikku HTTPS-i, SSH autentimisseadeid, UFW-d,
SQLite backup'i ja taastamist eraldi testbaasi. Täielik taastamine puhtale
hostile, kogu dropleti reboot ning Atomi production polling jäävad TODO-ks.

### Arenduspäevik

**KAARDISTA ISE — päevik.** Üks sissekanne iga töösessiooni kohta, kirjutatud
nii, et inimene, kes kohal ei olnud, saab aru. Sissekandeid lisatakse, mitte
ei muudeta.

**PP.KK.AA — kes olid kohal**

* Tegime:
* Juhtus (numbrid):
* Otsustasime, ja miks:
* Lahti järgmiseks korraks:

**11.10.26 — Nikita**

* Tegime: Valmistasin ette ja viisin software-foundation'i tasemele Flaski +
  SQLite'i postkontori, autentitud Atomi polling/result API, TTL/expiry ja
  idempotentsuse, AtomS3R PlatformIO polling-püsivara aluse, station'i
  job-adapteri ja kaamerakihi, XIAO ESP32S3 Sense PlatformIO kaamerapüsivara
  aluse ning Gunicorni, systemd ja Caddy näidetega dropleti paigaldusaluse.
  Lisasin regressioonitestid ja software-only E2E kontrolli. Füüsilist
  riistvara ega päris dropletit selles töös ei kasutatud.
* Juhtus (numbrid): Python: `63 passed`; deployment-testid: `7/7`; Atomi
  native-testid: `12/12`; XIAO native-testid: `6/6`; mõlemad PlatformIO buildid:
  `SUCCESS`; software E2E: `server_status=done`, `hardware_used=false`.
* Otsustasime, ja miks: Atom algatab dropleti suunas väljamineva pollingu ning
  droplet ei loo otseühendust station'i ega MG400-ga. Internetist võetakse vastu
  ainult kõrgtaseme töid, kaamerad jäävad lokaalsesse võrku ning direct
  control/VPN kuulub Lab 3-sse. Atom ja XIAO kasutavad kohustuslikult
  PlatformIO-d, saladused jäävad repost välja ning ebaselge või korduv töö
  lõpetatakse fail-safe keeldumisega, mitte robotiliikumise kordamisega.
* Lahti järgmiseks korraks: AtomS3R-i päris upload ja lokaalne polling-katse,
  päris droplet, MG400 integratsioon, teine kõrgtaseme töö, füüsilised kaamerad
  ning Andmehõive Lab 2 rõhukalibratsioon.

**12.10.26 — Nikita**

* Tegime: Viisin Lab 2 README Lab 1-ga samasse struktuuri ja stiili ning
  kontrollisin kõigi kolme kursuse Lab 2 README vormingute kooskõla. Tegin Smart
  Solutions pre-hardware auditi: kontrollisin faile `docs/server_api.md`,
  `docs/atom_page.md`, `docs/safety.md`, `docs/bom.md`, mõõtmiste CSV-malle ja
  juurfaili `AGENTS.md`. Lisasin süsteemiarhitektuuri failid
  `docs/system.drawio` ja `docs/system.svg`, dokumenteerisin Andmehõive ja 3D
  Printing sõltuvused ning märkisin puuduva teise kõrgtaseme töö selgeks
  blocker'iks.
* Juhtus (numbrid): `git diff --check` läbis; `4` measurement CSV-malli
  sisaldavad ainult päiseid; lubatud kõrgtaseme robotitöid on `1` (`letter`);
  teine töö on `TODO`; loodud süsteemiskeemi faile on `2` (`system.drawio` ja
  `system.svg`). Need arvud on dokumentatsiooni- ja tarkvarafaktid, mitte
  füüsilised mõõtmistulemused.
* Otsustasime, ja miks: Lab 2 dokumentatsioon järgib Lab 1 vormingut ning
  füüsilised tulemused jäävad TODO-ks kuni päris mõõtmiseni. Rõhukalibratsioon
  tuleb Andmehõive Lab 2-st ning kaamerate füüsiline kinnitus ja FOV sõltuvad 3D
  Printing Lab 2-st. `pick_place` ei ole teostatud töö enne tegelikku lubamist
  ja kontrolli; tag luuakse alles pärast täielikku lõppkontrolli.
* Lahti järgmiseks korraks: ühendada päris AtomS3R, laadida Lab 2 püsivara
  PlatformIO-ga, kontrollida serial boot'i ja Atomi web/settings lehte, testida
  lokaalset postkontori pollingut ning hiljem teostada ja kontrollida teine
  kõrgtaseme töö.

**12.10.26 — Nikita (AtomS3R hardware test)**

* Tegime: Ehitasin Lab 2 `atoms3r` environment'i, tuvastasin ühendatud seadme
  PlatformIO abil ning laadisin püsivara füüsilisse AtomS3R-i. Vaatasin serial
  logi 115200 baudiga, käivitasin lokaalse Flask post-office'i development-only
  saladustega ja kontrollisin `/health` kättesaadavust nii loopback- kui ka
  sülearvuti LAN-aadressil. Peatasin katse enne Atomile Wi-Fi või API võtme
  sisestamist, sest server ei olnud LAN-ist kättesaadav.
* Juhtus (numbrid): Port oli `/dev/cu.usbmodem101` (USB VID:PID `303A:1001`).
  `pio run -e atoms3r` oli `SUCCESS` ajaga 4,36 s; RAM 50 168 / 327 680 baiti
  (15,3%) ja flash 1 122 541 / 3 342 336 baiti (33,6%). Upload oli `SUCCESS`
  ajaga 22,22 s ning kirjutatud image'i hash kontrolliti. Serialis ei nähtud
  panic'ut ega boot loop'i ja firmware jõudis pollingutsüklisse, kuid logis
  kordus `[E][Preferences.cpp] ... activeId NOT_FOUND` ligikaudu iga 9 ms ning
  `POST poll_failed` ligikaudu kord sekundis; seetõttu ei loetud boot-kontrolli
  puhtalt läbituks. Sülearvuti LAN IP oli `192.168.50.249`. Serveri
  `http://127.0.0.1:5001/health` vastas HTTP 200, kuid
  `http://192.168.50.249:5001/health` ei olnud kättesaadav.
* Otsustasime, ja miks: Praegust production'i localhost-piiri ei muudeta
  varjatult. Füüsilise Atomi lokaalseks arendustestiks on vaja eraldi selgelt
  lubatavat development-bind'i LAN-liidesele, säilitades production'i
  `127.0.0.1` vaikeväärtuse. Enne jätkamist tuleb eemaldada ka puuduva
  `activeId` võtme tekitatud NVS log storm. Web/settings lehte, server-test'i,
  pollingut/`last_seen` väärtust, persistence'it ega Wi-Fi reconnect'i selles
  katses läbituks ei märgitud.
* Lahti järgmiseks korraks: Lisada ja dokumenteerida minimaalne development-only
  LAN-bind, parandada puuduva `activeId` lugemine, korrata puhast serial boot'i,
  avada Atomi setup-AP/web settings, kasutada ainult lokaalset development
  võtit, testida `/health`, päris pollingut ja `last_seen` väärtust ning alles
  seejärel teha reboot persistence ja Wi-Fi reconnect kontrollid. MG400,
  droplet, XIAO, kaamerad ja ametlikud latentsusmõõtmised jäävad sellest katsest
  välja.

**12.10.26 — Nikita (AtomS3R hardware test, jätk)**

* Tegime: Leidsin LAN blocker'i põhjuse funktsioonist `server.app.main`, kus
  development-server kasutas alati `127.0.0.1`. Lisasin piiratud
  `POST_OFFICE_BIND` opt-in'i: default on endiselt loopback ning `0.0.0.0` on
  lubatud ainult teadlikuks development LAN testiks. Production'i Gunicorn ja
  Caddy jäid loopback-piirile. Leidsin NVS flood'i põhjuse funktsioonist
  `PersistentState::activeJobId()`: värskel seadmel normaalset puuduvat
  `activeId` võtit loeti igas võrgutsüklis `getString()` abil. Lisasin enne
  lugemist `isKey()` kontrolli, testisin tarkvara, ehitasin ja laadisin firmware
  uuesti ning kordasin serial- ja LAN-kontrolli.
* Juhtus (numbrid): Python suite: `66 passed`; Atom native-testid: `13/13`;
  Atom build: `SUCCESS` 7,82 s, RAM 50 168 / 327 680 baiti (15,3%), flash
  1 123 057 / 3 342 336 baiti (33,6%). Re-upload pordile
  `/dev/cu.usbmodem101` oli `SUCCESS` 16,25 s ja image'i hash kontrolliti.
  Mitmesekundilises serial-vaatluses ei olnud panic'ut ega reboot loop'i ning
  `activeId NOT_FOUND` log storm kadus täielikult; seadistamata ühenduse
  `POST poll_failed` jäi ligikaudu 1000 ms intervallile. Sülearvuti tegelik LAN
  IP oli endiselt `192.168.50.249`. Explicit `POST_OFFICE_BIND=0.0.0.0` korral
  vastasid nii `http://127.0.0.1:5001/health` kui ka
  `http://192.168.50.249:5001/health` HTTP 200.
* Otsustasime, ja miks: Kaht algset parandust ei laiendatud arhitektuuri
  refactor'iks ega production'i avalikuks bind'iks. Atom ei ilmunud praeguse
  LAN-i ARP-tabelisse ning `Lab2AtomSetup` AP-d ei leitud ka pärast normaalset
  restarti. Tõenäoline põhjus on varasem `wifi` NVS SSID, mille olemasolul
  firmware jääb STA connecting olekusse ega tee setup-AP fallback'i. Salvestatud
  Wi-Fi andmeid ei loetud ega kustutatud ilma eraldi kinnitamiseta. Seetõttu ei
  märgitud settings-lehte, server-test'i, autentitud pollingut, `last_seen`
  väärtust, persistence'it ega reconnect'i läbituks.
* Lahti järgmiseks korraks: Kinnitada turvaline Wi-Fi taastamisviis — kasutada
  teadaolevat salvestatud võrku, kustutada kasutaja loal ainult vana Wi-Fi NVS
  seadistus või lisada eraldi kontrollitud setup-AP fallback. Seejärel avada
  settings-leht, sisestada lokaalne development URL ja võti, kontrollida
  `/health`, autentitud pollingut ja tegelikku intervalli, `last_seen` väärtust,
  reboot persistence'it ning Wi-Fi reconnect'i. MG400, droplet, XIAO, kaamerad
  ja ametlik mid-job disconnect test jäävad endiselt välja.

**13.10.26 — Nikita (AtomS3R Wi-Fi reconnect test)**

* Tegime: Lisasin olemasolevale setup-AP fallback'ile piiratud AP+STA recovery:
  seadistus-AP jääb võrgu taastumise ootamise ajal aktiivseks, salvestatud
  STA-seadistust proovitakse perioodiliselt uuesti ning eduka ühenduse järel
  peatatakse retry ja setup-AP. Ehitasin ja laadisin püsivara päris AtomS3R-i,
  kontrollisin autentitud lokaalset pollingut ja reboot-järgset persistence'it
  ning tegin reaalse 2,4 GHz katkestus- ja taastamiskatse ilma Atomi reboot'ita.
* Juhtus (numbrid): Native-testid läbisid `21/21`; Atom build oli `SUCCESS`,
  RAM 50 176 / 327 680 baiti (15,3%) ja flash 1 127 693 / 3 342 336 baiti
  (33,7%); upload pordile `/dev/cu.usbmodem1101` oli `SUCCESS`. Enne katkestust
  vastas `POST /api/atom/poll` HTTP 200 ligikaudu `1000 ms` intervalliga ning
  `last_seen` uuenes. 2,4 GHz kadumisel lõppes polling, serial näitas esmalt
  reason `51` (`INVALID_FTE`) ja seejärel reason `201` (`NO_AP_FOUND`);
  `15 s` järel oli lõppolek `WL_NO_SSID_AVAIL` ja käivitus `Lab2AtomSetup`.
  Recovery retry intervall oli `20 s` ning ühe STA-katse timeout `15 s`.
  Võrgu taastumise järel assotsieerus Atom järgmisel retry-katsel, sai uuesti
  aadressi `192.168.50.19` ja polling jätkus automaatselt HTTP 200-ga;
  `last_seen` uuenes väärtuselt `2026-10-12T22:16:20.330494Z` väärtusele
  `2026-10-12T22:16:24.333387Z`. Käsitsi raadio sisselülitamise hetke ei
  timestamp'itud Atomiga samast kellast, seega täpset taastumisaega sekundites
  ei esitata. Panic'ut, reboot loop'i ega NVS log storm'i ei olnud.
* Otsustasime, ja miks: Fallback kasutab AP+STA režiimi, et setup-leht jääks
  kättesaadavaks, kuid retry ei muutuks tight loop'iks. SSID-d, Wi-Fi parooli,
  serveri URL-i, Atomi võtit ega pollinguseadeid katkestuse ajal ei kustutata.
  Edukas STA taastumine lõpetab recovery-oleku ja tavapolling jätkub ilma
  reboot'ita. Development-võtit ega muid saladusi päevikusse ei lisata.
* Lahti järgmiseks korraks: Ametlik mid-job katkestuskriteerium koos aktiivse
  töö ja saatmata tulemuse NVS retry-ga, production droplet/HTTPS, päris MG400,
  kaamerad, latentsusmõõtmised ja Andmehõive rõhukalibratsioon jäävad TODO-ks.

**16.10.2026 — Nikita Teterev**

* Tegime: Sain õppejõult serveri ligipääsuandmed ja logisin SSH võtmega
  DigitalOcean Dropletisse. Kloonisin repo kataloogi
  `/opt/smart-solutions-lab2/app`, lõin Python virtualenv'i ja paigaldasin
  production-sõltuvused. Käivitasin `deploy/install.sh`, mis lõi systemd
  teenuse `smart-solutions-lab2`. Täitsin kaitstud
  `/etc/smart-solutions-lab2/env` faili, kontrollisin nõutud väärtuste
  olemasolu ja placeholder'ite puudumist ning käivitasin teenuse käsitsi.
  Kontrollisin teenuse olekut, kuulamisaadressi, SQLite faili ning kohalikke
  HTTP vastuseid.
* Juhtus (numbrid): Ubuntu `24.04.5 LTS`, Python `3.12.3`, Flask `3.1.3` ja
  Gunicorn `23.0.0`. Install läbis; teenus oli `active (running)`, Gunicorn
  kuulas ainult `127.0.0.1:5001` ning töötasid `2` worker'it ja `1` master.
  Env-faili omanik oli `root:root`, õigused `0600`. Andmebaas
  `/var/lib/smart-solutions-lab2/post-office.sqlite3` oli `24 KB`, omanik
  `smart-solutions-lab2`, õigused `0600`. `GET /health` vastas HTTP `200` ja
  JSON-iga `{"ok":true,"service":"lab2-post-office"}`. Autentimata `GET /`
  vastas HTTP `401` päisega
  `WWW-Authenticate: Basic realm="Lab 2 post-office"`. Systemd autostart oli
  kontrolli ajal `disabled`, UFW `inactive`. Teenuse hilisemat peatamist
  ei ole kinnitatud.
* Otsustasime, ja miks: Hoidsin veebiparooli ja Atomi API-võtme eraldi
  paroolihalduris; saladusi ega env-faili sisu reposse ei lisanud. Jätsin
  Gunicorni loopback-liidesele ja SQLite faili lähtekoodipuust välja.
  Märkisin tehtuks esmase paigalduse, health'i ja autentimata ligipääsu
  keeldumise kontrolli. HTTP 401 ei kinnita õige parooliga login'it ning
  loopback HTTP ei kinnita avalikku HTTPS-i ega Atomi production-pollingut.
* Lahti järgmiseks korraks: Kontrollida login'it õige veebiparooliga ning
  tööde loomist ja salvestamist päris HTTP kaudu. Seadistada ja kontrollida
  Caddy/avalik HTTPS, UFW ning SSH hardening koos password-login'i
  keelamisega; läbida täielik `deploy/verify.sh`, backup ja taastamine.
  Lubada ja kontrollida teenuse autostart. Teha telefoni mobiilsidekatse ja
  AtomS3R production HTTPS polling. MG400, päris kaamerad ja latency
  mõõtmised jäävad TODO-ks.

**20.10.2026 — Nikita Teterev**

* Tegime: Uuendasin Ubuntu 24.04.5 LTS serverit, kontrollisin SSH
  autentimisseadeid ja sõltumatut võtmega login'it pärast UFW aktiveerimist.
  Lõin ja aktiveerisin swap-faili ning lisasin kirje `/etc/fstab` faili.
  Seadistasin Caddy avaliku postkontori jaoks domeenil `narva2.roboarena.org`.
  Kontrollisin HTTPS-i välise curl'iga Macist ning autentimist ja UI-d Safari
  kaudu Macis ja Chrome'iga telefonis 5G kaudu. Lõin töö `letter A`,
  kontrollisin aegumist ja SQLite kirje säilimist teenuse restardi järel.
  Tegin SQLite backup'i, taastasin selle eraldi testbaasi ja käivitasin
  `deploy/verify.sh`.
* Juhtus (numbrid): Ubuntu `24.04.5 LTS`, uuendatud `11` paketti.
  SSH effective config: `pubkeyauthentication yes`, `passwordauthentication no`,
  `kbdinteractiveauthentication no`. UFW `active`, sissetulevad TCP
  `22`, `80`, `443` lubatud, default `deny incoming`; uus sõltumatu SSH login
  õnnestus. Aktiivne swap-fail `1 GiB`, kirje `/etc/fstab` failis.
  Caddy `2.11.7`, `active`, `enabled`; `smart-solutions-lab2` samuti `active`
  ja `enabled`. Väline `/health` curl: `HTTP/2 200`, korrektne TLS.
  Mõlema brauseri autentimine ja UI töötasid. Töö `letter A` sai oleku
  `expired`, põhjus `ttl_expired`; kirje säilis teenuse restardi järel.
  SQLite backup: `24576` baiti, `root:root`, mode `600`. Eraldi testbaasis
  `integrity_check: ok` ja töö kirje taastati. `deploy/verify.sh`:
  `12 PASS, 0 FAIL, 0 SKIP`. Atom oli avalikus serveris offline.
* Otsustasime, ja miks: Eristan teenuse restarti kogu dropleti reboot'ist:
  kirje püsimine on kontrollitud teenuse restardiga, kuid hosti reboot ja
  teenuste käivitumine pärast seda pole kontrollitud. Taastasin backup'i
  eraldi SQLite baasi, et kontrollida terviklikkust ja töö kirjet toimivat
  baasi üle kirjutamata. Aegunud töö kinnitab TTL-rada; offline Atomiga ei
  kinnita see production pollingut ega roboti täitmisrada.
* Lahti järgmiseks korraks: Kontrollida kogu dropleti reboot'i ja teenuste
  automaatset taastumist, Atomi production HTTPS pollingut ning füüsilist
  Lab 2 end-to-end ahelat. Täielik taastamine puhtale hostile, MG400
  integratsioon, päris kaamerad, rõhuandur/Andmehõive kalibratsioon,
  latency/metrics, ametlik mid-job katkestuskatse ja ohutuskinnitused jäävad
  lahti.

**20.10.2026 — Nikita Teterev (production TLS ettevalmistus, jätk)**

* Tegime: Kontrollisin Macis `https://narva2.roboarena.org` TLS-ahelat
  OpenSSL-iga. Laadisin Let's Encrypti ametlikult veebilehelt ISRG Root X2
  juursertifikaadi ja kontrollisin SHA-256 fingerprint'i. Lõin lokaalse
  `firmware/include/post_office_ca_private.h` faili ning kontrollisin
  `git check-ignore` abil, et see jääb Git'ist välja. Ehitasin `atoms3r`
  püsivara, kontrollisin PEM-sertifikaadi olemasolu `firmware.bin` failis
  ning käivitasin `bash smart-solutions/lab2/check.sh`.
* Juhtus (numbrid): Kontrollitud TLS-ahelas olid Let's Encrypt YE2,
  Root YE ja ISRG Root X2. OpenSSL: `Verify return code: 0 (ok)`.
  ISRG Root X2 SHA-256 fingerprint:
  `69729b8e15a86efc177a57afb7171dfc64add28c2fca8cf1507e34453ccb1470`.
  `pio run -e atoms3r`: `SUCCESS`, RAM `15,4%`, flash `34,5%`, aeg `20,98 s`.
  Eraldi binaarikontroll leidis ISRG Root X2 PEM-sertifikaadi.
  Regressiooniskript lõpetas teatega
  `All software-only regression checks passed.`
* Otsustasime, ja miks: Hoian CA header'i ja build-artifact'id lokaalselt;
  dokumentatsiooni läheb sertifikaadi nimi ja fingerprint, mitte PEM ega
  binaar. Maci TLS-kontroll ja CA olemasolu build'is annavad aluse järgmisele
  seadmekatsele, kuid ei kinnita Atomi production HTTPS ühendust.
* Lahti järgmiseks korraks: Taastada projektipüsivara päris AtomS3R-i,
  kontrollida seadeid ja production HTTPS pollingut ning `last_seen`
  uuenemist. Päris MG400/jaama integratsioon, rõhuanduri ja kaamerate katsed,
  latency ning ametlik mid-job katkestuskatse jäävad TODO-ks.

**20.10.2026 — Nikita Teterev (production UI uuendus, jätk)**

* Tegime: Uuendasin `narva2.roboarena.org` postkontorit `deploy/update.sh`
  kaudu commit'ilt `7571582` commit'ile
  `7d374915f48e9f4cc7e4357e3a2c82df6191f231`. Enne uuendust loodi SQLite
  backup-failid ning Git fast-forward läbis. Kontrollisin pärast teenuse
  restarti käivitumist, kordasin `deploy/verify.sh` kontrolli ja vaatasin uut
  liidest Safari kaudu Macis ning Chrome'iga Androidis 5G kaudu.
* Juhtus (numbrid): Kohe pärast `systemctl restart` käsku sai kontroll
  `127.0.0.1:5001` aadressilt connection refused ja avalikult HTTPS-ilt `502`.
  Lühikese aja järel hakkas Gunicorn kuulama `127.0.0.1:5001`; täpset aega
  ei mõõdetud. Korduv `deploy/verify.sh`: `12 PASS, 0 FAIL`. Dropleti Git
  tööpuu oli puhas. Varasem `letter A` säilis SQLite'is olekuga `expired`,
  põhjusega `ttl_expired`. Telefonis töötasid letter/pick-place väljade
  ümberlülitus ja tööde mobiilikaardid.
* Otsustasime, ja miks: Esimene kontroll ebaõnnestus Gunicorni käivitumise
  ajal; edukas korduskontroll järgnes valmisolekule. `systemctl restart`
  lõpetamine ei kinnita veel avatud HTTP porti. Lisasime repos `update.sh`
  skripti enne muutmata `verify.sh` käivitamist piiratud lokaalse `/health`
  ootamise: kuni 15 päringut, igal päringul 1 s timeout ja katsete vahel 1 s
  paus. Ainult HTTP 200 lubab jätkata, limiidi ületamine lõpetab uuenduse
  veaga. Readiness-parandus on praegu ainult lokaalselt testitud.
* Lahti järgmiseks korraks: Kontrollida parandatud uuendusskripti järgmise
  lubatud production-uuenduse ajal. Atomi production HTTPS polling, füüsiline
  MG400/jaama ahel, rõhuandur ja päris kaamerad, latency/metrics ning kogu
  dropleti reboot jäävad eraldi kontrollideks.

**23.10.2026 — Nikita Teterev (AtomS3R BENCH-katse)**

* Tegime: Asendus-AtomS3R-i Lab 1 täis-flash backup loodi Macis väljaspool
  Git'i; kontrolliti suurust ja SHA-256 ning pärast backup'i töötas endiselt
  Lab 1 ekraan. Laadisime ühe kontrollitud `atoms3r` BENCH_MODE=1 püsivara.
  MacBook ühines kaitstud `Lab2AtomBench` AP-ga ja Safari avas
  `http://192.168.4.1` read-only eestikeelse liidese. Proovisime kohalikku
  G5 ADC testi ilma andurita. USB Serial Monitor ühendas kiirusel 115200;
  Reset'i vajutamisel näitas macOS katkestust ja taasühendumist ning LCD
  naasis `BENCH` / `execution disabled` kuvale. Atom oli kogu katse ajal
  välisest riistvarast lahti ühendatud.
* Juhtus (numbrid): ESP32-S3-PICO-1, flash `8 MB`; backup `8 388 608` baiti,
  SHA-256 kontrollitud, backup'i sisu ei avaldatud. BENCH puhas build
  `SUCCESS`, native `43/43`, Python `480 passed`. Upload `SUCCESS`, esptool
  kinnitas kirjutatud andmete hash'i; `erase_flash` ega `uploadfs` ei kasutatud.
  LCD näitas `BENCH`, `execution disabled`, `Lab2AtomBench`, `192.168.4.1`
  ja ajutist AP parooli (parooli ei dokumenteerita). ADC vastus:
  `status=not_calibrated`, `raw_adc=7`, `calibrated=false`,
  `sensor_connected=not_verified`, `voltage_v=null`, `pressure_kpa=null`.
  `raw_adc=7` on ujuva sisendi vaatlus, mitte füüsiline rõhumõõtmine.
  Save- ja postkontori testinupud olid lehel keelatud. HTTP 423 jõustamist
  kontrollisid software-testid, mitte eraldi päring päris Wi-Fi kaudu.
  Rakenduse diagnostilisi serial-teateid ei salvestatud ega kinnitatud.
* Otsustasime, ja miks: Hoidsime BENCH_MODE'i ja välise riistvara isolatsiooni.
  Kasutaja võttis selle katse jaoks teadlikult vastu ESP-IDF 4.4.7
  panic/coredump'i ja OTA metadata jääkriski: kogu flash'i muutumatust ei
  garanteerita. Kaitstud AP ja veebilehe avanemine ei tõenda production
  HTTPS-i ega pollingut. Reset'i järel nähtav BENCH-ekraan ei tõenda NVS-i
  säilimist ega puhtaid rakenduse serial-logisid. Salvestame ainult kinnitatud
  vaatlused; varasemate sessioonide kandeid ei muudeta.
* Lahti järgmiseks korraks: Püüda rakenduse diagnostilised serial-teated,
  mõõta päris HTTP 423 vastused ning kavandada NVS-i säilimise kontroll.
  Normaalrežiimi, production HTTPS/pollingu ja station-adapteri katsed vajavad
  eraldi luba. MG400, pump, kaamerad, rõhuandur/LM358 ahel, Andmehõive Lab 2
  kalibratsioon, latency-mõõtmised ja ametlik mid-job katkestuskatse jäävad TODO.

**23.10.2026 — Nikita Teterev (BENCH HTTP 423, jätk)**

* Tegime: Saatsin MacBookist curl'iga kaks POST-päringut päris AtomS3R-ile
  kohaliku `Lab2AtomBench` Wi-Fi kaudu. Päringutes ei olnud paroole ega API-võtmeid.
  Atom jäi BENCH_MODE'i; station, MG400, pump ja andurid olid lahti ühendatud.
* Juhtus (numbrid): `POST http://192.168.4.1/settings` andis `HTTP/1.1 423`
  ja `{"error":"bench_read_only"}`. `POST http://192.168.4.1/test/post-office`
  andis samuti `HTTP/1.1 423` ja `{"error":"bench_read_only"}`. Need kaks
  tulemust kinnitavad firmware HTTP-keeldu riistvaral, lisaks software-testidele.
  Esimese sama päeva kande HTTP 423 TODO on nende kahe endpoint'i osas täidetud.
* Otsustasime, ja miks: Kontrollisin keeldu otse HTTP kaudu, sest keelatud
  nupp brauseris üksi ei tõenda serveripoolset kaitset. See katse ei kinnita
  `/pressure/settings` POST-i, NVS-i täielikku säilimist ega production-pollingut.
  Production HTTPS-i/pollingut ei kasutatud; coredump'i jääkrisk jäi samaks.
* Lahti järgmiseks korraks: Kontrollida `/pressure/settings` POST-i päris
  HTTP 423 vastust, püüda rakenduse serial-diagnostika ja kavandada NVS-i
  säilimise kontroll. Production HTTPS, station/MG400, pump, kaamerad ning
  päris rõhuanduri/op-amp ahel ja kalibratsioon jäävad TODO-ks.

**23.10.2026 — Nikita Teterev (BENCH pressure/settings HTTP 423, jätk)**

* Tegime: Saatsin MacBookist curl'iga kohaliku `Lab2AtomBench` Wi-Fi kaudu
  kolmanda safety-päringu päris AtomS3R-ile. Kasutasin käsku
  `curl --noproxy '*' -i --max-time 5 -X POST http://192.168.4.1/pressure/settings`.
* Juhtus (numbrid): Vastus oli `HTTP/1.1 423`,
  `Content-Type: application/json`, keha `{"error":"bench_read_only"}`.
  Koos eelmise jätkukandega on kõik kolm POST-route'i (`/settings`,
  `/test/post-office`, `/pressure/settings`) riistvaral HTTP 423-ga kontrollitud.
* Otsustasime, ja miks: Säilitame BENCH_MODE'i piiratud kontrolli tulemuse.
  Kolm keeldumist kinnitavad nende HTTP-handler'ite kaitset, mitte täielikku
  NVS-i säilimist või kogu flash'i read-only olekut. ESP-IDF coredump'i risk jääb.
* Lahti järgmiseks korraks: Rakenduse serial-diagnostika ja füüsilise NVS-i
  säilimise kontroll. Production HTTPS/polling, station/MG400, pump, kaamerad,
  rõhuandur/op-amp ja kalibratsioon ning ametlikud mõõtmised jäävad TODO-ks.

**23.10.2026 — Nikita Teterev (AtomS3R HEALTH_ONLY, jätk)**

* Tegime: Laadisin asendus-AtomS3R-i eraldi `atoms3r_health` püsivara ja
  kontrollisin ekraani ning USB-helper'iga suhtlust. Lubasin ühe health-katse
  Redmi telefoni Wi-Fi hotspot'i kaudu. Varasemad BENCH-tulemused jäävad
  eraldi katseteks; neid kandeid ei kirjutata ümber.
* Juhtus (numbrid): Päris upload õnnestus. Helper näitas järjest
  `WIFI CONNECTED`, `TLS VERIFIED`, `HEALTH ERROR` ning naasis shell'i.
  Edukat HTTP 200 ega `{"ok":true,"service":"lab2-post-office"}` vastust
  ei kinnitatud. Wi-Fi ja TLS-i tulemus ei ole edukas `/health` end-to-end test.
* Otsustasime, ja miks: Säilitame isoleeritud ühe päringu build'i, USB kaudu
  antava ühekordse loa, RAM-only Wi-Fi seaded ning NVS-guard'id. API-võtit,
  pollingut, claim'i, result retry'd ega station/actuator-käske see katse ei
  vaja. Üldine `HEALTH ERROR` ei erista write/read/timeout'i, HTTP staatust,
  framing'ut ega JSON kontrolli. Dokumenteerisime piiratud diagnostikakoodide
  plaani; neid koode ei ole veel püsivarasse lisatud. Chunked-framing on
  parseris keelatud, kuid selle seost päris veaga ei ole tõendatud.
  ESP-IDF flash-coredump'i ja OTA metadata jääkrisk, Maci UTC usaldamine
  ning CRL/OCSP puudumine jäävad kehtima. Saladusi ega backup'i ei avaldata.
* Lahti järgmiseks korraks: Eristada HTTP etapi viga ilma saladuste või body
  logimiseta ning teha eraldi lubatud `/health` korduskatse. Autentitud
  production-polling, füüsiline station/MG400/pump, kaamerad, Andmehõive
  kalibratsioon, NVS-i säilimine, latency ja ametlik mid-job katse jäävad TODO.

### Väljundid ja tulemused

**Väljundid**
* Lab 3 saab siit postkontori tarkvara ning 16.10.26 ja 20.10.26 dropleti
  kontrollid: avalik HTTPS, SSH autentimine, UFW ning SQLite backup'i
  taastamine testbaasi. Kogu dropleti reboot ja täielik taaste on TODO.
* Lab 3 saab siit Atomi väljamineva pollingu ning lokaalse `letter` tarkvaralepingu;
  AtomS3R upload ja autentitud lokaalne polling on tehtud, kuid MG400
  riistvaraintegratsioon on TODO.
* Lab 3 saab siit kahe station'i kaamera lokaalse tarkvarakihi; mõlema päris
  kaamera samaaegne kontroll ja näidispildid on TODO — real hardware required.
* Lab 3 VPN/direct path saab siit postkontori, Atomi, station'i ja kaamerate
  piirid; VPN-i ega station'i otseühendust Lab 2-s ei teostata.

**KAARDISTA ISE, lõpus.**
* Git repo ja tag: TODO — lisada alles esitamisel.
* Numbrid, mille see labor andis, ühikutega: TODO — real measurement required;
  software-testide arvud ei ole füüsilised mõõtmistulemused.
* Postkontori paigaldus- ja taastamismallid: teostatud failis
  `deploy/README.md`; esmane paigaldus tehtud 16.10.26, `deploy/verify.sh`
  ja backup'i taastamine eraldi testbaasi kontrollitud 20.10.26. Täielik
  taaste puhtale hostile ning Atomi production polling on TODO.
* Meeskonna ohutuskinnitused: TODO — each team member must confirm personally.
* Mida me teeksime teisiti: TODO — complete after physical tests.
* Mida järgmine labor peaks enne alustamist teadma: TODO — complete at the end
  of Lab 2 after droplet, Atom, MG400 and camera tests.
