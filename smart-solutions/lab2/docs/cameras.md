# Lab 2 kohalik kaamera-arhitektuur

> **Olek:** station'i tarkvarakiht, mock-allikad ja automaattestid on valmis.
> 3D Printing Lab 2 kinnitab XIAO USB Serial diagnostilise JPEG-i; Smart
> Solutions Wi-Fi firmware upload, kogu laua vaade ja jõudlus on kontrollimata.

## Rollid ja süsteemipiir

- **Table camera** on Verbatim AWC-03 (49580), mille tulevane ülesanne on näidata kogu
  tööala, ruudustikku ja robotit.
- **Tool camera** on XIAO ESP32S3 Sense, mille tulevane ülesanne on näidata
  tööriista otsikut ja selle all olevat detaili. Station saab temalt JPEG-pildi
  kohaliku Wi-Fi kaudu.

Mõlemat pilti näitab ainult station-arvuti lokaalne leht. Dropleti
postkontoris ei ole kaamera route'e, proxy't ega voogu. Lab 2 ei loo selleks
VPN-i, WireGuardi ega pöördtunnelit.

Valitud ühendusskeem (võrgurada vajab veel kontrolli):

```text
MG400 <--- Ethernet/TCP ---> station PC
Verbatim AWC-03 <--- USB ---> station PC
AtomS3R <--- USB Serial ---> station PC
AtomS3R --- Wi-Fi/HTTPS ---> droplet post-office (videot ei vahenda)
station PC --- kohalik IP-võrk / Wi-Fi / GET /snapshot.jpg ---> XIAO
USB-C toiteallikas (TODO) ---> XIAO
```

Station PC Etherneti ja XIAO Wi-Fi vahel peab olema IP-ligipääs. Kontrollida
laboris alamvõrke, marsruutimist ja client isolation'it; seda pole kinnitatud.
XIAO USB-C toite lõplik allikas ja kaablitee vajavad liikumisulatuses kontrolli.

## Kinnitatud lähtefaktid ja püsivara valik

[3D Printing Lab 2 README](https://github.com/Dennel04/3d-printing-course/blob/main/3d-print/lab2/README.md)
kirjeldab 23.10.26 XIAO-d prinditud kinnituses MG400 J4 mootori nelikandil:
OV3660 sensor, üks JPEG `1600 × 1200` USB Serial COM5 kaudu, toide USB-C-ga
arvutist. J4 on meeskonna dokumenteeritud paigutusvariant; samas allikas on
04.10.26 õpetaja suuline luba valida kinnituskoht. See ei kinnita veel
töökoha FOV-d, kaabli ohutust kogu liikumisel ega lõplikku toidet.

Smart Solutions põhipüsivara on [`firmware-xiao-camera/`](../firmware-xiao-camera/README.md)
ja selle Wi-Fi HTTP `GET /snapshot.jpg` leping.
[USB Serial püsivara](https://github.com/Dennel04/3d-printing-course/tree/main/3d-print/lab2/tool-camera/firmware)
jääb diagnostiliseks varuks. USB tulemus ei tõenda Smart Solutions Wi-Fi
püsivara upload'i, Wi-Fi ühendust ega station'i HTTP snapshot'i.
Üldvaatekaamera on 3D Printingus identifitseeritud Verbatim AWC-03 (49580);
lõplik paigaldus, kogu laua vaade ja mõõtmised jäävad TODO-ks.

Kaamerakood ei impordi station'i job-adapterit, executor'it ega MG400 klienti.
Ühe kaamera rike ei muuda tööde vastuvõtmise või täitmise rada.

## Ühine allikaliides

`src/cameras/base.py` määrab kõigile allikatele sama liidese:

- `start()` käivitab ühe taustal töötava capture worker'i;
- `get_frame()` loeb viimast täielikku JPEG-kaadrit ega ava seadet;
- `status()` annab oleku, vea, resolutsiooni, konfiguratsiooni ja loendurid;
- `stop()` peatab worker'i ja vabastab allika.

HTTP kliendid jagavad sama worker'it ja viimast kaadrit. Seetõttu ei ava iga
brauser ega iga stream request USB-seadet uuesti. Allika lugemise või JPEG-i
viga märgib allika `unavailable`, kuid Flaski leht jääb tööle. Worker ootab
enne uut katset seadistatava retry-intervalli, et vältida tight loop'i.

## USB UHD backend

`UsbCamera` kasutab GUI-ta OpenCV paketti `opencv-python-headless`. Seadistatav
on seadme indeks või failitee, capture-resolutsioon, brauserivoogu skaleeritav
resolutsioon, FPS-siht, JPEG kvaliteet ja retry-intervall. `VideoCapture`
avatakse worker'i kohta üks kord ning vabastatakse nii stop'i kui vea järel.

Tarkvara arendusvaikeväärtused on capture `3840 × 2160`, stream `1280 × 720`
ja siht `10 FPS`. Need **ei ole mõõtmistulemus ega lõplik laborivalik**.
Lõplik capture/stream kombinatsioon valitakse päris vaatevälja, ruudustiku
loetavuse, viite ja koormuse katse järel.

## XIAO ESP32S3 Sense backend

`XiaoCamera` küsib seadistatavalt HTTP- või HTTPS-snapshot URL-ilt täieliku
JPEG-i. XIAO eraldi PlatformIO projekt `firmware-xiao-camera/` annab täpselt
`GET /snapshot.jpg` endpoint'i koos `image/jpeg` content type'i ja no-cache
päisega. IP-aadressi ega URL-i ei ole kummagi poole lähtekoodi kirjutatud.
Tühja URL-iga on station'i allikas ohutult `unavailable`; võrguviga käivitab
piiratud sagedusega uue katse. Vastuse suurus on piiratud ja poolik või
mitte-JPEG vastus lükatakse tagasi.

XIAO `GET /status` annab camera/Wi-Fi oleku, kohaliku IP, driver'i tuvastatud
sensorimudeli, väljastatud kaadrite loenduri ja uptime'i, kuid mitte Wi-Fi
parooli. Firmware SSID/parool tuleb ignored `wifi_private.h` failist. Station'i
status API näitab ainult seda, kas snapshot URL on seadistatud, ega tagasta
URL-i ennast.

Firmware kasutab ametlikku Seeed pin mapping'ut, boardi 8 MB PSRAM-i ja
`esp_camera` automaatset sensorituvastust. Driver toetab nii varasemat OV2640
kui uuemat OV3660 revision'it; 3D Printing USB-katse tuvastas OV3660.
Selle Wi-Fi build'i tuvastus on veel TODO. Pidevat
XIAO MJPEG handler'it ei lisatud, sest olemasolev station backend vajab ainult
snapshot'i ning loob lokaalse MJPEG voo ise. See hoiab XIAO status endpoint'i
diagnostiliselt kasutatavana ja capture ownership'i üheselt mutex'i taga.

### USB Serial varuvariant (`XiaoSerialCamera`)

Kui Etherneti station PC ei jõua XIAO Wi-Fi IP-ni, saab tööriistakaamerat
lugeda USB Seriali kaudu:

```bash
python -m src.camera_server --xiao-serial-port COM5
```

`XiaoSerialCamera` kasutab 3D Printing Lab 2
[USB diagnostikapüsivara](https://github.com/Dennel04/3d-printing-course/tree/main/3d-print/lab2/tool-camera/firmware)
protokolli: `c` → `JPG <baidid>` ja JPEG, `i` → `INFO camera=… pid=…`.
Ühendamisel küsitakse `INFO` rida; `/api/cameras` näitab väljas
`detected_sensor` driver'i PID-i järgi sensori nime (nt `OV3660`).
Resolutsioon loetakse iga JPEG-i SOF päisest. DTR/RTS hoitakse madalal, et
pordi avamine ESP32-S3-e ei lähtestaks. `--xiao-serial-port` ja
`--xiao-snapshot-url` välistavad teineteist. COM-porti saab korraga kasutada
üks protsess: `capture.py` ja station'i leht ei tööta samal ajal.

Automaattestid kasutavad simuleeritud porti. Päris COM5 kaader station'i
lehel, FPS ja viide: `TODO — waiting for physical test`.

## Mock-režiim ja lokaalne leht

Käivita Lab 2 juurkaustast:

```bash
python -m src.camera_server --mock
```

Leht avaneb vaikimisi ainult loopback-aadressil
`http://127.0.0.1:5002/`. Brauserit automaatselt ei avata. Mõlemad allikad
genereerivad standardteegi abil sünteetilist JPEG-i; JPEG comment sisaldab
rolli (`TABLE` või `TOOL`), kaadriloendurit ja ajatemplit. Mock ei loo võrgu-,
dropleti-, serial- ega MG400 ühendust. Mock-andmeid ei kirjutata mõõtmiste CSV-sse.

Lokaalsed route'id:

| Route | Otstarve |
| :--- | :--- |
| `GET /` | kaks kõrvuti kaamerasektsiooni ja perioodiline olek |
| `GET /api/cameras` | mõlema allika kohalik status ja software-loendurid |
| `GET /snapshot/{table|tool}.jpg` | viimane täielik JPEG |
| `GET /stream/{table|tool}.mjpg` | MJPEG multipart-voog |

Need route'id kuuluvad eraldi `src.camera_server` protsessile, mitte avalikku
`server.app` postkontorisse. Lab 1 station'i leht kuvab sama kaameralehte
iframe'is aadressilt `http://127.0.0.1:5002/`: mõlemad olemasolevad MJPEG-vood,
status API ja worker'id jäävad muutmata. Kaamera pole robotitöö callback;
kaameraprotsessi puudumine ei peata Lab 1 ega Lab 2 töid. Kitsal ekraanil
on kaamerad üksteise all; mõlemad vood on samal lehel aktiivsed.

See integratsioon on vaatamiseks station PC enda brauseris. Loopback iframe
ei tähenda LAN-kliendi jaoks station PC aadressi. Juhtimislehte ei seota
kaameravaate pärast `0.0.0.0` ega LAN-aadressile. Kaitstud kaugem LAN-vaade
ja ühine autentimine jäävad TODO-ks; avalikku proxy't ega dropleti muudatusi
ei lisata.

### Station'i tarkvaraline kontroll kahe mock-kaameraga

Aktiveeri ettevalmistatud Python-keskkond. Esimene terminal repo juurkaustast:

```powershell
cd smart-solutions/lab2
python -m src.camera_server --mock --host 127.0.0.1 --port 5002
```

Teine terminal repo juurkaustast:

```powershell
cd smart-solutions/lab1
python src/station.py --host 127.0.0.1 --port 5000 --dry-run
```

Ava station PC brauseris `http://127.0.0.1:5000/`. Teksti eelvaade ja
joonistusnupud säilivad; lehe all on korraga Table camera ja Tool camera.
Kaameravaate test ei vaja `--execute`, Atomit, USB seriali ega MG400-t.
Mock-pildid on selgelt sünteetilised 2 × 2 JPEG-id; need ei tõenda FOV-d ega
päris kaamera eraldust. Automaatkontroll kasutab Flask test client'i, mitte
päris võrku või brauseri riistvarakatset.

### Verbatim + XIAO tulevane laborikäsk

Jäta Lab 1 leht loopback'ile. Peata mock-kaameraprotsess ja kasuta selle
asemel järgmist käsku Lab 2 kataloogis, alles eraldi lubatud riistvarakatsel:

```powershell
$usbDevice = Read-Host "Verbatim AWC-03 tegelik OpenCV seadmeindeks"
$xiaoUrl = Read-Host "Kontrollitud XIAO kohalik http://aadress/snapshot.jpg URL"
python -m src.camera_server --host 127.0.0.1 --port 5002 --usb-device "$usbDevice" --usb-capture-width 1920 --usb-capture-height 1080 --stream-width 800 --stream-height 600 --fps 5 --xiao-snapshot-url "$xiaoUrl"
```

Need on algsed tarkvaralised taotlused, mitte Verbatimi mõõdetud režiim ega
valmis FPS-valik. Praegune XIAO lähtekood valib `FRAMESIZE_SVGA` (800 × 600);
station'i XIAO resolutsiooniväljad on oodatud mõõtmed, mitte JPEG-ist
automaatselt mõõdetud eraldus. Kontrolli tegelikke mõõtmeid ja vali mõlema
kaamera FOV järgi lõplikud seaded. Kaamerat ei pea ega tohi selle juhendi
tarkvarakontrolli ajal ühendada või uuesti flash'ida.

Praegu autentimist camera route'idel ei ole ja vaikebind `127.0.0.1` hoiab need
ainult station-arvutis. Kui päris laborikatse nõuab hiljem station'i lehe
sidumist LAN-aadressile, otsustatakse enne seda eraldi, kas lisada lokaalne
autentimispiir. See ei ole praeguse tarkvaraaluse valmimise väide ega ametliku
Lab 2 eraldi nõue. Ka XIAO `/status` ja `/snapshot.jpg` on kohaliku Wi-Fi-võrgu
endpoint'id; neid ei port-forward'ita ega lisata Caddy konfiguratsiooni.

## Tarkvaraloendurid

Iga allikas loendab:

- capture worker'i loodud kaadrid (`frames_captured`);
- HTTP kaudu väljastatud kaadrid (`frames_served`);
- JPEG payload'i väljastatud baidid (`bytes_served`);
- protsessi uptime'i;
- uptime'i põhjal arvutatud keskmise capture/served FPS-i;
- keskmise bytes/s ja ligikaudse Mbit/s väärtuse.

Need on protsessi tarkvaraloendurid. Eriti `served_fps` ja `mbit_per_s`
sõltuvad ühendatud brauseritest; need ei ole füüsiline camera latency ega
valmis hinnatav tulemus.

## Tulevane mõõtmismetoodika

### Kaamera viide

USB ja XIAO jaoks kasutatakse sama protseduuri. Kaamera vaatevälja pannakse
selgelt muutuv taimer või LED-sündmus. Ühes ajabaasis salvestatakse korraga
füüsiline sündmus ja brauseris kuvatud vastav kaader. Iga katse puhul leitakse
`physical event → displayed frame` vahe millisekundites. Korratakse piisav arv
kordi sama võrgu, resolutsiooni, FPS-sihti ja brauserit dokumenteerides. XIAO
puhul märgitakse lisaks Wi-Fi tingimused. Tegelikud tulemused lisatakse alles
pärast päriskatset faili `camera_metrics.csv`.

### FPS ja ribalaius

Kindla mõõteakna alguses ja lõpus loetakse `frames_served` ning
`bytes_served`. Tegelik served FPS on kaadrite vahe jagatud sekunditega;
keskmine ribalaius on baitide vahe × 8 / sekundid / 1 000 000. Mõõtmise ajal
fikseeritakse brauseriklientide arv, capture- ja stream-resolutsioon ning
JPEG kvaliteet. Mock-tulemusi graded CSV-sse ei lisata.

### Juhtimislatentsus 0 / 1 / 2 kaameraga

Sama valideeritud töö ja samad station'i seaded käivitatakse kolmes tingimuses:
kaamerateta, ainult ühe aktiivse vooga ja kahe aktiivse vooga. Igas tingimuses
kasutatakse sama sündmuse algus- ja station'i vastuvõtu/lõpetamise timestamp'i,
tehakse mitu kordust ning dokumenteeritakse klientide arv ja kaameraseaded.
Kaamerakood ei lisa job/executor rajale callback'e; võrdlus mõõdab eraldi
protsesside tegelikku koormusmõju. Tulemused lähevad pärast päriskatset faili
`control_latency_cameras.csv`.

## Labori kontrolliplaan

Järgmised sammud tehakse ainult päris riistvaraga. Mock-kaadreid ega software
loendureid ei kanta mõõtmistulemustena CSV-failidesse.

1. Kontrollida identifitseeritud Verbatim AWC-03 ja OV3660 XIAO kasutusvalmidust
   Smart Solutions töövoos. Kontrollida eraldi USB-pikendust, XIAO toidet ja
   station'i vabu USB-/võrguühendusi.
2. Paigaldada 3D Printing Lab 2 kinnitused: laua kaamera robotist kõrgemale ja
   tööriistakaamera dokumenteeritud J4 asendisse. Kontrollida otsiku ja detaili
   nähtavust; enne katset kontrollida kaabli tegelikku marsruuti,
   liikumisvaru ja strain relief'i.
3. Kontrollida laua kaamera vaatevälja: kogu laud, Gridfinity ruudustik servast
   servani, robot ja hoidikud peavad olema samas kaadris; ruutude nimed peavad
   valitud kuvamisresolutsioonis loetavaks jääma.
4. Kontrollida Etherneti station PC IP-ligipääsu Wi-Fi XIAO-le (alamvõrgud,
   marsruutimine, client isolation). Eraldi loa järel laadida selle repo
   PlatformIO Wi-Fi firmware päris XIAO-sse ja kontrollida
   `/status`, tuvastatud sensorit, PSRAM-i, Wi-Fi reconnect'i ning
   `/snapshot.jpg` JPEG-vastust. Salajast `wifi_private.h` faili reposse ei
   lisata ja XIAO endpoint'i internetti ei avaldata.
5. Kontrollida tööriistakaamera vaatevälja: otsik ja detail otse selle all
   peavad olema nähtavad kogu vajaliku robotiliikumise jooksul.
6. Käivitada mõlemad pärisallikad station'i lehel ja kontrollida, et Table
   camera ning Tool camera on samaaegselt eristatavad. Kui leht peab olema
   avatav teistest LAN-i seadmetest, otsustada ja dokumenteerida enne bind'i
   muutmist kohalik ligipääsupiir.
7. Mõõta kummagi kaamera kohta eraldi capture- ja kuvamisresolutsioon,
   sündmusest kuvatud kaadrini viide, tegelik FPS ning ribalaius. Fikseerida
   katse aeg, trial, klientide arv, seaded ja meetod failis
   `camera_metrics.csv`.
8. Korrata sama valideeritud robotitöö juhtimislatentsuse katset võrreldavates
   tingimustes: 0 aktiivset kaamerat, ainult 1 aktiivne kaamera ja mõlemad ehk
   2 aktiivset kaamerat. Kanda iga trial faili
   `control_latency_cameras.csv`; kokkuvõte ja valitud kaameraseaded tehakse
   alles pärisandmete põhjal.
9. Kontrollida lõpuks, et camera route'e ei ole postkontori Caddy
   konfiguratsioonis, droplet ei proxy pilte ning pildid jäävad ainult
   ettenähtud station'i/labori kohaliku võrgu piirile.

## Riistvara TODO

- kontrollida Verbatim AWC-03 lõplikku paigaldust ja kogu laua vaadet;
- valida vaatevälja ja loetavuse põhjal capture- ja stream-resolutsioon;
- laadida valitud Smart Solutions XIAO Wi-Fi firmware päris seadmesse, kontrollida sensor
  ning määrata lokaalne URL ja võimalik autentimine;
- kontrollida mõlema allika reconnect'i päris katkestustega;
- mõõta viide, FPS, ribalaius ning 0/1/2 kaamera juhtimislatentsus;
- paigaldada kaamerad ja lisada ainult päriskatses saadud tulemused/fotod.
