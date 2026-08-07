"""
File handler for uploading and parsing Excel, CSV, and PDF files.
"""
import pandas as pd
import io
from pathlib import Path
from typing import Optional, Union
import streamlit as st


def handle_upload(uploaded_file) -> Optional[pd.DataFrame]:
    """
    Handle file upload and return parsed DataFrame.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        
    Returns:
        DataFrame or None if parsing failed
    """
    if uploaded_file is None:
        return None
    
    file_name = uploaded_file.name.lower()
    
    try:
        if file_name.endswith('.xlsx') or file_name.endswith('.xls'):
            return parse_excel(uploaded_file)
        elif file_name.endswith('.csv'):
            return parse_csv(uploaded_file)
        elif file_name.endswith('.pdf'):
            return parse_pdf(uploaded_file)
        else:
            st.error(f"Filformatet stöds ej: {Path(uploaded_file.name).suffix}")
            return None
    except Exception as e:
        st.error(f"Fel vid inläsning av fil: {str(e)}")
        return None


def parse_excel(file) -> pd.DataFrame:
    """
    Parse Excel file, handling multiple sheets intelligently.
    
    Args:
        file: File-like object or path
        
    Returns:
        Combined DataFrame from all relevant sheets
    """
    # Read all sheets
    xlsx = pd.ExcelFile(file)
    sheet_names = xlsx.sheet_names
    
    if len(sheet_names) == 1:
        # Single sheet - read directly
        df = pd.read_excel(file, sheet_name=0)
    else:
        # Multiple sheets - try to find transaction data
        st.info(f"Filen innehåller {len(sheet_names)} ark: {', '.join(sheet_names)}")
        
        # Look for sheets with relevant keywords
        transaction_keywords = ['huvudbok', 'transak', 'verifikat', 'konto', 'journal', 'reskontra']
        
        relevant_sheets = []
        for name in sheet_names:
            name_lower = name.lower()
            if any(kw in name_lower for kw in transaction_keywords):
                relevant_sheets.append(name)
        
        if relevant_sheets:
            # Combine relevant sheets
            dfs = []
            for sheet in relevant_sheets:
                sheet_df = pd.read_excel(file, sheet_name=sheet)
                sheet_df['_källa_ark'] = sheet
                dfs.append(sheet_df)
            df = pd.concat(dfs, ignore_index=True)
            st.success(f"Läste in {len(relevant_sheets)} relevanta ark")
        else:
            # Let user choose
            selected = st.selectbox(
                "Välj ark att importera:",
                sheet_names,
                key="sheet_selector"
            )
            df = pd.read_excel(file, sheet_name=selected)
    
    return df


def parse_csv(file, encoding: str = None) -> pd.DataFrame:
    """
    Parse CSV file with encoding detection.
    
    Args:
        file: File-like object
        encoding: Optional encoding override
        
    Returns:
        DataFrame
    """
    # Try common Swedish encodings
    encodings = [encoding] if encoding else ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    # Read file content once
    content = file.read()
    
    for enc in encodings:
        try:
            df = pd.read_csv(
                io.BytesIO(content),
                encoding=enc,
                sep=None,  # Auto-detect separator
                engine='python'
            )
            return df
        except UnicodeDecodeError:
            continue
    
    # Fallback with error handling
    return pd.read_csv(
        io.BytesIO(content),
        encoding='utf-8',
        errors='replace'
    )


def parse_pdf(file) -> pd.DataFrame:
    """
    Extract tabular data from PDF file.
    Uses PyPDF2 for text extraction and attempts to parse tables.
    
    Args:
        file: File-like object
        
    Returns:
        DataFrame (may be empty if no tables found)
    """
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        st.error("PyPDF2 behövs för PDF-import. Installera med: pip install PyPDF2")
        return pd.DataFrame()
    
    reader = PdfReader(file)
    
    all_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            all_text.append(text)
    
    full_text = "\n".join(all_text)
    
    # Try to identify tabular structure
    lines = full_text.split('\n')
    
    # Look for lines with multiple numeric values (likely table rows)
    table_rows = []
    for line in lines:
        # Count numbers in line
        parts = line.split()
        num_count = sum(1 for p in parts if _is_numeric(p))
        
        if num_count >= 2 and len(parts) >= 3:
            table_rows.append(parts)
    
    if table_rows:
        # Try to create DataFrame from table rows
        try:
            # Use first row as potential header if it has text
            if any(not _is_numeric(p) for p in table_rows[0]):
                df = pd.DataFrame(table_rows[1:], columns=table_rows[0][:len(table_rows[1])])
            else:
                df = pd.DataFrame(table_rows)
            return df
        except Exception:
            pass
    
    # Fallback: return text for manual processing
    st.warning("PDF-filen innehåller ingen tydlig tabellstruktur. Texten visas nedan.")
    st.text_area("Extraherad text", full_text, height=300)
    
    return pd.DataFrame({'raw_text': [full_text]})


def _is_numeric(s: str) -> bool:
    """Check if string represents a number (including Swedish decimal format)."""
    s = s.replace(' ', '').replace(',', '.').replace('kr', '').replace('SEK', '')
    try:
        float(s)
        return True
    except ValueError:
        return False


def detect_columns(df: pd.DataFrame) -> dict:
    """
    Auto-detect which columns contain what type of data.
    
    Args:
        df: Input DataFrame
        
    Returns:
        Dict mapping column types to column names
    """
    detected = {
        'datum': None,
        'belopp': None,
        'konto': None,
        'kontonamn': None,
        'leverantör': None,
        'beskrivning': None,
        'verifikation': None
    }
    
    columns_lower = {col: col.lower() for col in df.columns}
    
    # Date column detection
    date_keywords = ['datum', 'date', 'bokföringsdatum', 'verifikationsdatum']
    for col, col_lower in columns_lower.items():
        if any(kw in col_lower for kw in date_keywords):
            detected['datum'] = col
            break
    
    # Amount column detection
    amount_keywords = ['belopp', 'summa', 'amount', 'saldo', 'debet', 'kredit']
    for col, col_lower in columns_lower.items():
        if any(kw in col_lower for kw in amount_keywords):
            detected['belopp'] = col
            break
    
    # Account number detection
    account_keywords = ['konto', 'kontonr', 'account', 'ktonr']
    for col, col_lower in columns_lower.items():
        if any(kw == col_lower or kw in col_lower for kw in account_keywords):
            # Distinguish between account number and account name
            if 'namn' in col_lower or 'name' in col_lower or 'text' in col_lower:
                detected['kontonamn'] = col
            else:
                detected['konto'] = col
    
    # Supplier detection
    supplier_keywords = ['leverantör', 'motpart', 'supplier', 'vendor', 'kund']
    for col, col_lower in columns_lower.items():
        if any(kw in col_lower for kw in supplier_keywords):
            detected['leverantör'] = col
            break
    
    # Description detection
    desc_keywords = ['beskrivning', 'text', 'description', 'kommentar', 'notering']
    for col, col_lower in columns_lower.items():
        if any(kw in col_lower for kw in desc_keywords):
            if detected['kontonamn'] != col:  # Don't use same column twice
                detected['beskrivning'] = col
                break
    
    # Verification number detection
    verif_keywords = ['verifikation', 'verifikat', 'ver.nr', 'vernr', 'voucher']
    for col, col_lower in columns_lower.items():
        if any(kw in col_lower for kw in verif_keywords):
            detected['verifikation'] = col
            break
    
    return detected


def validate_data(df: pd.DataFrame, column_mapping: dict) -> list[str]:
    """
    Validate that required data is present and correctly formatted.
    
    Args:
        df: DataFrame to validate
        column_mapping: Mapping of column types to column names
        
    Returns:
        List of warning/error messages
    """
    warnings = []
    
    # Check required columns
    required = ['belopp', 'konto']
    for req in required:
        if not column_mapping.get(req):
            warnings.append(f"⚠️ Kolumn för '{req}' kunde inte identifieras")
    
    # Check data quality
    if column_mapping.get('belopp'):
        amount_col = column_mapping['belopp']
        if amount_col in df.columns:
            null_count = df[amount_col].isna().sum()
            if null_count > 0:
                warnings.append(f"⚠️ {null_count} rader saknar belopp")
    
    if column_mapping.get('datum'):
        date_col = column_mapping['datum']
        if date_col in df.columns:
            null_count = df[date_col].isna().sum()
            if null_count > 0:
                warnings.append(f"⚠️ {null_count} rader saknar datum")
    
    # Check row count
    row_count = len(df)
    if row_count == 0:
        warnings.append("❌ Filen innehåller inga rader")
    elif row_count < 10:
        warnings.append(f"ℹ️ Filen innehåller bara {row_count} rader")
    else:
        warnings.append(f"✅ {row_count:,} transaktioner inlästa")
    
    return warnings
