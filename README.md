```text
================================================================================
CS396 EPA Full-Stack Air Emissions Data Analysis Application
================================================================================
```
Status: Active Development / Work-in-Progress (WIP)
Course: CS396


--------------------------------------------------------------------------------
TABLE OF CONTENTS
--------------------------------------------------------------------------------
1. Project Overview
2. Tech Stack
3. Repository Structure
4. Database Architecture
5. Local Setup and Installation
6. Database Initialization & Seeding
7. Running the Web Application
8. API Endpoints
9. Frontend & Features


--------------------------------------------------------------------------------
1. PROJECT OVERVIEW
--------------------------------------------------------------------------------
This project provides a full-stack web application designed to collect, store, 
query, analyze, and visualize environmental and power-sector air emissions data 
across industrial facilities and power generation units.

The application integrates data from the EPA Clean Air Markets Program Data 
(CAMPD), environmental characterization factors from EPA TRACI, and user-
uploaded datasets. Using MySQL for the relational database, Flask for the 
backend service, and Jinja2 for frontend templating, users can perform 
faceted searches, natural language queries, inspect unit-level annual metrics, 
validate/import custom CSV or Excel files, and export filtered data reports.


--------------------------------------------------------------------------------
2. TECH STACK
--------------------------------------------------------------------------------
BACKEND:
  * Framework: Python 3.9+, Flask 3.0.3
  * CORS Management: Flask-Cors 5.0.0
  * Data Processing: Pandas 2.0.3, NumPy 1.24.4, openpyxl 3.1.5
  * Environment Configuration: python-dotenv 1.0.1

DATABASE:
  * DBMS: MySQL
  * Connector: mysql-connector-python 9.0.0

FRONTEND:
  * Templating: Jinja2
  * UI & Styling: CSS (Flexbox / Grid Layouts)
  * Scripting: Vanilla JavaScript (ES6 Fetch API)


--------------------------------------------------------------------------------
3. REPOSITORY STRUCTURE
--------------------------------------------------------------------------------
```text
CS396-EPA-Air-Emissions/
  |-- data/
  |     |-- raw/
  |     |     |-- emissions-2025/
  |     |     |-- emissions-daily-2025-ky/
  |     |     |-- emissions-hourly-2025-ak/
  |     |     |-- emissions-hourly-2025-dc/
  |     |     |-- emissions-hourly-2025-me/
  |     |     |-- emissions-hourly-2025-pr/
  |     |     |-- emissions-hourly-2025-vt/
  |     |     |-- facility-2025/
  |     |     |-- traci_2_2/
  |     |-- seed/
  |           |-- clean_annual_records.csv
  |           |-- clean_daily_emissions.csv
  |           |-- clean_datasets_metadata.csv
  |           |-- clean_facilities.csv
  |           |-- clean_hourly_emissions.csv
  |           |-- clean_traci_factors.csv
  |           |-- clean_units.csv
  |           |-- rejected_records_report.csv
  |-- database/
  |     |-- DatabaseCreation.sql
  |-- templates/
  |     |-- Download.html
  |     |-- Explorepage.html
  |     |-- Facility-detail.html
  |     |-- Homepage.html
  |     |-- retrievelpage.html
  |     |-- Uploadpage.html
  |-- .env
  |-- .gitignore
  |-- app.py
  |-- cleaner.py
  |-- load_database.py
  |-- NatLangSearch.py
  |-- README
  |-- requirements.txt
```

--------------------------------------------------------------------------------
4. DATABASE ARCHITECTURE
--------------------------------------------------------------------------------
The relational schema ensures data integrity across batch metadata, physical 
plant hierarchies, continuous time-series emissions, and environmental impact 
factors:
```text
+--------------------------+---------------------------------------------------+
| Table Name               | Schema & Key Constraints                          |
+--------------------------+---------------------------------------------------+
| Dataset_Metadata         | metadata_id (PK), dataset_name, data_source,      |
|                          | reporting_year, granularity, raw_records_count,   |
|                          | accepted_records_count, rejected_records_count    |
+--------------------------+---------------------------------------------------+
| Measurement_Methods      | method_code (PK), method_name, method_description,|
|                          | data_tier                                         |
+--------------------------+---------------------------------------------------+
| TRACI_factors            | traci_id (PK), substance, cas_number, category,   |
|                          | factor, unit                                      |
+--------------------------+---------------------------------------------------+
| Facilities               | facility_id (PK), facility_name, state, county,   |
|                          | latitude, longitude, source_category              |
+--------------------------+---------------------------------------------------+
| Units                    | Primary Key: (facility_id, unit_id), unit_type,   |
|                          | so2_controls, nox_controls, pm_controls           |
+--------------------------+---------------------------------------------------+
| Annual_Emissions         | emission_id (PK), facility_id, unit_id,           |
|                          | metadata_id, reporting_year, associated_stacks,   |
|                          | operating_time_count, sum_of_the_operating_time,  |
|                          | gross_load_mwh, steam_load_1000_lb,               |
|                          | so2_mass_short_tons, so2_rate_lbs_mmbtu,          |
|                          | co2_mass_short_tons, co2_rate_short_tons_mmbtu,   |
|                          | nox_mass_short_tons, nox_rate_lbs_mmbtu,          |
|                          | heat_input_mmbtu, primary_fuel_type,              |
|                          | secondary_fuel_type, hg_controls, program_code    |
+--------------------------+---------------------------------------------------+
| Hourly_Emissions         | hourly_emission_id (PK), facility_id, unit_id,    |
|                          | metadata_id, op_date, op_hour, op_time, gload_mwh,|
|                          | sload_1000_lb, so2_mass_lbs, so2_mass_method_code,|
|                          | so2_rate_lbs_mmbtu, so2_rate_method_code,         |
|                          | co2_mass_tons, co2_mass_method_code,              |
|                          | co2_rate_tons_mmbtu, co2_rate_method_code,        |
|                          | nox_mass_lbs, nox_mass_method_code,               |
|                          | nox_rate_lbs_mmbtu, nox_rate_method_code,         |
|                          | heat_input_mmbtu, heat_input_method_code,         |
|                          | primary_fuel_type, secondary_fuel_type,           |
|                          | program_code                                      |
+--------------------------+---------------------------------------------------+
| Daily_Emissions          | daily_emission_id (PK), facility_id, unit_id,     |
|                          | metadata_id, op_date, operating_time_count,       |
|                          | sum_of_the_operating_time, gload_mwh,             |
|                          | sload_1000_lb, so2_mass_lbs, so2_mass_method_code,|
|                          | so2_rate_lbs_mmbtu, so2_rate_method_code,         |
|                          | co2_mass_tons, co2_mass_method_code,              |
|                          | co2_rate_tons_mmbtu, co2_rate_method_code,        |
|                          | nox_mass_lbs, nox_mass_method_code,               |
|                          | nox_rate_lbs_mmbtu, nox_rate_method_code,         |
|                          | heat_input_mmbtu, heat_input_method_code,         |
|                          | primary_fuel_type, secondary_fuel_type,           |
|                          | program_code                                      |
+--------------------------+---------------------------------------------------+
| Emissions_TRACI_Impacts  | impact_id (PK), emission_id, daily_emission_id,   |
|                          | hourly_emission_id, traci_id,                     |
|                          | calculated_impact_value                           |
+--------------------------+---------------------------------------------------+
```

--------------------------------------------------------------------------------
5. LOCAL SETUP AND INSTALLATION
--------------------------------------------------------------------------------
Prerequisites:
  * Python 3.9 or higher
  * MySQL Server running locally
  * Git

Step 1: Clone the repository
  git clone https://github.com/your-username/CS396-EPA-Air-Emissions.git
  cd CS396-EPA-Air-Emissions

Step 2: Set up virtual environment
  # On macOS / Linux:
  python3 -m venv venv
  source venv/bin/activate

  # On Windows:
  python -m venv venv
  venv\Scripts\activate

  OR
  (Recommended)
  python -m venv venv; Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force; .\venv\Scripts\Activate.ps1

Step 3: Install dependencies
  pip install -r requirements.txt

Step 4: Configure environment variables
  Create a file named .env in the root directory and add your MySQL password:
  DB_PASSWORD=your_mysql_root_password


--------------------------------------------------------------------------------
6. DATABASE INITIALIZATION & SEEDING
--------------------------------------------------------------------------------
1. Open your MySQL client and execute the database creation script:
   SOURCE database/DatabaseCreation.sql;

2. Execute the ETL pipeline script from the terminal to populate seed data:
   python load_database.py


--------------------------------------------------------------------------------
7. RUNNING THE WEB APPLICATION
--------------------------------------------------------------------------------
To launch the local Flask development server:
  python app.py

Open your web browser and navigate to:
  http://127.0.0.1:5000/


--------------------------------------------------------------------------------
8. API ENDPOINTS
--------------------------------------------------------------------------------
WEB PAGE ROUTES:
  GET /                Renders the Homepage
  GET /explorer        Renders the Data Explorer & search page
  GET /facility-detail Renders the Facility Details breakdown page
  GET /retrieval       Renders the Data Retrieval wizard page
  GET /upload          Renders the Spreadsheet Upload & validation page
  GET /download        Renders the Data Export page

RESTFUL API ENDPOINTS:
  GET  /api/stats               Summary record counts across all database tables
  GET  /api/facilities          Search/list facilities with state filter & pagination
  GET  /api/facilities/<id>     Detailed facility record and associated units
  GET  /api/facility-detail     Combined query for unit-level annual metrics
  GET  /api/emissions           Query annual emissions with dynamic pagination
  GET  /api/search/advanced     Multi-parameter search (state, fuel, year, ranges)
  GET  /api/search/natural      Natural language query parsing
  GET  /api/search/ranking      Ranked queries (top emitters, lowest emitting units)
  POST /api/upload/validate     Spreadsheet validation (schema, nulls, duplicates)
  POST /api/upload/import       Ingests validated spreadsheet data into MySQL
  GET  /api/export              Generates dynamic dataset downloads (.csv or .xlsx)


--------------------------------------------------------------------------------
9. FRONTEND & FEATURES
--------------------------------------------------------------------------------
* Data Explorer & Faceted Search: Dynamic filtering by facility name/ID, state, 
  reporting year, pollutant, and data source with server-side pagination.

* Natural Language Query Engine: Translates plain-English search phrases into 
  structured SQL queries automatically.

* Facility Detail Breakdown: Comprehensive dashboard displaying spatial 
  coordinates, operating hours, heat input, gross load, and pollutant emissions.

* Validation & Import Engine: Automatic validation checker that inspects 
  headers, data types, null counts, and duplicate rows before writing uploaded 
  spreadsheets to MySQL.

* Custom Export Engine: Exporter supporting multi-filter constraints to 
  download customized .csv or formatted .xlsx workbooks.
================================================================================