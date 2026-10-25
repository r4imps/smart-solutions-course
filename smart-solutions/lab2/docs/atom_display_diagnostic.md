# AtomS3R ekraani diagnostika — 13.10.26

## Seade

M5Stack AtomS3R on ühendatud Maciga USB-C kaudu. Viimase kontrolli serial-port
oli `/dev/cu.usbmodem101`, VID:PID `303A:1001`. Port võib pärast
taasühendamist muutuda; see tuleb iga upload'i eel uuesti tuvastada.

## Tehtud kontrollid

Allolev kirjeldab Nikita kinnitatud füüsilisi vaatlusi ja tööriistade tulemusi.

1. Smart Solutions Lab 2 püsivaraga jäi ekraan mustaks.
2. Olemasoleva, varem riistvaral kontrollitud Lab 1 püsivaraga jäi ekraan
   samuti mustaks.
3. Sõltumatu M5Unified display test build'is ja laaditi edukalt. Teek
   tuvastas ekraani mõõduks `128 × 128`, kuid pilti ei ilmunud.
4. Füüsilise küljenupu lühike vajutus pilti ei toonud.
5. 13.10.26 paigaldati ametliku M5Burneriga `UIFlow2.0 AtomS3R v2.5.3`.
6. M5Burner teatas `Burn successfully`, kirjutamine jõudis `100%`-ni ja
   kuvatud oli `Hash of data verified`.
7. Boot option oli `Show startup menu and network setup`.
8. Ekraan jäi täielikult mustaks nii automaatse reset'i kui ka USB uuesti
   ühendamise järel.
9. Pilti ei olnud näha ka taskulambiga valgustades ega pimedas.

## Järeldus ja praegune püsivara

USB-side ja püsivara kirjutamine töötavad, kuid ekraan ei näita pilti.
Kahtlustatakse ekraani, taustvalgustuse või ühenduse riistvaraprobleemi.
Lõplik riistvararike ei ole tõestatud; teine AtomS3R on vajalik võrdluseks.

**Füüsilises Atomis on praegu UIFlow2, mitte Smart Solutions Lab 2 püsivara.**
Seetõttu ei tööta praegu projektipolling, projekti station bridge ega
pressure page. Varasemad edukad kohaliku pollingu ja Wi-Fi recovery katsed
kirjeldavad enne UIFlow2 paigaldamist kontrollitud projektipüsivara.

Enne järgmisi projekti riistvarakatseid tuleb Lab 2 püsivara taastada
[PlatformIO juhendi järgi](../firmware/README.md#projekti-püsivara-taastamine-pärast-uiflow2).
Wi-Fi, serveri ja võtmete säilimist pärast UIFlow2 ei eeldata: need tuleb
seadmel kontrollida. Saladusi ei lisata dokumentidesse ega Git'i.
Praegune pressure-extension püsivara pole läbinud füüsilist kontrolli.

## Järgmine laborikontroll

1. Kontrollida praegust seadet ja teist teadaolevalt töötavat AtomS3R-i.
2. Võrrelda ekraanide tööd sama kontrollitud püsivaraga. Teist seadet pole
   veel kontrollitud.
3. Vajadusel arutada õppejõuga seadme asendamist.
4. Taastada projekti püsivara PlatformIO kaudu.
5. Kontrollida serial startup'i, AP/Wi-Fi ligipääsu, seadeid, autentitud
   lokaalset pollingut ja `last_seen`; vajadusel korrata reconnect-katset.
6. Jätkata pressure-, camera- ja MG400-katseid nende ohutusreeglite järgi.

Lab 2 [praegune seis](../README.md#praegune-seis--231026) eristab tarkvaralisi
tulemusi, välise ligipääsu takistust ja veel tegemata füüsilisi katseid.
