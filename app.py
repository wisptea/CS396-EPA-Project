import os

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv

import csv
import io
from flask import send_file
from openpyxl import Workbook
import pandas as pd
import json
# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# CREATE FLASK APPLICATION
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"),
        database="epadata"
    )


# ============================================================
# WEB PAGE ROUTES
# ============================================================

@app.route('/')
def home():
    return render_template('Homepage.html')
@app.route("/facility-detail")
def facility_detail():
    return render_template("Facility-detail.html")

@app.route('/explorer')
def explorer():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM Facilities LIMIT 100")
    facilities = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'Explorepage.html',
        facilities=facilities
    )





@app.route('/retrieval')
def retrieval():
    return render_template('retrievelpage.html')


@app.route('/download')
def download():
    return render_template('Download.html')


@app.route('/facility')
def facility():
    return render_template('Facility-detail.html')

@app.route('/upload')
def upload():
    return render_template('Uploadpage.html')
# ============================================================
# DATASET STATISTICS
# ============================================================

@app.route('/api/stats', methods=['GET'])
def get_stats():

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT COUNT(*) AS total_facilities FROM Facilities"
        )
        total_facilities = cursor.fetchone()['total_facilities']

        cursor.execute(
            "SELECT COUNT(*) AS total_units FROM Units"
        )
        total_units = cursor.fetchone()['total_units']

        cursor.execute(
            "SELECT COUNT(*) AS total_records FROM Annual_Emissions"
        )
        total_records = cursor.fetchone()['total_records']

        cursor.execute(
            "SELECT COUNT(*) AS total_daily FROM Daily_Emissions"
        )
        total_daily = cursor.fetchone()['total_daily']

        cursor.execute(
            "SELECT COUNT(*) AS total_hourly FROM Hourly_Emissions"
        )
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
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# FACILITIES
# ============================================================

@app.route('/api/facilities', methods=['GET'])
def get_facilities():

    try:
        search = request.args.get(
            'search',
            ''
        ).strip()

        state = request.args.get(
            'state',
            ''
        ).strip()

        page = max(
            1,
            int(request.args.get('page', 1))
        )

        limit = max(
            1,
            min(
                100,
                int(request.args.get('limit', 20))
            )
        )

        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        if search:
            where_clauses.append(
                "facility_name LIKE %s"
            )
            params.append(
                f"%{search}%"
            )

        if state:
            where_clauses.append(
                "state = %s"
            )
            params.append(state)

        where_sql = ""

        if where_clauses:
            where_sql = (
                "WHERE "
                + " AND ".join(where_clauses)
            )

        # Count matching facilities
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM Facilities
            {where_sql}
        """

        cursor.execute(
            count_query,
            params
        )

        total_records = cursor.fetchone()['total']

        # Get matching facilities
        query = f"""
            SELECT *
            FROM Facilities

            {where_sql}

            ORDER BY facility_name ASC

            LIMIT %s OFFSET %s
        """

        cursor.execute(
            query,
            params + [limit, offset]
        )

        facilities = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages":
                (total_records + limit - 1) // limit,
            "data": facilities
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# SINGLE FACILITY
# ============================================================

@app.route(
    '/api/facilities/<int:facility_id>',
    methods=['GET']
)
def get_facility_by_id(facility_id):

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM Facilities
            WHERE facility_id = %s
            """,
            (facility_id,)
        )

        facility = cursor.fetchone()

        if not facility:

            cursor.close()
            conn.close()

            return jsonify({
                "status": "error",
                "message": "Facility not found"
            }), 404

        cursor.execute(
            """
            SELECT *
            FROM Units
            WHERE facility_id = %s
            """,
            (facility_id,)
        )

        units = cursor.fetchall()

        facility['units'] = units

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "data": facility
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# ANNUAL EMISSIONS
# ============================================================

@app.route('/api/emissions', methods=['GET'])
def get_emissions():

    try:
        year = request.args.get('year')
        fuel_type = request.args.get('fuel_type')
        facility_id = request.args.get('facility_id')

        page = max(
            1,
            int(request.args.get('page', 1))
        )

        limit = max(
            1,
            min(
                100,
                int(request.args.get('limit', 20))
            )
        )

        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        if year:
            where_clauses.append(
                "e.reporting_year = %s"
            )
            params.append(int(year))

        if fuel_type:
            where_clauses.append(
                "e.primary_fuel_type = %s"
            )
            params.append(fuel_type)

        if facility_id:
            where_clauses.append(
                "e.facility_id = %s"
            )
            params.append(int(facility_id))

        where_sql = ""

        if where_clauses:
            where_sql = (
                "WHERE "
                + " AND ".join(where_clauses)
            )

        # Count annual records
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM Annual_Emissions e
            {where_sql}
        """

        cursor.execute(
            count_query,
            params
        )

        total_records = cursor.fetchone()['total']

        # Retrieve annual emissions
        query = f"""
            SELECT
                e.*,
                f.facility_name,
                f.state

            FROM Annual_Emissions e

            JOIN Facilities f
                ON e.facility_id = f.facility_id

            {where_sql}

            ORDER BY
                e.reporting_year DESC,
                e.co2_mass_short_tons DESC

            LIMIT %s OFFSET %s
        """

        cursor.execute(
            query,
            params + [limit, offset]
        )

        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages":
                (total_records + limit - 1) // limit,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# DAILY EMISSIONS
# ============================================================

@app.route('/api/emissions/daily', methods=['GET'])
def get_daily_emissions():

    try:
        facility_id = request.args.get('facility_id')
        unit_id = request.args.get('unit_id')
        op_date = request.args.get('date')

        page = max(
            1,
            int(request.args.get('page', 1))
        )

        limit = max(
            1,
            min(
                100,
                int(request.args.get('limit', 20))
            )
        )

        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        if facility_id:
            where_clauses.append(
                "d.facility_id = %s"
            )
            params.append(int(facility_id))

        if unit_id:
            where_clauses.append(
                "d.unit_id = %s"
            )
            params.append(unit_id)

        if op_date:
            where_clauses.append(
                "d.op_date = %s"
            )
            params.append(op_date)

        where_sql = ""

        if where_clauses:
            where_sql = (
                "WHERE "
                + " AND ".join(where_clauses)
            )

        count_query = f"""
            SELECT COUNT(*) AS total
            FROM Daily_Emissions d
            {where_sql}
        """

        cursor.execute(
            count_query,
            params
        )

        total_records = cursor.fetchone()['total']

        query = f"""
            SELECT
                d.*,
                f.facility_name,
                f.state

            FROM Daily_Emissions d

            JOIN Facilities f
                ON d.facility_id = f.facility_id

            {where_sql}

            ORDER BY d.op_date DESC

            LIMIT %s OFFSET %s
        """

        cursor.execute(
            query,
            params + [limit, offset]
        )

        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages":
                (total_records + limit - 1) // limit,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# HOURLY EMISSIONS
# ============================================================

@app.route('/api/emissions/hourly', methods=['GET'])
def get_hourly_emissions():

    try:
        facility_id = request.args.get('facility_id')
        unit_id = request.args.get('unit_id')
        op_date = request.args.get('date')
        op_hour = request.args.get('hour')

        page = max(
            1,
            int(request.args.get('page', 1))
        )

        limit = max(
            1,
            min(
                100,
                int(request.args.get('limit', 20))
            )
        )

        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        if facility_id:
            where_clauses.append(
                "h.facility_id = %s"
            )
            params.append(int(facility_id))

        if unit_id:
            where_clauses.append(
                "h.unit_id = %s"
            )
            params.append(unit_id)

        if op_date:
            where_clauses.append(
                "h.op_date = %s"
            )
            params.append(op_date)

        if op_hour is not None:
            where_clauses.append(
                "h.op_hour = %s"
            )
            params.append(int(op_hour))

        where_sql = ""

        if where_clauses:
            where_sql = (
                "WHERE "
                + " AND ".join(where_clauses)
            )

        count_query = f"""
            SELECT COUNT(*) AS total
            FROM Hourly_Emissions h
            {where_sql}
        """

        cursor.execute(
            count_query,
            params
        )

        total_records = cursor.fetchone()['total']

        query = f"""
            SELECT
                h.*,
                f.facility_name,
                f.state

            FROM Hourly_Emissions h

            JOIN Facilities f
                ON h.facility_id = f.facility_id

            {where_sql}

            ORDER BY
                h.op_date DESC,
                h.op_hour DESC

            LIMIT %s OFFSET %s
        """

        cursor.execute(
            query,
            params + [limit, offset]
        )

        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages":
                (total_records + limit - 1) // limit,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# DATASET METADATA
# ============================================================

@app.route('/api/metadata', methods=['GET'])
def get_metadata():

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM Dataset_Metadata
            ORDER BY metadata_id DESC
            """
        )

        metadata = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "data": metadata
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# GLOBAL SEARCH
# ============================================================

@app.route('/api/search', methods=['GET'])
def global_search():

    try:
        query = request.args.get(
            'q',
            ''
        ).strip()

        if not query:
            return jsonify({
                "status": "success",
                "data": {
                    "facilities": [],
                    "units": [],
                    "traci_factors": []
                }
            }), 200

        limit = max(
            1,
            min(
                50,
                int(request.args.get('limit', 10))
            )
        )

        search_pattern = f"%{query}%"

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Search facilities
        cursor.execute(
            """
            SELECT
                facility_id,
                facility_name,
                state,
                county,
                source_category

            FROM Facilities

            WHERE
                facility_name LIKE %s
                OR state LIKE %s
                OR county LIKE %s

            LIMIT %s
            """,
            (
                search_pattern,
                search_pattern,
                search_pattern,
                limit
            )
        )

        facilities = cursor.fetchall()

        # Search units
        cursor.execute(
            """
            SELECT
                facility_id,
                unit_id,
                unit_type,
                so2_controls,
                nox_controls

            FROM Units

            WHERE
                unit_id LIKE %s
                OR unit_type LIKE %s

            LIMIT %s
            """,
            (
                search_pattern,
                search_pattern,
                limit
            )
        )

        units = cursor.fetchall()

        # Search TRACI factors
        cursor.execute(
            """
            SELECT
                traci_id,
                substance,
                category,
                factor,
                unit

            FROM TRACI_Factors

            WHERE
                substance LIKE %s
                OR category LIKE %s
                OR cas_number LIKE %s

            LIMIT %s
            """,
            (
                search_pattern,
                search_pattern,
                search_pattern,
                limit
            )
        )

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
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# ADVANCED ANNUAL EMISSIONS SEARCH
# STATE + YEAR + FUEL + EMISSIONS RANGES
# ============================================================

@app.route('/api/search/advanced', methods=['GET'])
def advanced_emissions_search():

    try:
        # Main filters
        state = request.args.get(
            'state',
            ''
        ).strip()

        year = request.args.get('year')

        fuel = request.args.get(
            'fuel',
            ''
        ).strip()

        # Emissions filters
        min_co2 = request.args.get('min_co2')
        max_co2 = request.args.get('max_co2')

        min_so2 = request.args.get('min_so2')
        max_so2 = request.args.get('max_so2')

        min_nox = request.args.get('min_nox')
        max_nox = request.args.get('max_nox')

        # Operating filters
        min_op_time = request.args.get('min_op_time')
        max_op_time = request.args.get('max_op_time')

        min_gross_load = request.args.get(
            'min_gross_load'
        )

        max_gross_load = request.args.get(
            'max_gross_load'
        )

        # Sorting
        sort_by = request.args.get(
            'sort_by',
            'co2_mass_short_tons'
        )

        order = request.args.get(
            'order',
            'DESC'
        ).upper()

        # Pagination
        page = max(
            1,
            int(request.args.get('page', 1))
        )

        limit = max(
            1,
            min(
                100,
                int(request.args.get('limit', 20))
            )
        )

        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        where_clauses = []
        params = []

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        if state:
            where_clauses.append(
                "f.state = %s"
            )
            params.append(state)

        # ----------------------------------------------------
        # YEAR
        # ----------------------------------------------------

        if year:
            where_clauses.append(
                "e.reporting_year = %s"
            )
            params.append(int(year))

        # ----------------------------------------------------
        # FUEL
        # ----------------------------------------------------

        if fuel:
            where_clauses.append(
                "e.primary_fuel_type LIKE %s"
            )
            params.append(
                f"%{fuel}%"
            )

        # ----------------------------------------------------
        # CO2
        # ----------------------------------------------------

        if min_co2:
            where_clauses.append(
                "e.co2_mass_short_tons >= %s"
            )
            params.append(float(min_co2))

        if max_co2:
            where_clauses.append(
                "e.co2_mass_short_tons <= %s"
            )
            params.append(float(max_co2))

        # ----------------------------------------------------
        # SO2
        # ----------------------------------------------------

        if min_so2:
            where_clauses.append(
                "e.so2_mass_short_tons >= %s"
            )
            params.append(float(min_so2))

        if max_so2:
            where_clauses.append(
                "e.so2_mass_short_tons <= %s"
            )
            params.append(float(max_so2))

        # ----------------------------------------------------
        # NOX
        # ----------------------------------------------------

        if min_nox:
            where_clauses.append(
                "e.nox_mass_short_tons >= %s"
            )
            params.append(float(min_nox))

        if max_nox:
            where_clauses.append(
                "e.nox_mass_short_tons <= %s"
            )
            params.append(float(max_nox))

        # ----------------------------------------------------
        # OPERATING TIME
        # ----------------------------------------------------

        if min_op_time:
            where_clauses.append(
                "e.sum_of_the_operating_time >= %s"
            )
            params.append(float(min_op_time))

        if max_op_time:
            where_clauses.append(
                "e.sum_of_the_operating_time <= %s"
            )
            params.append(float(max_op_time))

        # ----------------------------------------------------
        # GROSS LOAD
        # ----------------------------------------------------

        if min_gross_load:
            where_clauses.append(
                "e.gross_load_mwh >= %s"
            )
            params.append(float(min_gross_load))

        if max_gross_load:
            where_clauses.append(
                "e.gross_load_mwh <= %s"
            )
            params.append(float(max_gross_load))

        # Build WHERE statement
        where_sql = ""

        if where_clauses:
            where_sql = (
                "WHERE "
                + " AND ".join(where_clauses)
            )

        # ----------------------------------------------------
        # SAFE SORTING
        # ----------------------------------------------------

        allowed_sorts = {
            "co2_mass_short_tons":
                "e.co2_mass_short_tons",

            "so2_mass_short_tons":
                "e.so2_mass_short_tons",

            "nox_mass_short_tons":
                "e.nox_mass_short_tons",

            "gross_load_mwh":
                "e.gross_load_mwh",

            "sum_of_the_operating_time":
                "e.sum_of_the_operating_time",

            "reporting_year":
                "e.reporting_year"
        }

        safe_sort = allowed_sorts.get(
            sort_by,
            "e.co2_mass_short_tons"
        )

        safe_order = (
            "ASC"
            if order == "ASC"
            else "DESC"
        )

        # ----------------------------------------------------
        # COUNT RESULTS
        # ----------------------------------------------------

        count_query = f"""
            SELECT COUNT(*) AS total

            FROM Annual_Emissions e

            JOIN Facilities f
                ON e.facility_id = f.facility_id

            {where_sql}
        """

        cursor.execute(
            count_query,
            params
        )

        total_records = cursor.fetchone()['total']

        # ----------------------------------------------------
        # GET RESULTS
        # ----------------------------------------------------

        query = f"""
            SELECT
                e.*,
                f.facility_name,
                f.state,
                f.county

            FROM Annual_Emissions e

            JOIN Facilities f
                ON e.facility_id = f.facility_id

            {where_sql}

            ORDER BY
                {safe_sort} {safe_order}

            LIMIT %s OFFSET %s
        """

        cursor.execute(
            query,
            params + [limit, offset]
        )

        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages":
                (total_records + limit - 1) // limit,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# RANKING SEARCH
# ============================================================

@app.route('/api/search/ranking', methods=['GET'])
def ranking_search():

    try:
        rank_type = request.args.get(
            'type',
            'top_facilities'
        )

        limit = max(
            1,
            min(
                50,
                int(request.args.get('limit', 10))
            )
        )

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if rank_type == 'top_facilities':

            query = """
                SELECT
                    f.facility_id,
                    f.facility_name,
                    f.state,
                    SUM(
                        e.co2_mass_short_tons
                    ) AS total_co2

                FROM Annual_Emissions e

                JOIN Facilities f
                    ON e.facility_id = f.facility_id

                GROUP BY
                    f.facility_id,
                    f.facility_name,
                    f.state

                ORDER BY total_co2 DESC

                LIMIT %s
            """

            cursor.execute(
                query,
                (limit,)
            )

        elif rank_type == 'lowest_so2':

            query = """
                SELECT
                    e.facility_id,
                    f.facility_name,
                    e.unit_id,
                    e.reporting_year,
                    e.so2_mass_short_tons,
                    e.primary_fuel_type

                FROM Annual_Emissions e

                JOIN Facilities f
                    ON e.facility_id = f.facility_id

                WHERE
                    e.so2_mass_short_tons
                    IS NOT NULL

                ORDER BY
                    e.so2_mass_short_tons ASC

                LIMIT %s
            """

            cursor.execute(
                query,
                (limit,)
            )

        else:
            cursor.close()
            conn.close()

            return jsonify({
                "status": "error",
                "message":
                    "Invalid ranking type specified."
            }), 400

        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "type": rank_type,
            "data": results
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================
# FILE UPLOAD PREVIEW
# ============================================================

@app.route(
    '/api/upload/preview',
    methods=['POST']
)
def upload_preview():

    if 'file' not in request.files:
        return jsonify({
            "status": "error",
            "message": "No file uploaded"
        }), 400

    file = request.files['file']

    return jsonify({
        "status": "success",
        "message": "File parsed successfully"
    }), 200


# ============================================================
# DATA EXPORT
# ============================================================


# ============================================================
# DOWNLOAD DATA - CSV OR EXCEL
# ============================================================

@app.route('/api/export', methods=['GET'])
def export_data():
    dataset = request.args.get('dataset', '').strip().lower()
    state = request.args.get('state', '').strip()
    year = request.args.get('year', '').strip()
    pollutant = request.args.get('pollutant', '').strip().upper()
    facility = request.args.get('facility', '').strip()
    source = request.args.get('source', '').strip()
    file_format = request.args.get('format', 'csv').strip().lower()

    if dataset not in ('facilities', 'units', 'annual'):
        return jsonify({
            "status": "error",
            "message": "Please select a valid dataset."
        }), 400

    if file_format not in ('csv', 'excel'):
        return jsonify({
            "status": "error",
            "message": "File format must be CSV or Excel."
        }), 400

    if source not in ('', 'EPA CAMPD'):
        return jsonify({
            "status": "error",
            "message": "This export currently supports EPA CAMPD data only."
        }), 400

    if year and (not year.isdigit() or dataset != 'annual'):
        return jsonify({
            "status": "error",
            "message": "Reporting year applies only to Annual Records."
        }), 400

    if pollutant and (
        dataset != 'annual'
        or pollutant not in ('CO2', 'SO2', 'NOX')
    ):
        return jsonify({
            "status": "error",
            "message": "Pollutant selection applies only to Annual Records."
        }), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if dataset == 'facilities':
            query = """
                SELECT f.*
                FROM Facilities f
                WHERE 1=1
            """
        elif dataset == 'units':
            query = """
                SELECT u.*, f.facility_name, f.state
                FROM Units u
                JOIN Facilities f
                  ON u.facility_id = f.facility_id
                WHERE 1=1
            """
        else:
            query = """
                SELECT e.*, f.facility_name, f.state
                FROM Annual_Emissions e
                JOIN Facilities f
                  ON e.facility_id = f.facility_id
                WHERE 1=1
            """

        params = []

        if state:
            query += " AND f.state = %s"
            params.append(state)

        if facility:
            query += """
                AND (
                    f.facility_name LIKE %s
                    OR CAST(f.facility_id AS CHAR) = %s
                )
            """
            params.extend([f"%{facility}%", facility])

        if year:
            query += " AND e.reporting_year = %s"
            params.append(int(year))

        cursor.execute(query, params)

        columns = [item[0] for item in cursor.description]
        records = cursor.fetchall()

        if not records:
            return jsonify({
                "status": "error",
                "message": "No records match your selected filters."
            }), 404

        # For annual data, export only the chosen pollutant
        # when one has been selected.
        if dataset == 'annual' and pollutant:
            pollutant_column = {
                'CO2': 'co2_mass_short_tons',
                'SO2': 'so2_mass_short_tons',
                'NOX': 'nox_mass_short_tons'
            }[pollutant]

            other_pollutant_columns = {
                'co2_mass_short_tons',
                'so2_mass_short_tons',
                'nox_mass_short_tons'
            } - {pollutant_column}

            columns = [
                col for col in columns
                if col not in other_pollutant_columns
            ]

        if file_format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)

            for record in records:
                writer.writerow([
                    record.get(column) for column in columns
                ])

            file_data = io.BytesIO(
                output.getvalue().encode('utf-8-sig')
            )
            extension = 'csv'
            mimetype = 'text/csv'

        else:
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = 'EPA Data'
            sheet.append(columns)

            for record in records:
                sheet.append([
                    record.get(column) for column in columns
                ])

            file_data = io.BytesIO()
            workbook.save(file_data)
            extension = 'xlsx'
            mimetype = (
                'application/vnd.openxmlformats-officedocument.'
                'spreadsheetml.sheet'
            )

        file_data.seek(0)

        return send_file(
            file_data,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f'epa_{dataset}.{extension}'
        )

    except Exception as error:
        print("Export error:", error)
        return jsonify({
            "status": "error",
            "message": "Unable to export the selected dataset."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


@app.route("/api/facility-detail")
def get_facility_detail():
    facility_id = request.args.get("facility_id")
    unit_id = request.args.get("unit_id")
    year = request.args.get("year")

    # Make sure all required values were provided
    if not facility_id or not unit_id or not year:
        return jsonify({
            "status": "error",
            "message": "facility_id, unit_id, and year are required"
        }), 400

    connection = None
    cursor = None

    try:
        # Connect to MySQL

        connection = get_db_connection()
        cursor = connection.cursor()

        # Get the selected facility/unit/year
        query = """
            SELECT
                ae.*,
                f.facility_name,
                f.state,
                f.county,
                f.latitude,
                f.longitude,
                f.source_category
            FROM Annual_Emissions ae
            JOIN Facilities f
                ON ae.facility_id = f.facility_id
            WHERE ae.facility_id = %s
              AND ae.unit_id = %s
              AND ae.reporting_year = %s
            LIMIT 1
        """

        cursor.execute(
            query,
            (facility_id, unit_id, year)
        )

        record = cursor.fetchone()

        # If no matching record exists
        if record is None:
            return jsonify({
                "status": "error",
                "message": "Facility record not found"
            }), 404

        # Return the matching record
        return jsonify({
            "status": "success",
            "data": record
        })

    except Exception as error:
        print("Facility detail error:", error)

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

# ==========================================
# UPLOAD DATA - FILE VALIDATION
# ==========================================

@app.route("/api/upload/validate", methods=["POST"])
def validate_uploaded_file():
    if "file" not in request.files:
        return jsonify({
            "status": "error",
            "message": "No file was uploaded."
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "status": "error",
            "message": "Please select a file."
        }), 400

    filename = file.filename
    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ["csv", "xlsx", "xls"]:
        return jsonify({
            "status": "error",
            "message": "Only CSV and Excel files are supported."
        }), 400

    try:
        if extension == "csv":
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        if df.empty:
            return jsonify({
                "status": "error",
                "message": "The uploaded dataset is empty."
            }), 400
              

        if len(df.columns) == 0 or df.columns.isna().any():
            return jsonify({
                "status": "error",
                "message": "The dataset must have valid column headers."
            }), 400
                # Check for invalid or duplicate column names
        df.columns = df.columns.astype(str).str.strip()

        invalid_columns = [
            col for col in df.columns
            if not col or col.lower().startswith("unnamed:")
        ]

        duplicate_columns = df.columns[
            df.columns.duplicated()
        ].tolist()

        if invalid_columns or duplicate_columns:
            return jsonify({
                "status": "error",
                "message": "Invalid dataset schema.",
                "validation_results": {
                    "invalid_columns": invalid_columns,
                    "duplicate_columns": duplicate_columns
                }
            }), 400

        # Check data types and values for recognized EPA fields
        type_errors = {}

        numeric_fields = [
            "facility_id",
            "unit_id",
            "reporting_year",
            "co2_emissions",
            "so2_emissions",
            "nox_emissions"
        ]

        for column in numeric_fields:
            if column in df.columns:
                numeric_values = pd.to_numeric(
                    df[column], errors="coerce"
                )

                invalid_count = int(
                    (df[column].notna() & numeric_values.isna()).sum()
                )

                if column == "reporting_year":
                    invalid_count += int(
                        (numeric_values.notna() &
                         (numeric_values % 1 != 0)).sum()
                    )

                if column in [
                    "co2_emissions",
                    "so2_emissions",
                    "nox_emissions"
                ]:
                    invalid_count += int(
                        (numeric_values < 0).sum()
                    )

                if invalid_count > 0:
                    type_errors[column] = invalid_count

        if type_errors:
            return jsonify({
                "status": "error",
                "message": "Dataset contains invalid data types or values.",
                "validation_results": {
                    "type_errors": type_errors
                }
            }), 400
          # Check for missing values
        missing_values = int(df.isnull().sum().sum())
        
                # Check for duplicate rows
        duplicate_rows = int(df.duplicated().sum())
        
        if missing_values > 0 or duplicate_rows > 0:
                    return jsonify({
                        "status": "error",
                        "message": "Dataset contains validation issues.",
                        "validation_results": {
                            "missing_values": missing_values,
                            "duplicate_rows": duplicate_rows,
                            "total_records": len(df)
                        }
                    }), 400

        return jsonify({
            "status": "success",
            "message": "File passed basic validation.",
            "filename": filename,
            "total_records": len(df),
            "columns": df.columns.tolist()
        })

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to read the uploaded file."
        }), 400

    # ==========================================
# UPLOAD DATA - IMPORT INTO MYSQL
# ==========================================

@app.route("/api/upload/import", methods=["POST"])
def import_uploaded_data():

    if "file" not in request.files:
        return jsonify({
            "status": "error",
            "message": "No file was uploaded."
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "status": "error",
            "message": "Please select a file."
        }), 400

    filename = file.filename
    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ["csv", "xlsx", "xls"]:
        return jsonify({
            "status": "error",
            "message": "Unsupported file format."
        }), 400

    connection = None
    cursor = None

    try:
        # Read the uploaded file
        if extension == "csv":
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        # Basic validation
        if df.empty:
            return jsonify({
                "status": "error",
                "message": "Cannot import an empty dataset."
            }), 400

        if (len(df.columns) == 0
                or df.columns.isna().any()
              or any(str(col).strip() == "" for col in df.columns)
                or df.columns.duplicated().any()):
            return jsonify({
                "status": "error",
                "message": "Invalid or duplicate column headers."
            }), 400
        # Check for missing values
        missing_values = int(df.isnull().sum().sum())

        # Check for duplicate rows
        duplicate_rows = int(df.duplicated().sum())

        # Reject invalid datasets
        if missing_values > 0 or duplicate_rows > 0:
            return jsonify({
                "status": "error",
                "message": "Cannot import dataset with validation issues.",
                "validation_results": {
                    "missing_values": missing_values,
                    "duplicate_rows": duplicate_rows,
                    "total_records": len(df)
                }
            }), 400
         
        # Convert records to JSON for storage
        file_data = df.to_json(
            orient="records",
            date_format="iso"
        )

        total_records = len(df)

        # Connect to MySQL
        connection = get_db_connection()
        cursor = connection.cursor()

        # Insert the dataset into the upload table
        query = """
            INSERT INTO Uploaded_Datasets
            (file_name, file_type, total_records, status, file_data)
            VALUES (%s, %s, %s, %s, %s)
        """

        values = (
            filename,
            extension,
            total_records,
            "Imported",
            file_data
        )

        cursor.execute(query, values)
        upload_id = cursor.lastrowid

        # Record metadata for the successful upload
        reporting_year = None

        if "reporting_year" in df.columns:
            years = pd.to_numeric(df["reporting_year"], errors="coerce")
            unique_years = years.dropna().unique()

            if len(unique_years) == 1:
                reporting_year = int(unique_years[0])

        metadata_query = """
            INSERT INTO Dataset_Metadata
            (
                dataset_name,
                data_source,
                reporting_year,
                granularity,
                original_filename,
                raw_records_count,
                accepted_records_count,
                rejected_records_count
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        metadata_values = (
            filename,
            "User Upload",
            reporting_year,
            "Unknown",
            filename,
            total_records,
            total_records,
            0
        )

        cursor.execute(metadata_query, metadata_values)
        connection.commit()

        return jsonify({
            "status": "success",
            "message": "Dataset successfully imported into MySQL.",
            "upload_id": upload_id,
            "total_records": total_records
        })

    except Exception as error:
        if connection:
            connection.rollback()

        print("Upload import error:", error)

        return jsonify({
            "status": "error",
          "message": "Unable to import the dataset."
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()

import re

def parse_natural_language_query(text):
    text = text.lower()
    filters = {}

    # Identify states
    states = {
        "kentucky": "KY",
        "ohio": "OH",
        "tennessee": "TN",
        "indiana": "IN",
        "illinois": "IL",
        "texas": "TX",
        "california": "CA",
        "florida": "FL"
    }

    for state_name, abbreviation in states.items():
        if re.search(r"\b" + state_name + r"\b", text):
            filters["state"] = abbreviation
            break

    # Identify fuel types
    fuels = ["coal", "natural gas", "oil", "diesel"]

    for fuel in fuels:
        if fuel in text:
            filters["fuel"] = fuel
            break

    # Identify reporting year
    year_match = re.search(r"\b(20\d{2})\b", text)

    if year_match:
        filters["year"] = int(year_match.group(1))

    # Identify minimum CO2 emissions
    co2_match = re.search(
        r"co2.*?(?:greater than|more than|over|above)\s*([\d,]+)",
        text
    )

    if co2_match:
        filters["min_co2"] = float(
            co2_match.group(1).replace(",", "")
        )

    return filters

def get_sorting_sql(request):
    allowed_columns = {
        "year": "e.reporting_year",
        "co2": "e.co2_mass_short_tons",
        "so2": "e.so2_mass_short_tons",
        "nox": "e.nox_mass_short_tons",
        "facility": "f.facility_name",
        "state": "f.state"
    }

    sort_by = request.args.get(
        "sort_by",
        request.args.get("sort", "co2")
    ).lower()

    order = request.args.get("order", "DESC").upper()

    if sort_by not in allowed_columns:
        sort_by = "co2"

    if order not in ("ASC", "DESC"):
        order = "DESC"

    column = allowed_columns[sort_by]

    order_sql = f"ORDER BY {column} {order}"

    sorting_meta = {
        "sort_by": sort_by,
        "order": order
    }

    return order_sql, sorting_meta

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
        filters =  parse_natural_language_query(text)

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

   

# KEEP THIS AT THE VERY BOTTOM
if __name__ == "__main__":
    app.run(debug=True)


