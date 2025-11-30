from flask import Blueprint, jsonify, request, redirect
from services.kite_client import kite_client

kite_auth_bp = Blueprint('kite_auth', __name__)

@kite_auth_bp.route('/api/kite/login', methods=['GET'])
def login():
    """Get Kite login URL"""
    try:
        url = kite_client.get_login_url()
        return jsonify({'login_url': url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@kite_auth_bp.route('/api/kite/callback', methods=['GET', 'POST'])
def callback():
    """Handle Kite callback after user login"""
    request_token = request.args.get('request_token')
    
    # Also allow POST for manual submission
    if not request_token and request.method == 'POST':
        data = request.get_json()
        request_token = data.get('request_token')
        
    if not request_token:
        # Redirect to frontend with error
        return redirect('http://localhost:3000?kite_auth=error&message=no_token')
        
    try:
        # Exchange request token for access token
        data = kite_client.generate_session(request_token)
        
        # Redirect to frontend with success
        return redirect('http://localhost:3000?kite_auth=success')
        
    except Exception as e:
        # Redirect to frontend with error
        error_msg = str(e).replace(' ', '_')
        return redirect(f'http://localhost:3000?kite_auth=error&message={error_msg}')

@kite_auth_bp.route('/api/kite/status', methods=['GET'])
def status():
    """Check if Kite client is connected"""
    is_connected = kite_client.access_token is not None
    return jsonify({
        'connected': is_connected,
        'has_instruments': bool(kite_client.instruments_map)
    })

@kite_auth_bp.route('/api/kite/export-instruments', methods=['POST'])
def export_instruments():
    """Export all NSE equity instruments from Kite to JSON file"""
    try:
        if not kite_client.access_token:
            return jsonify({'error': 'Not connected to Kite'}), 401
        
        success = kite_client.save_kite_instruments_to_json()
        
        if success:
            return jsonify({
                'message': 'Instruments exported successfully',
                'filename': 'kite_instruments.json'
            })
        else:
            return jsonify({'error': 'Failed to export instruments'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
