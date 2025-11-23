#!/usr/bin/env python3
"""
Query the procurement data parquet file with the 4 filters from Explore.tsx
and calculate the sum of MontoLineaAdjudica for each filter and their combination.
"""

import duckdb
import requests
from pathlib import Path

# Download the parquet file if not already cached
parquet_url = 'https://r2.themis.lat/all_months_tsne_gpu.parquet'
cache_file = Path('/tmp/all_months_tsne_gpu.parquet')

if not cache_file.exists():
    print(f"Downloading parquet file from {parquet_url}...")
    response = requests.get(parquet_url, stream=True)
    total_size = int(response.headers.get('content-length', 0))

    with open(cache_file, 'wb') as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    progress = (downloaded / total_size) * 100
                    print(f"\rProgress: {progress:.1f}%", end='', flush=True)
    print("\n✓ Download complete")
else:
    print("Using cached parquet file")

# Connect to DuckDB and load the parquet file
print("\nInitializing DuckDB and loading data...")
con = duckdb.connect(':memory:')
con.execute(f"CREATE TABLE data AS SELECT * FROM parquet_scan('{cache_file}')")

# Define the 4 filters from Explore.tsx (lines 397-413)
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

print("\n" + "="*80)
print("RESULTS - Sum of MontoLineaAdjudica for each filter")
print("="*80)

# Query each filter individually
for name, predicate in filters.items():
    query = f"""
    SELECT
        COUNT(*) as count,
        SUM(MontoLineaAdjudica) as total_monto,
        AVG(MontoLineaAdjudica) as avg_monto
    FROM data
    WHERE {predicate}
        AND MontoLineaAdjudica IS NOT NULL
    """
    result = con.execute(query).fetchone()
    count, total_monto, avg_monto = result

    print(f"\n{name}:")
    print(f"  Records: {count:,}")
    print(f"  Total Monto Adjudicado: ${total_monto:,.2f}" if total_monto else "  Total Monto Adjudicado: $0.00")
    print(f"  Average Monto: ${avg_monto:,.2f}" if avg_monto else "  Average Monto: $0.00")

# Query with ALL 4 filters combined (OR)
print("\n" + "="*80)
print("COMBINED - All 4 filters together (OR condition)")
print("="*80)

combined_where = " OR ".join([f"({predicate})" for predicate in filters.values()])
query = f"""
SELECT
    COUNT(*) as count,
    SUM(MontoLineaAdjudica) as total_monto,
    AVG(MontoLineaAdjudica) as avg_monto
FROM data
WHERE {combined_where}
    AND MontoLineaAdjudica IS NOT NULL
"""
result = con.execute(query).fetchone()
count, total_monto, avg_monto = result

print(f"\nRecords matching ALL filters: {count:,}")
print(f"Total Monto Adjudicado: ${total_monto:,.2f}" if total_monto else "Total Monto Adjudicado: $0.00")
print(f"Average Monto: ${avg_monto:,.2f}" if avg_monto else "Average Monto: $0.00")

# Show some sample records that match all filters
print("\n" + "="*80)
print("Sample records matching all filters (first 5):")
print("="*80)

query = f"""
SELECT
    CodigoExterno,
    tender_name,
    MontoLineaAdjudica,
    FechaPublicacion,
    FechaCierre,
    FechaAdjudicacion,
    first_activity_date
FROM data
WHERE {combined_where}
    AND MontoLineaAdjudica IS NOT NULL
LIMIT 5
"""
result = con.execute(query).fetchall()
for row in result:
    print(f"\n  Código: {row[0]}")
    print(f"  Nombre: {row[1][:80]}..." if len(str(row[1])) > 80 else f"  Nombre: {row[1]}")
    print(f"  Monto: ${row[2]:,.2f}")
    print(f"  Publicación: {row[3]} | Cierre: {row[4]} | Adjudicación: {row[5]}")

print("\n" + "="*80)
