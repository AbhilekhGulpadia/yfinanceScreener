# Stock Analyzer

A comprehensive stock analysis application with real-time data tracking, technical indicators, and portfolio management.

## Features

- 📊 Real-time stock data tracking
- 📈 Technical analysis with RSI and MACD indicators
- 🔥 Market heatmaps for quick insights
- 💼 Portfolio management
- 📱 Responsive web interface
- 🔔 Real-time updates via WebSocket

## Tech Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: SQLAlchemy
- **Real-time**: Socket.IO
- **API**: Kite Connect for market data

### Frontend
- **Framework**: React
- **Charts**: Plotly.js
- **Real-time**: Socket.IO Client

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Node.js 14 or higher
- npm or yarn
- Google Chrome browser

### Automated Setup (Recommended)

Simply run the initialization script:

```bash
./start.sh
```

This script will:
1. ✅ Check all prerequisites
2. 📦 Set up Python virtual environment
3. 📦 Install backend dependencies
4. 🚀 Start the Flask backend server
5. 📦 Install frontend dependencies
6. 🚀 Start the React development server
7. 🌐 Launch Chrome browser automatically

The application will be available at:
- **Frontend**: http://localhost:3000
- **Backend**: https://localhost:5000

To stop all servers, press `Ctrl+C` in the terminal.

### Manual Setup

If you prefer to set up manually:

#### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

#### Frontend Setup

```bash
cd frontend
npm install
npm start
```

## Configuration

### Backend Configuration

Edit `backend/config.py` to configure:
- Database settings
- API credentials
- Server settings

### Kite Connect Setup

1. Create a Kite Connect app at https://developers.kite.trade/
2. Add your API credentials to `backend/config.py`
3. Run the authentication flow to generate access tokens

## Project Structure

```
stockAnalyzer-1/
├── backend/
│   ├── app.py              # Flask application entry point
│   ├── config.py           # Configuration settings
│   ├── models.py           # Database models
│   ├── routes/             # API routes
│   ├── services/           # Business logic
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── App.js          # Main React component
│   │   └── index.js        # Entry point
│   ├── public/             # Static files
│   └── package.json        # Node dependencies
├── start.sh                # Initialization script
└── README.md               # This file
```

## Available Scripts

### Backend

- `python app.py` - Start the Flask server with HTTPS
- `python test_api.py` - Test API endpoints
- `python export_data.py` - Export OHLCV data

### Frontend

- `npm start` - Start development server
- `npm build` - Build for production
- `npm test` - Run tests

## Logs

Application logs are written to `startup.log` when using the initialization script.

## Troubleshooting

### Port Already in Use

If you get a "port already in use" error:

```bash
# Find and kill process on port 5000 (backend)
lsof -ti:5000 | xargs kill -9

# Find and kill process on port 3000 (frontend)
lsof -ti:3000 | xargs kill -9
```

### SSL Certificate Warnings

The backend uses a self-signed certificate for HTTPS. You may need to accept the security warning in your browser.

### Dependencies Issues

If you encounter dependency issues:

```bash
# Backend
cd backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please create an issue in the repository.
