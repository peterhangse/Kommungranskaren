# AGENTS.md — Kommungranskaren

**Läs `CONTEXT.md` först** innan du ändrar något.

## Kontrakt

- Ändrar du funktioner, dataväg eller struktur: **uppdatera `CONTEXT.md`
  i samma commit**.
- A) Allt utom ROUGH måste fungera i Streamlit `streamlit run app.py` med bara
  `ANTHROPIC_API_KEY` satt (app/.env). B) **Data lever bara i minne/session** —
  lägg inte till egen state i disk utan att säga till.
- Appen är en **transaktionskoach för importerad ekonomi**, inte en
  PDF-dokumentsökare — håll fokus.
- `plotly` är närvarande men OANVÄND i requirements — bygg inte tester som
  antar att den renderar grafer.
- Ingen automatisk test-suite idag: verifiera manuellt i Streamlit-UI
  (t.ex. import av demo_data.csv → analys → export).