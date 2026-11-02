import os
import glob
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

    # =============================================================
    # 1. PROCESS FACILITIES & UNITS (Multi-Year Dynamic Glob)
    # =============================================================
    facility_files = glob.glob(os.path.join(RAW_DIR, "facility-*.csv"))
    if not facility_files:
        facility_files = glob.glob(os.path.join(RAW_DIR, "*facility*.csv"))

    all_fac_dfs = []
    for fac_path in facility_files:
        print(f"Processing facility file: {os.path.basename(fac_path)}...")
        df_fac = pd.read_csv(fac_path, low_memory=False)
        total_raw_fac = len(df_fac)
        df_fac.columns = df_fac.columns.str.strip().str.lower().str.replace(' ', '_')

        fac_invalid_mask = df_fac['facility_id'].isna() | df_fac['state'].isna()
        if fac_invalid_mask.any():
            bad_fac = df_fac[fac_invalid_mask].copy()
            bad_fac['rejection_reason'] = 'Missing Facility ID or State'
            rejected_records.append(bad_fac)
        
        df_fac_clean = df_fac[~fac_invalid_mask].copy()
        df_fac_clean['state'] = df_fac_clean['state'].astype(str).str.upper().str.strip()
        df_fac_clean['facility_name'] = df_fac_clean['facility_name'].astype(str).str.strip()
        all_fac_dfs.append(df_fac_clean)

        datasets_metadata.append({
            'dataset_name': f'CAMPD Facility & Unit Attributes ({os.path.basename(fac_path)})',
            'data_source': 'EPA CAMPD',
            'reporting_year': None,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': os.path.basename(fac_path),
            'raw_records_count': total_raw_fac,
            'accepted_records_count': len(df_fac_clean),
            'rejected_records_count': fac_invalid_mask.sum(),
            'notes': 'Facility capacity attributes processed successfully.'
        })

    if all_fac_dfs:
        combined_fac = pd.concat(all_fac_dfs, ignore_index=True)

        # --- A. Extract Clean Facilities Table ---
        facilities_cols = ['facility_id', 'facility_name', 'state', 'county', 'latitude', 'longitude', 'source_category']
        facilities_cols = [c for c in facilities_cols if c in combined_fac.columns]
        facilities_df = combined_fac[facilities_cols].drop_duplicates(subset=['facility_id'])
        facilities_df.to_parquet(os.path.join(SEED_DIR, 'clean_facilities.parquet'), compression='snappy', index=False)

        # --- B. Extract Clean Units Table ---
        units_cols = ['facility_id', 'unit_id', 'unit_type', 'primary_fuel_info', 'secondary_fuel_info',
                      'so2_controls', 'nox_controls', 'pm_controls', 'operating_date', 'retirement_date']
        units_cols = [c for c in units_cols if c in combined_fac.columns]
        units_df = combined_fac[units_cols].drop_duplicates(subset=['facility_id', 'unit_id'])
        
        text_cols_to_fill = ['primary_fuel_info', 'secondary_fuel_info', 'so2_controls', 'nox_controls', 'pm_controls']
        for col in text_cols_to_fill:
            if col in units_df.columns:
                units_df[col] = units_df[col].fillna('None').astype(str).str.strip()

        units_df.to_parquet(os.path.join(SEED_DIR, 'clean_units.parquet'), compression='snappy', index=False)


    # =============================================================
    # 2. PROCESS ANNUAL EMISSIONS RECORDS (Multi-Year Dynamic Glob)
    # =============================================================
    annual_emissions_files = glob.glob(os.path.join(RAW_DIR, "emissions-[0-9][0-9][0-9][0-9].csv"))
    all_annual_dfs = []

    for emiss_path in annual_emissions_files:
        print(f"Processing annual emissions file: {os.path.basename(emiss_path)}...")
        df_emiss = pd.read_csv(emiss_path, low_memory=False)
        total_raw_emiss = len(df_emiss)
        df_emiss.columns = df_emiss.columns.str.strip().str.lower().str.replace(' ', '_')

        if 'year' in df_emiss.columns and 'reporting_year' not in df_emiss.columns:
            df_emiss.rename(columns={'year': 'reporting_year'}, inplace=True)

        if 'reporting_year' not in df_emiss.columns:
            import re
            year_match = re.search(r'20\d{2}|19\d{2}', os.path.basename(emiss_path))
            if year_match:
                df_emiss['reporting_year'] = int(year_match.group(0))

        if 'facility_id' in df_emiss.columns and 'unit_id' in df_emiss.columns:
            emiss_invalid_mask = df_emiss['facility_id'].isna() | df_emiss['unit_id'].isna()
            if emiss_invalid_mask.any():
                bad_emiss = df_emiss[emiss_invalid_mask].copy()
                bad_emiss['rejection_reason'] = 'Missing Facility ID or Unit ID'
                rejected_records.append(bad_emiss)
            df_emiss_clean = df_emiss[~emiss_invalid_mask].copy()
        else:
            df_emiss['facility_id'] = None
            df_emiss['unit_id'] = None
            emiss_invalid_mask = df_emiss['state'].isna() if 'state' in df_emiss.columns else pd.Series(False, index=df_emiss.index)
            if emiss_invalid_mask.any():
                bad_emiss = df_emiss[emiss_invalid_mask].copy()
                bad_emiss['rejection_reason'] = 'Missing State'
                rejected_records.append(bad_emiss)
            df_emiss_clean = df_emiss[~emiss_invalid_mask].copy()

        numeric_targets = ['operating_time', 'gross_load', 'steam_load', 'heat_input', 'co2_mass', 'so2_mass', 'nox_mass']
        for col in df_emiss_clean.columns:
            for target in numeric_targets:
                if target in col:
                    df_emiss_clean[col] = pd.to_numeric(df_emiss_clean[col], errors='coerce').fillna(0.0)

        all_annual_dfs.append(df_emiss_clean)

        datasets_metadata.append({
            'dataset_name': f'CAMPD Annual Emissions & Operating Data ({os.path.basename(emiss_path)})',
            'data_source': 'EPA CAMPD',
            'reporting_year': int(df_emiss_clean['reporting_year'].iloc[0]) if 'reporting_year' in df_emiss_clean.columns and not df_emiss_clean['reporting_year'].isna().all() else None,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': os.path.basename(emiss_path),
            'raw_records_count': total_raw_emiss,
            'accepted_records_count': len(df_emiss_clean),
            'rejected_records_count': emiss_invalid_mask.sum(),
            'notes': 'Annual emissions and operating metrics processed successfully.'
        })

    if all_annual_dfs:
        combined_annual = pd.concat(all_annual_dfs, ignore_index=True)
        combined_annual.to_parquet(os.path.join(SEED_DIR, 'clean_annual_records.parquet'), compression='snappy', index=False)


    # =============================================================
    # 3. PROCESS TRACI FACTORS
    # =============================================================
    traci_path = os.path.join(RAW_DIR, "traci_2_2.xlsx")
    if os.path.exists(traci_path):
        print("Processing TRACI characterization factors...")
        df_traci = pd.read_excel(traci_path, sheet_name="Substances")
        df_traci.columns = df_traci.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # FIX: Ensure all columns (especially ID/CAS columns) are converted to string to prevent PyArrow type conflicts
        for col in df_traci.columns:
            if df_traci[col].dtype == 'object':
                df_traci[col] = df_traci[col].astype(str)

        df_traci.to_parquet(os.path.join(SEED_DIR, 'clean_traci_factors.parquet'), compression='snappy', index=False)


    # =============================================================
    # 4. PROCESS HOURLY EMISSIONS (Dynamic Multi-Year Glob)
    # =============================================================
    hourly_files = glob.glob(os.path.join(RAW_DIR, "emissions-hourly-*.csv"))
    output_hourly_path = os.path.join(SEED_DIR, "clean_hourly_emissions.parquet")

    total_raw_hourly = 0
    total_clean_hourly = 0
    total_rejected_hourly = 0
    all_hourly_chunks = []

    for h_path in hourly_files:
        print(f"Processing hourly file: {os.path.basename(h_path)}...")
        for chunk in pd.read_csv(h_path, chunksize=50000, low_memory=False):
            total_raw_hourly += len(chunk)
            chunk.columns = chunk.columns.str.strip().str.lower().str.replace(' ', '_')

            column_mapping = {
                'orispl_code': 'facility_id',
                'facility_id_(orispl)':'facility_id',
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

            # FIX: Ensure unit_id is strictly string to prevent pyarrow type conflicts
            if 'unit_id' in clean_chunk.columns:
                clean_chunk['unit_id'] = clean_chunk['unit_id'].astype(str)

            all_hourly_chunks.append(clean_chunk)
            total_clean_hourly += len(clean_chunk)

    if all_hourly_chunks:
        combined_hourly = pd.concat(all_hourly_chunks, ignore_index=True)
        # Ensure final safety cast on unit_id
        if 'unit_id' in combined_hourly.columns:
            combined_hourly['unit_id'] = combined_hourly['unit_id'].astype(str)
        combined_hourly.to_parquet(output_hourly_path, compression='snappy', index=False)

    if total_raw_hourly > 0:
        datasets_metadata.append({
            'dataset_name': 'CAMPD Hourly CEMS Emissions (Multi-Year)',
            'data_source': 'EPA CAMPD',
            'reporting_year': None,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': 'emissions-hourly-*.csv',
            'raw_records_count': total_raw_hourly,
            'accepted_records_count': total_clean_hourly,
            'rejected_records_count': total_rejected_hourly,
            'notes': 'Multi-year hourly CEMS files processed successfully.'
        })


    # =============================================================
    # 5. PROCESS DAILY EMISSIONS (Dynamic Multi-Year Glob)
    # =============================================================
    daily_files = glob.glob(os.path.join(RAW_DIR, "emissions-daily-*.csv"))
    output_daily_path = os.path.join(SEED_DIR, "clean_daily_emissions.parquet")

    total_raw_daily = 0
    total_clean_daily = 0
    total_rejected_daily = 0
    all_daily_chunks = []

    for d_path in daily_files:
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

            # FIX: Ensure unit_id is strictly string
            if 'unit_id' in clean_chunk.columns:
                clean_chunk['unit_id'] = clean_chunk['unit_id'].astype(str)

            all_daily_chunks.append(clean_chunk)
            total_clean_daily += len(clean_chunk)

    if all_daily_chunks:
        combined_daily = pd.concat(all_daily_chunks, ignore_index=True)
        if 'unit_id' in combined_daily.columns:
            combined_daily['unit_id'] = combined_daily['unit_id'].astype(str)
        combined_daily.to_parquet(output_daily_path, compression='snappy', index=False)

    if total_raw_daily > 0:
        datasets_metadata.append({
            'dataset_name': 'CAMPD Daily CEMS Emissions (Multi-Year)',
            'data_source': 'EPA CAMPD',
            'reporting_year': None,
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_filename': 'emissions-daily-*.csv',
            'raw_records_count': total_raw_daily,
            'accepted_records_count': total_clean_daily,
            'rejected_records_count': total_rejected_daily,
            'notes': 'Multi-year daily CEMS files processed successfully.'
        })

    # =============================================================
    # 6. EXPORT METADATA & REJECTION REPORTS
    # =============================================================
    if datasets_metadata:
        metadata_df = pd.DataFrame(datasets_metadata)
        metadata_df.to_parquet(os.path.join(SEED_DIR, 'clean_datasets_metadata.parquet'), compression='snappy', index=False)

    if rejected_records:
        report_df = pd.concat(rejected_records, ignore_index=True)
        report_df.to_parquet(os.path.join(SEED_DIR, 'rejected_records_report.parquet'), compression='snappy', index=False)

    print("Data cleaning pipeline complete! Generated multi-year Parquet seed files in data/seed/")

if __name__ == "__main__":
    clean_epa_pipeline()