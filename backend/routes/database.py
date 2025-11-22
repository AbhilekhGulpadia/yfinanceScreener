from flask import Blueprint, jsonify, request
from extensions import db
from sqlalchemy import inspect, text

database_bp = Blueprint('database', __name__)

@database_bp.route('/api/database/tables', methods=['GET'])
def get_database_tables():
    """Get list of all database tables"""
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    table_info = {}
    for table in tables:
        # Get row count for each table
        result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}"))
        count = result.scalar()
        table_info[table] = {'row_count': count}
    
    return jsonify({
        'tables': tables,
        'details': table_info
    })

@database_bp.route('/api/database/view/<table_name>', methods=['GET'])
def view_table_data(table_name):
    """View data from any table"""
    try:
        limit = request.args.get('limit', type=int, default=100)
        offset = request.args.get('offset', type=int, default=0)
        
        # Get table data
        query = text(f"SELECT * FROM {table_name} LIMIT :limit OFFSET :offset")
        result = db.session.execute(query, {'limit': limit, 'offset': offset})
        
        # Get column names
        columns = result.keys()
        
        # Fetch rows
        rows = []
        for row in result:
            rows.append(dict(zip(columns, row)))
        
        # Get total count
        count_query = text(f"SELECT COUNT(*) FROM {table_name}")
        total_count = db.session.execute(count_query).scalar()
        
        return jsonify({
            'table': table_name,
            'columns': list(columns),
            'rows': rows,
            'total_count': total_count,
            'returned_count': len(rows),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400
