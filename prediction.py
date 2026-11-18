import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def run_co2_prediction_pipeline(
    df, target_col='co2_mass_short_tons', test_year=None, forecast_year=None
):
  """Trains and evaluates models on historical data, then projects future years

  using facility-level operational trends and the top-performing regressor.
  """
  numeric_features = [
      'gross_load_mwh',
      'heat_input_mmbtu',
      'sum_of_the_operating_time',
      'steam_load_1000_lb',
  ]
  categorical_features = ['primary_fuel_type', 'unit_type', 'state']

  numeric_features = [c for c in numeric_features if c in df.columns]
  categorical_features = [c for c in categorical_features if c in df.columns]
  all_features = numeric_features + categorical_features

  clean_df = df.dropna(subset=[target_col]).copy()
  for col in numeric_features + [target_col]:
    clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce')
  clean_df = clean_df.dropna(subset=[target_col])

  if len(clean_df) < 10:
    raise ValueError(
        'Not enough valid records (minimum 10 required) to train and evaluate'
        ' models.'
    )

  # ---------------------------------------------------------
  # 1. TRAIN / TEST SPLIT (Temporal if multi-year, else 80/20)
  # ---------------------------------------------------------
  unique_years = (
      sorted(
          [int(y) for y in clean_df['reporting_year'].dropna().unique()]
      )
      if 'reporting_year' in clean_df.columns
      else []
  )

  if len(unique_years) > 1:
    split_year = (
        int(test_year)
        if (test_year and int(test_year) in unique_years)
        else unique_years[-1]
    )
    train_df = clean_df[clean_df['reporting_year'] < split_year]
    test_df = clean_df[clean_df['reporting_year'] == split_year]

    if len(train_df) > 0 and len(test_df) > 0:
      split_method = (
          f'Temporal Split (Train: < {split_year}, Test: {split_year})'
      )
      X_train, y_train = train_df[all_features], train_df[target_col]
      X_test, y_test = test_df[all_features], test_df[target_col]
    else:
      split_method = 'Random 80/20 Split'
      X_train, X_test, y_train, y_test = train_test_split_custom(
          clean_df, all_features, target_col
      )
  else:
    split_method = 'Random 80/20 Split (Single Year Dataset)'
    X_train, X_test, y_train, y_test = train_test_split_custom(
        clean_df, all_features, target_col
    )

  # ---------------------------------------------------------
  # 2. PREPROCESSING & MODEL EVALUATION
  # ---------------------------------------------------------
  preprocessor = build_preprocessor(numeric_features, categorical_features)

  models = {
      'Baseline (Mean Predictor)': DummyRegressor(strategy='mean'),
      'Candidate 1 (Ridge Regression)': Ridge(alpha=1.0, random_state=42),
      'Candidate 2 (Random Forest)': RandomForestRegressor(
          n_estimators=50, max_depth=10, random_state=42, n_jobs=-1
      ),
  }

  evaluation_results = []
  predictions_sample = pd.DataFrame({'actual_target': y_test.values})

  test_indices = y_test.index
  for id_col in ['facility_id', 'facility_name', 'unit_id', 'reporting_year']:
    if id_col in clean_df.columns:
      predictions_sample[id_col] = clean_df.loc[test_indices, id_col].values

  best_r2 = -np.inf
  best_regressor_factory = lambda: RandomForestRegressor(
      n_estimators=50, max_depth=10, random_state=42, n_jobs=-1
  )
  best_model_label = 'Candidate 2 (Random Forest)'

  for model_name, regressor in models.items():
    clf = Pipeline(
        steps=[('preprocessor', preprocessor), ('regressor', regressor)]
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    evaluation_results.append({
        'model': model_name,
        'mae_short_tons': round(float(mae), 2),
        'rmse_short_tons': round(float(rmse), 2),
        'r2_score': round(float(r2), 4),
    })

    if model_name != 'Baseline (Mean Predictor)' and r2 > best_r2:
      best_r2 = r2
      best_model_label = model_name
      if 'Ridge' in model_name:
        best_regressor_factory = lambda: Ridge(alpha=1.0, random_state=42)
      else:
        best_regressor_factory = lambda: RandomForestRegressor(
            n_estimators=50, max_depth=10, random_state=42, n_jobs=-1
        )

    safe_col_name = (
        model_name.split('(')[0].strip().lower().replace(' ', '_') + '_pred'
    )
    predictions_sample[safe_col_name] = np.round(y_pred, 2)

  # ---------------------------------------------------------
  # 3. FUTURE FORECASTING (Retrain on 100% of Historical Data)
  # ---------------------------------------------------------
  future_forecast = generate_future_forecast(
      clean_df=clean_df,
      numeric_features=numeric_features,
      categorical_features=categorical_features,
      target_col=target_col,
      best_regressor=best_regressor_factory(),
      best_model_label=best_model_label,
      forecast_year=forecast_year,
  )

  return {
      'target': target_col,
      'features_used': all_features,
      'split_method': split_method,
      'train_records': int(len(X_train)),
      'test_records': int(len(X_test)),
      'known_years': unique_years,
      'model_metrics': evaluation_results,
      'sample_predictions': predictions_sample.head(25)
      .replace({np.nan: None})
      .to_dict(orient='records'),
      'future_forecast': future_forecast,
  }


def generate_future_forecast(
    clean_df,
    numeric_features,
    categorical_features,
    target_col,
    best_regressor,
    best_model_label,
    forecast_year=None,
):
  """Projects future facility operational inputs from historical trends and

  predicts target emissions/impacts through `forecast_year`.
  """
  if 'reporting_year' not in clean_df.columns or clean_df['reporting_year'].dropna().empty:
    return None

  all_features = numeric_features + categorical_features
  full_pipeline = Pipeline(
      steps=[
          ('preprocessor', build_preprocessor(numeric_features, categorical_features)),
          ('regressor', best_regressor),
      ]
  )
  full_pipeline.fit(clean_df[all_features], clean_df[target_col])

  max_known_year = int(clean_df['reporting_year'].max())
  target_end_year = (
      int(forecast_year)
      if (forecast_year and int(forecast_year) > max_known_year)
      else max_known_year + 3
  )
  future_years = list(range(max_known_year + 1, target_end_year + 1))

  # Historical aggregate totals by year for trajectory chart
  hist_yearly = (
      clean_df.groupby('reporting_year')[target_col]
      .agg(['sum', 'mean', 'count'])
      .reset_index()
      .sort_values('reporting_year')
  )
  historical_series = [
      {
          'year': int(row['reporting_year']),
          'total_value': round(float(row['sum']), 2),
          'mean_value': round(float(row['mean']), 2),
          'unit_count': int(row['count']),
      }
      for _, row in hist_yearly.iterrows()
  ]

  # Build projected future rows per active (facility_id, unit_id)
  group_cols = [c for c in ['facility_id', 'unit_id'] if c in clean_df.columns]
  if not group_cols:
    return None

  future_rows = []
  for keys, grp in clean_df.groupby(group_cols):
    grp_sorted = grp.sort_values('reporting_year')
    latest_row = grp_sorted.iloc[-1].to_dict()

    # Estimate annual slope for each numeric feature if >=2 years exist
    slopes = {}
    years_arr = grp_sorted['reporting_year'].values.reshape(-1, 1)
    for feat in numeric_features:
      valid = grp_sorted[['reporting_year', feat]].dropna()
      if len(valid) >= 2 and valid['reporting_year'].nunique() >= 2:
        lr = LinearRegression()
        lr.fit(valid[['reporting_year']], valid[feat])
        # Dampen extreme slopes by 50% for conservative long-term projection
        slopes[feat] = float(lr.coef_[0]) * 0.5
      else:
        slopes[feat] = 0.0

    last_yr = int(latest_row['reporting_year'])
    for f_year in future_years:
      dt = f_year - last_yr
      proj_row = {
          'facility_id': latest_row.get('facility_id'),
          'facility_name': latest_row.get('facility_name', 'Unknown'),
          'unit_id': latest_row.get('unit_id', '—'),
          'state': latest_row.get('state', 'Unknown'),
          'primary_fuel_type': latest_row.get('primary_fuel_type', 'Unknown'),
          'reporting_year': f_year,
          'last_actual_target': float(latest_row.get(target_col, 0.0)),
      }
      if 'unit_type' in categorical_features:
        proj_row['unit_type'] = latest_row.get('unit_type', 'Unknown')

      for feat in numeric_features:
        base_val = latest_row.get(feat)
        if pd.notna(base_val):
          proj_row[feat] = max(0.0, float(base_val) + slopes[feat] * dt)
        else:
          proj_row[feat] = np.nan

      future_rows.append(proj_row)

  if not future_rows:
    return None

  future_df = pd.DataFrame(future_rows)
  future_df['predicted_value'] = np.maximum(
      0.0, full_pipeline.predict(future_df[all_features])
  )

  # Aggregate future trajectory by year
  proj_yearly = (
      future_df.groupby('reporting_year')['predicted_value']
      .agg(['sum', 'mean', 'count'])
      .reset_index()
      .sort_values('reporting_year')
  )
  projected_series = [
      {
          'year': int(row['reporting_year']),
          'total_value': round(float(row['sum']), 2),
          'mean_value': round(float(row['mean']), 2),
          'unit_count': int(row['count']),
      }
      for _, row in proj_yearly.iterrows()
  ]

  # Top facility/unit projections for the final target year
  final_year_df = (
      future_df[future_df['reporting_year'] == target_end_year]
      .sort_values('predicted_value', ascending=False)
      .head(25)
  )
  facility_forecasts = []
  for _, r in final_year_df.iterrows():
    last_val = r['last_actual_target']
    pred_val = float(r['predicted_value'])
    pct_change = ((pred_val - last_val) / last_val * 100.0) if last_val > 0 else 0.0
    facility_forecasts.append({
        'facility_id': int(r['facility_id']) if pd.notna(r['facility_id']) else None,
        'facility_name': r['facility_name'],
        'unit_id': r['unit_id'],
        'state': r['state'],
        'primary_fuel_type': r['primary_fuel_type'],
        'forecast_year': int(r['reporting_year']),
        'last_actual_value': round(last_val, 2),
        'predicted_value': round(pred_val, 2),
        'projected_change_pct': round(pct_change, 2),
    })

  return {
      'model_used': best_model_label,
      'base_year': max_known_year,
      'target_forecast_year': target_end_year,
      'forecast_years': future_years,
      'historical_series': historical_series,
      'projected_series': projected_series,
      'facility_forecasts': facility_forecasts,
  }


def build_preprocessor(numeric_features, categorical_features):
  numeric_transformer = Pipeline(
      steps=[
          ('imputer', SimpleImputer(strategy='median')),
          ('scaler', StandardScaler()),
      ]
  )
  categorical_transformer = Pipeline(
      steps=[
          (
              'imputer',
              SimpleImputer(strategy='constant', fill_value='Unknown'),
          ),
          ('onehot', OneHotEncoder(handle_unknown='ignore')),
      ]
  )
  return ColumnTransformer(
      transformers=[
          ('num', numeric_transformer, numeric_features),
          ('cat', categorical_transformer, categorical_features),
      ]
  )


def train_test_split_custom(df, features, target):
  train_df = df.sample(frac=0.8, random_state=42)
  test_df = df.drop(train_df.index)
  if len(test_df) == 0:
    test_df = train_df.sample(frac=0.2, random_state=42)
  return (
      train_df[features],
      test_df[features],
      train_df[target],
      test_df[target],
  )