import os
import csv
import io
import pandas as pd
from flask import Flask, jsonify, request, render_template, make_response
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv

#Beginning of importing other files
from NatLangSearch import parse_natural_language_query, build_where_clause, get_sorting_sql

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enables cross-origin requests for frontend integration

#Connects to the database

def get_db_connection():
    """Establishes and returns a connection to the MySQL database."""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"),
        database="epadata"
    )


#Implement web page routes

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/explorer')
def explorer():
    return render_template('explorer.html')

@app.route('/upload')
def upload():
    return render_template('upload.html')

@app.route('/retrieval')
def retrieval():
    return render_template('retrieval.html')

@app.route('/download')
def download():
    return render_template('download.html')

@app.route('/unit/<int:facility_id>/<unit_id>')
def unit_detail(facility_id, unit_id):
    return render_template('detail.html', facility_id=facility_id, unit_id=unit_id)


#API routes to help with searching

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Returns high-level dataset statistics for the home page."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total_facilities FROM Facilities")
        total_facilities = cursor.fetchone()['total_facilities']
        
        cursor.execute("SELECT COUNT(*) as total_units FROM Units")
        total_units = cursor.fetchone()['total_units']
        
        cursor.execute("SELECT COUNT(*) as total_records FROM Annual_Emissions")
        total_records = cursor.fetchone()['total_records']

        cursor.execute("SELECT COUNT(*) as total_daily FROM Daily_Emissions")
        total_daily = cursor.fetchone()['total_daily']

        cursor.execute("SELECT COUNT(*) as total_hourly FROM Hourly_Emissions")
        total_hourly = cursor.fetchone()['total_hourly']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "data": {
                "facilities": total_facilities,
                "units": total_units,
                "annual_emissions_records": total_records,
                "daily_emissions_records": total_daily,
                "hourly_emissions_records": total_hourly
            }
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/facilities', methods=['GET'])
def get_facilities():
    """
    Retrieves facilities with search, state filtering, and pagination.
    Query Params:
      - search: string (matches facility_name)
      - state: string (e.g., 'TX', 'CA')
      - page: int (default 1)
      - limit: int (default 20)
    """
    try:
        search = request.args.get('search', '').strip()
        state = request.args.get('state', '').strip()
        page = max(1, int(request.args.get('page', 1)))
        limit = max(1, min(100, int(request.args.get('limit', 20))))
        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        if search:
            where_clauses.append("facility_name LIKE %s")
            params.append(f"%{search}%")

        if state:
            where_clauses.append("state = %s")
            params.append(state)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # Get total matching count for pagination
        count_query = f"SELECT COUNT(*) as total FROM Facilities {where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']

        # Get paginated results
        query = f"""
            SELECT * FROM Facilities 
            {where_sql} 
            ORDER BY facility_name ASC 
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        facilities = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": (total_records + limit - 1) // limit,
            "data": facilities
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/facilities/<int:facility_id>', methods=['GET'])
def get_facility_by_id(facility_id):
    """Retrieves a single facility along with its registered units."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch facility detail
        cursor.execute("SELECT * FROM Facilities WHERE facility_id = %s", (facility_id,))
        facility = cursor.fetchone()

        if not facility:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Facility not found"}), 404

        # Fetch associated units
        cursor.execute("SELECT * FROM Units WHERE facility_id = %s", (facility_id,))
        units = cursor.fetchall()

        facility['units'] = units

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "data": facility}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/emissions', methods=['GET'])
def get_emissions():
    """
    Retrieves annual emissions with multi-criteria filtering and pagination.
    Query Params:
      - year: int (e.g., 2025)
      - fuel_type: string (e.g., 'Coal', 'Natural Gas')
      - facility_id: int
      - page: int (default 1)
      - limit: int (default 20)
    """
    try:
        year = request.args.get('year')
        fuel_type = request.args.get('fuel_type')
        facility_id = request.args.get('facility_id')
        page = max(1, int(request.args.get('page', 1)))
        limit = max(1, min(100, int(request.args.get('limit', 20))))
        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        if year:
            where_clauses.append("reporting_year = %s")
            params.append(int(year))

        if fuel_type:
            where_clauses.append("primary_fuel_type = %s")
            params.append(fuel_type)

        if facility_id:
            where_clauses.append("facility_id = %s")
            params.append(int(facility_id))

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # Count total records
        count_query = f"SELECT COUNT(*) as total FROM Annual_Emissions {where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']

        # Fetch paginated records joined with facility name
        query = f"""
            SELECT e.*, f.facility_name, f.state 
            FROM Annual_Emissions e
            JOIN Facilities f ON e.facility_id = f.facility_id
            {where_sql}
            ORDER BY e.reporting_year DESC, e.co2_mass_short_tons DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": (total_records + limit - 1) // limit,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/emissions/daily', methods=['GET'])
def get_daily_emissions():
    """
    Retrieves daily emissions with filtering and pagination.
    Query Params:
      - facility_id: int
      - unit_id: string
      - date: string (YYYY-MM-DD)
      - page: int (default 1)
      - limit: int (default 20)
    """
    try:
        facility_id = request.args.get('facility_id')
        unit_id = request.args.get('unit_id')
        op_date = request.args.get('date')
        page = max(1, int(request.args.get('page', 1)))
        limit = max(1, min(100, int(request.args.get('limit', 20))))
        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        if facility_id:
            where_clauses.append("d.facility_id = %s")
            params.append(int(facility_id))

        if unit_id:
            where_clauses.append("d.unit_id = %s")
            params.append(unit_id)

        if op_date:
            where_clauses.append("d.op_date = %s")
            params.append(op_date)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) as total FROM Daily_Emissions d {where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']

        query = f"""
            SELECT d.*, f.facility_name, f.state 
            FROM Daily_Emissions d
            JOIN Facilities f ON d.facility_id = f.facility_id
            {where_sql}
            ORDER BY d.op_date DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": (total_records + limit - 1) // limit,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/emissions/hourly', methods=['GET'])
def get_hourly_emissions():
    """
    Retrieves hourly emissions with filtering and pagination.
    Query Params:
      - facility_id: int
      - unit_id: string
      - date: string (YYYY-MM-DD)
      - hour: int (0-23)
      - page: int (default 1)
      - limit: int (default 20)
    """
    try:
        facility_id = request.args.get('facility_id')
        unit_id = request.args.get('unit_id')
        op_date = request.args.get('date')
        op_hour = request.args.get('hour')
        page = max(1, int(request.args.get('page', 1)))
        limit = max(1, min(100, int(request.args.get('limit', 20))))
        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        if facility_id:
            where_clauses.append("h.facility_id = %s")
            params.append(int(facility_id))

        if unit_id:
            where_clauses.append("h.unit_id = %s")
            params.append(unit_id)

        if op_date:
            where_clauses.append("h.op_date = %s")
            params.append(op_date)

        if op_hour is not None:
            where_clauses.append("h.op_hour = %s")
            params.append(int(op_hour))

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) as total FROM Hourly_Emissions h {where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']

        query = f"""
            SELECT h.*, f.facility_name, f.state 
            FROM Hourly_Emissions h
            JOIN Facilities f ON h.facility_id = f.facility_id
            {where_sql}
            ORDER BY h.op_date DESC, h.op_hour DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": (total_records + limit - 1) // limit,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/metadata', methods=['GET'])
def get_metadata():
    """Retrieves dataset processing logs and record intake counts."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM Dataset_Metadata ORDER BY metadata_id DESC")
        metadata = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "data": metadata}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/search', methods=['GET'])
def global_search():
    """
    Unified search endpoint.
    Query Params:
      - q: string (search term)
      - limit: int (default 10)
    """
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({"status": "success", "data": {"facilities": [], "units": [], "traci_factors": []}}), 200

        limit = max(1, min(50, int(request.args.get('limit', 10))))
        search_pattern = f"%{query}%"

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Search Facilities by Name or State
        cursor.execute("""
            SELECT facility_id, facility_name, state, county, source_category 
            FROM Facilities 
            WHERE facility_name LIKE %s OR state LIKE %s OR county LIKE %s
            LIMIT %s
        """, (search_pattern, search_pattern, search_pattern, limit))
        facilities = cursor.fetchall()

        # 2. Search Units by Unit ID or Control System
        cursor.execute("""
            SELECT facility_id, unit_id, unit_type, so2_controls, nox_controls 
            FROM Units 
            WHERE unit_id LIKE %s OR unit_type LIKE %s
            LIMIT %s
        """, (search_pattern, search_pattern, limit))
        units = cursor.fetchall()

        # 3. Search TRACI Environmental Factors by Substance or Category
        cursor.execute("""
            SELECT traci_id, substance, category, factor, unit 
            FROM TRACI_Factors 
            WHERE substance LIKE %s OR category LIKE %s OR cas_number LIKE %s
            LIMIT %s
        """, (search_pattern, search_pattern, search_pattern, limit))
        traci_factors = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "query": query,
            "data": {
                "facilities": facilities,
                "units": units,
                "traci_factors": traci_factors
            }
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



#ADVANCED SEARCH FEATURES
# ADVANCED SEARCH FEATURES
@app.route('/api/search/advanced', methods=['GET'])
def advanced_emissions_search():
    """
    Advanced multi-criteria, range, and sorting search for annual emissions.
    Query Params:
      - state: string (e.g., 'KY')
      - year: int (e.g., 2025)
      - fuel: string (e.g., 'coal')
      - min_co2: float / max_co2: float
      - min_so2: float / max_so2: float
      - min_nox: float
      - min_op_time: float / max_op_time: float
      - min_gross_load: float
      - sort / sort_by: string
      - order: string ('ASC' or 'DESC')
      - page: int (default 1)
      - limit: int (default 20)
    """
    try:
        # Extract filter parameters
        state = request.args.get('state', '').strip()
        year = request.args.get('year')
        fuel = request.args.get('fuel', '').strip()
        
        min_co2 = request.args.get('min_co2')
        max_co2 = request.args.get('max_co2')
        min_so2 = request.args.get('min_so2')
        max_so2 = request.args.get('max_so2')
        min_nox = request.args.get('min_nox')
        max_op_time = request.args.get('max_op_time')
        min_op_time = request.args.get('min_op_time')
        min_gross_load = request.args.get('min_gross_load')
        
        page = max(1, int(request.args.get('page', 1)))
        limit = max(1, min(100, int(request.args.get('limit', 20))))
        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        # Multi-criteria filters
        if state:
            where_clauses.append("f.state = %s")
            params.append(state)
            
        if year:
            where_clauses.append("e.reporting_year = %s")
            params.append(int(year))
            
        if fuel:
            where_clauses.append("e.primary_fuel_type LIKE %s")
            params.append(f"%{fuel}%")

        # Range filters
        if min_co2:
            where_clauses.append("e.co2_mass_short_tons >= %s")
            params.append(float(min_co2))
        if max_co2:
            where_clauses.append("e.co2_mass_short_tons <= %s")
            params.append(float(max_co2))
            
        if min_so2:
            where_clauses.append("e.so2_mass_short_tons >= %s")
            params.append(float(min_so2))
        if max_so2:
            where_clauses.append("e.so2_mass_short_tons <= %s")
            params.append(float(max_so2))

        if min_nox:
            where_clauses.append("e.nox_mass_short_tons >= %s")
            params.append(float(min_nox))
            
        if max_op_time:
            where_clauses.append("e.sum_of_the_operating_time <= %s")
            params.append(float(max_op_time))

        if min_op_time:
            where_clauses.append("e.sum_of_the_operating_time >= %s")
            params.append(float(min_op_time))
            
        if min_gross_load:
            where_clauses.append("e.gross_load_mwh >= %s")
            params.append(float(min_gross_load))

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # Get dynamic sorting SQL and metadata via helper function
        order_sql, sorting_meta = get_sorting_sql(request)

        # Count total records for pagination
        count_query = f"""
            SELECT COUNT(*) as total 
            FROM Annual_Emissions e
            JOIN Facilities f ON e.facility_id = f.facility_id
            {where_sql}
        """
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']

        # Fetch filtered, sorted, paginated records
        query = f"""
            SELECT e.*, f.facility_name, f.state, f.county 
            FROM Annual_Emissions e
            JOIN Facilities f ON e.facility_id = f.facility_id
            {where_sql}
            {order_sql}
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": (total_records + limit - 1) // limit,
            "sorting": sorting_meta,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/search/ranking', methods=['GET'])
def ranking_search():
    """
    Supports Top-N, Bottom-N, and Group-and-Rank searches as required by project specs.
    Query Params:
      - type: 'top_facilities', 'top_units', 'lowest_so2'
      - metric: column to rank by
      - limit: int (default 10)
    """
    try:
        rank_type = request.args.get('type', 'top_facilities')
        limit = max(1, min(50, int(request.args.get('limit', 10))))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if rank_type == 'top_facilities':
            # Top N facilities by total CO2 emissions
            query = """
                SELECT f.facility_id, f.facility_name, f.state, SUM(e.co2_mass_short_tons) as total_co2
                FROM Annual_Emissions e
                JOIN Facilities f ON e.facility_id = f.facility_id
                GROUP BY f.facility_id, f.facility_name, f.state
                ORDER BY total_co2 DESC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
            
        elif rank_type == 'lowest_so2':
            # Bottom N units by SO2 emissions
            query = """
                SELECT e.facility_id, f.facility_name, e.unit_id, e.reporting_year, e.so2_mass_short_tons, e.primary_fuel_type
                FROM Annual_Emissions e
                JOIN Facilities f ON e.facility_id = f.facility_id
                WHERE e.so2_mass_short_tons IS NOT NULL
                ORDER BY e.so2_mass_short_tons ASC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
        else:
            return jsonify({"status": "error", "message": "Invalid ranking type specified."}), 400

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "type": rank_type,
            "data": results
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# NATURAL LANGUAGE SEARCH SECTION
@app.route('/api/search/natural', methods=['GET'])
def natural_language_search():
    """
    Natural language search for annual emissions.
    Query Params:
      - text: string (e.g., "coal power plants in Kentucky with high co2")
      - sort / sort_by: string
      - order: string ('ASC' or 'DESC')
      - page: int (default 1)
      - limit: int (default 20)
    """
    try:
        text = request.args.get('text', '').strip()
        if not text:
            return jsonify({"status": "error", "message": "No search description provided."}), 400

        # 1. Parse filters using your separate module
        filters = parse_natural_language_query(text)

        # 2. Get pagination parameters from URL (defaults to page 1, limit 20)
        page = max(1, int(request.args.get('page', 1)))
        limit = max(1, min(100, int(request.args.get('limit', 20))))
        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Build where clause from natural language parser results
        where_clauses = []
        params = []
        
        if filters.get("state"):
            where_clauses.append("f.state = %s")
            params.append(filters["state"])
            
        if filters.get("fuel"):
            where_clauses.append("e.primary_fuel_type LIKE %s")
            params.append(f"%{filters['fuel']}%")
            
        if filters.get("year"):
            where_clauses.append("e.reporting_year = %s")
            params.append(int(filters["year"]))
            
        if filters.get("min_co2") is not None:
            where_clauses.append("e.co2_mass_short_tons >= %s")
            params.append(float(filters["min_co2"]))
            
        if filters.get("max_co2") is not None:
            where_clauses.append("e.co2_mass_short_tons <= %s")
            params.append(float(filters["max_co2"]))
            
        if filters.get("min_so2") is not None:
            where_clauses.append("e.so2_mass_short_tons >= %s")
            params.append(float(filters["min_so2"]))
            
        if filters.get("max_so2") is not None:
            where_clauses.append("e.so2_mass_short_tons <= %s")
            params.append(float(filters["max_so2"]))
            
        if filters.get("min_nox") is not None:
            where_clauses.append("e.nox_mass_short_tons >= %s")
            params.append(float(filters["min_nox"]))

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # 3. Get dynamic sorting SQL and metadata via helper function
        order_sql, sorting_meta = get_sorting_sql(request)

        # 4. Get total count of matching records for pagination math
        count_query = f"""
            SELECT COUNT(*) as total 
            FROM Annual_Emissions e
            JOIN Facilities f ON e.facility_id = f.facility_id
            {where_sql}
        """
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()["total"]
        total_pages = max(1, (total_records + limit - 1) // limit)

        # 5. Fetch the paginated and sorted records using LIMIT, OFFSET, and dynamic order_sql
        data_query = f"""
            SELECT e.*, f.facility_name, f.state, f.county 
            FROM Annual_Emissions e
            JOIN Facilities f ON e.facility_id = f.facility_id
            {where_sql}
            {order_sql}
            LIMIT %s OFFSET %s
        """
        cursor.execute(data_query, params + [limit, offset])
        records = cursor.fetchall()

        cursor.close()
        conn.close()

        # 6. Return the full response containing pagination, interpreted filters, and sorting metadata
        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages,
            "interpreted_filters": filters,
            "sorting": sorting_meta,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


#EXPORT SEARCH FILTERS
@app.route('/api/search/export', methods=['GET'])
def export_csv():
    """
    Consolidated export route. Handles both Advanced Search parameters 
    and Natural Language text queries, with support for dynamic sorting.
    """
    try:
        text_query = request.args.get('text', '').strip()
        
        # Scenario A: User passed a natural language text string
        if text_query:
            filters = parse_natural_language_query(text_query)
        
        # Scenario B: User passed individual advanced search parameters
        else:
            filters = {
                "state": request.args.get('state'),
                "fuel": request.args.get('fuel'),
                "year": request.args.get('year', type=int),
                "min_co2": request.args.get('min_co2', type=float),
                "max_co2": request.args.get('max_co2', type=float),
                "min_so2": request.args.get('min_so2', type=float),
                "max_so2": request.args.get('max_so2', type=float),
                "min_op_time": request.args.get('min_op_time', type=float),
                "min_gross_load": request.args.get('min_gross_load', type=float)
            }

        where_sql, params = build_where_clause(filters)
        
        # Integrate dynamic sorting helper so the exported CSV matches user view sorting
        order_sql, _ = get_sorting_sql(request)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT e.facility_id, f.facility_name, f.state, f.county, 
                   e.reporting_year, e.primary_fuel_type, 
                   e.co2_mass_short_tons, e.so2_mass_short_tons, 
                   e.sum_of_the_operating_time
            FROM Annual_Emissions e
            JOIN Facilities f ON e.facility_id = f.facility_id
            {where_sql}
            {order_sql}
            LIMIT 5000
        """
        cursor.execute(query, params)
        records = cursor.fetchall()

        cursor.close()
        conn.close()

        # Build CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Facility ID", "Facility Name", "State", "County", 
            "Reporting Year", "Fuel Type", "CO2 (tons)", "SO2 (tons)", "Operating Time (hrs)"
        ])

        for row in records:
            writer.writerow([
                row.get("facility_id"), row.get("facility_name"), row.get("state"),
                row.get("county"), row.get("reporting_year"), row.get("primary_fuel_type"),
                row.get("co2_mass_short_tons"), row.get("so2_mass_short_tons"),
                row.get("sum_of_the_operating_time")
            ])

        output.seek(0)

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=emissions_export.csv"
        response.headers["Content-Type"] = "text/csv"

        return response

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


#File Upload & Data Export Routes
@app.route('/api/upload/preview', methods=['POST'])
def upload_preview():
    """Parses uploaded CSV/Excel files and returns a data quality validation report."""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    try:
        # Read file based on extension
        filename = file.filename.lower()
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
            return jsonify({"status": "error", "message": "Invalid file format. Please upload a CSV or Excel file."}), 400

        total_rows = len(df)

        # 1. Field Validation: Check for required columns
        required_cols = ['facility_id', 'reporting_year', 'co2_mass_short_tons']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            return jsonify({
                "status": "error",
                "message": f"Validation failed. Missing required columns: {missing_cols}"
            }), 400

        # 2. Row-Level Quality Checks
        # Identify valid rows (e.g., CO2 cannot be negative, facility_id must not be null)
        valid_mask = (df['co2_mass_short_tons'] >= 0) & (df['facility_id'].notna())
        
        valid_df = df[valid_mask]
        invalid_df = df[~valid_mask]

        valid_count = len(valid_df)
        invalid_count = len(invalid_df)

        return jsonify({
            "status": "success",
            "filename": file.filename,
            "data_quality_report": {
                "total_rows": total_rows,
                "valid_rows": valid_count,
                "invalid_rows": invalid_count,
                "validation_passed": invalid_count == 0
            },
            # Optional: Preview the first few valid rows
            "preview_data": valid_df.head(5).to_dict(orient='records')
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "success", "message": "File parsed successfully"}), 200

# RUN SERVER

if __name__ == '__main__':
    app.run(debug=True, port=5000)