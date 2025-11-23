#!/usr/bin/env python3
"""
Show the actual query logic being used
"""

print("="*80)
print("QUERY LOGIC FOR THE TWO FILTERS")
print("="*80)

print("\n" + "="*80)
print("FILTER 1: Adjudicación Rápida (<30 días)")
print("="*80)
print("""
SELECT *
FROM data
WHERE date_diff('day', first_activity_date, FechaAdjudicacion) < 30
  AND date_diff('day', first_activity_date, FechaAdjudicacion) > 0
  AND first_activity_date >= '2000-01-01'
  AND FechaAdjudicacion >= '2000-01-01'
  AND MontoLineaAdjudica IS NOT NULL
  AND MontoLineaAdjudica > 0
  AND MontoLineaAdjudica < 1000000000000  -- Exclude extreme outliers

Logic:
  - Days from first_activity_date to FechaAdjudicacion < 30
  - Days must be positive (no negative date ranges)
  - Dates must be after 2000 (exclude placeholder dates like 1900-01-01)
  - Monto must be positive and less than $1 trillion (exclude corrupted data)
""")

print("\n" + "="*80)
print("FILTER 2: Publicación a Cierre (<5 días)")
print("="*80)
print("""
SELECT *
FROM data
WHERE date_diff('day', FechaPublicacion, FechaCierre) < 5
  AND date_diff('day', FechaPublicacion, FechaCierre) >= 0
  AND FechaPublicacion >= '2000-01-01'
  AND FechaCierre >= '2000-01-01'
  AND MontoLineaAdjudica IS NOT NULL
  AND MontoLineaAdjudica > 0
  AND MontoLineaAdjudica < 1000000000000  -- Exclude extreme outliers

Logic:
  - Days from FechaPublicacion to FechaCierre < 5
  - Days must be non-negative (0 or more)
  - Dates must be after 2000 (exclude placeholder dates)
  - Monto must be positive and less than $1 trillion (exclude corrupted data)
""")

print("\n" + "="*80)
print("COMBINED QUERY (OR condition)")
print("="*80)
print("""
SELECT *
FROM data
WHERE (
    -- Filter 1: Adjudicación Rápida
    (
      date_diff('day', first_activity_date, FechaAdjudicacion) < 30
      AND date_diff('day', first_activity_date, FechaAdjudicacion) > 0
      AND first_activity_date >= '2000-01-01'
      AND FechaAdjudicacion >= '2000-01-01'
    )
    OR
    -- Filter 2: Publicación a Cierre
    (
      date_diff('day', FechaPublicacion, FechaCierre) < 5
      AND date_diff('day', FechaPublicacion, FechaCierre) >= 0
      AND FechaPublicacion >= '2000-01-01'
      AND FechaCierre >= '2000-01-01'
    )
  )
  AND MontoLineaAdjudica IS NOT NULL
  AND MontoLineaAdjudica > 0
  AND MontoLineaAdjudica < 1000000000000

Logic:
  - Match records that satisfy EITHER filter 1 OR filter 2
  - Apply common data quality checks to all results
""")

print("\n" + "="*80)
print("KEY FIELDS EXPLAINED")
print("="*80)
print("""
first_activity_date: The earliest activity date for the tender
FechaPublicacion: Publication date of the tender
FechaCierre: Closing date for submissions
FechaAdjudicacion: Date when the tender was awarded
MontoLineaAdjudica: The awarded amount (in Chilean pesos)

date_diff('day', start_date, end_date):
  - Calculates the number of days between two dates
  - Returns negative if end_date < start_date
""")

print("\n" + "="*80)
print("DATA QUALITY FILTERS")
print("="*80)
print("""
1. Date validation:
   - All dates >= '2000-01-01' to exclude placeholder dates (1900, 1993, etc.)
   - Date differences must be positive or zero (no time travel!)

2. Amount validation:
   - MontoLineaAdjudica IS NOT NULL (exclude missing values)
   - MontoLineaAdjudica > 0 (exclude zero or negative amounts)
   - MontoLineaAdjudica < 1000000000000 (exclude 33 corrupted records with
     values in the quadrillions)

3. Why these limits?
   - The median award is around $78-211K pesos
   - The max realistic value is around $792B pesos
   - Values above $1 trillion are clearly data errors
""")

print("="*80)
