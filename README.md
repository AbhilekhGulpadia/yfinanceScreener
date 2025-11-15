# Stock Analyzer Web App

A barebone full-stack web application with Python Flask backend and React frontend.

## Project Structure

```
stockAnalyzer/
├── backend/           # Python Flask API
│   ├── app.py        # Main Flask application
│   ├── requirements.txt
│   └── .gitignore
└── frontend/         # React application
    ├── public/
    │   └── index.html
    ├── src/
    │   ├── App.js
    │   ├── App.css
    │   ├── index.js
    │   └── index.css
    ├── package.json
    └── .gitignore
```

## Features

### Backend (Flask)
- Health check endpoint: `GET /api/health`
- Get data endpoint: `GET /api/data`
- Create data endpoint: `POST /api/data`
- CORS enabled for frontend integration

### Frontend (React)
- Fetches and displays data from backend API
- Form to submit new data to backend
- Responsive design
- Modern React hooks (useState, useEffect)

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   ```bash
   # On macOS/Linux:
   source venv/bin/activate
   
   # On Windows:
   # venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Run the Flask server:
   ```bash
   python app.py
   ```

   The backend will run on `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory (in a new terminal):
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the React development server:
   ```bash
   npm start
   ```

   The frontend will run on `http://localhost:3000`

## Usage

1. Start the backend server first (port 5000)
2. Start the frontend server (port 3000)
3. Open your browser to `http://localhost:3000`
4. The app will display data from the backend and allow you to submit new items

## API Endpoints

### GET /api/health
Health check endpoint to verify the backend is running.

**Response:**
```json
{
  "status": "healthy",
  "message": "Backend is running"
}
```

### GET /api/data
Retrieve sample data.

**Response:**
```json
{
  "items": [
    {"id": 1, "name": "Item 1", "value": 100},
    {"id": 2, "name": "Item 2", "value": 200},
    {"id": 3, "name": "Item 3", "value": 300}
  ]
}
```

### POST /api/data
Submit new data to the backend.

**Request Body:**
```json
{
  "name": "New Item",
  "value": 400
}
```

**Response:**
```json
{
  "message": "Data received successfully",
  "data": {"name": "New Item", "value": 400}
}
```

## Development

- Backend uses Flask with debug mode enabled
- Frontend uses React development server with hot reload
- Proxy configured in frontend to route API calls to backend

## Next Steps

To expand this application, you can:
- Add a database (SQLite, PostgreSQL, etc.)
- Implement authentication
- Add more API endpoints
- Create additional React components
- Add state management (Redux, Context API)
- Implement stock analysis features
- Add data visualization libraries (Chart.js, D3.js)
