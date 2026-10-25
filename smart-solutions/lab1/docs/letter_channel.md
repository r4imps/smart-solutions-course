# Tähe kanal Atomi ja jaama vahel

## Valitud lahendus

Labor 1 jaoks kasutame varianti, kus **Atom algatab ühenduse ja saadab tähe
jaamale HTTP POST päringuga**.

Põhjus:

- täht on sündmus, mitte pidev andmevoog;
- polling lisaks tarbetu viite ja päringud;
- HTTP sobib Atomi olemasoleva Wi-Fi lahendusega;
- jaam on niikuinii Python/Flask rakendus;
- HTTP vastus annab Atomile selge kinnituse, kas sündmus jõudis jaama.

## Lisandus 03.10.26: USB kanal laboriarvutile

Laboriarvutil, kus jookseb `mg400 serve`, **ei ole Wi-Fi adapterit** (ainult
kaks Ethernet porti: ülikooli võrk ja robot). Seega Atom ei saa sellele
arvutile HTTP-ga tähte saata. HTTP kanal jääb kehtima, kui jaam jookseb
Wi-Fi-ga sülearvutis.

Ühendatud püsivara (`firmware/`) saadab iga tähe korraga kahte teed:

1. sama JSON rea USB-serialisse:
   `{"letter":"K","session":"…","seq":3,"atom_sent_ms":81234}`;
2. HTTP POST jaama aadressile, kui see on seadetes olemas.

Laboriarvutis loeb USB rida kas `src/atom_bridge.py` (ainult tähed) või
Andmehõive `logger.py --station http://127.0.0.1:5000` (pump ja tähed sama
COM-pordi kaudu; COM-porti saab avada ainult üks programm). Kui täht jõuab
mõlemat teed pidi, tunneb jaam teise koopia `session`+`seq` järgi ära ega
joonista kaks korda.

`logger.py` loeb esimese sekundi jooksul (nullpunkti kontroll) ainult rõhku,
seega vajuta tähte alles pärast logger'i käivitumist.

## Osapooled

### AtomS3

Atomil on eraldi seadistatav tähe nupurežiim. Selles režiimis valib lühike
vajutus järgmise tähe `A`–`Z` ja pikk vajutus kinnitab saatmise. Kui tähe
nupurežiim on välja lülitatud, töötavad varasemad sloti short/long/double
žestid muutmata kujul.

Jaama aadress ei ole lähtekoodis fikseeritud. See salvestatakse Atomi
veebilehe seadetes väljale `station address`. Saatja normaliseerib palja
hosti või IP-aadressi kujule `http://<host>:5000/api/letter` ning lisab
juba skeemi ja pordiga baasaadressile ainult `/api/letter` tee.

### Jaam

Jaam käivitab Flask serveri:

```text
http://<JAAMA_IP>:5000
```

Reaalne `<JAAMA_IP>` lisatakse pärast laborikatset.

Endpoint:

```text
POST /api/letter
Content-Type: application/json
```

## Sõnum

Minimaalne nõutud väli on õpetaja ülesandes kirjeldatud `letter`.

Meie protokoll lisab kaks välja, mis teevad korduskatse ohutuks:

```json
{
  "letter": "A",
  "session": "atom-boot-id",
  "seq": 12,
  "atom_sent_ms": 153422
}
```

Väljad:

| Väli | Tähendus |
| :--- | :--- |
| `letter` | üks ladina suurtäht `A`–`Z` |
| `session` | Atomi boot/session identifikaator |
| `seq` | selles session'is kasvav sündmuse number |
| `atom_sent_ms` | Atomi `millis()` hetkel, kui saatmine algas |

`session + seq` võimaldab Atomil HTTP vea korral sama sündmust uuesti saata
ilma, et robot sama tähte kaks korda joonistaks.

## Jaama vastus

Uus dry-run sündmus:

```json
{
  "ok": true,
  "duplicate": false,
  "letter": "A",
  "seq": 12,
  "station_received_iso": "TODO",
  "robot_started": false,
  "dry_run": true
}
```

Execute-režiimis teeb jaam enne vastust kalibratsiooni ja mg400-base oleku
kontrolli. Kui kontroll läbib, käivitab ta ühe taustatöötaja ning vastab kohe:

```json
{
  "ok": true,
  "accepted": true,
  "duplicate": false,
  "letter": "A",
  "seq": 12,
  "robot_started": true,
  "execution_status": "started",
  "dry_run": false
}
```

Siin `robot_started=true` tähendab, et täitmine võeti vastu ja töötaja
käivitati; see **ei kinnita**, et täht on valmis joonistatud. Lõpptulemus
(`completed` või `failed`) salvestatakse jaama sündmuslogisse. Kui sama
`session + seq` saabub töö ajal uuesti, kinnitab jaam selle ilma teist töötajat
käivitamata.

Kordussõnum pärast lõpetamist:

```json
{
  "ok": true,
  "duplicate": true,
  "letter": "A",
  "seq": 12,
  "station_received_iso": "TODO",
  "execution_status": "completed"
}
```

HTTP:

- `202` — uus täht võeti vastu või sama sündmus on veel käimas;
- `200` — sama `session + seq` oli juba lõpetatud ja ainult kinnitatakse;
- `400` — vigane JSON või vigane täht.
- `422` — tähe trajektoor ei ole jaamas seadistatud.
- `409` — station täidab juba teist uut tähesündmust või sama sündmus on
  pärast liikumise alustamist veaga lõppenud; viimast ei joonistata uuesti.
- `503` — kalibratsioon, mg400-base ühendus või roboti safety gate ei luba täitmist.

Enne täitmise algust tekkinud kalibratsiooni või safety gate'i vea puhul
võib sama `session + seq` pärast vea parandamist uuesti saata. Atomi 2 s
vastuse timeout'i tõttu toimub joonistamine HTTP päringust eraldi.

## Atomi saatja teostus

Püsivaras luuakse igal käivitusel `esp_random()` põhine session'i tunnus.
See tunnus püsib ühe boot'i jooksul sama ja uue käivituse järel luuakse uus.
Järjekorranumber `seq` algab väärtusest `1` ning suureneb täpselt ühe korra
iga järjekorda vastu võetud kasutaja saatmissündmuse kohta. Sama sündmuse
korduskatsed kasutavad muutmata tähte, session'it, `seq` väärtust ja
`atom_sent_ms` väärtust.

Saatmine toimub `loop()`-is väikese olekumasinaga:

- `idle` — saatmist ei ole;
- `pending` — uus sündmus ootab esimest katset;
- `waiting_retry` — sama sündmus ootab järgmist katset;
- `success` — jaam vastas HTTP `200` või `202`;
- `failed` — aadress puudub või kõik katsed ebaõnnestusid.

Ühe sündmuse jaoks tehakse kuni kolm HTTP POST katset. Võrguvea, timeout'i
või muu kui `200`/`202` HTTP vastuse järel oodatakse ligikaudu 250 ms ja
proovitakse sama sündmust uuesti. HTTP ühenduse ja vastuse timeout on
piiratud. Kogu retry-tsüklit ei käivitata veebipäringu handler'is.

Kui `station address` on tühi, lõpetab saatja sündmuse arusaadava veaga ega
tee võrgupäringut. Serial logi sisaldab sündmuse tähte, session'it, `seq`
väärtust, katse numbrit ja ACK või vea olekut, kuid mitte Wi-Fi parooli.

## Tarkvaraline test

Endpoint:

```text
POST /test/letter
Content-Type: application/x-www-form-urlencoded
letter=A
```

Endpoint valideerib ühe tähe vahemikus `A`–`Z`, lisab uue sündmuse samasse
saatja järjekorda ja tagastab kohe JSON vastuse olekuga `pending`. See ei oota
HTTP handler'is retry-tsükli lõppu. Settings & tests lehe nupp
`TEST LETTER SEND` kasutab seda endpoint'i ja sama saatmisteed nagu füüsilise
nupu pikk vajutus.

## Ekraani tagasiside

Tähe nupurežiimis näitab ekraan valitud tähte. Saatmise ajal kuvatakse
`SENDING`, ACK järel `SENT`, vea korral `FAILED` ning seadistamata jaama puhul
`NO STATION`. Tagasiside ei kirjuta üle `frameBuf` sisu ega salvesta slotte.
Pärast lühikest tagasisidet taastatakse valitud tähe vaade või varasem
pildi-/olekuvaade vastavalt aktiivsele režiimile.

Reaalne ekraanikuva, nupud, retry ja Atom ↔ jaam ühendus kontrollitakse
AtomS3-l laboris.

## Ohutus

Tähe vastuvõtmine **ei tohi iseenesest tähendada, et robot liigub**.

Jaam peab enne esimese MG400 käsu saatmist kontrollima vähemalt:

- kas robot on ühendatud;
- kas robot on lubatud;
- kas robot ei täida juba teist jada;
- kas tähe trajektoor on olemas;
- kas reaalsed Z väärtused on mõõdetud.

`station.py` käivitub vaikimisi dry-run režiimis ja ei saada robotikäske.
Reaalne täitmisrada aktiveerub ainult lipuga `--execute`; ka siis nõuab see
täielikku kalibratsiooni ja ohutut mg400-base olekut. Tarkvararada on
mockidega kontrollitud, kuid reaalne MG400 tähejoonistus on endiselt laboris
kontrollimata.

See oli 02.10.26 vaheolek. 03.10.26 kontrolliti sama täitmisrada päris
MG400-ga: Atomilt tulnud tähed joonistati paberile ning meeskonna initsiaalid
D, N ja R valmisid füüsiliselt.

Jaam peatab täitmise, kui mg400-base `servo_active` on väär või `/api/move`
vastuses teatatud sihtpunkti on piiratult muudetud (`clamped`). Vea järel
tehakse best-effort `/api/stop` ja rohkem plaani samme ei saadeta.

## Ajatemplid ja latentsus

Algne ülesanne nõudis 30 katse kohta kolme ajatemplit:

1. Atom saatis;
2. jaam sai;
3. jaam saatis esimese käsu robotile.

Praegune protokoll salvestab:

- `atom_sent_ms`;
- `station_received_iso`;
- `station_received_monotonic_ns`;
- execute-režiimis `robot_command_monotonic_ns` vahetult enne esimest
  `/api/move` päringut, mis alustab tähe trajektoori. `/api/speed` on
  ettevalmistuskäsk ja ei ole joonistuse latentsuse alguspunkt.

**Oluline:** Atomi `millis()` ja arvuti monotonic clock ei ole sama kell.
Neid ei tohi lihtsalt lahutada ja nimetada tulemuseks millisekundites.

Atom → jaam täpse latentsuse mõõtmise meetod valitakse laborikatse ajal
(nt kellade offseti mõõtmine/handshake või jaama poolt mõõdetud request/ACK
meetod). Väljamõeldud latentsusnumbreid dokumenti ei lisata.

Jaam → robot hüpet saab mõõta sama arvuti monotonic clockiga, sest mõlemad
ajatemplid tekivad jaamas.

Lõpptulemusena tehti viis reaalset mõõtmist. Õppejõuga lepiti kokku, et
selle labori jaoks piisab viiest mõõtmisest, mistõttu ülejäänud 25 katset ei
tehtud. `docs/latency.csv` sisaldab neid viit päris mõõtmist ning Lab 1 jaoks
ei ole täiendavaid latentsusmõõtmisi vaja.

## Failid

Planeeritud repo failid:

```text
smart-solutions/lab1/src/station.py
smart-solutions/lab1/src/mock_atom.py
smart-solutions/lab1/src/requirements.txt
smart-solutions/lab1/data/letter_events.csv
smart-solutions/lab1/docs/letter_channel.md
```

`mock_atom.py` on ainult arenduseks: sellega saab HTTP kanali enne
laborisse minekut läbi proovida.

## Enne laborit kontrollitav

- [x] HTTP sõnumiformaat on valitud.
- [x] Jaama endpoint on valitud.
- [x] ACK ja duplicate käitumine on kirjeldatud.
- [x] Station receiver on kirjutatud.
- [x] Mock Atom sender on kirjutatud.
- [x] Atomi püsivara saatmisfunktsioon ja retry-olekumasin on kirjutatud.
- [x] `/test/letter` tarkvaraline testitee on kirjutatud.
- [x] Käivitada station lokaalselt ja teha mock test.
- [x] Ehitada ja kontrollida saatmisfunktsioon PlatformIO-ga.

02.10.26 tarkvaraline kontroll: station töötas vaikimisi dry-run režiimis,
`mock_atom.py` saatis tähe A, vastus oli HTTP 202 ning robotikäske ei saadetud.

## Laboris kontrollitav

- [ ] Jaama tegelik IP.
- [ ] Atom ja jaam näevad teineteist võrgus.
- [ ] Päris nupuvajutus saadab tähe.
- [ ] Katkestatud ühenduse retry töötab.
- [ ] `/test/letter` saadab sündmuse päris Atomilt jaamale.
- [ ] Tähe nupurežiim ei riku tavalisi sloti žeste.
- [ ] Sama `session + seq` ei käivita robotit kaks korda.
- [ ] MG400 safety gate.
- [ ] Esimese robotikäsu ajatempel.
- [x] Latentsuse mõõtmine: viis päris katset, õppejõuga kokkuleppel piisav Lab 1 jaoks.

## Tähe oleku päring (lisatud 25.10.26, Lab 2 jaoks)

Lab 2 jaamaadapter saadab Atomi `letter` töö edasi sellele samale jaamale
(`POST /api/letter`), et MG400-t liigutaks ainult Lab 1 jaam oma
kalibratsiooni ja ohutusväravatega. Lõpu ootamiseks lisati üks read-only
päring:

| Meetod | Tee | Vastus |
| :--- | :--- | :--- |
| GET | `/api/letter/status?session=<session>&seq=<seq>` | `execution_status`: `preflight`, `started`, `completed` või `failed`; `error`; `dry_run` |

Päring ei saada robotile käske. Dry-run tähel ja tundmata sündmusel kirjet
ei ole (HTTP 404). Olek on jaama mälus; jaama restart kustutab selle.
Lab 1 senist käitumist ega mõõdetud väärtusi see ei muuda.
