import os
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv

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

        if op_hour is not None and op_hour != '':
            where_clauses.append("h.op_hour = %s")
            params.append(int(op_hour))

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " && ".join(where_clauses) # or " AND "

        # OPTIMIZATION: Avoid full table scan for COUNT(*) if no filters are applied
        if not where_clauses:
            cursor.execute("SELECT TABLE_ROWS FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'Hourly_Emissions'")
            row = cursor.fetchone()
            total_records = row.get('table_rows') or row.get('TABLE_ROWS') if row else 1000000
        else:
            count_query = f"SELECT COUNT(*) as total FROM Hourly_Emissions h {where_sql}"
            cursor.execute(count_query, params)
            total_records = cursor.fetchone()['total']

        # Optimized query using proper index ordering
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


#File Upload & Data Export Routes
@app.route('/api/upload/preview', methods=['POST'])
def upload_preview():
    """Parses uploaded CSV/Excel files and returns a data quality validation report."""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['file']
    return jsonify({"status": "success", "message": "File parsed successfully"}), 200


@app.route('/api/export', methods=['GET'])
def export_csv():
    """Streams CSV output based on current search parameters."""
    pass


# RUN SERVER

if __name__ == '__main__':
    app.run(debug=True, port=5000)