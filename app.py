import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  #Enables cross-origin requests for frontend integration

# DATABASE HELPER

def get_db_connection():
    """Establishes and returns a connection to the MySQL database."""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"),
        database="epadata"
    )


#ROUTES

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

        #Get total matching count for pagination
        count_query = f"SELECT COUNT(*) as total FROM Facilities {where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']

        #Get paginated results
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

        #Fetch facility detail
        cursor.execute("SELECT * FROM Facilities WHERE facility_id = %s", (facility_id,))
        facility = cursor.fetchone()

        if not facility:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Facility not found"}), 404

        #Fetch associated units
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

        #Count total records
        count_query = f"SELECT COUNT(*) as total FROM Annual_Emissions {where_sql}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']

        #Fetch paginated records joined with facility name
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


# RUN SERVER

if __name__ == '__main__':
    app.run(debug=True, port=5000)