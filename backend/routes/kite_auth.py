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
    """Handle Kite callback or manual token submission"""
    request_token = request.args.get('request_token')
    
    # Also allow POST for manual submission
    if not request_token and request.method == 'POST':
        data = request.get_json()
        request_token = data.get('request_token')
        
    if not request_token:
        return jsonify({'error': 'Request token is required'}), 400
        
    try:
        data = kite_client.generate_session(request_token)
        return jsonify({
            'message': 'Login successful',
            'access_token': data.get('access_token'),
            'public_token': data.get('public_token')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@kite_auth_bp.route('/api/kite/status', methods=['GET'])
def status():
    """Check if Kite client is connected"""
    is_connected = kite_client.access_token is not None
    return jsonify({
        'connected': is_connected,
        'has_instruments': bool(kite_client.instruments_map)
    })
