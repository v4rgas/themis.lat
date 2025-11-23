#!/usr/bin/env python3
"""
Query with first_activity_date validation removed from Filter 1
"""

import duckdb
from pathlib import Path

cache_file = Path('/tmp/all_months_tsne_gpu.parquet')

print("Loading data...")
con = duckdb.connect(':memory:')
con.execute(f"CREATE TABLE data AS SELECT * FROM parquet_scan('{cache_file}')")

# Define the filters - removed first_activity_date >= '2000-01-01' check
filters = {
    "Adjudicación Rápida (<30 días)": """
        date_diff('day', first_activity_date, FechaAdjudicacion) < 30
        AND date_diff('day', first_activity_date, FechaAdjudicacion) > 0
        AND FechaAdjudicacion >= '2000-01-01'
    """,

    "Publicación a Cierre (<5 días)": """
        date_diff('day', FechaPublicacion, FechaCierre) < 5
        AND date_diff('day', FechaPublicacion, FechaCierre) >= 0
        AND FechaPublicacion >= '2000-01-01'
        AND FechaCierre >= '2000-01-01'
    """
}

print("\n" + "="*80)
print("RESULTS - Without first_activity_date validation")
print("="*80)

# Query each filter individually
for name, predicate in filters.items():
    query = f"""
    SELECT
        COUNT(*) as count,
        SUM(MontoLineaAdjudica) as total_monto,
        AVG(MontoLineaAdjudica) as avg_monto,
        MEDIAN(MontoLineaAdjudica) as median_monto,
        MIN(MontoLineaAdjudica) as min_monto,
        MAX(MontoLineaAdjudica) as max_monto
    FROM data
    WHERE {predicate}
        AND MontoLineaAdjudica IS NOT NULL
        AND MontoLineaAdjudica > 0
        AND MontoLineaAdjudica < 1000000000000
    """
    result = con.execute(query).fetchone()
    count, total_monto, avg_monto, median_monto, min_monto, max_monto = result

    print(f"\n{name}:")
    print(f"  Records: {count:,}")
    print(f"  Total Monto: ${total_monto:,.2f}" if total_monto else "  Total Monto: $0.00")
    print(f"  Average: ${avg_monto:,.2f}" if avg_monto else "  Average: $0.00")
    print(f"  Median: ${median_monto:,.2f}" if median_monto else "  Median: $0.00")

# Query with both filters combined (OR)
print("\n" + "="*80)
print("COMBINED - Both filters (OR condition)")
print("="*80)

combined_where = " OR ".join([f"({predicate})" for predicate in filters.values()])
query = f"""
SELECT
    COUNT(*) as count,
    SUM(MontoLineaAdjudica) as total_monto,
    AVG(MontoLineaAdjudica) as avg_monto,
    MEDIAN(MontoLineaAdjudica) as median_monto
FROM data
WHERE ({combined_where})
    AND MontoLineaAdjudica IS NOT NULL
    AND MontoLineaAdjudica > 0
    AND MontoLineaAdjudica < 1000000000000
"""
result = con.execute(query).fetchone()
count, total_monto, avg_monto, median_monto = result

print(f"\nRecords matching ANY filter: {count:,}")
print(f"Total Monto: ${total_monto:,.2f}" if total_monto else "Total Monto: $0.00")
print(f"Average: ${avg_monto:,.2f}" if avg_monto else "Average: $0.00")
print(f"Median: ${median_monto:,.2f}" if median_monto else "Median: $0.00")

# Check for overlap
print("\n" + "="*80)
print("OVERLAP CHECK")
print("="*80)

filter1 = list(filters.values())[0]
filter2 = list(filters.values())[1]

query = f"""
SELECT COUNT(*) as count, SUM(MontoLineaAdjudica) as total_monto
FROM data
WHERE ({filter1}) AND ({filter2})
    AND MontoLineaAdjudica IS NOT NULL
    AND MontoLineaAdjudica > 0
    AND MontoLineaAdjudica < 1000000000000
"""
result = con.execute(query).fetchone()
overlap_count, overlap_monto = result

print(f"Records matching BOTH filters: {overlap_count:,}")
print(f"Total Monto in overlap: ${overlap_monto:,.2f}" if overlap_monto else "Total Monto in overlap: $0.00")

print("\n" + "="*80)
