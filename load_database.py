import os
import pandas as pd
import mysql.connector
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


# -----------------------------
# CONNECT TO MYSQL
# -----------------------------

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password=os.getenv("DB_PASSWORD"),
    database="epadata",
    allow_local_infile=True,
    use_pure=True  # Force pure Python connector
)

cursor = conn.cursor()

print("Connected to MySQL!")


# -----------------------------
# FILE PATHS
# -----------------------------

FACILITIES_FILE = "data/seed/clean_facilities.csv"
UNITS_FILE = "data/seed/clean_units.csv"
EMISSIONS_FILE = "data/seed/clean_annual_records.csv"
METADATA_FILE = "data/seed/clean_datasets_metadata.csv"
TRACI_FILE = "data/seed/clean_traci_factors.csv"
HOURLY_EMISSIONS_FILE = "data/seed/clean_hourly_emissions.csv"  # Hourly CEMS dataset
DAILY_EMISSIONS_FILE = "data/seed/clean_daily_emissions.csv"    # Daily CEMS dataset


# Helper function to standardize DataFrame column names
def normalize_df_columns(df):
    df.columns = df.columns.str.strip().str.lower()
    return df


# -----------------------------
# 1. SEED MEASUREMENT METHODS
# -----------------------------

seed_methods = [
    ("CEMS", "Continuous Emission Monitoring System", "Direct real-time measurement via installed stack monitors.", "Primary"),
    ("SUB", "Missing Data Substitution", "EPA Part 75 conservative value substitution for system downtime.", "Substitute"),
    ("APP_D", "Appendix D Fuel Sampling", "Mass flow meter and fuel sampling protocol for oil/gas units.", "Calculated"),
    ("APP_E", "Appendix E NOx Estimation", "Mass flow meter/correlation curve method for gas-fired peaking units.", "Calculated"),
    ("DEFAULT", "Default Emission Factor", "Standard default EPA emission factor applied based on fuel type.", "Estimated")
]

methods_sql = """
INSERT IGNORE INTO Measurement_Methods (
    method_code,
    method_name,
    method_description,
    data_tier
)
VALUES (%s, %s, %s, %s)
"""

cursor.executemany(methods_sql, seed_methods)
conn.commit()
print(f"Seeded {len(seed_methods)} measurement methods.")


# -----------------------------
# 2. LOAD DATASET METADATA
# -----------------------------

if os.path.exists(METADATA_FILE):
    metadata_df = pd.read_csv(METADATA_FILE)
    metadata_df = normalize_df_columns(metadata_df)
    metadata_df = metadata_df.astype(object).where(pd.notnull(metadata_df), None)

    metadata_sql = """
    INSERT IGNORE INTO Dataset_Metadata (
        dataset_name,
        data_source,
        reporting_year,
        granularity,
        processed_date,
        original_filename,
        raw_records_count,
        accepted_records_count,
        rejected_records_count,
        notes
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    metadata_records = [
        (
            row.get("dataset_name"),
            row.get("data_source"),
            row.get("reporting_year"),
            row.get("granularity", "Annual"),
            row.get("processed_date"),
            row.get("original_filename"),
            row.get("raw_records_count"),
            row.get("accepted_records_count"),
            row.get("rejected_records_count"),
            row.get("notes")
        )
        for _, row in metadata_df.iterrows()
    ]

    cursor.executemany(metadata_sql, metadata_records)
    conn.commit()
    print(f"Loaded {len(metadata_records)} metadata records.")


# -----------------------------
# 3. LOAD TRACI FACTORS
# -----------------------------

if os.path.exists(TRACI_FILE):
    traci_df = pd.read_csv(TRACI_FILE)
    traci_df = normalize_df_columns(traci_df)
    traci_df = traci_df.astype(object).where(pd.notnull(traci_df), None)

    traci_sql = """
    INSERT IGNORE INTO TRACI_Factors (
        substance, cas_number, category, factor, unit
    ) VALUES (%s, %s, %s, %s, %s)
    """

    traci_records = []
    for _, row in traci_df.iterrows():
        substance = row.get("substance") or row.get("chemical") or row.get("pollutant") or row.get("substance_name") or row.get("substance name")
        category = row.get("category") or row.get("impact_category") or row.get("traci_category") or row.get("impact category")
        factor = row.get("factor") or row.get("value") or row.get("traci_factor") or row.get("characterization factor")
        unit = row.get("unit") or row.get("units") or "kg eq"

        if substance and category and factor is not None:
            traci_records.append((
                str(substance).strip(),
                row.get("cas_number") or row.get("cas") or row.get("cas_no"),
                str(category).strip(),
                float(factor),
                str(unit).strip()
            ))

    if traci_records:
        cursor.executemany(traci_sql, traci_records)
        conn.commit()
    print(f"Loaded {len(traci_records)} TRACI factors.")
else:
    print(f"Warning: TRACI file not found at {TRACI_FILE}")


# -----------------------------
# 4. LOAD FACILITIES
# -----------------------------

if os.path.exists(FACILITIES_FILE):
    facilities_df = pd.read_csv(FACILITIES_FILE)
    facilities_df = normalize_df_columns(facilities_df)
    facilities_df = facilities_df.astype(object).where(pd.notnull(facilities_df), None)

    facility_sql = """
    INSERT IGNORE INTO Facilities (
        facility_id,
        facility_name,
        state,
        county,
        latitude,
        longitude,
        source_category
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    facility_records = [
        (
            row.get("facility_id"),
            row.get("facility_name"),
            row.get("state"),
            row.get("county"),
            row.get("latitude"),
            row.get("longitude"),
            row.get("source_category")
        )
        for _, row in facilities_df.iterrows()
    ]

    cursor.executemany(facility_sql, facility_records)
    conn.commit()
    print(f"Loaded {len(facility_records)} facilities.")


# -----------------------------
# 5. LOAD UNITS
# -----------------------------

if os.path.exists(UNITS_FILE):
    units_df = pd.read_csv(UNITS_FILE)
    units_df = normalize_df_columns(units_df)
    units_df = units_df.astype(object).where(pd.notnull(units_df), None)

    units_df["unit_id"] = units_df["unit_id"].apply(
        lambda x: str(x) if x is not None else None
    )

    unit_sql = """
    INSERT IGNORE INTO Units (
        facility_id,
        unit_id,
        unit_type,
        so2_controls,
        nox_controls,
        pm_controls
    )
    VALUES (%s, %s, %s, %s, %s, %s)
    """

    unit_records = [
        (
            row.get("facility_id"),
            row.get("unit_id"),
            row.get("unit_type"),
            row.get("so2_controls"),
            row.get("nox_controls"),
            row.get("pm_controls")
        )
        for _, row in units_df.iterrows()
    ]

    cursor.executemany(unit_sql, unit_records)
    conn.commit()
    print(f"Loaded {len(unit_records)} units.")


# -----------------------------
# 6. LOAD ANNUAL EMISSIONS
# -----------------------------

if os.path.exists(EMISSIONS_FILE):
    emissions_df = pd.read_csv(EMISSIONS_FILE)
    emissions_df = normalize_df_columns(emissions_df)
    emissions_df = emissions_df.astype(object).where(pd.notnull(emissions_df), None)

    emissions_df["unit_id"] = emissions_df["unit_id"].apply(
        lambda x: str(x) if x is not None else None
    )

    emissions_sql = """
    INSERT IGNORE INTO Annual_Emissions (
        facility_id,
        unit_id,
        metadata_id,
        reporting_year,
        associated_stacks,
        operating_time_count,
        sum_of_the_operating_time,
        gross_load_mwh,
        steam_load_1000_lb,
        so2_mass_short_tons,
        so2_rate_lbs_mmbtu,
        co2_mass_short_tons,
        co2_rate_short_tons_mmbtu,
        nox_mass_short_tons,
        nox_rate_lbs_mmbtu,
        heat_input_mmbtu,
        primary_fuel_type,
        secondary_fuel_type,
        hg_controls,
        program_code
    )
    VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    )
    """

    emissions_records = [
        (
            row.get("facility_id"),
            row.get("unit_id"),
            row.get("metadata_id"),
            row.get("reporting_year"),
            row.get("associated_stacks"),
            row.get("operating_time_count"),
            row.get("sum_of_the_operating_time"),
            row.get("gross_load_(mwh)") or row.get("gross_load_mwh"),
            row.get("steam_load_(1000_lb)") or row.get("steam_load_1000_lb"),
            row.get("so2_mass_(short_tons)") or row.get("so2_mass_short_tons"),
            row.get("so2_rate_(lbs/mmbtu)") or row.get("so2_rate_lbs_mmbtu"),
            row.get("co2_mass_(short_tons)") or row.get("co2_mass_short_tons"),
            row.get("co2_rate_(short_tons/mmbtu)") or row.get("co2_rate_short_tons_mmbtu"),
            row.get("nox_mass_(short_tons)") or row.get("nox_mass_short_tons"),
            row.get("nox_rate_(lbs/mmbtu)") or row.get("nox_rate_lbs_mmbtu"),
            row.get("heat_input_(mmbtu)") or row.get("heat_input_mmbtu"),
            row.get("primary_fuel_type"),
            row.get("secondary_fuel_type"),
            row.get("hg_controls"),
            row.get("program_code")
        )
        for _, row in emissions_df.iterrows()
    ]

    cursor.executemany(emissions_sql, emissions_records)
    conn.commit()
    print(f"Loaded {len(emissions_records)} annual emissions records.")


# -----------------------------
# 7. LOAD DAILY EMISSIONS (BATCHED EXECUTEMANY)
# -----------------------------

if os.path.exists(DAILY_EMISSIONS_FILE):
    print("Loading Daily Emissions using batched executemany...")
    
    # Temporarily disable index checks for faster batch inserts
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("SET UNIQUE_CHECKS = 0;")

    daily_sql = """
    INSERT IGNORE INTO Daily_Emissions (
        facility_id, unit_id, metadata_id, op_date,
        gload_mwh, sload_1000_lb, so2_mass_lbs, so2_mass_short_tons,
        co2_mass_tons, nox_mass_lbs, nox_mass_short_tons, heat_input_mmbtu
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    chunk_size = 50000
    total_loaded_daily = 0

    for chunk in pd.read_csv(DAILY_EMISSIONS_FILE, chunksize=chunk_size, low_memory=False):
        chunk = normalize_df_columns(chunk)
        chunk = chunk.astype(object).where(pd.notnull(chunk), None)

        records = [
            (
                row.get("facility_id"),
                str(row.get("unit_id")) if row.get("unit_id") is not None else None,
                1,  # metadata_id default
                row.get("op_date"),
                row.get("gload_mwh"),
                row.get("sload_1000_lb"),
                row.get("so2_mass_lbs"),
                row.get("so2_mass_short_tons"),
                row.get("co2_mass_tons"),
                row.get("nox_mass_lbs"),
                row.get("nox_mass_short_tons"),
                row.get("heat_input_mmbtu")
            )
            for _, row in chunk.iterrows()
        ]

        cursor.executemany(daily_sql, records)
        conn.commit()
        total_loaded_daily += len(records)
        print(f"  Inserted daily batch... ({total_loaded_daily:,} total records loaded)")

    # Re-enable checks
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    cursor.execute("SET UNIQUE_CHECKS = 1;")
    print(f"Finished loading {total_loaded_daily:,} daily records!")

# -----------------------------
# 8. LOAD HOURLY EMISSIONS (BATCHED EXECUTEMANY)
# -----------------------------

if os.path.exists(HOURLY_EMISSIONS_FILE):
    print("Loading Hourly Emissions using batched executemany...")
    
    # Temporarily disable index checks for faster batch inserts
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("SET UNIQUE_CHECKS = 0;")

    hourly_sql = """
    INSERT IGNORE INTO Hourly_Emissions (
        facility_id, unit_id, metadata_id, op_date, op_hour,
        op_time, gload_mwh, so2_mass_lbs, nox_mass_lbs, 
        co2_mass_tons, heat_input_mmbtu,
        so2_mass_method_code, nox_mass_method_code, co2_mass_method_code
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'CEMS', 'CEMS', 'CEMS')
    """

    chunk_size = 50000
    total_loaded = 0

    for chunk in pd.read_csv(HOURLY_EMISSIONS_FILE, chunksize=chunk_size, low_memory=False):
        chunk = normalize_df_columns(chunk)
        chunk = chunk.astype(object).where(pd.notnull(chunk), None)

        records = [
            (
                row.get("facility_id"),
                str(row.get("unit_id")) if row.get("unit_id") is not None else None,
                1,  # metadata_id default
                row.get("op_date"),
                row.get("op_hour"),
                row.get("op_time"),
                row.get("gload_mwh"),
                row.get("so2_mass_lbs"),
                row.get("nox_mass_lbs"),
                row.get("co2_mass_tons"),
                row.get("heat_input_mmbtu")
            )
            for _, row in chunk.iterrows()
        ]

        cursor.executemany(hourly_sql, records)
        conn.commit()
        total_loaded += len(records)
        print(f"  Inserted hourly batch... ({total_loaded:,} total records loaded)")

    # Re-enable checks
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    cursor.execute("SET UNIQUE_CHECKS = 1;")
    print(f"Finished loading {total_loaded:,} hourly records!")


# -----------------------------
# 9. CALCULATE EMISSIONS TRACI IMPACTS
# -----------------------------

impacts_sql = """
INSERT INTO Emissions_TRACI_Impacts (
    emission_id, traci_id, calculated_impact_value
)
SELECT 
    e.emission_id,
    t.traci_id,
    CASE 
        WHEN LOWER(t.category) LIKE '%acidification%' AND (LOWER(t.substance) LIKE '%sulfur%' OR LOWER(t.substance) LIKE '%so2%') THEN
            (e.so2_mass_short_tons * 907.185) * t.factor
            
        WHEN LOWER(t.category) LIKE '%global warming%' AND (LOWER(t.substance) LIKE '%carbon%' OR LOWER(t.substance) LIKE '%co2%') THEN
            (e.co2_mass_short_tons * 907.185) * t.factor
            
        WHEN LOWER(t.category) LIKE '%eutrophication%' AND (LOWER(t.substance) LIKE '%nitrogen%' OR LOWER(t.substance) LIKE '%nox%') THEN
            (e.nox_mass_short_tons * 907.185) * t.factor
        ELSE 0
    END AS calculated_impact_value
FROM Annual_Emissions e
CROSS JOIN TRACI_Factors t
WHERE (
    (LOWER(t.category) LIKE '%acidification%' AND (LOWER(t.substance) LIKE '%sulfur%' OR LOWER(t.substance) LIKE '%so2%')) OR
    (LOWER(t.category) LIKE '%global warming%' AND (LOWER(t.substance) LIKE '%carbon%' OR LOWER(t.substance) LIKE '%co2%')) OR
    (LOWER(t.category) LIKE '%eutrophication%' AND (LOWER(t.substance) LIKE '%nitrogen%' OR LOWER(t.substance) LIKE '%nox%'))
)
ON DUPLICATE KEY UPDATE 
    calculated_impact_value = VALUES(calculated_impact_value);
"""

cursor.execute(impacts_sql)
conn.commit()
print(f"Calculated {cursor.rowcount} TRACI environmental impact records.")


# -----------------------------
# FINISH
# -----------------------------

cursor.close()
conn.close()

print("Database loading complete!")