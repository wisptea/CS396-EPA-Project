#Creating the natural language search into it's own file so the app.py doesn't get too long
#And it's easier to edit
import re

def parse_natural_language_query(text):
    """
    Parses a plain-English query string into structured filter parameters
    for emissions, fuels, states, and numerical thresholds.
    """
    text = text.lower().strip()
    
    filters = {
        "state": None,
        "fuel": None,
        "year": None,
        "unit_type": None,
        "so2_controls": None,
        "nox_controls": None,
        "min_co2": None,
        "max_co2": None,
        "min_so2": None,
        "max_so2": None,
        "min_op_time": None,
        "min_gross_load": None
    }

    # 1. State Mapping
    state_map = {
        "kentucky": "KY", "texas": "TX", "california": "CA", "florida": "FL",
        "ohio": "OH", "pennsylvania": "PA", "indiana": "IN", "illinois": "IL",
        "georgia": "GA", "north carolina": "NC", "michigan": "MI", "alaska": "AK",
        "district of columbia": "DC", "dc": "DC", "maine": "ME", "puerto rico": "PR", "vermont": "VT"
    }
    for full_name, code in state_map.items():
        if full_name in text:
            filters["state"] = code
            break

    # 2. Year Extraction
    year_match = re.search(r'\b(20\d{2})\b', text)
    if year_match:
        filters["year"] = int(year_match.group(1))

    # 3. Fuel Type
    if "coal" in text:
        filters["fuel"] = "coal"
    elif "natural gas" in text or "gas" in text:
        filters["fuel"] = "natural gas"
    elif "oil" in text:
        filters["fuel"] = "oil"

    # 4. Unit Type
    if "boiler" in text:
        filters["unit_type"] = "boiler"
    elif "turbine" in text:
        filters["unit_type"] = "turbine"

    # 5. Emission Controls
    if "scrubber" in text or "so2 control" in text:
        filters["so2_controls"] = True
    if "low nox" in text or "nox control" in text:
        filters["nox_controls"] = True

    # 6. Semantic/Numeric Thresholds (CO2, SO2, Operating Time, Gross Load)
    if "high co2" in text or "large co2" in text:
        filters["min_co2"] = 500000
    elif "low co2" in text:
        filters["max_co2"] = 100000

    co2_match = re.search(r'co2.*?(?:greater than|>|exceeding|over|of)\s*(\d+)', text)
    if co2_match:
        filters["min_co2"] = float(co2_match.group(1))

    so2_match = re.search(r'so2.*?(?:less than|<|under|below)\s*(\d+)', text)
    if so2_match:
        filters["max_so2"] = float(so2_match.group(1))
        
    so2_min_match = re.search(r'so2.*?(?:greater than|>|exceeding|over)\s*(\d+)', text)
    if so2_min_match:
        filters["min_so2"] = float(so2_min_match.group(1))

    op_time_match = re.search(r'(?:operating time|hours).*?(?:greater than|>|exceeding|over|above)\s*(\d+)', text)
    if op_time_match:
        filters["min_op_time"] = float(op_time_match.group(1))

    load_match = re.search(r'(?:gross load|load).*?(?:greater than|>|exceeding|over|above)\s*(\d+)', text)
    if load_match:
        filters["min_gross_load"] = float(load_match.group(1))

    return filters

#Helps with the export of the natural language and advanced language searches
def build_where_clause(filters):
    """
    Takes a dictionary of filters and builds SQL WHERE clauses and parameters.
    """
    where_clauses = []
    params = []

    if filters.get("state"):
        where_clauses.append("f.state = %s")
        params.append(filters["state"])
    if filters.get("year"):
        where_clauses.append("e.reporting_year = %s")
        params.append(filters["year"])
    if filters.get("fuel"):
        where_clauses.append("e.primary_fuel_type LIKE %s")
        params.append(f"%{filters['fuel']}%")
    if filters.get("min_co2"):
        where_clauses.append("e.co2_mass_short_tons >= %s")
        params.append(filters["min_co2"])
    if filters.get("max_co2"):
        where_clauses.append("e.co2_mass_short_tons <= %s")
        params.append(filters["max_co2"])
    if filters.get("min_so2"):
        where_clauses.append("e.so2_mass_short_tons >= %s")
        params.append(filters["min_so2"])
    if filters.get("max_so2"):
        where_clauses.append("e.so2_mass_short_tons <= %s")
        params.append(filters["max_so2"])
    if filters.get("min_op_time"):
        where_clauses.append("e.sum_of_the_operating_time >= %s")
        params.append(filters["min_op_time"])
    if filters.get("min_gross_load"):
        where_clauses.append("e.gross_load_mwh >= %s")
        params.append(filters["min_gross_load"])

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
        
    return where_sql, params

#Helps with sorting
def get_sorting_sql(request):
    """
    Extracts and whitelists sorting parameters from any request
    to prevent SQL injection and return a safe ORDER BY clause.
    """
    sort_field = (request.args.get('sort') or request.args.get('sort_by', 'co2')).lower()
    sort_order = (request.args.get('order') or request.args.get('order_by', 'desc')).upper()

    allowed_sorts = {
        'co2': 'e.co2_mass_short_tons',
        'co2_mass_short_tons': 'e.co2_mass_short_tons',
        'so2': 'e.so2_mass_short_tons',
        'so2_mass_short_tons': 'e.so2_mass_short_tons',
        'nox': 'e.nox_mass_short_tons',
        'nox_mass_short_tons': 'e.nox_mass_short_tons',
        'load': 'e.gross_load_mwh',
        'gross_load_mwh': 'e.gross_load_mwh',
        'time': 'e.sum_of_the_operating_time',
        'sum_of_the_operating_time': 'e.sum_of_the_operating_time',
        'year': 'e.reporting_year',
        'reporting_year': 'e.reporting_year'
    }
    
    db_column = allowed_sorts.get(sort_field, 'e.co2_mass_short_tons')
    safe_order = 'ASC' if sort_order == 'ASC' else 'DESC'
    
    order_sql = f"ORDER BY {db_column} {safe_order}"
    sorting_metadata = {"sort": sort_field, "order": safe_order}
    
    return order_sql, sorting_metadata