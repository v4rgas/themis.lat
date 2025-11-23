#!/usr/bin/env python3
"""
Investigate the data to understand why the sums are so large
"""

import duckdb
from pathlib import Path

cache_file = Path('/tmp/all_months_tsne_gpu.parquet')

# Connect to DuckDB and load the parquet file
print("Loading data...")
con = duckdb.connect(':memory:')
con.execute(f"CREATE TABLE data AS SELECT * FROM parquet_scan('{cache_file}')")

# Check the schema
print("\n" + "="*80)
print("TABLE SCHEMA")
print("="*80)
schema = con.execute("DESCRIBE data").fetchall()
for row in schema:
    print(f"{row[0]}: {row[1]}")

# Check basic stats on MontoLineaAdjudica
print("\n" + "="*80)
print("MontoLineaAdjudica STATISTICS")
print("="*80)
stats = con.execute("""
    SELECT
        COUNT(*) as total_records,
        COUNT(MontoLineaAdjudica) as non_null_records,
        MIN(MontoLineaAdjudica) as min_value,
        MAX(MontoLineaAdjudica) as max_value,
        AVG(MontoLineaAdjudica) as avg_value,
        MEDIAN(MontoLineaAdjudica) as median_value,
        SUM(MontoLineaAdjudica) as total_sum
    FROM data
""").fetchone()

print(f"Total Records: {stats[0]:,}")
print(f"Non-NULL Records: {stats[1]:,}")
print(f"Min Value: ${stats[2]:,.2f}" if stats[2] else "Min Value: NULL")
print(f"Max Value: ${stats[3]:,.2f}" if stats[3] else "Max Value: NULL")
print(f"Average Value: ${stats[4]:,.2f}" if stats[4] else "Average Value: NULL")
print(f"Median Value: ${stats[5]:,.2f}" if stats[5] else "Median Value: NULL")
print(f"Total Sum: ${stats[6]:,.2f}" if stats[6] else "Total Sum: NULL")

# Look at top 10 largest values
print("\n" + "="*80)
print("TOP 10 LARGEST MontoLineaAdjudica VALUES")
print("="*80)
top_values = con.execute("""
    SELECT
        CodigoExterno,
        tender_name,
        MontoLineaAdjudica,
        first_activity_date,
        FechaPublicacion,
        FechaCierre,
        FechaAdjudicacion
    FROM data
    WHERE MontoLineaAdjudica IS NOT NULL
    ORDER BY MontoLineaAdjudica DESC
    LIMIT 10
""").fetchall()

for i, row in enumerate(top_values, 1):
    print(f"\n{i}. Código: {row[0]}")
    print(f"   Nombre: {row[1][:80]}..." if len(str(row[1])) > 80 else f"   Nombre: {row[1]}")
    print(f"   Monto: ${row[2]:,.2f}")
    print(f"   Dates: {row[3]} | {row[4]} | {row[5]} | {row[6]}")

# Check for the filters - see how many records match and their stats
print("\n" + "="*80)
print("FILTER ANALYSIS - Checking for outliers")
print("="*80)

filters = {
    "Adjudicación Rápida (<30 días)":
        "date_diff('day', first_activity_date, FechaAdjudicacion) < 30",
    "Adjudicación Diaria > $1M (desde inicio)":
        "MontoLineaAdjudica/date_diff('day', first_activity_date, FechaAdjudicacion) > 1000000",
    "Adjudicación Diaria > $1M (desde publicación)":
        "MontoLineaAdjudica/date_diff('day', FechaPublicacion, FechaAdjudicacion) > 1000000",
    "Publicación a Cierre (<5 días)":
        "date_diff('day', FechaPublicacion, FechaCierre) < 5"
}

for name, predicate in filters.items():
    print(f"\n{name}:")
    stats = con.execute(f"""
        SELECT
            COUNT(*) as count,
            MIN(MontoLineaAdjudica) as min_monto,
            MAX(MontoLineaAdjudica) as max_monto,
            AVG(MontoLineaAdjudica) as avg_monto,
            MEDIAN(MontoLineaAdjudica) as median_monto
        FROM data
        WHERE {predicate}
            AND MontoLineaAdjudica IS NOT NULL
    """).fetchone()

    print(f"  Count: {stats[0]:,}")
    print(f"  Min: ${stats[1]:,.2f}" if stats[1] else "  Min: NULL")
    print(f"  Max: ${stats[2]:,.2f}" if stats[2] else "  Max: NULL")
    print(f"  Avg: ${stats[3]:,.2f}" if stats[3] else "  Avg: NULL")
    print(f"  Median: ${stats[4]:,.2f}" if stats[4] else "  Median: NULL")

# Check if there are issues with date calculations (division by zero or negative)
print("\n" + "="*80)
print("DATE CALCULATION ISSUES")
print("="*80)

# Check for zero or negative day differences
for filter_name, date_calc in [
    ("Desde inicio", "date_diff('day', first_activity_date, FechaAdjudicacion)"),
    ("Desde publicación", "date_diff('day', FechaPublicacion, FechaAdjudicacion)")
]:
    result = con.execute(f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN {date_calc} = 0 THEN 1 ELSE 0 END) as zero_days,
            SUM(CASE WHEN {date_calc} < 0 THEN 1 ELSE 0 END) as negative_days,
            SUM(CASE WHEN {date_calc} = 1 THEN 1 ELSE 0 END) as one_day,
            MIN({date_calc}) as min_days,
            MAX({date_calc}) as max_days
        FROM data
        WHERE MontoLineaAdjudica IS NOT NULL
            AND {date_calc} IS NOT NULL
    """).fetchone()

    print(f"\n{filter_name}:")
    print(f"  Total: {result[0]:,}")
    print(f"  Zero days: {result[1]:,}")
    print(f"  Negative days: {result[2]:,}")
    print(f"  One day: {result[3]:,}")
    print(f"  Min days: {result[4]}")
    print(f"  Max days: {result[5]}")
