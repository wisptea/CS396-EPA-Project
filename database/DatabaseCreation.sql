CREATE DATABASE IF NOT EXISTS epadata;
USE epadata;

USE epadata;
ALTER TABLE Emissions_TRACI_Impacts MODIFY COLUMN calculated_impact_value DECIMAL(24, 6) NOT NULL;

-- 1. DATASET METADATA TABLE (Batch & Provenance Tracking)
CREATE TABLE IF NOT EXISTS Dataset_Metadata (
    metadata_id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL,
    data_source VARCHAR(255),
    reporting_year INT,
    granularity VARCHAR(50) DEFAULT 'Annual', -- 'Annual', 'Daily', or 'Hourly'
    processed_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    original_filename VARCHAR(255),
    raw_records_count INT,
    accepted_records_count INT,
    rejected_records_count INT,
    notes TEXT
);

-- 2. MEASUREMENT METHODS LOOKUP TABLE
CREATE TABLE IF NOT EXISTS Measurement_Methods (
    method_code VARCHAR(20) PRIMARY KEY, -- e.g., 'CEMS', 'SUB', 'DEFAULT', 'APP_D'
    method_name VARCHAR(100) NOT NULL,
    method_description TEXT,
    data_tier VARCHAR(50)
);

-- 3. TRACI FACTORS LOOKUP TABLE
CREATE TABLE IF NOT EXISTS TRACI_Factors (
    traci_id INT AUTO_INCREMENT PRIMARY KEY,
    substance VARCHAR(255) NOT NULL,    -- e.g., 'SO2', 'NOx', 'CO2'
    cas_number VARCHAR(50),
    category VARCHAR(100) NOT NULL,     -- e.g., 'Acidification', 'Global Warming', 'Smog'
    factor DECIMAL(14, 6) NOT NULL,     -- Impact multiplier value
    unit VARCHAR(50) NOT NULL,            -- e.g., 'kg SO2 eq / kg', 'kg CO2 eq / kg'
    UNIQUE KEY uq_substance_category (substance, category)
);

-- 4. FACILITIES TABLE
CREATE TABLE IF NOT EXISTS Facilities (
    facility_id INT PRIMARY KEY,
    facility_name VARCHAR(255) NOT NULL,
    state VARCHAR(50),
    county VARCHAR(100),
    latitude DECIMAL(9, 6),
    longitude DECIMAL(9, 6),
    source_category VARCHAR(100)
);

-- 5. UNITS TABLE
CREATE TABLE IF NOT EXISTS Units (
    facility_id INT,
    unit_id VARCHAR(50),
    unit_type VARCHAR(100),
    so2_controls VARCHAR(255),
    nox_controls VARCHAR(255),
    pm_controls VARCHAR(255),
    PRIMARY KEY (facility_id, unit_id),
    FOREIGN KEY (facility_id) REFERENCES Facilities(facility_id) ON DELETE CASCADE
);

-- 6. ANNUAL EMISSIONS TABLE (Linked to Metadata)
CREATE TABLE IF NOT EXISTS Annual_Emissions (
    emission_id INT AUTO_INCREMENT PRIMARY KEY,
    facility_id INT NOT NULL,
    unit_id VARCHAR(50) NOT NULL,
    metadata_id INT, -- Linked to Dataset_Metadata
    reporting_year INT NOT NULL,
    associated_stacks VARCHAR(255),
    operating_time_count INT,
    sum_of_the_operating_time DECIMAL(10, 2),
    gross_load_mwh DECIMAL(15, 2),
    steam_load_1000_lb DECIMAL(15, 2),
    so2_mass_short_tons DECIMAL(15, 4),
    so2_rate_lbs_mmbtu DECIMAL(10, 4),
    co2_mass_short_tons DECIMAL(15, 4),
    co2_rate_short_tons_mmbtu DECIMAL(10, 4),
    nox_mass_short_tons DECIMAL(15, 4),
    nox_rate_lbs_mmbtu DECIMAL(10, 4),
    heat_input_mmbtu DECIMAL(15, 2),
    primary_fuel_type VARCHAR(100),
    secondary_fuel_type VARCHAR(100),
    hg_controls VARCHAR(255),
    program_code VARCHAR(255),
    FOREIGN KEY (facility_id, unit_id) REFERENCES Units(facility_id, unit_id) ON DELETE CASCADE,
    FOREIGN KEY (metadata_id) REFERENCES Dataset_Metadata(metadata_id) ON DELETE SET NULL,
    UNIQUE KEY uq_unit_year (facility_id, unit_id, reporting_year),
    INDEX idx_annual_search (reporting_year, primary_fuel_type)
);

-- 7. HOURLY EMISSIONS TABLE (Linked to Metadata & Measurement Methods)
CREATE TABLE IF NOT EXISTS Hourly_Emissions (
    hourly_emission_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    facility_id INT NOT NULL,
    unit_id VARCHAR(50) NOT NULL,
    metadata_id INT, -- Linked to Dataset_Metadata
    op_date DATE NOT NULL,
    op_hour INT NOT NULL,
    op_time DECIMAL(4, 2),
    gload_mwh DECIMAL(10, 2),
    sload_1000_lb DECIMAL(10, 2),
    so2_mass_lbs DECIMAL(12, 4),
    so2_mass_method_code VARCHAR(20), -- FK to Measurement_Methods
    so2_rate_lbs_mmbtu DECIMAL(10, 4),
    so2_rate_method_code VARCHAR(20),
    co2_mass_tons DECIMAL(12, 4),
    co2_mass_method_code VARCHAR(20),
    co2_rate_tons_mmbtu DECIMAL(10, 4),
    co2_rate_method_code VARCHAR(20),
    nox_mass_lbs DECIMAL(12, 4),
    nox_mass_method_code VARCHAR(20),
    nox_rate_lbs_mmbtu DECIMAL(10, 4),
    nox_rate_method_code VARCHAR(20),
    heat_input_mmbtu DECIMAL(12, 4),
    heat_input_method_code VARCHAR(20),
    primary_fuel_type VARCHAR(100),
    secondary_fuel_type VARCHAR(100),
    program_code VARCHAR(255),
    -- Foreign Key Relationships
    FOREIGN KEY (facility_id, unit_id) REFERENCES Units(facility_id, unit_id) ON DELETE CASCADE,
    FOREIGN KEY (metadata_id) REFERENCES Dataset_Metadata(metadata_id) ON DELETE SET NULL,
    FOREIGN KEY (so2_mass_method_code) REFERENCES Measurement_Methods(method_code),
    FOREIGN KEY (so2_rate_method_code) REFERENCES Measurement_Methods(method_code),
    FOREIGN KEY (co2_mass_method_code) REFERENCES Measurement_Methods(method_code),
    FOREIGN KEY (co2_rate_method_code) REFERENCES Measurement_Methods(method_code),
    FOREIGN KEY (nox_mass_method_code) REFERENCES Measurement_Methods(method_code),
    FOREIGN KEY (nox_rate_method_code) REFERENCES Measurement_Methods(method_code),
    FOREIGN KEY (heat_input_method_code) REFERENCES Measurement_Methods(method_code),
    UNIQUE KEY uq_unit_hour (facility_id, unit_id, op_date, op_hour),
    INDEX idx_hourly_date (op_date, facility_id)
);

-- 8. DAILY EMISSIONS TABLE
CREATE TABLE IF NOT EXISTS Daily_Emissions (
    daily_emission_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    facility_id INT NOT NULL,
    unit_id VARCHAR(50) NOT NULL,
    metadata_id INT, -- Linked to Dataset_Metadata
    op_date DATE NOT NULL,
    operating_time_count INT,
    sum_of_the_operating_time DECIMAL(10, 2),
    gload_mwh DECIMAL(12, 2),
    sload_1000_lb DECIMAL(12, 2),
    so2_mass_lbs DECIMAL(14, 4),
    so2_mass_short_tons DECIMAL(12, 4),
    so2_rate_lbs_mmbtu DECIMAL(10, 4),
    co2_mass_tons DECIMAL(14, 4),
    co2_rate_tons_mmbtu DECIMAL(10, 4),
    nox_mass_lbs DECIMAL(14, 4),
    nox_mass_short_tons DECIMAL(12, 4),
    nox_rate_lbs_mmbtu DECIMAL(10, 4),
    heat_input_mmbtu DECIMAL(14, 4),
    primary_fuel_type VARCHAR(100),
    secondary_fuel_type VARCHAR(100),
    program_code VARCHAR(255),
    FOREIGN KEY (facility_id, unit_id) REFERENCES Units(facility_id, unit_id) ON DELETE CASCADE,
    FOREIGN KEY (metadata_id) REFERENCES Dataset_Metadata(metadata_id) ON DELETE SET NULL,
    UNIQUE KEY uq_unit_day (facility_id, unit_id, op_date),
    INDEX idx_daily_date (op_date, facility_id)
);

-- 9. EMISSIONS TRACI IMPACTS BRIDGE TABLE (Connects Emissions to TRACI Factors)
CREATE TABLE IF NOT EXISTS Emissions_TRACI_Impacts (
    impact_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    emission_id INT NULL,           -- FK for annual calculations
    daily_emission_id BIGINT NULL,  -- FK for daily calculations
    hourly_emission_id BIGINT NULL, -- FK for hourly calculations
    traci_id INT NOT NULL,          -- FK to TRACI_Factors
    calculated_impact_value DECIMAL(24, 6) NOT NULL, -- Fixed precision to prevent out-of-range errors
    FOREIGN KEY (emission_id) REFERENCES Annual_Emissions(emission_id) ON DELETE CASCADE,
    FOREIGN KEY (daily_emission_id) REFERENCES Daily_Emissions(daily_emission_id) ON DELETE CASCADE,
    FOREIGN KEY (hourly_emission_id) REFERENCES Hourly_Emissions(hourly_emission_id) ON DELETE CASCADE,
    FOREIGN KEY (traci_id) REFERENCES TRACI_Factors(traci_id) ON DELETE CASCADE,
    UNIQUE KEY uq_annual_traci (emission_id, traci_id),
    UNIQUE KEY uq_daily_traci (daily_emission_id, traci_id),
    UNIQUE KEY uq_hourly_traci (hourly_emission_id, traci_id)
);

-- INITIAL SEED DATA FOR MEASUREMENT METHODS
INSERT IGNORE INTO Measurement_Methods (method_code, method_name, data_tier, method_description) VALUES
('CEMS', 'Continuous Emission Monitoring System', 'Primary', 'Direct real-time measurement via installed stack monitors.'),
('SUB', 'Missing Data Substitution', 'Substitute', 'EPA Part 75 conservative value substitution for system downtime.'),
('APP_D', 'Appendix D Fuel Sampling', 'Calculated', 'Mass flow meter and fuel sampling protocol for oil/gas units.'),
('APP_E', 'Appendix E NOx Estimation', 'Calculated', 'NOx correlation curve method for gas-fired peaking units.'),
('DEFAULT', 'Default Emission Factor', 'Estimated', 'Standard default EPA emission factor applied based on fuel type.');

CREATE TABLE IF NOT EXISTS Uploaded_Datasets (
    upload_id INT AUTO_INCREMENT PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    total_records INT,
    status VARCHAR(50) DEFAULT 'Imported',
    file_data LONGTEXT,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);