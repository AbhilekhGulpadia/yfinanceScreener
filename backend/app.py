from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Backend is running'})

@app.route('/api/data', methods=['GET'])
def get_data():
    """Sample GET endpoint"""
    sample_data = {
        'items': [
            {'id': 1, 'name': 'Item 1', 'value': 100},
            {'id': 2, 'name': 'Item 2', 'value': 200},
            {'id': 3, 'name': 'Item 3', 'value': 300}
        ]
    }
    return jsonify(sample_data)

@app.route('/api/data', methods=['POST'])
def create_data():
    """Sample POST endpoint"""
    data = request.get_json()
    return jsonify({
        'message': 'Data received successfully',
        'data': data
    }), 201

if __name__ == '__main__':
    app.run(debug=True, port=5000)
