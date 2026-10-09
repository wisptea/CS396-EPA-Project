import os
import pandas as pd
from datetime import datetime

# Define relative directories
RAW_DIR = "data/raw"
SEED_DIR = "data/seed"

def clean_epa_pipeline():
    os.makedirs(SEED_DIR, exist_ok=True)
    
    # Track invalid records for data quality reporting
    rejected_records = []
    datasets_metadata = []

    # PROCESS FACILITIES & UNITS
    fac_path = os.path.join(RAW_DIR, "facility-2025.csv")
    if os.path.exists(fac_path):
        df_fac = pd.read_csv(fac_path)
        total_raw_fac = len(df_fac)
        df_fac.columns = df_fac.columns.str.strip().str.lower().str.replace(' ', '_')

        # Validate facilities (Facility ID and State are required)
        fac_invalid_mask = df_fac['facility_id'].isna() | df_fac['state'].isna()
        if fac_invalid_mask.any():
            bad_fac = df_fac[fac_invalid_mask].copy()
            bad_fac['rejection_reason'] = 'Missing Facility ID or State'
            rejected_records.append(bad_fac)
        
        df_fac_clean = df_fac[~fac_invalid_mask].copy()

        # Clean basic text fields
        df_fac_clean['state'] = df_fac_clean['state'].astype(str).str.upper().str.strip()
        df_fac_clean['facility_name'] = df_fac_clean['facility_name'].astype(str).str.strip()

        # --- A. Extract Clean Facilities Table ---
        facilities_cols = [
            'facility_id', 'facility_name', 'state', 'county', 
            'latitude', 'longitude', 'source_category'
        ]
        facilities_cols = [c for c in facilities_cols if c in df_fac_clean.columns]
        facilities_df = df_fac_clean[facilities_cols].drop_duplicates(subset=['facility_id'])
        facilities_df.to_csv(os.path.join(SEED_DIR, 'clean_facilities.csv'), index=False)

        # --- B. Extract Clean Units Table ---
        units_cols = [
            'facility_id', 'unit_id', 'unit_type', 
            'primary_fuel_info', 'secondary_fuel_info',
            'so2_controls', 'nox_controls', 'pm_controls',
            'operating_date', 'retirement_date'
        ]
        units_cols = [c for c in units_cols if c in df_fac_clean.columns]
        units_df = df_fac_clean[units_cols].drop_duplicates(subset=['facility_id', 'unit_id'])
        
        # Clean text & fill defaults for null controls/fuels
        text_cols_to_fill = ['primary_fuel_info', 'secondary_fuel_info', 'so2_controls', 'nox_controls', 'pm_controls']
        for col in text_cols_to_fill:
            if col in units_df.columns:
                units_df[col] = units_df[col].fillna('None').astype(str).str.strip()

        units_df.to_csv(os.path.join(SEED_DIR, 'clean_units.csv'), index=False)

        # Record Facility Dataset Metadata
        datasets_metadata.append({
            'dataset_name': 'CAMPD Facility & Unit Attributes',
            'data_source': 'EPA CAMPD',
            'reporting_year': 2025,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': 'facility-2025.csv',
            'raw_records_count': total_raw_fac,
            'accepted_records_count': len(df_fac_clean),
            'rejected_records_count': fac_invalid_mask.sum(),
            'notes': 'Facilities and unit capacity attributes processed successfully.'
        })


    # PROCESS ANNUAL EMISSIONS RECORDS
    emiss_path = os.path.join(RAW_DIR, "emissions-2025.csv")
    if os.path.exists(emiss_path):
        df_emiss = pd.read_csv(emiss_path)
        total_raw_emiss = len(df_emiss)
        df_emiss.columns = df_emiss.columns.str.strip().str.lower().str.replace(' ', '_')

        # Map column name variants
        if 'year' in df_emiss.columns and 'reporting_year' not in df_emiss.columns:
            df_emiss.rename(columns={'year': 'reporting_year'}, inplace=True)

        # Validate annual records (Facility ID and Unit ID are required keys)
        emiss_invalid_mask = df_emiss['facility_id'].isna() | df_emiss['unit_id'].isna()
        if emiss_invalid_mask.any():
            bad_emiss = df_emiss[emiss_invalid_mask].copy()
            bad_emiss['rejection_reason'] = 'Missing Facility ID or Unit ID'
            rejected_records.append(bad_emiss)
            
        df_emiss_clean = df_emiss[~emiss_invalid_mask].copy()

        # Standardize and clean numerical values
        numeric_targets = [
            'operating_time', 'gross_load', 'steam_load', 'heat_input',
            'co2_mass', 'so2_mass', 'nox_mass'
        ]
        
        for col in df_emiss_clean.columns:
            for target in numeric_targets:
                if target in col:
                    df_emiss_clean[col] = pd.to_numeric(df_emiss_clean[col], errors='coerce').fillna(0.0)

        df_emiss_clean.to_csv(os.path.join(SEED_DIR, 'clean_annual_records.csv'), index=False)

        # Record Emissions Dataset Metadata
        datasets_metadata.append({
            'dataset_name': 'CAMPD Annual Emissions & Operating Data',
            'data_source': 'EPA CAMPD',
            'reporting_year': 2025,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': 'emissions-2025.csv',
            'raw_records_count': total_raw_emiss,
            'accepted_records_count': len(df_emiss_clean),
            'rejected_records_count': emiss_invalid_mask.sum(),
            'notes': 'Annual emissions, operating hours, and generation processed successfully.'
        })


    # PROCESS TRACI FACTORS
    traci_path = os.path.join(RAW_DIR, "traci_2_2.xlsx")
    if os.path.exists(traci_path):
        df_traci = pd.read_excel(traci_path)
        df_traci.columns = df_traci.columns.str.strip().str.lower().str.replace(' ', '_')
        df_traci.to_csv(os.path.join(SEED_DIR, 'clean_traci_factors.csv'), index=False)


    # -------------------------------------------------------------
    # PROCESS HOURLY EMISSIONS (2025 Q1 - Q4 Chunked Processing)
    # -------------------------------------------------------------
    hourly_files = [
        os.path.join(RAW_DIR, "emissions-hourly-2025-ak.csv"),
        os.path.join(RAW_DIR, "emissions-hourly-2025-dc.csv"),
        os.path.join(RAW_DIR, "emissions-hourly-2025-me.csv"),
        os.path.join(RAW_DIR, "emissions-hourly-2025-pr.csv"),
        os.path.join(RAW_DIR, "emissions-hourly-2025-vt.csv")
        #os.path.join(RAW_DIR, "emissions-hourly-2025-ks.csv"),
        #os.path.join(RAW_DIR, "emissions-hourly-2025-q3.csv"),
        #os.path.join(RAW_DIR, "emissions-hourly-2025-q4.csv")
    ]
    
    output_hourly_path = os.path.join(SEED_DIR, "clean_hourly_emissions.csv")
    if os.path.exists(output_hourly_path):
        os.remove(output_hourly_path)

    total_raw_hourly = 0
    total_clean_hourly = 0
    total_rejected_hourly = 0

    for h_path in hourly_files:
        if not os.path.exists(h_path):
            print(f"Skipping missing file: {h_path}")
            continue

        print(f"Processing hourly file: {os.path.basename(h_path)}...")

        for chunk in pd.read_csv(h_path, chunksize=50000, low_memory=False):
            total_raw_hourly += len(chunk)
            chunk.columns = chunk.columns.str.strip().str.lower().str.replace(' ', '_')

            column_mapping = {
                'orispl_code': 'facility_id',
                'facility_id_(orispl)': 'facility_id',
                'op_date': 'op_date',
                'date': 'op_date',
                'op_hour': 'op_hour',
                'hour': 'op_hour',
                'so2_mass_(lbs)': 'so2_mass_lbs',
                'so2_mass': 'so2_mass_lbs',
                'nox_mass_(lbs)': 'nox_mass_lbs',
                'nox_mass': 'nox_mass_lbs',
                'co2_mass_(tons)': 'co2_mass_tons',
                'co2_mass': 'co2_mass_tons',
                'gross_load_(mwh)': 'gload_mwh',
                'gload': 'gload_mwh',
                'heat_input_(mmbtu)': 'heat_input_mmbtu',
                'heat_input': 'heat_input_mmbtu'
            }
            chunk.rename(columns=column_mapping, inplace=True)
            chunk = chunk.loc[:, ~chunk.columns.duplicated()].copy()

            fac_missing = chunk['facility_id'].isna() if 'facility_id' in chunk.columns else pd.Series(False, index=chunk.index)
            unit_missing = chunk['unit_id'].isna() if 'unit_id' in chunk.columns else pd.Series(False, index=chunk.index)
            date_missing = chunk['op_date'].isna() if 'op_date' in chunk.columns else pd.Series(False, index=chunk.index)

            invalid_mask = fac_missing | unit_missing | date_missing
            if invalid_mask.any():
                total_rejected_hourly += invalid_mask.sum()

            clean_chunk = chunk[~invalid_mask].copy()

            hourly_numerics = ['gload_mwh', 'so2_mass_lbs', 'nox_mass_lbs', 'co2_mass_tons', 'heat_input_mmbtu']
            for col in hourly_numerics:
                if col in clean_chunk.columns:
                    clean_chunk[col] = pd.to_numeric(clean_chunk[col], errors='coerce').fillna(0.0)

            if 'op_date' in clean_chunk.columns:
                clean_chunk['op_date'] = pd.to_datetime(clean_chunk['op_date'], errors='coerce').dt.strftime('%Y-%m-%d')

            is_first_chunk = not os.path.exists(output_hourly_path)
            clean_chunk.to_csv(output_hourly_path, mode='a', header=is_first_chunk, index=False)
            total_clean_hourly += len(clean_chunk)

    if total_raw_hourly > 0:
        datasets_metadata.append({
            'dataset_name': 'CAMPD Hourly CEMS Emissions 2025 (Q1-Q4)',
            'data_source': 'EPA CAMPD',
            'reporting_year': 2025,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': 'emissions-hourly-2025-q1..q4.csv',
            'raw_records_count': total_raw_hourly,
            'accepted_records_count': total_clean_hourly,
            'rejected_records_count': total_rejected_hourly,
            'notes': 'Streamed Q1-Q4 hourly files in chunks to clean_hourly_emissions.csv successfully.'
        })


    # -------------------------------------------------------------
    # PROCESS DAILY EMISSIONS (2025 Q1 - Q4 Chunked Processing)
    # -------------------------------------------------------------
    daily_files = [
        os.path.join(RAW_DIR, "emissions-daily-2025-ky.csv"),
        #os.path.join(RAW_DIR, "emissions-daily-2025-q2.csv"),
        #os.path.join(RAW_DIR, "emissions-daily-2025-q3.csv"),
        #os.path.join(RAW_DIR, "emissions-daily-2025-q4.csv")
    ]
    
    output_daily_path = os.path.join(SEED_DIR, "clean_daily_emissions.csv")
    if os.path.exists(output_daily_path):
        os.remove(output_daily_path)

    total_raw_daily = 0
    total_clean_daily = 0
    total_rejected_daily = 0

    for d_path in daily_files:
        if not os.path.exists(d_path):
            print(f"Skipping missing file: {d_path}")
            continue

        print(f"Processing daily file: {os.path.basename(d_path)}...")

        for chunk in pd.read_csv(d_path, chunksize=50000, low_memory=False):
            total_raw_daily += len(chunk)
            chunk.columns = chunk.columns.str.strip().str.lower().str.replace(' ', '_')

            daily_column_mapping = {
                'orispl_code': 'facility_id',
                'facility_id_(orispl)': 'facility_id',
                'op_date': 'op_date',
                'date': 'op_date',
                'gross_load_(mwh)': 'gload_mwh',
                'gload': 'gload_mwh',
                'steam_load_(1000_lb)': 'sload_1000_lb',
                'so2_mass_(lbs)': 'so2_mass_lbs',
                'so2_mass_(short_tons)': 'so2_mass_short_tons',
                'co2_mass_(tons)': 'co2_mass_tons',
                'nox_mass_(lbs)': 'nox_mass_lbs',
                'nox_mass_(short_tons)': 'nox_mass_short_tons',
                'heat_input_(mmbtu)': 'heat_input_mmbtu'
            }
            chunk.rename(columns=daily_column_mapping, inplace=True)
            chunk = chunk.loc[:, ~chunk.columns.duplicated()].copy()

            fac_missing = chunk['facility_id'].isna() if 'facility_id' in chunk.columns else pd.Series(False, index=chunk.index)
            unit_missing = chunk['unit_id'].isna() if 'unit_id' in chunk.columns else pd.Series(False, index=chunk.index)
            date_missing = chunk['op_date'].isna() if 'op_date' in chunk.columns else pd.Series(False, index=chunk.index)

            invalid_mask = fac_missing | unit_missing | date_missing
            if invalid_mask.any():
                total_rejected_daily += invalid_mask.sum()

            clean_chunk = chunk[~invalid_mask].copy()

            daily_numerics = [
                'gload_mwh', 'sload_1000_lb', 'so2_mass_lbs', 'so2_mass_short_tons', 
                'co2_mass_tons', 'nox_mass_lbs', 'nox_mass_short_tons', 'heat_input_mmbtu'
            ]
            for col in daily_numerics:
                if col in clean_chunk.columns:
                    clean_chunk[col] = pd.to_numeric(clean_chunk[col], errors='coerce').fillna(0.0)

            if 'op_date' in clean_chunk.columns:
                clean_chunk['op_date'] = pd.to_datetime(clean_chunk['op_date'], errors='coerce').dt.strftime('%Y-%m-%d')

            is_first_chunk = not os.path.exists(output_daily_path)
            clean_chunk.to_csv(output_daily_path, mode='a', header=is_first_chunk, index=False)
            total_clean_daily += len(clean_chunk)

    if total_raw_daily > 0:
        datasets_metadata.append({
            'dataset_name': 'CAMPD Daily CEMS Emissions 2025 (Q1-Q4)',
            'data_source': 'EPA CAMPD',
            'reporting_year': 2025,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': 'emissions-daily-2025-q1..q4.csv',
            'raw_records_count': total_raw_daily,
            'accepted_records_count': total_clean_daily,
            'rejected_records_count': total_rejected_daily,
            'notes': 'Streamed Q1-Q4 daily files in chunks to clean_daily_emissions.csv successfully.'
        })


    # Export Dataset Provenance Metadata Table
    if datasets_metadata:
        metadata_df = pd.DataFrame(datasets_metadata)
        metadata_df.to_csv(os.path.join(SEED_DIR, 'clean_datasets_metadata.csv'), index=False)

    # Export Quality & Rejection Report
    if rejected_records:
        report_df = pd.concat(rejected_records, ignore_index=True)
        report_df.to_csv(os.path.join(SEED_DIR, 'rejected_records_report.csv'), index=False)
    else:
        pd.DataFrame(columns=['facility_id', 'unit_id', 'rejection_reason']).to_csv(
            os.path.join(SEED_DIR, 'rejected_records_report.csv'), index=False
        )

    print("Data cleaning pipeline complete! Generated seed CSVs and provenance metadata in data/seed/")

if __name__ == "__main__":
    clean_epa_pipeline()