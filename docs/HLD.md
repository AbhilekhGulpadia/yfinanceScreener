# Stock Analyzer - High-Level Design (HLD)

## 1. System Overview

Stock Analyzer is a **full-stack web application** for real-time analysis of Indian stock market data, specifically focused on the **Nifty 500** universe. The application integrates with **Kite Connect API** to fetch live and historical market data, applies technical analysis algorithms (including **Weinstein Stage Analysis**), and provides interactive visualizations for stock screening and portfolio management.

### Key Features
- **Real-time OHLCV Data**: Fetch and store 5 years of daily OHLCV data for 500+ stocks
- **Technical Analysis**: RSI, MACD, EMA crossovers, and custom scoring
- **Weinstein Screening**: Stage analysis methodology for identifying Stage 2 (bullish) stocks
- **Sector Heatmap**: Visual representation of sector-wise performance
- **Interactive Charts**: Candlestick charts with technical indicators
- **Portfolio Management**: Track trades, transactions, and watchlists
- **Brokerage Calculator**: Calculate trading costs for Indian markets

---

## 2. Technology Stack

### Backend
```
Language:   Python 3.x
Framework:  Flask (Web framework)
Database:   SQLite (ORM: SQLAlchemy)
Real-time:  Flask-SocketIO (WebSocket support)
API:        Kite Connect (Market data provider)
Scheduling: APScheduler (Background tasks)
Data:       Pandas, NumPy (Data processing)
Analytics:  pandas-ta (Technical indicators)
```

### Frontend
```
Language:   JavaScript (ES6+)
Framework:  React 18.2.0
UI:         Custom CSS (No framework)
Charts:     Plotly.js + react-plotly.js
Real-time:  socket.io-client (WebSocket)
Build:      react-scripts (Create React App)
```

### Infrastructure
```
Database:     stock_analyzer.db (SQLite, ~120MB)
Web Server:   Flask Development Server (Port 5000)
App Server:   React Dev Server (Port 3000)
Deployment:   Shell script launcher (start.sh)
```

---

## 3. System Architecture

### 3.1 High-Level Architecture Diagram

```mermaid
graph TB
    subgraph Client["Client Layer"]
        Browser["Web Browser<br/>(Chrome/Firefox)"]
    end
    
    subgraph Frontend["Frontend Layer<br/>(React - Port 3000)"]
        UI["React Components"]
        Charts["Plotly Charts"]
        SocketClient["Socket.IO Client"]
    end
    
    subgraph Backend["Backend Layer<br/>(Flask - Port 5000)"]
        API["REST API Endpoints<br/>(14 Blueprints)"]
        WS["WebSocket Server<br/>(SocketIO)"]
        Services["Business Logic Services"]
        Scheduler["APScheduler<br/>(Background Jobs)"]
    end
    
    subgraph Data["Data Layer"]
        SQLite["SQLite Database<br/>(7 Tables)"]
        KiteAPI["Kite Connect API<br/>(External)"]
    end
    
    Browser <-->|HTTP/HTTPS| UI
    UI <-->|REST API| API
    UI <-->|WebSocket| WS
    SocketClient <-->|Real-time Updates| WS
    
    API --> Services
    Services --> SQLite
    Services --> KiteAPI
    Scheduler --> Services
    
    style Client fill:#e1f5ff
    style Frontend fill:#fff3e0
    style Backend fill:#f3e5f5
    style Data fill:#e8f5e9
```

### 3.2 Component Architecture

```mermaid
graph LR
    subgraph Frontend["Frontend Components"]
        App["App.js<br/>(Root)"]
        Heatmap["SectorHeatmap"]
        Analysis["Analysis"]
        Weinstein["WiensteinScoring"]
        Shortlist["Shortlist"]
        Charts["CandlestickChart"]
        DataDL["DataDownload"]
        Kite["KiteConnectionManager"]
    end
    
    subgraph Backend["Backend Routes"]
        MainRoute["main"]
        OHLCV["ohlcv"]
        AnalysisRoute["analysis"]
        WeinRoute["weinstein"]
        ShortRoute["shortlist"]
        TradesRoute["trades"]
        StocksRoute["stocks"]
    end
    
    App --> Heatmap
    App --> Analysis
    App --> Weinstein
    App --> Shortlist
    App --> Kite
    
    Heatmap --> OHLCV
    Analysis --> AnalysisRoute
    Weinstein --> WeinRoute
    Shortlist --> ShortRoute
    
    Charts --> OHLCV
    DataDL --> OHLCV
```

---

## 4. Data Flow

### 4.1 Data Download Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant KiteAPI
    participant Database
    
    User->>Frontend: Click "Download Data"
    Frontend->>Backend: POST /api/ohlcv/initialize
    Backend->>Database: Clear existing OHLCV data
    Backend->>Backend: Read symbols.csv (502 symbols)
    
    loop For each symbol
        Backend->>KiteAPI: Fetch 5 years daily data
        KiteAPI-->>Backend: Return OHLCV DataFrame
        Backend->>Database: Insert records (skip close=0)
        Backend->>Frontend: Emit progress via WebSocket
        Frontend->>User: Update progress bar
    end
    
    Backend-->>Frontend: Completion status
    Frontend->>User: Show success message
```

### 4.2 Weinstein Screening Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Database
    
    User->>Frontend: Navigate to Weinstein tab
    Frontend->>Backend: GET /api/weinstein/scores
    Backend->>Database: Fetch OHLCV data (all stocks)
    Backend->>Backend: Resample to weekly timeframe
    Backend->>Backend: Calculate MA30, RS, Stage
    Backend->>Backend: Apply 3 filters (Stage 2, Low Resistance, Not Overextended)
    Backend->>Backend: Score: 33.33 points per condition
    Backend-->>Frontend: Return scored stocks
    Frontend->>User: Display table with scores
```

### 4.3 Real-time Analysis Flow

```mermaid
sequenceDiagram
    participant User
    participant React
    participant SocketIO
    participant Flask
    participant Database
    
    User->>React: Load Analysis page
    React->>Flask: GET /api/analysis/data
    Flask->>Database: Query OHLCV + Calculate indicators
    Flask-->>React: Return analysis data
    React->>User: Render table
    
    User->>React: Click stock row
    React->>Flask: GET /api/analysis/chart/:symbol
    Flask->>Database: Fetch all historical data
    Flask->>Flask: Calculate RSI, MACD, EMAs
    Flask-->>React: Return chart data + indicators
    React->>User: Display Plotly candlestick chart
```

---

## 5. Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    Stock ||--o{ Transaction : has
    Stock ||--o{ WatchList : has
    Portfolio ||--o{ Transaction : contains
    
    Stock {
        int id PK
        string symbol UK
        string name
        string sector
        float current_price
        float market_cap
        datetime last_updated
    }
    
    OHLCV {
        int id PK
        string symbol
        datetime timestamp
        float open
        float high
        float low
        float close
        bigint volume
        constraint unique_symbol_timestamp
    }
    
    Portfolio {
        int id PK
        string name
        text description
        float total_value
        float cash_balance
        datetime created_at
    }
    
    Transaction {
        int id PK
        int portfolio_id FK
        int stock_id FK
        string transaction_type
        int quantity
        float price
        float total_amount
        datetime transaction_date
        text notes
    }
    
    WatchList {
        int id PK
        int stock_id FK
        float target_price
        text notes
        datetime added_at
    }
    
    ShortlistedStock {
        int id PK
        string symbol
        string name
        string sector
        datetime shortlisted_at
        float price_at_shortlist
        int score
        string stage
        float ma30
        float rs
        text notes
    }
    
    Trade {
        int id PK
        string symbol
        string trade_type
        int quantity
        float price
        datetime trade_date
        float brokerage
        float stt
        float exchange_charges
        float gst
        float sebi_charges
        float stamp_duty
        float total_charges
        text notes
    }
```

---

## 6. External Integrations

### 6.1 Kite Connect API

**Purpose**: Official Zerodha API for Indian stock market data

**Integration Points**:
- Authentication (OAuth 2.0 flow)
- Historical data fetching (OHLCV)
- Instrument token lookup
- Real-time quote retrieval

**Authentication Flow**:
```mermaid
sequenceDiagram
    User->>Frontend: Click "Connect Kite"
    Frontend->>Backend: GET /api/kite/auth/login
    Backend->>KiteAPI: Generate login URL
    Backend-->>Frontend: Return URL
    Frontend->>Browser: Redirect to Kite
    Browser->>KiteAPI: User logs in
    KiteAPI->>Backend: Callback with request_token
    Backend->>KiteAPI: Exchange for access_token
    KiteAPI-->>Backend: Return access_token
    Backend->>FileSystem: Save token to kite_token.json
    Backend-->>Frontend: Redirect with success
```

**Key Methods**:
```python
- kite.generate_session(request_token) → access_token
- kite.instruments(exchange="NSE") → List of instruments
- kite.historical_data(instrument_token, from_date, to_date, interval)
```

---

## 7. API Endpoints (Overview)

| Blueprint | Base Route | Purpose |
|-----------|-----------|---------|
| `main_bp` | `/` | Health check, status |
| `stocks_bp` | `/api/stocks` | Stock CRUD operations |
| `portfolios_bp` | `/api/portfolios` | Portfolio management |
| `transactions_bp` | `/api/transactions` | Transaction records |
| `watchlist_bp` | `/api/watchlist` | User watchlists |
| `ohlcv_bp` | `/api/ohlcv` | OHLCV data fetch/query |
| `nifty500_bp` | `/api/nifty500` | Nifty 500 stock list |
| `database_bp` | `/api/database` | Database operations |
| `analysis_bp` | `/api/analysis` | Technical analysis |
| `kite_auth_bp` | `/api/kite/auth` | Kite authentication |
| `weinstein_bp` | `/api/weinstein` | Weinstein screening |
| `shortlist_bp` | `/api/shortlist` | Shortlisted stocks |
| `trades_bp` | `/api/trades` | Trade management |

---

## 8. Deployment Architecture

### Current Setup (Development)

```mermaid
graph TB
    subgraph Machine["macOS Machine"]
        subgraph Project["Project Directory<br/>/stockAnalyzer-1"]
            StartScript["start.sh<br/>(Launcher)"]
            
            subgraph Backend["Backend<br/>(venv)"]
                AppPy["app.py<br/>Port 5000"]
                DB["stock_analyzer.db"]
            end
            
            subgraph Frontend["Frontend<br/>(node_modules)"]
                ReactApp["React App<br/>Port 3000"]
            end
        end
        
        Browser["Chrome Browser<br/>localhost:3000"]
    end
    
    StartScript --> Backend
    StartScript --> Frontend
    Frontend --> Browser
    Browser --> Backend
```

### Launch Process
```bash
./start.sh
├── 1. Check prerequisites (Python, npm)
├── 2. Create/activate Python venv
├── 3. Install backend dependencies
├── 4. Start Flask server (background)
├── 5. Install frontend dependencies
├── 6. Start React dev server (background)
└── 7. Open Chrome browser
```

### macOS App Bundle
```
Stock Analyzer.app/
└── Contents/
    ├── Info.plist        # App metadata
    ├── MacOS/
    │   └── launcher      # Opens Terminal + runs start.sh
    └── Resources/
        └── AppIcon.png   # Custom icon
```

---

## 9. Key Design Decisions

### 9.1 Why SQLite?
- ✅ Single-user application
- ✅ No separate database server needed
- ✅ Simple deployment
- ✅ Adequate for 500 stocks × 5 years = ~600K records
- ❌ Not suitable for multi-user or high concurrency

### 9.2 Why Flask + React (Not Next.js)?
- ✅ Clear separation of concerns
- ✅ Python ecosystem for financial calculations
- ✅ React for dynamic UI
- ❌ Requires two servers (more complex deployment)

### 9.3 Why WebSocket (SocketIO)?
- ✅ Real-time progress updates during data download
- ✅ Bi-directional communication
- ✅ Better UX for long-running operations

### 9.4 Why Weekly Resampling (Weinstein)?
- ✅ Reduces noise from daily fluctuations
- ✅ Aligns with Stan Weinstein's methodology
- ✅ Easier to identify long-term trends

---

## 10. Performance Considerations

### Data Volume
- **Stocks**: 502 (Nifty 500 + few more)
- **Historical Period**: 5 years
- **Daily Records**: ~1,260 trading days
- **Total OHLCV Records**: 502 × 1,260 = ~632,520 records
- **Database Size**: ~120 MB

### Optimization Strategies
1. **Indexing**: Symbol + Timestamp composite index
2. **Batch Inserts**: Commit every stock (not every row)
3. **Skip Invalid Data**: Close price = 0 → skip
4. **Lazy Loading**: Charts load only when clicked
5. **Caching**: Instruments cached in KiteClient

---

## 11. Security Considerations

> [!WARNING]
> **Hardcoded Credentials**: `config.py` contains Kite API keys. Move to environment variables in production.

```python
# config.py (Current - Insecure)
KITE_API_KEY = 'iyi9a2huwplqqzvg'
KITE_API_SECRET = 'zd5b9dc6shmnwxjuquydj0rgjalkp526'

# Recommended (Production)
KITE_API_KEY = os.environ.get('KITE_API_KEY')
KITE_API_SECRET = os.environ.get('KITE_API_SECRET')
```

### Access Token Storage
- Stored in `kite_token.json` (plain text)
- ⚠️ File permissions should be `600` (owner read/write only)

### CORS
- Currently allows `origins: "*"` (all origins)
- 🔒 Restrict to specific domains in production

---

## 12. Scalability & Future Enhancements

### Current Limitations
- ❌ Single-user only (SQLite)
- ❌ No user authentication
- ❌ No data backup/restore
- ❌ Manual data refresh required

### Potential Improvements
1. **Multi-user Support**: Migrate to PostgreSQL, add user auth
2. **Automated Data Refresh**: Scheduled downloads (daily/weekly)
3. **Cloud Deployment**: Deploy to AWS/GCP/Heroku
4. **Mobile App**: React Native wrapper
5. **Backtesting**: Test strategies on historical data
6. **Alerts**: Email/SMS notifications for shortlisted stocks
7. **Export**: PDF reports, Excel exports

---

## 13. Technology Dependencies

### Backend Dependencies
```
flask                  # Web framework
flask-cors            # CORS handling
flask-sqlalchemy      # ORM
sqlalchemy            # Database abstraction
yfinance              # Fallback data source
APScheduler           # Background jobs
pandas                # Data manipulation
pandas-ta             # Technical analysis
flask-socketio        # WebSocket support
python-socketio       # SocketIO implementation
kiteconnect           # Official Kite API client
pyopenssl             # SSL/TLS support
openpyxl              # Excel export
```

### Frontend Dependencies
```
react                 # UI library
react-dom             # React renderer
plotly.js             # Charting library
react-plotly.js       # React wrapper for Plotly
socket.io-client      # WebSocket client
react-scripts         # Build tooling
```

---

## 14. Glossary

| Term | Definition |
|------|------------|
| **OHLCV** | Open, High, Low, Close, Volume - standard candlestick data |
| **Weinstein Stage Analysis** | Technical analysis method identifying 4 market stages |
| **Stage 2** | Bullish/advancing phase in Weinstein methodology |
| **RSI** | Relative Strength Index (momentum indicator) |
| **MACD** | Moving Average Convergence Divergence |
| **EMA** | Exponential Moving Average |
| **Nifty 500** | Stock index of top 500 companies on NSE |
| **Kite Connect** | Zerodha's official trading API |

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Author**: Stock Analyzer Development Team
