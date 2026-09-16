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
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "data": {
                "facilities": total_facilities,
                "units": total_units,
                "emissions_records": total_records
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
      - year: int (e.g., 2022)
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


#File Upload & Data Export Routes
@app.route('/api/upload/preview', methods=['POST'])
def upload_preview():
    """Parses uploaded CSV/Excel files and returns a data quality validation report."""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['file']
    # Add Pandas parsing, column verification, and duplicate check logic here
    return jsonify({"status": "success", "message": "File parsed successfully"}), 200


@app.route('/api/export', methods=['GET'])
def export_csv():
    """Streams CSV output based on current search parameters."""
    pass


# RUN SERVER

if __name__ == '__main__':
    app.run(debug=True, port=5000)