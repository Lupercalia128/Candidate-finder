# Pro&Pro · Candidate finder

Python/Streamlit-MVP för att samla yrkesunderlag och prioritera **manuell granskning** av möjliga managementkonsulter. CSV, manuell inmatning och 15 helt fiktiva demoprofiler fungerar utan API-nyckel. Ingen automatiserad kontakt med kandidater eller automatiska anställningsbeslut.

## Starta

Python 3.12 rekommenderas. Kör från projektets rot:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

På Windows: använd `.venv\Scripts\python` istället. Öppna Streamlits lokala adress i din egen utvecklingsmiljö. Välj **Ladda fiktiva demoprofiler** på Sök kandidater. Importen kan upprepas utan dubbletter. Demodata läses inte in automatiskt i databasen.

```sh
.venv/bin/python -m pytest -q
```

Tester täcker kategorier A–D och överlapp, saknade uppgifter, poäng och källor, CSV/Excel, databasens dubbletter/radering, mockad sök-API och Streamlits demo-, filter-, gransknings- och raderingsflöde.

## Arbetsflöde

1. **Sök kandidater:** CSV, manuell profil eller frivillig webbsökning.
2. **Kandidatöversikt:** fritext, ort, företag, kategorier, status och erfarenhetsintervall. Okänd erfarenhet kan inkluderas separat. Sortering efter belägg eller täckning. Välj person i listan under tabellen och öppna Kandidatdetaljer i sidomenyn.
3. **Kandidatdetaljer:** granska underlag, primär/sekundär kategori, källor, saknade uppgifter, anteckningar och status. Komplettera yrkesuppgifter och belägg direkt i detaljsidans formulär och bekräfta källverifiering. Radering kräver en uttrycklig bekräftelse.
4. Export till CSV och Excel av det filtrerade urvalet. Exportfiler är separata personuppgiftskopior och måste omfattas av samma lagringsregler.

## Datamodell och CSV

`Candidate` innehåller namn/sidtitel, ort, roll, företag, dokumenterade erfarenhetsår, utbildning, källänk, yrkesbeskrivning, konsulterfarenhet, strukturerade belägg, upptäcktsflagga, status och anteckningar. SQLite lagrar profilen som JSON plus ID, unik källidentitet och skapandetid. Databassökväg styrs av `CANDIDATE_DB` (standard `data/candidates.sqlite3`).

CSV använder UTF-8 och kommatecken. Obligatoriska kolumner: `name,source_url`. Valfria: `city,role,company,years,education,description,consultant,evidence,discovery`. `years` är numeriskt eller tomt; booleska värden är true/false. `evidence` är JSON i en korrekt CSV-citerad cell. Se [demo_candidates.csv](data/demo_candidates.csv) för ett komplett format. Varje rad valideras; felaktiga rader visas och giltiga kan importeras separat.

Exempel på beläggobjekt:

```json
{"change": {"text": "Ledde införandet av ny produktionsprocess i tre fabriker.", "level": 2, "confidence": "Medel", "source": "https://example.com/profil"}}
```

Kriterier: `change`, `customer`, `analysis`, `business`, `responsibility`, `industry`. Varje belägg måste ha text och en nivå 1–3. Källa är obligatorisk på profilen och används som standard för belägget. Säkerhet: Låg/Medel/Hög, standard Låg. **Användaren ansvarar för att beläggen faktiskt framgår av källan.** Inga meriter extraheras automatiskt ur fri text; MVP:n bedömer inte negativa formuleringar eller bevisens sanningshalt.

Dubbletter identifieras med normaliserad käll-URL (query-parametrar, fragment och avslutande snedstreck tas bort). Import skriver aldrig över en befintlig profil eller dess anteckningar. Samma person från olika käll-URL:er måste i denna MVP identifieras och sammanföras manuellt; samma namn räcker inte för säker identitetsmatchning. Använd kanoniska profillänkar, inte sök-URL:er vars identitet ligger i query-parametrar.

## Transparent modell

Vikter: förändringsledning 3, kundrelationer 3, analys/konsulthantverk 2, affärsutveckling 2, ansvar 2, bransch 1. Nivåer anges vid dokumentation: 1 relevant erfarenhet, 2 konkret ansvar, 3 dokumenterat resultat. Poäng = summan av nivå × vikt / 39 × 100. Täckning = andel vikt med dokumenterade belägg. Säkerheten avser underlagets kvalitet, anges av dokumenteraren och påverkar inte poängen.

**Poängen mäter mängden dokumenterade belägg, inte människans förmåga.** Saknat underlag visas som ”Okänt – kräver manuell bedömning”, utan nollnivå per kriterium. Täckning visas alltid intill totalpoängen. Tätare dokumenterade profiler kan få högre prioritet; använd inte denna ordning som ett automatiskt avslag eller för anställningsbeslut. Erfarenhetsintervall används som användarstyrt filter, inte åldersproxy eller gissning från utbildningsdatum.

Kategorier, i prioritetsordning:

- B: uttryckligen dokumenterad erfarenhet från managementkonsultföretag.
- C: 3–5 dokumenterade erfarenhetsår samt belägg för ansvar.
- A: belägg för intern förändringsledning, utan markerad konsulterfarenhet.
- D: otillräckligt underlag eller andra profiler för manuell granskning.

Alla matchande kategorier visas. Upptäckta söksidor får D, okända meriter och 0 % täckning oavsett sökutdrag. Utbildning, personliga egenskaper, ålder, kön och andra skyddade egenskaper påverkar inte modellen. Ödmjukhet, ambition, nyfikenhet och samarbete visas endast som intervjufrågor.

## Frivillig sök-API och framtida AI

Kopiera `.env.example` till `.env` och konfigurera `BRAVE_SEARCH_API_KEY` lokalt via en säker kanal. Sökadaptern anropar endast `https://api.search.brave.com/res/v1/web/search`, med timeout och TLS-verifiering, och hämtar aldrig LinkedIn eller andra profilsidor. I molnmiljön behöver API-domänen godkännas och en nyckel bindas till den via miljöinställningarna. Sök-API-integrationen testas med mockade svar; liveanrop kräver egen licens/nyckel och är inte verifierat utan dessa.

Kontrollera att ert API-avtal uttryckligen medger aktuell användning och lagring av sökutdrag; en API-nyckel ger inte i sig rätt till all vidarebehandling. Användaren bekräftar rättigheterna före sökning. Sökresultatens sidtitlar sparas som obekräftade profiler, inte som verifierade namn. Geografiska synonymer och relaterade roller genererar frågor. Erfarenhetsår i sökfrågan är endast en söksignal; dessa tilldelas aldrig en profil som fakta.

`SearchProvider` är ett separat gränssnitt för ett framtida licensierat rekryterings-API. `OptionalAnalyzer` är en ej aktiverad anslutningspunkt för framtida AI; ingen data skickas till AI i MVP:n. En framtida implementation måste ha separat uttryckligt godkännande av datadelning, rätt att skicka underlaget, avtal med leverantören och källspårbara resultat som granskas manuellt.

## Innan riktiga personuppgifter används

MVP:n är avsedd för lokal utveckling och fiktiva data. Den saknar inloggning, behörighetsstyrning, krypterad databas, automatisk gallring och revisionslogg och ska inte exponeras offentligt med verkliga personuppgifter.

Pro&Pro behöver före skarp användning dokumentera rättslig grund och ändamål, eventuell intresseavvägning, vilka källor som får användas, informationsskyldighet (inklusive indirekt insamling), rutiner för rättelse, invändning och radering samt vem som ansvarar. Fastställ och genomför en motiverad lagringstid med regelbunden manuell gallring tills automatisk gallring finns. Minimera fria anteckningar och importera inga känsliga eller ovidkommande personuppgifter. Säkerställ personuppgiftsbiträdesavtal och eventuella tredjelandsöverföringar där det behövs.

Raderingsknappen tar bort posten och aktiverar SQLite secure_delete för lagringen. Gallra även exporter, säkerhetskopior och andra kopior enligt beslutad rutin; säker överskrivning på fysiska lagringsmedier garanteras inte av SQLite. Databasen, `.env` och exporter ska skyddas med lämpliga filrättigheter och organisatoriska åtkomstregler. Exporter kan innehålla kandidatuppgifter och anteckningar.

## Kodstruktur

- `candidate_finder/model.py`: datamodell och validering.
- `ingestion.py`: CSV och export med skydd mot kalkylbladsformler.
- `storage.py`: SQLite, dubbletter, uppdatering och radering.
- `analysis.py`: kriterier, kategorisering och AI-anslutningspunkt.
- `search.py`: frågegenerering, datakällegränssnitt och Brave-adapter.
- `app.py`: tre Streamlit-sidor.

Varje molnuppgift har redan en isolerad miljö. Använd befintlig checkout; skapa ingen extra Git-worktree för installation eller start.
