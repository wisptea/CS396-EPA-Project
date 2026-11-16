import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def run_co2_prediction_pipeline(df, target_col='co2_mass_short_tons', test_year=None):
  """Trains and evaluates a baseline model and two candidate models to predict

  annual emissions, operating metrics, or TRACI environmental impacts.
  """
  numeric_features = [
      'gross_load_mwh',
      'heat_input_mmbtu',
      'sum_of_the_operating_time',
      'steam_load_1000_lb',
  ]
  categorical_features = ['primary_fuel_type', 'unit_type', 'state']

  # Filter to columns that exist in the dataframe
  numeric_features = [c for c in numeric_features if c in df.columns]
  categorical_features = [c for c in categorical_features if c in df.columns]
  all_features = numeric_features + categorical_features

  # Drop rows where target is missing
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
      sorted(clean_df['reporting_year'].dropna().unique())
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
  # 2. PREPROCESSING PIPELINE
  # ---------------------------------------------------------
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

  preprocessor = ColumnTransformer(
      transformers=[
          ('num', numeric_transformer, numeric_features),
          ('cat', categorical_transformer, categorical_features),
      ]
  )

  # ---------------------------------------------------------
  # 3. MODELS
  # ---------------------------------------------------------
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

    safe_col_name = (
        model_name.split('(')[0].strip().lower().replace(' ', '_') + '_pred'
    )
    predictions_sample[safe_col_name] = np.round(y_pred, 2)

  return {
      'target': target_col,
      'features_used': all_features,
      'split_method': split_method,
      'train_records': int(len(X_train)),
      'test_records': int(len(X_test)),
      'model_metrics': evaluation_results,
      'sample_predictions': predictions_sample.head(25)
      .replace({np.nan: None})
      .to_dict(orient='records'),
  }


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