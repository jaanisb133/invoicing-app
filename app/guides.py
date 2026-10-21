"""Public guides (/celvedis). Drafts are reachable by URL but noindex and left out
of the sitemap and the guide index until `published` is True. Publishing: set it
True and `published_on` to the day; later content changes bump `updated` only.

Every claim was checked against the law texts on likumi.lv (21.10.2026); the
sources list only what was actually read."""

GUIDES = [
    {
        "slug": "e-rekini-2028",
        "title": "E-rēķini Latvijā: obligāti no 2028. gada",
        "description": "Kopš 2025. gada e-rēķini ir obligāti rēķiniem budžeta iestādēm, no 01.01.2028 arī starp uzņēmumiem. Kas ir e-rēķins un kā sagatavoties.",
        "lede": "Uzziniet, no kura datuma strukturētie e-rēķini Latvijā ir obligāti, kas par e-rēķinu neskaitās un kas mazam uzņēmumam jādara jau tagad.",
        "updated": "2026-10-21",
        "published": True,
        "published_on": "2026-10-21",
        "sources": [
            ("Grāmatvedības likums (likumi.lv)", "https://likumi.lv/ta/id/324249-gramatvedibas-likums"),
            ("Grozījumi Grāmatvedības likumā, 31.10.2024 (likumi.lv)", "https://likumi.lv/ta/id/356316-grozijumi-gramatvedibas-likuma"),
            ("MK 09.12.2025 noteikumi Nr. 749 par strukturētu elektronisko rēķinu apriti (likumi.lv)", "https://likumi.lv/ta/id/365040"),
            ("Oficiālās elektroniskās adreses likums (likumi.lv)", "https://likumi.lv/ta/id/283229-oficialas-elektroniskas-adreses-likums"),
            ("LV portāls: Obligātie e-rēķini visiem uzņēmumiem būs jāievieš no 2028. gada", "https://lvportals.lv/dienaskartiba/377035-obligatie-e-rekini-visiem-uznemumiem-bus-jaievies-no-2028-gada-2025"),
        ],
    },
    {
        "slug": "rekina-rekviziti",
        "title": "Rēķina rekvizīti: kas jānorāda rēķinā Latvijā",
        "description": "Kontrolsaraksts, kas jānorāda PVN rēķinā un rēķinā bez PVN saskaņā ar PVN likuma 125. pantu un Grāmatvedības likuma 11. pantu.",
        "lede": "Uzziniet, kuri rekvizīti ir obligāti katrā rēķinā, kuri papildus vajadzīgi PVN rēķinā un kad rēķinā jāieraksta īpaša norāde.",
        "updated": "2026-10-21",
        "published": True,
        "published_on": "2026-10-21",
        "sources": [
            ("Pievienotās vērtības nodokļa likums (likumi.lv)", "https://likumi.lv/ta/id/253451-pievienotas-vertibas-nodokla-likums"),
            ("Grāmatvedības likums (likumi.lv)", "https://likumi.lv/ta/id/324249-gramatvedibas-likums"),
        ],
    },
    {
        "slug": "rekina-paraugs",
        "title": "Rēķina paraugs ar PVN: katrs lauks paskaidrots",
        "description": "Pareizi aizpildīta PVN rēķina paraugs: numurs, datumi, piegādātājs, saņēmējs, rindas un PVN aprēķins, ar paskaidrojumu, kāpēc katrs lauks vajadzīgs.",
        "lede": "Apskatiet aizpildītu PVN rēķinu lauku pa laukam un uzziniet, ko prasa likums, kā aprēķina PVN un kad šis paraugs Jums neder.",
        "sample_title": "PVN rēķina paraugs",
        "sample_pages": "1 lapa",
        "sample_alt": "PVN rēķina paraugs: SIA „Ziemeļu Kadrs” rēķins Nr. 26-041 SIA „Bērzu Darbnīca” par produktu fotografēšanu",
        "updated": "2026-10-21",
        "published": True,
        "published_on": "2026-10-21",
        "sources": [
            ("Pievienotās vērtības nodokļa likums (likumi.lv)", "https://likumi.lv/ta/id/253451-pievienotas-vertibas-nodokla-likums"),
            ("Grāmatvedības likums (likumi.lv)", "https://likumi.lv/ta/id/324249-gramatvedibas-likums"),
        ],
    },
    {
        "slug": "pasnodarbinata-rekins",
        "title": "Pašnodarbinātā rēķins bez PVN: kā to izrakstīt",
        "description": "Kā pašnodarbinātais vai PVN nemaksātājs izraksta rēķinu: obligātie rekvizīti, numurēšana, paraksts, glabāšana un kad jāreģistrējas PVN maksātājam.",
        "lede": "Uzziniet, kas jānorāda rēķinā, ja neesat PVN maksātājs, kā rēķinus numurēt un glabāt un pie kāda apgrozījuma jāreģistrējas PVN maksātāju reģistrā.",
        "updated": "2026-10-21",
        "published": True,
        "published_on": "2026-10-21",
        "sources": [
            ("Grāmatvedības likums (likumi.lv)", "https://likumi.lv/ta/id/324249-gramatvedibas-likums"),
            ("Pievienotās vērtības nodokļa likums (likumi.lv)", "https://likumi.lv/ta/id/253451-pievienotas-vertibas-nodokla-likums"),
            ("MK 31.05.2022 noteikumi Nr. 322 par grāmatvedību vienkāršā ieraksta sistēmā (likumi.lv)", "https://likumi.lv/ta/id/332883"),
            ("Elektronisko dokumentu likums (likumi.lv)", "https://likumi.lv/ta/id/68521-elektronisko-dokumentu-likums"),
            ("LV portāls: PVN izmaiņas no 2024. gada", "https://lvportals.lv/skaidrojumi/358988-pvn-izmainas-no-2024-gada-pretimnaksanas-solitis-mazajam-biznesam-un-es-cina-ar-nemaksatajiem-2024"),
        ],
    },
    {
        "slug": "apgriezta-maksasana",
        "title": "PVN apgrieztā maksāšana: kad un kā to norādīt rēķinā",
        "description": "Kas ir nodokļa apgrieztā maksāšana Latvijā, kuriem darījumiem to piemēro, kurš maksā PVN un kas jāraksta rēķinā. Ar rēķina rindas piemēru.",
        "lede": "Uzziniet, kuriem iekšzemes darījumiem PVN maksā saņēmējs, kas tad jāraksta rēķinā un kā saņēmējs šo PVN uzrāda savā deklarācijā.",
        "updated": "2026-10-21",
        "published": True,
        "published_on": "2026-10-21",
        "sources": [
            ("Pievienotās vērtības nodokļa likums (likumi.lv)", "https://likumi.lv/ta/id/253451-pievienotas-vertibas-nodokla-likums"),
        ],
    },
]
