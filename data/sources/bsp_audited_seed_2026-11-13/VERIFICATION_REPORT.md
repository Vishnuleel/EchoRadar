# Blue Science Park data verification report

Audit date: 2026-11-13
Primary source: https://www.bluesciencepark.se/bli-medlem/

## Result
- 55 organisation profiles/records in this audited seed; all 55 have an opened Blue Science Park profile page in this audit trail.
- The original 43-record package was incomplete and had missing fields.
- 12 additional organisations were added after following official Blue Science Park "Fler medlemmar" links and opening their official member profile pages.
- The official directory's initial rendered view shows 16 entries and a dynamic "Ladda mer" control.
- Blue Science Park describes its ecosystem as 80+ members. Therefore, 55 records is **not complete directory coverage**.

## Corrections made
- Replaced several guessed or empty profile descriptions and profile fields with values copied from the official individual Blue Science Park member pages.
- Corrected `Länsstyrelsen Blekinge` profile slug from `/medlem/lanstyrelsen-blekinge/` to `/medlem/lansstyrelsen-blekinge/`.
- Added Lysa's actual profile URL `/medlem/lysa/`.
- Added organisations discovered through official "Fler medlemmar" profile links: WIP, Telenor, Försäkringskassan, Indigo Ipex, Nexer, Hi Story, Veridens, Nicon, Factor10, Techinova, Kingspan BAGA and Roxtec.
- Kept DNV Cyber employee range blank because the official profile shows no employee-range value. Länsstyrelsen Blekinge was enriched from its corrected live profile URL.
- Kept any unpublished field blank and marked it in `missing_fields`.

## Remaining missing information
- DNV Cyber: employee range is not published in the retrieved official profile.
- No other core profile fields are blank in this audited seed.

## Important limitations
1. This is a verified partial dataset, not a complete 80+ directory export.
2. The live directory has a dynamic Load More control. The crawler must run against the live site and continue until no more cards are added.
3. Blue Science Park's application page distinguishes member and partner types, but individual profiles do not consistently publish the classification. Do not guess the classification for each organisation.
4. A company profile can show a company-wide website and a city/location value; do not interpret those as a specific office street address.
5. Employee ranges and founding years are transcribed from Blue Science Park profile pages; they are not independently audited against company registries.

## Official source pages checked
- Directory: https://www.bluesciencepark.se/bli-medlem/
- 3D Vision: https://www.bluesciencepark.se/medlem/3d-vision/
- AddSecure: https://www.bluesciencepark.se/medlem/addsecure/
- Affärsverken: https://www.bluesciencepark.se/medlem/affarsverken/
- AFRY: https://www.bluesciencepark.se/medlem/afry/
- AllBinary: https://www.bluesciencepark.se/medlem/allbinary/
- Almi: https://www.bluesciencepark.se/medlem/almi/
- Atea: https://www.bluesciencepark.se/medlem/atea/
- Ballou: https://www.bluesciencepark.se/medlem/ballou/
- Baltic Offshore: https://www.bluesciencepark.se/medlem/baltic-offshore/
- Blekinge Business Incubator: https://www.bluesciencepark.se/medlem/blekinge-business-incubator/
- BTH: https://www.bluesciencepark.se/medlem/blekinge-tekniska-hogskola/
- C Marine AB: https://www.bluesciencepark.se/medlem/c-marine-ab/
- Cleura: https://www.bluesciencepark.se/medlem/cleura/
- Compani 56: https://www.bluesciencepark.se/medlem/compani-56/
- DNV Cyber: https://www.bluesciencepark.se/medlem/dnv-cyber/
- DXC Technology: https://www.bluesciencepark.se/medlem/dxc-technology/
- EmbeddedArt: https://www.bluesciencepark.se/medlem/embeddedart/
- GE 99: https://www.bluesciencepark.se/medlem/ge-99/
- Ocean Harvesting: https://www.bluesciencepark.se/medlem/ocean-harvesting/
- Stena Line: https://www.bluesciencepark.se/medlem/stena-line/
- Njord X: https://www.bluesciencepark.se/medlem/njord-x/
- HiQ: https://www.bluesciencepark.se/medlem/hiq/
- Sweco: https://www.bluesciencepark.se/medlem/sweco/
- NKT: https://www.bluesciencepark.se/medlem/nkt/
- Ericsson: https://www.bluesciencepark.se/medlem/ericsson/
- Knowit: https://www.bluesciencepark.se/medlem/knowit/
- Yellowfish: https://www.bluesciencepark.se/medlem/yellowfish/
- MJ MarCable Consulting AB: https://www.bluesciencepark.se/medlem/mj-marcable-consulting-ab/
- Kiwa: https://www.bluesciencepark.se/medlem/kiwa/
- Hundtjänst Blekinge AB: https://www.bluesciencepark.se/medlem/hundtjanst-blekinge-ab/
- Region Blekinge: https://www.bluesciencepark.se/medlem/region-blekinge/
- SAAB: https://www.bluesciencepark.se/medlem/saab/
- Karlskrona Kommun: https://www.bluesciencepark.se/medlem/karlskrona-kommun/
- Försvarsmakten: https://www.bluesciencepark.se/medlem/forsvarsmakten/
- FMV: https://www.bluesciencepark.se/medlem/fmv/
- Kustbevakningen: https://www.bluesciencepark.se/medlem/kustbevakningen/
- Softhouse: https://www.bluesciencepark.se/medlem/softhouse/
- Midcon: https://www.bluesciencepark.se/medlem/midcon/
- Malvacom: https://www.bluesciencepark.se/medlem/malvacom/
- Spirius: https://www.bluesciencepark.se/medlem/spirius/
- Lassen Construction: https://www.bluesciencepark.se/medlem/lassen-construction/
- Lysa: https://www.bluesciencepark.se/medlem/lysa/
- WIP: https://www.bluesciencepark.se/medlem/wip/
- Telenor: https://www.bluesciencepark.se/medlem/telenor/
- Försäkringskassan: https://www.bluesciencepark.se/medlem/forsakringskassan/
- Indigo Ipex: https://www.bluesciencepark.se/medlem/indigo-ipex/
- Nexer: https://www.bluesciencepark.se/medlem/nexer/
- Hi Story: https://www.bluesciencepark.se/medlem/hi-story/
- Veridens: https://www.bluesciencepark.se/medlem/varidens/
- Nicon: https://www.bluesciencepark.se/medlem/nicon/
- Factor10: https://www.bluesciencepark.se/medlem/factor10/
- Techinova: https://www.bluesciencepark.se/medlem/techinova/
- Kingspan BAGA: https://www.bluesciencepark.se/medlem/kingspan-baga/
- Roxtec: https://www.bluesciencepark.se/medlem/roxtec/

## Recommendation for NEXUS
Use this file as a corrected, source-linked seed. Then run the dynamic directory crawler and reconcile the full set. A record should only become `directory_complete=true` after the full directory crawl has reached a stable end and the organisation's profile has been checked.
