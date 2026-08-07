"""
Transaction analyzer with SQL-based pattern detection and AI flagging.
"""
import pandas as pd
import sqlite3
from typing import Optional
from dataclasses import dataclass
import streamlit as st

from .claude_coach import GranskningsCoach


@dataclass
class RedFlag:
    """Represents a detected issue in the data."""
    kategori: str
    allvarlighet: int  # 1-5
    beskrivning: str
    transaktioner: list[int]  # Row indices
    rekommendation: str


def analyze_transactions(df: pd.DataFrame, column_mapping: dict) -> list[RedFlag]:
    """
    Analyze transactions to find suspicious patterns.
    
    Uses SQL queries for pattern detection:
    1. Large representation transactions (>2000 SEK)
    2. Many small transactions to same supplier (split purchases)
    3. Recurring round numbers (possible dummy invoices)
    4. Unusual travel patterns
    
    Args:
        df: Cleaned transaction DataFrame
        column_mapping: Dict mapping column types to column names
        
    Returns:
        List of RedFlag objects
    """
    flags = []
    
    # Create in-memory SQLite database
    conn = sqlite3.connect(':memory:')
    
    # Prepare data for SQL analysis
    sql_df = df.copy()
    sql_df['row_index'] = sql_df.index
    
    # Rename columns to standard names for SQL
    rename_map = {v: k for k, v in column_mapping.items() if v}
    sql_df = sql_df.rename(columns=rename_map)
    
    sql_df.to_sql('transactions', conn, index=False)
    
    # 1. Large representation transactions
    flags.extend(_check_representation(conn))
    
    # 2. Suspected split purchases
    flags.extend(_check_split_purchases(conn))
    
    # 3. Round number anomalies
    flags.extend(_check_round_numbers(conn))
    
    # 4. Travel cost analysis
    flags.extend(_check_travel_costs(conn))
    
    conn.close()
    
    return flags


def _check_representation(conn: sqlite3.Connection) -> list[RedFlag]:
    """Check for large representation costs."""
    flags = []
    
    try:
        query = """
        SELECT row_index, belopp, leverantör, beskrivning, konto
        FROM transactions
        WHERE (konto LIKE '6071%' OR konto LIKE '6072%')
          AND ABS(belopp) > 2000
        ORDER BY ABS(belopp) DESC
        LIMIT 50
        """
        result = pd.read_sql(query, conn)
        
        if len(result) > 0:
            total = result['belopp'].abs().sum()
            flags.append(RedFlag(
                kategori="Representation",
                allvarlighet=3 if total > 50000 else 2,
                beskrivning=f"Hittade {len(result)} representationstransaktioner över 2000 kr. "
                           f"Totalt: {total:,.0f} kr",
                transaktioner=result['row_index'].tolist(),
                rekommendation="Granska syfte och deltagare. Enligt Skatteverket bör intern "
                              "representation vara max ca 600 kr/person."
            ))
    except Exception as e:
        st.warning(f"Kunde inte analysera representation: {e}")
    
    return flags


def _check_split_purchases(conn: sqlite3.Connection) -> list[RedFlag]:
    """Check for suspected split purchases to avoid procurement thresholds."""
    flags = []
    
    try:
        # Find suppliers with many transactions just under common thresholds
        query = """
        WITH supplier_stats AS (
            SELECT 
                leverantör,
                COUNT(*) as antal,
                SUM(ABS(belopp)) as total,
                AVG(ABS(belopp)) as snitt,
                GROUP_CONCAT(row_index) as rows
            FROM transactions
            WHERE leverantör IS NOT NULL 
              AND leverantör != ''
              AND ABS(belopp) > 0
            GROUP BY leverantör
            HAVING COUNT(*) >= 5
        )
        SELECT *
        FROM supplier_stats
        WHERE 
            -- Many transactions just under procurement threshold
            (snitt BETWEEN 80000 AND 110000 AND antal >= 3)
            OR
            -- Many small transactions that sum to large amount
            (snitt < 50000 AND total > 500000 AND antal >= 10)
        ORDER BY total DESC
        """
        result = pd.read_sql(query, conn)
        
        for _, row in result.iterrows():
            row_indices = [int(x) for x in str(row['rows']).split(',') if x]
            flags.append(RedFlag(
                kategori="Uppdelade inköp",
                allvarlighet=4,
                beskrivning=f"Leverantör '{row['leverantör']}' har {row['antal']} transaktioner "
                           f"med snitt {row['snitt']:,.0f} kr, totalt {row['total']:,.0f} kr. "
                           f"Kan vara uppdelat för att undvika upphandling.",
                transaktioner=row_indices[:20],  # Limit for display
                rekommendation="Undersök om inköpen borde ha upphandlats samlat. "
                              "Direktupphandlingsgränsen är ca 700 000 kr."
            ))
    except Exception as e:
        st.warning(f"Kunde inte analysera uppdelade inköp: {e}")
    
    return flags


def _check_round_numbers(conn: sqlite3.Connection) -> list[RedFlag]:
    """Check for suspicious round number patterns."""
    flags = []
    
    try:
        query = """
        SELECT row_index, belopp, leverantör, konto, beskrivning
        FROM transactions
        WHERE ABS(belopp) > 5000
          AND ABS(belopp) = CAST(ABS(belopp) / 1000 AS INTEGER) * 1000
        ORDER BY ABS(belopp) DESC
        """
        result = pd.read_sql(query, conn)
        
        if len(result) > 10:  # Only flag if pattern is common
            # Check if same round amount appears multiple times
            amount_counts = result.groupby('belopp').size()
            repeated = amount_counts[amount_counts >= 3]
            
            if len(repeated) > 0:
                total = result['belopp'].abs().sum()
                flags.append(RedFlag(
                    kategori="Jämna belopp",
                    allvarlighet=2,
                    beskrivning=f"Hittade {len(result)} transaktioner med jämna tusentalsbelopp. "
                               f"Belopp som {list(repeated.index[:3])} förekommer upprepat.",
                    transaktioner=result.head(20)['row_index'].tolist(),
                    rekommendation="Jämna belopp kan indikera schabloner eller påhittade fakturor. "
                                  "Begär underlag för ett urval."
                ))
    except Exception as e:
        st.warning(f"Kunde inte analysera jämna belopp: {e}")
    
    return flags


def _check_travel_costs(conn: sqlite3.Connection) -> list[RedFlag]:
    """Analyze travel costs for anomalies."""
    flags = []
    
    try:
        query = """
        SELECT 
            leverantör,
            COUNT(*) as antal,
            SUM(ABS(belopp)) as total,
            MAX(ABS(belopp)) as max_belopp,
            GROUP_CONCAT(row_index) as rows
        FROM transactions
        WHERE konto LIKE '58%'  -- Travel accounts
          AND ABS(belopp) > 0
        GROUP BY leverantör
        HAVING SUM(ABS(belopp)) > 50000
        ORDER BY total DESC
        LIMIT 10
        """
        result = pd.read_sql(query, conn)
        
        if len(result) > 0:
            total_travel = result['total'].sum()
            
            # Check for conference/MIPIM type spending
            suspicious_keywords = ['cannes', 'mipim', 'monaco', 'london', 'dubai', 'konferens']
            suspicious_suppliers = result[
                result['leverantör'].str.lower().str.contains('|'.join(suspicious_keywords), na=False)
            ]
            
            if len(suspicious_suppliers) > 0:
                for _, row in suspicious_suppliers.iterrows():
                    row_indices = [int(x) for x in str(row['rows']).split(',') if x]
                    flags.append(RedFlag(
                        kategori="Resekostnader - varning",
                        allvarlighet=4,
                        beskrivning=f"Reseutgifter till '{row['leverantör']}': {row['total']:,.0f} kr. "
                                   f"Kan röra internationella konferenser/mässor.",
                        transaktioner=row_indices,
                        rekommendation="Undersök vem som reste, syftet, och om det finns "
                                      "tillhörande representation eller privata inslag."
                    ))
            
            if total_travel > 200000:
                all_rows = []
                for rows_str in result['rows']:
                    all_rows.extend([int(x) for x in str(rows_str).split(',') if x][:5])
                
                flags.append(RedFlag(
                    kategori="Resekostnader - översikt",
                    allvarlighet=2,
                    beskrivning=f"Totala resekostnader: {total_travel:,.0f} kr fördelat på "
                               f"{len(result)} leverantörer.",
                    transaktioner=all_rows[:20],
                    rekommendation="Begär reseräkningar och syftesrapporter för större resor."
                ))
    except Exception as e:
        st.warning(f"Kunde inte analysera resekostnader: {e}")
    
    return flags


def ai_analyze_flags(flags: list[RedFlag], df: pd.DataFrame, coach: GranskningsCoach) -> list[RedFlag]:
    """
    Enhance red flags with AI analysis.
    
    Args:
        flags: List of detected red flags
        df: Original DataFrame for context
        coach: GranskningsCoach instance
        
    Returns:
        Enhanced list of red flags
    """
    enhanced = []
    
    for flag in flags:
        # Get sample transactions for context
        if flag.transaktioner:
            sample_rows = df.iloc[flag.transaktioner[:5]].to_dict('records')
            context = f"Flagga: {flag.kategori}\n"
            context += f"Beskrivning: {flag.beskrivning}\n"
            context += f"Exempel på transaktioner:\n"
            for row in sample_rows:
                context += f"  - {row}\n"
            
            # Ask AI for enhanced recommendation
            try:
                ai_analysis = coach.ask(
                    "Baserat på denna flagga från transaktionsanalysen, ge en kort "
                    "rekommendation om vad journalisten bör fokusera på.",
                    context=context
                )
                flag.rekommendation = ai_analysis
            except Exception:
                pass  # Keep original recommendation
        
        enhanced.append(flag)
    
    return enhanced


def generate_summary(df: pd.DataFrame, flags: list[RedFlag], column_mapping: dict) -> dict:
    """
    Generate analysis summary statistics.
    
    Args:
        df: Analyzed DataFrame
        flags: List of red flags found
        column_mapping: Column mapping
        
    Returns:
        Dict with summary statistics
    """
    summary = {
        'total_transactions': len(df),
        'total_amount': 0,
        'date_range': None,
        'top_suppliers': [],
        'account_distribution': {},
        'flags_by_severity': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        'total_flags': len(flags)
    }
    
    # Total amount
    if column_mapping.get('belopp') and column_mapping['belopp'] in df.columns:
        summary['total_amount'] = df[column_mapping['belopp']].abs().sum()
    
    # Date range
    if column_mapping.get('datum') and column_mapping['datum'] in df.columns:
        date_col = df[column_mapping['datum']]
        if pd.api.types.is_datetime64_any_dtype(date_col):
            valid_dates = date_col.dropna()
            if len(valid_dates) > 0:
                summary['date_range'] = (valid_dates.min(), valid_dates.max())
    
    # Top suppliers
    if column_mapping.get('leverantör') and column_mapping['leverantör'] in df.columns:
        belopp_col = column_mapping.get('belopp', 'belopp')
        if belopp_col in df.columns:
            top = (df.groupby(column_mapping['leverantör'])[belopp_col]
                   .agg(['sum', 'count'])
                   .sort_values('sum', ascending=False)
                   .head(10))
            summary['top_suppliers'] = top.to_dict('index')
    
    # Account distribution
    if column_mapping.get('konto') and column_mapping['konto'] in df.columns:
        belopp_col = column_mapping.get('belopp', 'belopp')
        if belopp_col in df.columns:
            dist = (df.groupby(column_mapping['konto'])[belopp_col]
                    .sum()
                    .abs()
                    .sort_values(ascending=False)
                    .head(15))
            summary['account_distribution'] = dist.to_dict()
    
    # Flags by severity
    for flag in flags:
        summary['flags_by_severity'][flag.allvarlighet] += 1
    
    return summary


def search_transactions(df: pd.DataFrame, 
                        column_mapping: dict,
                        supplier: str = None,
                        min_amount: float = None,
                        max_amount: float = None,
                        account: str = None,
                        description: str = None) -> pd.DataFrame:
    """
    Search and filter transactions.
    
    Args:
        df: DataFrame to search
        column_mapping: Column mapping
        supplier: Supplier name filter (partial match)
        min_amount: Minimum amount
        max_amount: Maximum amount
        account: Account number filter (prefix match)
        description: Description filter (partial match)
        
    Returns:
        Filtered DataFrame
    """
    result = df.copy()
    
    if supplier and column_mapping.get('leverantör'):
        col = column_mapping['leverantör']
        result = result[result[col].str.contains(supplier, case=False, na=False)]
    
    if min_amount is not None and column_mapping.get('belopp'):
        col = column_mapping['belopp']
        result = result[result[col].abs() >= min_amount]
    
    if max_amount is not None and column_mapping.get('belopp'):
        col = column_mapping['belopp']
        result = result[result[col].abs() <= max_amount]
    
    if account and column_mapping.get('konto'):
        col = column_mapping['konto']
        result = result[result[col].astype(str).str.startswith(account)]
    
    if description and column_mapping.get('beskrivning'):
        col = column_mapping['beskrivning']
        result = result[result[col].str.contains(description, case=False, na=False)]
    
    return result
