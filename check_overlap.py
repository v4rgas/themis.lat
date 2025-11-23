#!/usr/bin/env python3
"""
Check for overlap between the two filters
"""

import duckdb
from pathlib import Path

cache_file = Path('/tmp/all_months_tsne_gpu.parquet')

print("Loading data...")
con = duckdb.connect(':memory:')
con.execute(f"CREATE TABLE data AS SELECT * FROM parquet_scan('{cache_file}')")

# Define the filters
filter1 = """
    date_diff('day', first_activity_date, FechaAdjudicacion) < 30
    AND date_diff('day', first_activity_date, FechaAdjudicacion) > 0
    AND first_activity_date >= '2000-01-01'
    AND FechaAdjudicacion >= '2000-01-01'
"""

filter2 = """
    date_diff('day', FechaPublicacion, FechaCierre) < 5
    AND date_diff('day', FechaPublicacion, FechaCierre) >= 0
    AND FechaPublicacion >= '2000-01-01'
    AND FechaCierre >= '2000-01-01'
"""

base_conditions = """
    AND MontoLineaAdjudica IS NOT NULL
    AND MontoLineaAdjudica > 0
    AND MontoLineaAdjudica < 1000000000000
"""

print("\n" + "="*80)
print("OVERLAP ANALYSIS")
print("="*80)

# Filter 1 only
query = f"""
SELECT
    COUNT(*) as count,
    SUM(MontoLineaAdjudica) as total_monto
FROM data
WHERE ({filter1})
    {base_conditions}
"""
result = con.execute(query).fetchone()
filter1_count, filter1_total = result
print(f"\nFilter 1 ONLY (Adjudicación Rápida <30 días):")
print(f"  Records: {filter1_count:,}")
print(f"  Total Monto: ${filter1_total:,.2f}")

# Filter 2 only
query = f"""
SELECT
    COUNT(*) as count,
    SUM(MontoLineaAdjudica) as total_monto
FROM data
WHERE ({filter2})
    {base_conditions}
"""
result = con.execute(query).fetchone()
filter2_count, filter2_total = result
print(f"\nFilter 2 ONLY (Publicación a Cierre <5 días):")
print(f"  Records: {filter2_count:,}")
print(f"  Total Monto: ${filter2_total:,.2f}")

# Records matching BOTH filters
query = f"""
SELECT
    COUNT(*) as count,
    SUM(MontoLineaAdjudica) as total_monto
FROM data
WHERE ({filter1})
    AND ({filter2})
    {base_conditions}
"""
result = con.execute(query).fetchone()
both_count, both_total = result
print(f"\nRecords matching BOTH filters (overlap):")
print(f"  Records: {both_count:,}")
print(f"  Total Monto: ${both_total:,.2f}" if both_total else "  Total Monto: $0.00")

# Records matching either (OR) - actual count
query = f"""
SELECT
    COUNT(*) as count,
    SUM(MontoLineaAdjudica) as total_monto
FROM data
WHERE (({filter1}) OR ({filter2}))
    {base_conditions}
"""
result = con.execute(query).fetchone()
or_count, or_total = result
print(f"\nRecords matching EITHER filter (OR):")
print(f"  Records: {or_count:,}")
print(f"  Total Monto: ${or_total:,.2f}")

# Breakdown
print("\n" + "="*80)
print("BREAKDOWN:")
print("="*80)
only_filter1 = filter1_count - both_count
only_filter2 = filter2_count - both_count
both_total = both_total or 0
only_filter1_monto = filter1_total - both_total
only_filter2_monto = filter2_total - both_total

print(f"\nRecords ONLY in Filter 1: {only_filter1:,}")
print(f"  Total Monto: ${only_filter1_monto:,.2f}")

print(f"\nRecords ONLY in Filter 2: {only_filter2:,}")
print(f"  Total Monto: ${only_filter2_monto:,.2f}")

print(f"\nRecords in BOTH filters: {both_count:,}")
print(f"  Total Monto: ${both_total:,.2f}")

print(f"\nVerification:")
print(f"  {only_filter1:,} + {only_filter2:,} + {both_count:,} = {only_filter1 + only_filter2 + both_count:,} (should equal {or_count:,})")

# Show some samples from the overlap
if both_count > 0:
    print("\n" + "="*80)
    print("Sample records matching BOTH filters:")
    print("="*80)
    query = f"""
    SELECT
        CodigoExterno,
        tender_name,
        MontoLineaAdjudica,
        first_activity_date,
        FechaPublicacion,
        FechaCierre,
        FechaAdjudicacion,
        date_diff('day', first_activity_date, FechaAdjudicacion) as days_to_adjudication,
        date_diff('day', FechaPublicacion, FechaCierre) as days_pub_to_close
    FROM data
    WHERE ({filter1})
        AND ({filter2})
        {base_conditions}
    LIMIT 5
    """
    result = con.execute(query).fetchall()
    for row in result:
        print(f"\n  Código: {row[0]}")
        print(f"  Nombre: {row[1][:60]}..." if len(str(row[1])) > 60 else f"  Nombre: {row[1]}")
        print(f"  Monto: ${row[2]:,.2f}")
        print(f"  Days to adjudication: {row[7]} | Days pub to close: {row[8]}")

print("\n" + "="*80)
