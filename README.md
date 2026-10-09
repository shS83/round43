# Round43

Remix of the old Round42 game.

## Pelaaminen

- Käynnistys: `uv run round43.py`. Aloitusruutu näyttää `assets/round43-logo.png`-kuvan ja sisään/ulos feidautuvan tekstin “Press space bar to start the game”. Välilyönti aloittaa pelin.
- Liikkuminen: A/D tai nuolinäppäimet.
- Vasen hiirinappi tai välilyönti: oranssi tulipallo suoraan ylöspäin. Välilyönti pohjassa ampuu jatkuvasti 0,15 sekunnin välein.
- Kerää vihollisesta putoava sateenkaaren värinen R-powerup aluksella: saat 3 rainbow-pursketta. Pudotustodennäköisyys on 2,5 %, ja pudotusten välillä on vähintään 12 sekuntia.
- Oikean hiirinapin painallus: yksi 0,5 sekunnin mittainen rainbow-purske hiiren osoittimen suuntaan. Seuraava purske vaatii uuden painalluksen. Ruudun alareuna näyttää jäljellä olevat lataukset.
- Kerää vaaleansininen salamapowerup: saat 3 salamalatausta. Pudotustodennäköisyys on 2,5 % ja oma pudotustauko 12 sekuntia.
- F1: yksi valkosininen, haarautuva salama satunnaiseen elossa olevaan viholliseen. Osuma on varma ja tuhoaa kohdealuksen riippumatta sen hitpointseista. Sivuharat eivät vahingoita muita vihollisia. Ilman kohdetta latausta ei kulu.
- Esc: lopetus.

Viholliset ampuvat suoraan alaspäin purppuraisia tulipalloja 2,5–5,5 sekunnin välein. Niiden kuva on 21 × 32 pikseliä ja osuma-alue 5 × 7 pikseliä. Niiden nopeus on 420 pikseliä sekunnissa (pelaajan tulipallot: 1560). Pelaajalla on alussa 3 elämää. Ammuksen tai vihollisen osuma vie yhden elämän: aluksen kuvapikselit lentävät suoraviivaisesti eri suuntiin ilman painovoimaa ja palaavat puolen ruudun korkeuden päästä osumapaikkaan muodostaen saman aluksen. Räjähdyspikselit ovat 4–8 pikselin kokoisia; palojen maksimietäisyydet arvotaan erikseen, jotta ne jäävät hajanaiseksi pilveksi; kun kaikki ovat saavuttaneet oman maksimietäisyytensä, ne pysähtyvät 0,5 sekunniksi ennen paluuta. Liikkuminen ja ampuminen odottavat uudelleenmuodostumista, jonka jälkeen pelaaja saa 2 sekunnin suojan (vahva vaaleansininen hohto). Viimeisen elämän animaation jälkeen näkyviin tulee highscore-lista. Välilyönnin uusi painallus käynnistää uuden pelin; Esc lopettaa. Vihollisista voi pudota myös +1-lisäelämä 2,5 % todennäköisyydellä; sillä on oma 12 sekunnin pudotustauko. Rainbow-värit kiertävät ajan perusteella samalla tavalla kaikissa ampumissuunnissa. Laserissa on 1872 pyörivää S-kirjainta sekunnissa, noin 1,83 pikselin välein, jotta purske näyttää yhtenäiseltä viivalta.

Liike käyttää pikseleitä sekunnissa ja pelilogiikka kiinteää 1/156 sekunnin aika-askelta. Tulipallojen lämpökenttä, jäähdytys, sivuttaisvaellus ja väripaletti pohjautuvat paikallisen Flaming-June-projektin toteutukseen. Tulianimaatiot ja alusten kuvat lasketaan/ladataan valmiiksi, ja hohdon osuma-alue kattaa vain tulipallon ytimen.

Alusten koko on 36 × 48 pikseliä eli neljäsosa aiemmasta leveydestä ja korkeudesta. Horde sisältää oletuksena 40 vihollista. Vihollisten hyppy kestää 0,4 sekuntia, ja laskeutumista seuraa joka kerta satunnainen 0,35–1,3 sekunnin tauko. Myös ensimmäisen hypyn aloitusaika arvotaan erikseen jokaiselle viholliselle. Vihollisten välissä on 48 pikseliä. Nopeuksia, välejä ja rainbow-asetta voi säätää `round43.py`:n alun vakioista; hyppyjen ajoitus on `Enemy`-luokassa.

Rivinvaihto ohittaa rivit, joilla viholliset kulkevat vastaan. Myös muiden vihollisten meneillään olevien rivinvaihtojen laskeutumisrivit huomioidaan. Samansuuntaisesti liikkuvalle riville voi liittyä. Koko pudotusreitti varataan rivinvaihdon ajaksi: varatulla reitillä olevat tai sille siirtyvät viholliset odottavat, kunnes reitti vapautuu.

## Testit

`uv run python -m unittest discover -s tests -v`

Testit käyttävät SDL:n dummy-ajuria eivätkä avaa fullscreen-ikkunaa.

## Tasot ja pisteet

Jokainen tuhottu vihollinen antaa 100 pistettä. Pisteet, taso ja elämät näkyvät ruudun alareunassa. Pelkkä osuma ei anna pisteitä eikä pudota powerupia.

Kun kaikki 40 vihollista on tuhottu, seuraavan tason `LEVEL 2`, `LEVEL 3` jne. teksti feidautuu keskelle ruutua. Siirtymä kestää 2,4 sekuntia; vanhat ammukset poistuvat, ja uusi horde syntyy tekstin hävittyä. Pelaajan elämät, pisteet, rainbow-lataukset ja salamalataukset säilyvät.

Tason numero määrää vihollisten hitpointsit: tasolla 1 yksi, tasolla 2 kaksi, tasolla 3 kolme jne. Selvinnyt vihollinen välähtää valkoisena 0,12 sekuntia osumasta. Liike ja hyppyjen rytmi nopeutuvat 10 % edellisestä tasosta (1×, 1,1×, 1,21× jne.). Ammusten nopeus ja ampumisvälit säilyvät ennallaan.

## Highscore

Kymmenen parasta tulosta tallentuvat projektin `highscores.json`-tiedostoon ja säilyvät käynnistysten välillä. Lista näyttää pisteet ja saavutetun tason, ja nykyinen tulos korostetaan keltaisella, jos se mahtuu listalle. Uusi peli aloittaa tasolta 1, kolmella elämällä, nollapisteillä ja ilman aselatauksia.

Jokainen pelaajan laukaus (tulipallo, rainbow-purskeen aloitus tai salama) synnyttää tykin suulle pienen oranssin liekkipurkauksen ja ylöspäin nousevaa savua. Vihollisen laukauksen purkaus on purppurainen ja suuntautuu alaspäin; savu nousee ylöspäin. Puolen sekunnin animaatio käyttää samaa lämpökentän, jäähdytyksen ja sivuttaisvaelluksen tekniikkaa sekä lämpöpalettia kuin tulipallot. Animaation kuvat lasketaan valmiiksi, eivätkä välähdys tai savu aiheuta osumia.

Pelin päättyessä voit kirjoittaa highscore-nimen (enintään 24 merkkiä, välilyönnit ja ääkköset sallittu). Backspace poistaa merkin ja Enter tallentaa tuloksen. Tyhjälle tai pelkkiä välilyöntejä sisältävälle nimelle arvotaan John Doe tai Jane Doe. Tallennuksen jälkeen välilyönti aloittaa uuden pelin. Myös Esc tai ikkunan sulkeminen nimikentässä tallentaa tuloksen. Vanhoille nimettömille tuloksille näytetään John Doe.

## Pääkanuunan tehostus

Oranssi C+-powerup lisää pääkanuunan vahinkoa yhdellä HP:llä joka keräyksellä. Lähtöteho on 1 HP/osuma, ja pelin vasemmassa yläkulmassa näkyy `MAIN CANNON POWER: N/4 HP`. Pudotustodennäköisyys on 2,5 % ja tehostuksella on oma 12 sekunnin pudotustauko.

Ammuksen väri on alussa oranssi, teholla 2 punaisempi, teholla 3 sinisempi ja teholla 4 valkoinen. Teho on enintään 4 HP/osuma, ja sen saavutettua C+-poweruppeja ei enää pudoteta. Jo ruudulla olevat C+-powerupit poistuvat. Laukaus säilyttää ampumishetken vahingon ja värin. Tehostus säilyy elämän menetyksessä ja tasojen välillä; uusi peli alkaa teholla 1. Rainbow ja salama toimivat ennallaan.

Powerupit sijoitetaan vapaisiin paikkoihin vähintään 8 pikselin välein, myös saman vihollisen pudottaessa useita eri poweruppeja.

## Vihollistyypit

Vihollistyypit toistuvat kuuden tason kierrossa: `vihu1.png`, `vihu2.png`, `vihu3.png`, `vihu4.png`, pikselilinnut ja valkoinen rect-hahmo. Taso 7 käyttää taas vihu1-kuvaa, taso 11 lintuja ja taso 12 rect-hahmoa. Hitpointsit ja 10 % nopeutus jatkavat kasvua todellisen tason mukaan.

Linnut muistuttavat annettua Round42-kuvaa: pienet punaiset, syaanit, magentat tai keltaiset pikselisiivet ja lyhyt keskivartalo. Siivet vaihtavat karkean animaation kuvia kuusi kertaa sekunnissa. Linnut liikkuvat tasaisesti sivusuunnassa ilman hyppyjä, vaihtavat reunassa riviä alaspäin ja jatkavat vastakkaiseen suuntaan. Perusnopeus on 20 pikseliä sekunnissa ennen tasokohtaista nopeutusta.

Lintutason jälkeen tuleva rect-hahmo hyppii kuten aiemmat alukset. Kuusi alkuperäistä `pg.draw.rect`-komentoa löytyivät commitista `3e8021c` (Base game working); silmien ja alareunan aukot ovat läpinäkyviä.

Debug: F5 siirtyy heti seuraavalle tasolle, myös tasonvaihtoanimaation aikana. Elämät, pisteet ja asetehostukset säilyvät. Edellisen tason viholliset, ammukset ja powerupit poistetaan ilman pistehyvitystä.
