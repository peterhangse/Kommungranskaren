# Granskning-Coach

AI-driven assistent för att granska kommunala bolags ekonomi. Specialiserad för Karlshamns kommun.

## Funktioner

- **Begära handlingar**: Generera korrekta begäran enligt Tryckfrihetsförordningen 2 kap
- **Importera data**: Läs in Excel/CSV-filer med transaktionsdata
- **Automatisk analys**: Hitta avvikelser med SQL-baserad mönsterdetektering
- **AI-coach**: Få svar på frågor om bokföring, offentlighetsprincipen och granskningsmetodik
- **Leverantörskontroll**: Sök information om leverantörer med webbsökning
- **Exportera**: Ladda ner rapporter i Markdown, faktarutor för artiklar

## Installation

### Lokalt

```bash
# Klona eller kopiera projektet
cd Kommungranskaren

# Skapa virtuell miljö
python -m venv venv
source venv/bin/activate  # macOS/Linux
# eller: venv\Scripts\activate  # Windows

# Installera dependencies
pip install -r requirements.txt

# Skapa .env-fil med din API-nyckel
cp .env.example .env
# Redigera .env och lägg till din ANTHROPIC_API_KEY

# Kör applikationen
streamlit run app.py
```

### Streamlit Cloud

1. Pusha projektet till GitHub
2. Gå till [share.streamlit.io](https://share.streamlit.io)
3. Välj ditt repo och `app.py`
4. Lägg till `ANTHROPIC_API_KEY` i Secrets-inställningarna

## Användning

### 1. Begär handlingar

Gå till **Begäran**-sidan och fyll i:
- Bolagsnamn (t.ex. "Karlshamns Energi AB")
- Typ av handlingar (huvudbok, fakturor, etc.)
- Tidsperiod

Systemet genererar en korrekt begäran enligt TF 2 kap.

### 2. Importera data

När du fått svar från bolaget:
1. Gå till **Import**
2. Ladda upp Excel-filen
3. Justera kolumnmappning om nödvändigt
4. Klicka "Rensa och importera"

### 3. Analysera

Under **Analys**:
1. Klicka "Kör automatisk analys"
2. Granska varningsflaggorna
3. Använd sökfunktionen för att undersöka specifika transaktioner

### 4. Korsreferera leverantörer

På **Korsreferens**-sidan:
1. Ange leverantörsnamn
2. Systemet söker på webben efter information om ägarstruktur och kopplingar

### 5. Exportera

Under **Export** kan du ladda ner:
- Rensad transaktionsdata (CSV/Excel)
- Granskningsrapport (Markdown)
- Faktaruta för artikeln (TXT)

## Teknisk stack

- **Frontend**: Streamlit
- **AI**: Claude Sonnet via Anthropic API
- **Databehandling**: Pandas, SQLite
- **Webgrafer**: Plotly

## Känsliga konton

Systemet flaggar automatiskt transaktioner på:
- 5800-5899: Resekostnader
- 6071-6072: Representation
- 6550: Konsultkostnader
- 5940: Sponsring

## Licens

Endast för internt bruk i granskningsprojekt.

## Kontakt

Utvecklad för granskning av Karlshamns kommuns bolag.
