#!/usr/bin/env python3
"""
Find the records with extreme outlier values
"""

import duckdb
from pathlib import Path

cache_file = Path('/tmp/all_months_tsne_gpu.parquet')

print("Loading data...")
con = duckdb.connect(':memory:')
con.execute(f"CREATE TABLE data AS SELECT * FROM parquet_scan('{cache_file}')")

# Define the 4 filters
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

# Find outliers in the OR combination
combined_where = " OR ".join([f"({predicate})" for predicate in filters.values()])

print("\n" + "="*80)
print("RECORDS WITH EXTREME VALUES (> $1 Trillion)")
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
    date_diff('day', first_activity_date, FechaAdjudicacion) as days_from_start,
    date_diff('day', FechaPublicacion, FechaAdjudicacion) as days_from_pub
FROM data
WHERE ({combined_where})
    AND MontoLineaAdjudica > 1000000000000
ORDER BY MontoLineaAdjudica DESC
"""

result = con.execute(query).fetchall()

print(f"\nFound {len(result)} records with MontoLineaAdjudica > $1 Trillion\n")

for i, row in enumerate(result, 1):
    print(f"{i}. CodigoExterno: {row[0]}")
    print(f"   Nombre: {row[1]}")
    print(f"   MontoLineaAdjudica: ${row[2]:,.2f}")
    print(f"   first_activity_date: {row[3]}")
    print(f"   FechaPublicacion: {row[4]}")
    print(f"   FechaCierre: {row[5]}")
    print(f"   FechaAdjudicacion: {row[6]}")
    print(f"   Days from start: {row[7]}")
    print(f"   Days from publication: {row[8]}")
    print()

print("="*80)
