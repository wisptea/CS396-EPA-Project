import pandas as pd
import numpy as np

def calculate_derived_indicators(df):
    """
    Calculates normalized performance indicators while safely handling 
    missing values and division by zero (returning NaN instead of 0).
    """
    df = df.copy()
    
    # Ensure numeric conversion
    numeric_cols = ['gross_load_mwh', 'heat_input_mmbtu', 'co2_mass_short_tons', 
                    'so2_mass_short_tons', 'nox_mass_short_tons', 'sum_of_the_operating_time']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Safe division helper for intensities and heat rate
    def safe_divide(numerator, denominator):
        num = df.get(numerator)
        den = df.get(denominator)
        if num is not None and den is not None:
            result = num / den
            # Replace infinities or zeros caused by zero denominators with NaN
            result = result.replace([np.inf, -np.inf], np.nan)
            result[den == 0] = np.nan
            return result
        return pd.Series([np.nan] * len(df))

    # Derived Performance Indicators
    df['co2_intensity'] = safe_divide('co2_mass_short_tons', 'gross_load_mwh')
    df['so2_intensity'] = safe_divide('so2_mass_short_tons', 'gross_load_mwh')
    df['nox_intensity'] = safe_divide('nox_mass_short_tons', 'gross_load_mwh')
    df['heat_rate'] = safe_divide('heat_input_mmbtu', 'gross_load_mwh')

    return df

def get_missing_value_summary(df):
    """Returns missing value counts and percentages for each variable."""
    missing_counts = df.isnull().sum()
    missing_percentage = (df.isnull().mean() * 100).round(2)
    summary_df = pd.DataFrame({
        'missing_count': missing_counts,
        'missing_percentage_%': missing_percentage
    })
    return summary_df[summary_df['missing_count'] > 0].to_dict(orient='index')