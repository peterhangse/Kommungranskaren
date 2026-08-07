"""
Granskning-Coach - AI-driven assistant for municipal financial investigation.

Main Streamlit application with multi-page navigation:
- Start: Overview and getting started
- Begäran: Generate document request letters
- Import: Upload and clean transaction data
- Analys: Analyze transactions for red flags
- Korsreferens: Research suppliers
- Export: Download reports and data
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import modules
from modules.claude_coach import GranskningsCoach
from modules.file_handler import handle_upload, detect_columns, validate_data
from modules.data_cleaner import (
    auto_clean, categorize_accounts, flag_interesting_accounts, extract_year_month
)
from modules.analyzer import analyze_transactions, ai_analyze_flags, generate_summary, search_transactions
from modules.exporter import (
    export_to_csv, export_to_excel, export_flags_to_markdown, 
    generate_factbox, create_download_buttons
)


# Page config
st.set_page_config(
    page_title="Granskning-Coach",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'coach' not in st.session_state:
    st.session_state.coach = GranskningsCoach()

if 'data' not in st.session_state:
    st.session_state.data = None

if 'column_mapping' not in st.session_state:
    st.session_state.column_mapping = {}

if 'flags' not in st.session_state:
    st.session_state.flags = []

if 'summary' not in st.session_state:
    st.session_state.summary = {}

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []


# Sidebar navigation
st.sidebar.title("🔍 Granskning-Coach")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["Start", "Begäran", "Import", "Analys", "Korsreferens", "Export"],
    format_func=lambda x: {
        "Start": "🏠 Start",
        "Begäran": "📝 Begära handlingar",
        "Import": "📤 Importera data",
        "Analys": "🔎 Analysera",
        "Korsreferens": "🔗 Korsreferens",
        "Export": "📥 Exportera"
    }.get(x, x)
)

# Show data status in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("Status")

if st.session_state.data is not None:
    st.sidebar.success(f"✅ {len(st.session_state.data):,} transaktioner")
    if st.session_state.flags:
        st.sidebar.warning(f"⚠️ {len(st.session_state.flags)} varningsflaggor")
else:
    st.sidebar.info("Ingen data importerad")

st.sidebar.markdown("---")
st.sidebar.caption("v1.0 | Karlshamn-granskning")


# ============================================================================
# PAGE: START
# ============================================================================
if page == "Start":
    st.title("🔍 Granskning-Coach")
    st.markdown("### Din AI-assistent för att granska kommunala bolag")
    
    st.markdown("""
    Välkommen! Granskning-Coach hjälper dig att:
    
    1. **Begära ut handlingar** från kommunala bolag enligt offentlighetsprincipen
    2. **Importera och rensa** ekonomidata från Excel-filer
    3. **Hitta avvikelser** automatiskt med SQL-analys och AI
    4. **Undersöka leverantörer** med webbsökning
    5. **Exportera rapporter** för publicering
    
    ---
    """)
    
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("⚠️ **Varning:** Ingen 'ANTHROPIC_API_KEY' hittades i miljön. AI-funktioner (som 'Fråga coachen' och automatisk textgenerering) kommer inte att fungera. Vänligen lägg till nyckeln i en `.env` fil.")
        st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💬 Fråga coachen")
        question = st.text_area(
            "Ställ en fråga om granskning, bokföring eller offentlighetsprincipen:",
            placeholder="T.ex. 'Vad innebär konto 6071?' eller 'Hur begär jag ut fakturakopior?'"
        )
        
        if st.button("Skicka fråga"):
            if question:
                with st.spinner("Tänker..."):
                    response = st.session_state.coach.ask(question)
                st.markdown("**Svar:**")
                st.markdown(response)
                
                # Add to history
                st.session_state.chat_history.append({
                    "question": question,
                    "answer": response
                })
    
    with col2:
        st.subheader("📚 Kom igång")
        
        with st.expander("Steg 1: Identifiera målbolag"):
            st.markdown("""
            Välj vilket kommunalt bolag du vill granska. 
            I Karlshamn finns bl.a.:
            - Karlshamns Energi AB
            - Karlshamnsbostäder AB
            - Kreativum Science Center
            """)
        
        with st.expander("Steg 2: Begär handlingar"):
            st.markdown("""
            Gå till **Begäran**-sidan för att generera en begäran om 
            allmänna handlingar. Du behöver inte ange varför du vill ha dem.
            """)
        
        with st.expander("Steg 3: Importera och analysera"):
            st.markdown("""
            När du fått Excel-filer, ladda upp dem under **Import**.
            Systemet rensar automatiskt datan och identifierar kolumner.
            Kör sedan **Analys** för att hitta misstänkta transaktioner.
            """)
    
    # Show chat history
    if st.session_state.chat_history:
        st.markdown("---")
        st.subheader("Tidigare frågor")
        for i, chat in enumerate(reversed(st.session_state.chat_history[-5:])):
            with st.expander(f"Q: {chat['question'][:50]}..."):
                st.markdown(f"**Fråga:** {chat['question']}")
                st.markdown(f"**Svar:** {chat['answer']}")


# ============================================================================
# PAGE: BEGÄRAN
# ============================================================================
elif page == "Begäran":
    st.title("📝 Begära ut handlingar")
    st.markdown("""
    Generera en formell begäran om allmänna handlingar enligt Tryckfrihetsförordningen 2 kap.
    Kommunala bolag är skyldiga att lämna ut handlingar skyndsamt.
    """)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        company = st.text_input(
            "Bolagsnamn",
            value="Karlshamns Energi AB",
            help="Namnet på det kommunala bolaget"
        )
        
        doc_types = st.multiselect(
            "Typ av handlingar",
            [
                "Huvudbok/Transaktionslista",
                "Fakturakopior",
                "Reserapporter",
                "Deltagarlistor vid representation",
                "Avtal med leverantörer",
                "Styrelseprotokoll",
                "Intern policy för representation",
                "Upphandlingsdokumentation"
            ],
            default=["Huvudbok/Transaktionslista"]
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            from_date = st.text_input("Från datum", "2023-01-01")
        with col_b:
            to_date = st.text_input("Till datum", "2023-12-31")
        
        accounts = st.multiselect(
            "Specifika konton (valfritt)",
            ["5800-5899 (Resor)", "6071-6072 (Representation)", "6550 (Konsulter)", "5940 (Sponsring)"],
            help="Lämna tomt för att begära hela huvudboken"
        )
    
    with col2:
        st.markdown("### Förhandsgranskning")
        
        if st.button("Generera begäran", type="primary"):
            if company and doc_types:
                with st.spinner("Genererar begäran..."):
                    # Parse account codes
                    account_codes = []
                    for acc in accounts:
                        code = acc.split(" ")[0]
                        account_codes.append(code)
                    
                    letter = st.session_state.coach.generate_request_letter(
                        company_name=company,
                        document_types=doc_types,
                        date_range=(from_date, to_date) if from_date and to_date else None,
                        specific_accounts=account_codes if account_codes else None
                    )
                
                st.text_area("Genererad begäran", letter, height=400)
                
                # Copy button
                st.download_button(
                    "📋 Ladda ner som textfil",
                    data=letter,
                    file_name=f"begaran_{company.replace(' ', '_')}.txt",
                    mime="text/plain"
                )
            else:
                st.warning("Ange bolagsnamn och välj minst en typ av handling.")
    
    st.markdown("---")
    st.info("""
    **Tips:** 
    - Be alltid om digitalt format (Excel/CSV) istället för PDF
    - Du behöver inte motivera varför du vill ha handlingarna
    - Om de säger nei eller dröjer, hänvisa till TF 2 kap och "skyndsamt"
    """)


# ============================================================================
# PAGE: IMPORT
# ============================================================================
elif page == "Import":
    st.title("📤 Importera transaktionsdata")
    
    uploaded_file = st.file_uploader(
        "Ladda upp fil",
        type=['xlsx', 'xls', 'csv', 'pdf'],
        help="Excel-filer fungerar bäst. PDF kan ha begränsad tabellextrahering."
    )
    
    st.markdown("Eller")
    
    if st.button("Ladda demo-data", help="Ladda syntetiskt data för att testa verktyget"):
        st.session_state.use_demo_data = True
    
    # Setup uploaded_file based on state or actual upload
    if getattr(st.session_state, 'use_demo_data', False) and not uploaded_file:
        demo_file_path = Path(__file__).parent / "demo_data.csv"
        if demo_file_path.exists():
            with open(demo_file_path, "rb") as f:
                class MockUpload:
                    def __init__(self, name, data):
                        self.name = name
                        self.data = data
                    def getvalue(self):
                        return self.data
                    def read(self):
                        return self.data
                
                uploaded_file = MockUpload("demo_data.csv", f.read())
            st.info("💡 Använder syntetiskt testdata.")
        else:
            st.error("Kunde inte hitta demo_data.csv")
            
    # Clear demo data state if real file is uploaded
    if uploaded_file and getattr(uploaded_file, "name", "") != "demo_data.csv":
        st.session_state.use_demo_data = False
    
    if uploaded_file:
        with st.spinner("Läser fil..."):
            df = handle_upload(uploaded_file)
        
        if df is not None and len(df) > 0:
            st.success(f"Läste in {len(df):,} rader och {len(df.columns)} kolumner")
            
            # Show preview
            st.subheader("Förhandsvisning")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Auto-detect columns
            st.subheader("Kolumnmappning")
            detected = detect_columns(df)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.session_state.column_mapping['belopp'] = st.selectbox(
                    "Belopp-kolumn",
                    [""] + list(df.columns),
                    index=list(df.columns).index(detected['belopp']) + 1 if detected['belopp'] else 0
                )
                
                st.session_state.column_mapping['konto'] = st.selectbox(
                    "Konto-kolumn",
                    [""] + list(df.columns),
                    index=list(df.columns).index(detected['konto']) + 1 if detected['konto'] else 0
                )
                
                st.session_state.column_mapping['datum'] = st.selectbox(
                    "Datum-kolumn",
                    [""] + list(df.columns),
                    index=list(df.columns).index(detected['datum']) + 1 if detected['datum'] else 0
                )
            
            with col2:
                st.session_state.column_mapping['leverantör'] = st.selectbox(
                    "Leverantör-kolumn",
                    [""] + list(df.columns),
                    index=list(df.columns).index(detected['leverantör']) + 1 if detected['leverantör'] else 0
                )
                
                st.session_state.column_mapping['kontonamn'] = st.selectbox(
                    "Kontonamn-kolumn",
                    [""] + list(df.columns),
                    index=list(df.columns).index(detected['kontonamn']) + 1 if detected['kontonamn'] else 0
                )
                
                st.session_state.column_mapping['beskrivning'] = st.selectbox(
                    "Beskrivning-kolumn",
                    [""] + list(df.columns),
                    index=list(df.columns).index(detected['beskrivning']) + 1 if detected['beskrivning'] else 0
                )
            
            # Clean empty mappings
            st.session_state.column_mapping = {k: v for k, v in st.session_state.column_mapping.items() if v}
            
            # Process button
            if st.button("Rensa och importera", type="primary"):
                with st.spinner("Rensar data..."):
                    # Clean data
                    cleaned_df = auto_clean(df, st.session_state.column_mapping)
                    
                    # Categorize accounts
                    if st.session_state.column_mapping.get('konto'):
                        cleaned_df = categorize_accounts(cleaned_df, st.session_state.column_mapping['konto'])
                        cleaned_df = flag_interesting_accounts(cleaned_df, st.session_state.column_mapping['konto'])
                    
                    # Extract year/month
                    if st.session_state.column_mapping.get('datum'):
                        cleaned_df = extract_year_month(cleaned_df, st.session_state.column_mapping['datum'])
                    
                    st.session_state.data = cleaned_df
                
                st.success(f"✅ Importerade {len(cleaned_df):,} transaktioner!")
                st.balloons()
                
                # Show cleaned preview
                st.subheader("Rensad data")
                st.dataframe(cleaned_df.head(20), use_container_width=True)


# ============================================================================
# PAGE: ANALYS
# ============================================================================
elif page == "Analys":
    st.title("🔎 Analysera transaktioner")
    
    if st.session_state.data is None:
        st.warning("Importera data först under 'Import'-sidan.")
        st.stop()
    
    df = st.session_state.data
    
    # Analysis controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.metric("Totalt antal transaktioner", f"{len(df):,}")
    
    with col2:
        if st.session_state.column_mapping.get('belopp'):
            total = df[st.session_state.column_mapping['belopp']].abs().sum()
            st.metric("Total omsättning", f"{total:,.0f} kr")
    
    with col3:
        if 'intressant' in df.columns:
            interesting = df['intressant'].sum()
            st.metric("Känsliga konton", f"{interesting:,}")
    
    st.markdown("---")
    
    # Run analysis
    if st.button("Kör automatisk analys", type="primary"):
        with st.spinner("Analyserar transaktioner..."):
            flags = analyze_transactions(df, st.session_state.column_mapping)
            st.session_state.flags = flags
            summary = generate_summary(df, flags, st.session_state.column_mapping)
            st.session_state.summary = summary
        
        st.success(f"Analys klar! Hittade {len(flags)} varningsflaggor.")
    
    # Show flags
    if st.session_state.flags:
        st.subheader("⚠️ Varningsflaggor")
        
        for i, flag in enumerate(sorted(st.session_state.flags, key=lambda x: x.allvarlighet, reverse=True)):
            severity_colors = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", 5: "⛔"}
            
            with st.expander(f"{severity_colors.get(flag.allvarlighet, '⚪')} {flag.kategori} - Allvarlighet {flag.allvarlighet}/5"):
                st.markdown(f"**Beskrivning:** {flag.beskrivning}")
                st.markdown(f"**Rekommendation:** {flag.rekommendation}")
                
                if flag.transaktioner:
                    st.markdown(f"*{len(flag.transaktioner)} berörda transaktioner*")
                    
                    # Show sample transactions
                    sample_df = df.iloc[flag.transaktioner[:10]]
                    st.dataframe(sample_df, use_container_width=True)
    
    st.markdown("---")
    
    # Manual search
    st.subheader("🔍 Sök transaktioner")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_supplier = st.text_input("Leverantör")
        search_account = st.text_input("Konto (prefix)")
    
    with col2:
        search_min = st.number_input("Minimibelopp", value=0)
        search_max = st.number_input("Maxbelopp", value=0)
    
    with col3:
        search_desc = st.text_input("Beskrivning innehåller")
    
    if st.button("Sök"):
        results = search_transactions(
            df,
            st.session_state.column_mapping,
            supplier=search_supplier if search_supplier else None,
            min_amount=search_min if search_min > 0 else None,
            max_amount=search_max if search_max > 0 else None,
            account=search_account if search_account else None,
            description=search_desc if search_desc else None
        )
        
        st.write(f"Hittade {len(results):,} transaktioner")
        st.dataframe(results, use_container_width=True)


# ============================================================================
# PAGE: KORSREFERENS
# ============================================================================
elif page == "Korsreferens":
    st.title("🔗 Korsreferens och leverantörskontroll")
    st.markdown("""
    Undersök leverantörer genom webbsökning. 
    Letar efter ägarstruktur, styrelsemedlemmar och eventuella varningsflaggor.
    """)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        company_name = st.text_input(
            "Företagsnamn",
            placeholder="T.ex. 'ABC Konsult AB'"
        )
        
        # Show frequent suppliers if data is loaded
        if st.session_state.data is not None and st.session_state.column_mapping.get('leverantör'):
            st.markdown("**Vanligaste leverantörer:**")
            lev_col = st.session_state.column_mapping['leverantör']
            top_suppliers = st.session_state.data[lev_col].value_counts().head(10)
            
            for supplier, count in top_suppliers.items():
                if st.button(f"{supplier} ({count})", key=f"sup_{supplier}"):
                    company_name = supplier
    
    with col2:
        if st.button("Sök leverantör", type="primary") and company_name:
            with st.spinner(f"Söker information om {company_name}..."):
                result = st.session_state.coach.research_supplier(company_name)
            
            st.markdown("### Sökresultat")
            st.markdown(result)
            
            # Add to history
            st.session_state.chat_history.append({
                "question": f"Leverantörssökning: {company_name}",
                "answer": result
            })
    
    st.markdown("---")
    
    # Ask coach about specific transaction
    st.subheader("💬 Fråga coachen om en transaktion")
    
    if st.session_state.data is not None:
        st.markdown("Välj en transaktion att analysera:")
        
        # Let user select a row
        row_index = st.number_input(
            "Radnummer",
            min_value=0,
            max_value=len(st.session_state.data) - 1,
            value=0
        )
        
        selected_row = st.session_state.data.iloc[row_index]
        st.dataframe(pd.DataFrame([selected_row]), use_container_width=True)
        
        if st.button("Analysera denna transaktion"):
            # Build transaction dict
            transaction_data = {
                'datum': selected_row.get(st.session_state.column_mapping.get('datum', ''), 'Okänt'),
                'belopp': selected_row.get(st.session_state.column_mapping.get('belopp', ''), 0),
                'konto': selected_row.get(st.session_state.column_mapping.get('konto', ''), 'Okänt'),
                'kontonamn': selected_row.get(st.session_state.column_mapping.get('kontonamn', ''), ''),
                'leverantör': selected_row.get(st.session_state.column_mapping.get('leverantör', ''), 'Okänd'),
                'beskrivning': selected_row.get(st.session_state.column_mapping.get('beskrivning', ''), '')
            }
            
            with st.spinner("Analyserar transaktion..."):
                analysis = st.session_state.coach.analyze_transaction(transaction_data)
            
            st.markdown("### Analys")
            st.markdown(analysis)


# ============================================================================
# PAGE: EXPORT
# ============================================================================
elif page == "Export":
    st.title("📥 Exportera data och rapporter")
    
    if st.session_state.data is None:
        st.warning("Ingen data att exportera. Importera data först.")
        st.stop()
    
    df = st.session_state.data
    flags = st.session_state.flags
    summary = st.session_state.summary
    
    st.subheader("Exportera transaktionsdata")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv_buffer, csv_name = export_to_csv(df)
        st.download_button(
            "📥 Ladda ner CSV",
            data=csv_buffer,
            file_name=csv_name,
            mime="text/csv"
        )
    
    with col2:
        excel_buffer, excel_name = export_to_excel(df)
        st.download_button(
            "📥 Ladda ner Excel",
            data=excel_buffer,
            file_name=excel_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col3:
        # Export only flagged transactions
        if 'intressant' in df.columns:
            flagged_df = df[df['intressant'] == True]
            if len(flagged_df) > 0:
                flagged_buffer, flagged_name = export_to_csv(flagged_df, "känsliga_transaktioner.csv")
                st.download_button(
                    "📥 Endast känsliga konton",
                    data=flagged_buffer,
                    file_name=flagged_name,
                    mime="text/csv"
                )
    
    st.markdown("---")
    
    st.subheader("Exportera analysrapport")
    
    if flags:
        col1, col2 = st.columns(2)
        
        with col1:
            md_report = export_flags_to_markdown(flags, "Karlshamn-granskning")
            st.download_button(
                "📥 Rapport (Markdown)",
                data=md_report,
                file_name="granskningsrapport.md",
                mime="text/markdown"
            )
        
        with col2:
            project_name = st.text_input("Bolagsnamn för faktaruta", "Karlshamns Energi AB")
            if summary:
                factbox = generate_factbox(flags, summary, project_name)
                st.download_button(
                    "📥 Faktaruta (TXT)",
                    data=factbox,
                    file_name="faktaruta.txt",
                    mime="text/plain"
                )
        
        st.markdown("---")
        
        st.subheader("Förhandsvisa rapport")
        
        with st.expander("Visa Markdown-rapport"):
            st.markdown(md_report)
        
        if summary:
            with st.expander("Visa faktaruta"):
                st.code(generate_factbox(flags, summary, project_name))
    else:
        st.info("Kör analysen först för att generera rapporter.")


# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Byggd för granskning av Karlshamns kommun")
