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
    database="epadata"
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


# -----------------------------
# LOAD FACILITIES
# -----------------------------

facilities_df = pd.read_csv(FACILITIES_FILE)

facilities_df = facilities_df.astype(object).where(
    pd.notnull(facilities_df),
    None
)

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

for _, row in facilities_df.iterrows():
    cursor.execute(
        facility_sql,
        (
            row["facility_id"],
            row["facility_name"],
            row["state"],
            row["county"],
            row["latitude"],
            row["longitude"],
            row["source_category"]
        )
    )

conn.commit()

print(f"Loaded {len(facilities_df)} facilities.")


# -----------------------------
# LOAD UNITS
# -----------------------------

units_df = pd.read_csv(UNITS_FILE)

units_df = units_df.astype(object).where(
    pd.notnull(units_df),
    None
)

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

for _, row in units_df.iterrows():
    cursor.execute(
        unit_sql,
        (
            row["facility_id"],
            row["unit_id"],
            row["unit_type"],
            row["so2_controls"],
            row["nox_controls"],
            row["pm_controls"]
        )
    )

conn.commit()

print(f"Loaded {len(units_df)} units.")


# -----------------------------
# LOAD ANNUAL EMISSIONS
# -----------------------------

emissions_df = pd.read_csv(EMISSIONS_FILE)

emissions_df = emissions_df.astype(object).where(
    pd.notnull(emissions_df),
    None
)

emissions_df["unit_id"] = emissions_df["unit_id"].apply(
    lambda x: str(x) if x is not None else None
)

emissions_sql = """
INSERT IGNORE INTO Annual_Emissions (
    facility_id,
    unit_id,
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
    %s, %s, %s, %s
)
"""

for _, row in emissions_df.iterrows():
    cursor.execute(
        emissions_sql,
        (
            row["facility_id"],
            row["unit_id"],
            row["reporting_year"],
            row["associated_stacks"],
            row["operating_time_count"],
            row["sum_of_the_operating_time"],
            row["gross_load_(mwh)"],
            row["steam_load_(1000_lb)"],
            row["so2_mass_(short_tons)"],
            row["so2_rate_(lbs/mmbtu)"],
            row["co2_mass_(short_tons)"],
            row["co2_rate_(short_tons/mmbtu)"],
            row["nox_mass_(short_tons)"],
            row["nox_rate_(lbs/mmbtu)"],
            row["heat_input_(mmbtu)"],
            row["primary_fuel_type"],
            row["secondary_fuel_type"],
            row["hg_controls"],
            row["program_code"]
        )
    )

conn.commit()

print(f"Loaded {len(emissions_df)} annual emissions records.")


# -----------------------------
# LOAD DATASET METADATA
# -----------------------------

metadata_df = pd.read_csv(METADATA_FILE)

metadata_df = metadata_df.astype(object).where(
    pd.notnull(metadata_df),
    None
)

metadata_sql = """
INSERT IGNORE INTO Dataset_Metadata (
    dataset_name,
    data_source,
    reporting_year,
    processed_date,
    original_filename,
    raw_records_count,
    accepted_records_count,
    rejected_records_count,
    notes
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

for _, row in metadata_df.iterrows():
    cursor.execute(
        metadata_sql,
        (
            row["dataset_name"],
            row["data_source"],
            row["reporting_year"],
            row["processed_date"],
            row["original_filename"],
            row["raw_records_count"],
            row["accepted_records_count"],
            row["rejected_records_count"],
            row["notes"]
        )
    )

conn.commit()

print(f"Loaded {len(metadata_df)} metadata records.")


# -----------------------------
# FINISH
# -----------------------------

cursor.close()
conn.close()

print("Database loading complete!")