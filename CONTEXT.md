# CONTEXT.md — Kommungranskaren (Granskning-Coach)

**AI-stödsverktyg för grävande journalistik kring kommunala bolags
ekonomi/bokföring** (transaktionsnivå), byggd för Karlshamns kommun.
Streamlit-app som guidar genom: begäran-ut-ut, import/renault av
transaktionsdata, röd-flaggsanalys, korsreferens på nätet, rapport-export
och "Coach"-chat över hela materialet.

## Teknik (verifierat)

- **Python 3 + Streamlit** (`streamlit run app.py`). Kräver `ANTHROPIC_API_KEY`
  i `app/.env`.
- **anthropic** claude-sonnet-4 + web_search; **pandas + openpyxl + xlsxwriter**
  (Excel), **PyPDF2** (PDF-texting), **sqlite3 in-memory** (är Relational DB
  byggd i kod varje session). **plotly ligger i requirements men används INTE**
  — död dependency.
- Inga transvektordata hämtas från `retrieval/Biesse` — appen är ett oberoende
  chat-coach över **den importerade datan**.

## Struktur

```
app.py          — EN enda Streamlit-file med alla sidor inline (45 sidolöp)
modules/        — hjälpmoduler (excel-import, clean, analys)
prompts/        — mappar till "undersidor"-fraser (dead/deprecated enligt rapport)
knowledge/*.md  — prompts-innehåll som injiceras i körningen (race-condition-lösning)
demo_data.csv   — demo-transaktionsdata
```

## Funktioner (verifierade)

1. **Begäran ut** — genererar tjänste-/försörjningsbrev (2 kap. OSL) som PDF.
2. **Import** — Excel/CSV/PDF → rent + BAS-2023/2024-kategorisering
   (tilläggsförklaringar muistio) + "Intressanta konton"-detektion.
3. **Analys** — 4 inbyggda SQL-röd-flaggor (klumpsummor på konton,
   närstående, avvikelser) + manuellt konto/kostnadsställe-filter.
4. **Korsreferens** — söker på internet (web_search) kring
   motparter/belopp som Analytics tar fram. **Kräver internet.
5. **Export** — sammanställ kategoriserad data → Excel.
6. **Coach** — chat över alla dokument.

## Present & state

- Databasen skapas/skickas i minne per session — **INGEN permanent
  lagring**. `SSE`/session-state lagrar filtreringsval.
- `streamlit rerun` på varje widget-värde; allt sker i app-processen.

## Köra / deploya

```bash
cd app && pip install -r requirements.txt  # eller venv
cp ../.env.example .env                     # fyll ANTHROPIC_API_KEY
streamlit run app.py
```

- Cloud: Streamlit Cloud (deploy-sim > secrets).

## Gotchas / policy

- **Gammal CONTEXT är delvis felställd:** den här appen gör INTE
  "retrieval-assisted sökning av kommunala dokument/beslut", har inte
  `data/`-lagring (data-i-minne), och har INTE en "AiBi/Bosse NO_UNDERLAG"-
  parallell — den är ett eget streamlit-verktyg som analyserar importdata.
- `plotly` i requirements är oanvänd — gör om du introducerar grafer; ta inte
  bort plötsligt om andra moduler beror.
- Data spendras helt sessionellt — hotar SDD:arkiv ger behov av export.

## Vet-läge

Ingen automatisk test-suite; manuell verifiering via Streamlit-UI.