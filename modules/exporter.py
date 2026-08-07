"""
Export functionality for reports and data.
"""
import pandas as pd
from io import BytesIO
from datetime import datetime
from typing import Optional


def export_to_csv(df: pd.DataFrame, filename: str = None) -> tuple[BytesIO, str]:
    """
    Export DataFrame to CSV file.
    
    Args:
        df: DataFrame to export
        filename: Optional filename (default: generated with timestamp)
        
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"granskning_export_{timestamp}.csv"
    
    buffer = BytesIO()
    df.to_csv(buffer, index=False, encoding='utf-8-sig')  # UTF-8 with BOM for Excel
    buffer.seek(0)
    
    return buffer, filename


def export_to_excel(df: pd.DataFrame, 
                    filename: str = None,
                    sheet_name: str = "Transaktioner",
                    include_summary: bool = True) -> tuple[BytesIO, str]:
    """
    Export DataFrame to Excel file with formatting.
    
    Args:
        df: DataFrame to export
        filename: Optional filename
        sheet_name: Name of main data sheet
        include_summary: Whether to include summary sheet
        
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"granskning_export_{timestamp}.xlsx"
    
    buffer = BytesIO()
    
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        # Main data sheet
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Get workbook and worksheet for formatting
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        # Format headers
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#1E3A5F',
            'font_color': 'white',
            'border': 1
        })
        
        for col_num, column in enumerate(df.columns):
            worksheet.write(0, col_num, column, header_format)
            # Auto-width columns
            max_len = max(df[column].astype(str).str.len().max(), len(column)) + 2
            worksheet.set_column(col_num, col_num, min(max_len, 50))
        
        # Freeze header row
        worksheet.freeze_panes(1, 0)
        
        # Add summary sheet if requested
        if include_summary:
            _add_summary_sheet(df, writer, workbook)
    
    buffer.seek(0)
    return buffer, filename


def _add_summary_sheet(df: pd.DataFrame, writer, workbook):
    """Add a summary statistics sheet."""
    summary_data = {
        'Statistik': [
            'Totalt antal transaktioner',
            'Datum från',
            'Datum till',
            'Totalt belopp (absolutvärde)'
        ],
        'Värde': [
            len(df),
            str(df.select_dtypes(include=['datetime64']).min().min()) if len(df.select_dtypes(include=['datetime64']).columns) > 0 else 'N/A',
            str(df.select_dtypes(include=['datetime64']).max().max()) if len(df.select_dtypes(include=['datetime64']).columns) > 0 else 'N/A',
            df.select_dtypes(include=['number']).abs().sum().sum()
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_excel(writer, sheet_name='Sammanfattning', index=False)


def export_flags_to_markdown(flags: list, project_name: str = "Granskning") -> str:
    """
    Export red flags to Markdown format for documentation.
    
    Args:
        flags: List of RedFlag objects
        project_name: Name of the project
        
    Returns:
        Markdown formatted string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    md = f"""# Granskningsrapport: {project_name}

**Genererad:** {timestamp}

## Sammanfattning

Totalt hittades **{len(flags)}** varningsflaggor.

### Flaggor per allvarlighetsgrad

"""
    # Count by severity
    severity_counts = {}
    for flag in flags:
        severity_counts[flag.allvarlighet] = severity_counts.get(flag.allvarlighet, 0) + 1
    
    severity_labels = {
        1: '🟢 Låg',
        2: '🟡 Låg-Medium',
        3: '🟠 Medium',
        4: '🔴 Hög',
        5: '⛔ Kritisk'
    }
    
    for sev in sorted(severity_counts.keys(), reverse=True):
        md += f"- {severity_labels.get(sev, sev)}: {severity_counts[sev]} flagga(or)\n"
    
    md += "\n---\n\n## Detaljerade fynd\n\n"
    
    # Group by category
    flags_by_category = {}
    for flag in flags:
        if flag.kategori not in flags_by_category:
            flags_by_category[flag.kategori] = []
        flags_by_category[flag.kategori].append(flag)
    
    for category, category_flags in flags_by_category.items():
        md += f"### {category}\n\n"
        
        for i, flag in enumerate(category_flags, 1):
            severity_emoji = ['', '🟢', '🟡', '🟠', '🔴', '⛔'][flag.allvarlighet]
            md += f"#### {i}. {severity_emoji} Allvarlighet {flag.allvarlighet}/5\n\n"
            md += f"**Beskrivning:** {flag.beskrivning}\n\n"
            md += f"**Rekommendation:** {flag.rekommendation}\n\n"
            
            if flag.transaktioner:
                md += f"*Berörda transaktioner: {len(flag.transaktioner)} st (rad-index: {flag.transaktioner[:5]}...)*\n\n"
            
            md += "---\n\n"
    
    md += """## Nästa steg

1. Läs igenom flaggorna och prioritera
2. Begär kompletterande underlag för misstänkta transaktioner
3. Korsreferera leverantörer mot ägaruppgifter
4. Kontakta bolaget för kommentar innan publicering

---

*Genererad av Granskning-Coach*
"""
    
    return md


def generate_factbox(flags: list, 
                     summary: dict,
                     company_name: str) -> str:
    """
    Generate a journalistic fact box for article use.
    
    Args:
        flags: List of red flags
        summary: Analysis summary dict
        company_name: Name of investigated company
        
    Returns:
        Formatted fact box as string
    """
    high_severity = sum(1 for f in flags if f.allvarlighet >= 4)
    
    factbox = f"""
═══════════════════════════════════════════════
                   FAKTARUTA
═══════════════════════════════════════════════

GRANSKNINGEN I KORTHET

Bolag: {company_name}

Analyserade transaktioner: {summary.get('total_transactions', 0):,}

Totalt belopp: {summary.get('total_amount', 0):,.0f} kr

Identifierade varningsflaggor: {len(flags)} st
  - Varav hög allvarlighet: {high_severity} st

Period: {_format_date_range(summary.get('date_range'))}

═══════════════════════════════════════════════

VIKTIGA FYND
"""
    
    # Add top 3 flags
    top_flags = sorted(flags, key=lambda x: x.allvarlighet, reverse=True)[:3]
    for i, flag in enumerate(top_flags, 1):
        factbox += f"\n{i}. {flag.kategori}: {flag.beskrivning[:100]}..."
    
    factbox += """

═══════════════════════════════════════════════

Om analysen: Transaktionsdata har analyserats 
med hjälp av Granskning-Coach för att identifiera 
mönster som kan kräva närmare granskning.

═══════════════════════════════════════════════
"""
    
    return factbox


def _format_date_range(date_range: Optional[tuple]) -> str:
    """Format date range tuple to readable string."""
    if not date_range:
        return "Okänd period"
    
    start, end = date_range
    try:
        return f"{start.strftime('%Y-%m-%d')} till {end.strftime('%Y-%m-%d')}"
    except AttributeError:
        return f"{start} till {end}"


def create_download_buttons(df: pd.DataFrame, flags: list, summary: dict, st_module):
    """
    Create Streamlit download buttons for various export formats.
    
    Args:
        df: DataFrame to export
        flags: List of red flags
        summary: Analysis summary
        st_module: Streamlit module reference
    """
    col1, col2, col3 = st_module.columns(3)
    
    with col1:
        csv_buffer, csv_filename = export_to_csv(df)
        st_module.download_button(
            label="📥 Ladda ner CSV",
            data=csv_buffer,
            file_name=csv_filename,
            mime="text/csv"
        )
    
    with col2:
        excel_buffer, excel_filename = export_to_excel(df)
        st_module.download_button(
            label="📥 Ladda ner Excel",
            data=excel_buffer,
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col3:
        if flags:
            md_content = export_flags_to_markdown(flags)
            st_module.download_button(
                label="📥 Ladda ner rapport (MD)",
                data=md_content,
                file_name=f"granskning_rapport_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown"
            )
