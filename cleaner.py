import os
import pandas as pd

# Define relative directories
RAW_DIR = "data/raw"
SEED_DIR = "data/seed"

def clean_epa_pipeline():
    os.makedirs(SEED_DIR, exist_ok=True)
    
    #Track invalid records for data quality reporting
    rejected_records = []

    #PROCESS FACILITIES & UNITS
    fac_path = os.path.join(RAW_DIR, "facility-2025.csv")
    df_fac = pd.read_csv(fac_path)
    df_fac.columns = df_fac.columns.str.strip().str.lower().str.replace(' ', '_')

    #Validate facilities
    fac_invalid_mask = df_fac['facility_id'].isna() | df_fac['state'].isna()
    if fac_invalid_mask.any():
        rejected_records.append(df_fac[fac_invalid_mask])
    df_fac_clean = df_fac[~fac_invalid_mask].copy()

    #Clean text
    df_fac_clean['state'] = df_fac_clean['state'].astype(str).str.upper().str.strip()
    df_fac_clean['facility_name'] = df_fac_clean['facility_name'].astype(str).str.strip()

    #Extract clean Facilities parent table
    facilities_cols = ['facility_id', 'facility_name', 'state', 'county']
    #Safely select columns present in file
    facilities_cols = [c for c in facilities_cols if c in df_fac_clean.columns]
    facilities_df = df_fac_clean[facilities_cols].drop_duplicates(subset=['facility_id'])
    facilities_df.to_csv(os.path.join(SEED_DIR, 'clean_facilities.csv'), index=False)

    #Extract clean Units parent table
    units_cols = ['facility_id', 'unit_id', 'unit_type', 'primary_fuel_info']
    units_cols = [c for c in units_cols if c in df_fac_clean.columns]
    units_df = df_fac_clean[units_cols].drop_duplicates(subset=['facility_id', 'unit_id'])
    units_df.to_csv(os.path.join(SEED_DIR, 'clean_units.csv'), index=False)


    #PROCESS ANNUAL EMISSIONS RECORDS
    emiss_path = os.path.join(RAW_DIR, "emissions-2025.csv")
    df_emiss = pd.read_csv(emiss_path)
    df_emiss.columns = df_emiss.columns.str.strip().str.lower().str.replace(' ', '_')

    #Map column variants from CAMPD export
    if 'year' in df_emiss.columns and 'reporting_year' not in df_emiss.columns:
        df_emiss.rename(columns={'year': 'reporting_year'}, inplace=True)

    #Validate annual records
    emiss_invalid_mask = df_emiss['facility_id'].isna() | df_emiss['unit_id'].isna()
    if emiss_invalid_mask.any():
        rejected_records.append(df_emiss[emiss_invalid_mask])
    df_emiss_clean = df_emiss[emiss_invalid_mask == False].copy()

    #Clean numerical values
    emissions_cols = ['co2_mass_(short_tons)', 'so2_mass_(short_tons)', 'nox_mass_(short_tons)', 'gross_load_(mwh)', 'heat_input_(mmbtu)']
    #Standardize column names if present
    for col in df_emiss_clean.columns:
        for target in ['co2_mass', 'so2_mass', 'nox_mass', 'gross_load', 'heat_input']:
            if target in col:
                df_emiss_clean[col] = pd.to_numeric(df_emiss_clean[col], errors='coerce').fillna(0.0)

    df_emiss_clean.to_csv(os.path.join(SEED_DIR, 'clean_annual_records.csv'), index=False)


    #PROCESS TRACI FACTORS
    traci_path = os.path.join(RAW_DIR, "traci_2_2.xlsx")
    df_traci = pd.read_excel(traci_path)
    df_traci.columns = df_traci.columns.str.strip().str.lower().str.replace(' ', '_')
    df_traci.to_csv(os.path.join(SEED_DIR, 'clean_traci_factors.csv'), index=False)


    #EXPORT QUALITY REPORT
    if rejected_records:
        report_df = pd.concat(rejected_records, ignore_index=True)
        report_df.to_csv(os.path.join(SEED_DIR, 'rejected_records_report.csv'), index=False)
    else:
        # Create empty report if no bad records found
        pd.DataFrame(columns=['facility_id', 'reason']).to_csv(os.path.join(SEED_DIR, 'rejected_records_report.csv'), index=False)

    print("Data cleaning complete! Generated seed CSVs in data/seed/")

if __name__ == "__main__":
    clean_epa_pipeline()