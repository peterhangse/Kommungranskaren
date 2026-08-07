"""
Data cleaning and normalization for Swedish accounting data.
"""
import pandas as pd
import re
from typing import Optional
import streamlit as st


def auto_clean(df: pd.DataFrame, column_mapping: dict) -> pd.DataFrame:
    """
    Automatically clean and normalize transaction data.
    
    Steps:
    1. Clean amount columns (belopp)
    2. Normalize account names (kontonamn)
    3. Parse and standardize dates (datum)
    4. Remove exact duplicates
    5. Strip whitespace from text columns
    
    Args:
        df: Raw DataFrame
        column_mapping: Dict mapping column types to column names
        
    Returns:
        Cleaned DataFrame
    """
    df = df.copy()
    
    # 1. Clean amount column
    if column_mapping.get('belopp'):
        df = clean_amounts(df, column_mapping['belopp'])
    
    # 2. Normalize account names
    if column_mapping.get('kontonamn'):
        df = normalize_account_names(df, column_mapping['kontonamn'])
    
    # 3. Parse dates
    if column_mapping.get('datum'):
        df = parse_dates(df, column_mapping['datum'])
    
    # 4. Remove duplicates
    original_count = len(df)
    df = df.drop_duplicates()
    removed = original_count - len(df)
    if removed > 0:
        st.info(f"Removed {removed} duplicate rows")
    
    # 5. Strip whitespace from string columns
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace('nan', '')
    
    return df


def clean_amounts(df: pd.DataFrame, amount_col: str) -> pd.DataFrame:
    """
    Clean and normalize amount column to numeric values.
    
    Handles:
    - Swedish number format (1 234,56 → 1234.56)
    - Currency symbols (kr, SEK, :-)
    - Parentheses for negative numbers
    - Empty values
    
    Args:
        df: DataFrame
        amount_col: Name of amount column
        
    Returns:
        DataFrame with cleaned amount column
    """
    if amount_col not in df.columns:
        return df
    
    df = df.copy()
    
    def parse_swedish_amount(val) -> Optional[float]:
        if pd.isna(val):
            return None
        
        s = str(val).strip()
        if s == '' or s.lower() == 'nan':
            return None
        
        # Check for negative in parentheses: (1234,56) → -1234.56
        is_negative = False
        if s.startswith('(') and s.endswith(')'):
            s = s[1:-1]
            is_negative = True
        
        # Remove currency symbols and whitespace
        s = re.sub(r'[kr|SEK|:-]', '', s, flags=re.IGNORECASE)
        s = s.replace(' ', '').replace('\xa0', '')  # Remove non-breaking spaces
        
        # Handle Swedish format: change comma to dot, keep only last dot
        parts = s.replace(',', '.').split('.')
        if len(parts) > 1:
            # Last part is decimals, rest are thousands
            integer_part = ''.join(parts[:-1])
            decimal_part = parts[-1]
            s = f"{integer_part}.{decimal_part}"
        else:
            s = parts[0]
        
        # Handle minus sign
        if '-' in s:
            s = s.replace('-', '')
            is_negative = True
        
        try:
            val = float(s)
            return -val if is_negative else val
        except ValueError:
            return None
    
    df[amount_col] = df[amount_col].apply(parse_swedish_amount)
    
    # Report conversion results
    null_count = df[amount_col].isna().sum()
    if null_count > 0:
        st.warning(f"{null_count} beloppsvärden kunde inte tolkas")
    
    return df


def normalize_account_names(df: pd.DataFrame, account_name_col: str) -> pd.DataFrame:
    """
    Normalize account names for consistent grouping.
    
    Args:
        df: DataFrame
        account_name_col: Name of account name column
        
    Returns:
        DataFrame with normalized account names
    """
    if account_name_col not in df.columns:
        return df
    
    df = df.copy()
    
    # Create a normalized version (lowercase, stripped)
    df[f'{account_name_col}_norm'] = (
        df[account_name_col]
        .astype(str)
        .str.lower()
        .str.strip()
        .str.replace(r'\s+', ' ', regex=True)  # Normalize whitespace
    )
    
    return df


def parse_dates(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """
    Parse and standardize date column.
    
    Handles various Swedish date formats:
    - 2024-01-15
    - 15/01/2024
    - 15.01.2024
    - 15 januari 2024
    
    Args:
        df: DataFrame
        date_col: Name of date column
        
    Returns:
        DataFrame with parsed date column
    """
    if date_col not in df.columns:
        return df
    
    df = df.copy()
    
    # Swedish month names
    swedish_months = {
        'januari': '01', 'februari': '02', 'mars': '03', 'april': '04',
        'maj': '05', 'juni': '06', 'juli': '07', 'augusti': '08',
        'september': '09', 'oktober': '10', 'november': '11', 'december': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
        'okt': '10', 'nov': '11', 'dec': '12'
    }
    
    def parse_date(val):
        if pd.isna(val):
            return pd.NaT
        
        s = str(val).strip().lower()
        if not s or s == 'nan':
            return pd.NaT
        
        # Replace Swedish month names
        for swe, num in swedish_months.items():
            s = s.replace(swe, num)
        
        # Try pandas parsing with common formats
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y', '%Y%m%d', '%d %m %Y']:
            try:
                return pd.to_datetime(s, format=fmt)
            except ValueError:
                continue
        
        # Fallback to pandas auto-detection
        try:
            return pd.to_datetime(s, dayfirst=True)
        except ValueError:
            return pd.NaT
    
    df[date_col] = df[date_col].apply(parse_date)
    
    # Report parsing results
    valid_dates = df[date_col].notna().sum()
    total = len(df)
    st.info(f"Parsade {valid_dates:,} av {total:,} datum")
    
    return df


def extract_year_month(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """
    Add year and month columns from date column.
    
    Args:
        df: DataFrame with parsed date column
        date_col: Name of date column
        
    Returns:
        DataFrame with 'år' and 'månad' columns added
    """
    if date_col not in df.columns:
        return df
    
    df = df.copy()
    
    if pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df['år'] = df[date_col].dt.year
        df['månad'] = df[date_col].dt.month
        df['år_månad'] = df[date_col].dt.to_period('M').astype(str)
    
    return df


def categorize_accounts(df: pd.DataFrame, account_col: str) -> pd.DataFrame:
    """
    Add account category based on BAS-kontoplan.
    
    Args:
        df: DataFrame
        account_col: Name of account number column
        
    Returns:
        DataFrame with 'kontokategori' column added
    """
    if account_col not in df.columns:
        return df
    
    df = df.copy()
    
    # BAS account categories
    categories = {
        '1': 'Tillgångar',
        '2': 'Skulder och eget kapital',
        '3': 'Intäkter',
        '4': 'Kostnader för varor',
        '5': 'Övriga externa kostnader',
        '6': 'Övriga externa kostnader',
        '7': 'Personal',
        '8': 'Finansiella poster'
    }
    
    # Interesting sub-categories for investigation
    interesting_accounts = {
        '5800': 'Resekostnader',
        '5810': 'Flygresor',
        '5830': 'Hotell',
        '5840': 'Traktamenten',
        '5890': 'Övriga resekostnader',
        '5940': 'Sponsring',
        '6071': 'Representation, extern',
        '6072': 'Representation, intern',
        '6550': 'Konsultkostnader',
        '6590': 'Övriga tjänster',
        '6991': 'Övriga kostnader',
        '6992': 'Engångskostnader',
    }
    
    def get_category(account):
        if pd.isna(account):
            return 'Okänd'
        
        account_str = str(int(float(account))) if isinstance(account, (int, float)) else str(account).strip()
        
        # Check specific accounts first
        for code, name in interesting_accounts.items():
            if account_str.startswith(code):
                return name
        
        # Fall back to main category
        if account_str and account_str[0] in categories:
            return categories[account_str[0]]
        
        return 'Okänd'
    
    df['kontokategori'] = df[account_col].apply(get_category)
    
    return df


def flag_interesting_accounts(df: pd.DataFrame, account_col: str) -> pd.DataFrame:
    """
    Flag accounts that are particularly interesting for investigation.
    
    Args:
        df: DataFrame
        account_col: Name of account number column
        
    Returns:
        DataFrame with 'intressant' boolean column
    """
    if account_col not in df.columns:
        return df
    
    df = df.copy()
    
    # Accounts that warrant extra scrutiny
    interesting_prefixes = [
        '5800', '5810', '5820', '5830', '5840', '5850', '5860', '5890',  # Travel
        '5940', '5950',  # Sponsorship, donations
        '6071', '6072',  # Representation
        '6550', '6560', '6590',  # Consultants
        '6991', '6992', '6993',  # Miscellaneous
    ]
    
    def is_interesting(account):
        if pd.isna(account):
            return False
        
        account_str = str(int(float(account))) if isinstance(account, (int, float)) else str(account).strip()
        
        return any(account_str.startswith(prefix) for prefix in interesting_prefixes)
    
    df['intressant'] = df[account_col].apply(is_interesting)
    
    interesting_count = df['intressant'].sum()
    if interesting_count > 0:
        st.info(f"🔍 {interesting_count:,} transaktioner på känsliga konton")
    
    return df
