# Stock Analyzer - Low-Level Design (LLD)

## 1. Backend Architecture

### 1.1 Directory Structure

```
backend/
├── app.py                      # Application entry point
├── config.py                   # Configuration (DB, API keys)
├── extensions.py               # Shared extensions (db, socketio, cors)
├── models.py                   # SQLAlchemy models (7 models)
├── routes/                     # API blueprints (14 files)
│   ├── main.py
│   ├── stocks.py
│   ├── portfolios.py
│   ├── transactions.py
│   ├── watchlist.py
│   ├── ohlcv.py
│   ├── nifty500.py
│   ├── database.py
│   ├── analysis.py
│   ├── kite_auth.py
│   ├── weinstein.py
│   ├── shortlist.py
│   └── trades.py
├── services/                   # Business logic (7 files)
│   ├── data_fetcher.py        # 5-year data download
│   ├── kite_client.py         # Kite API wrapper (Singleton)
│   ├── weinstein_screening.py # Weinstein algorithm
│   ├── brokerage_calculator.py
│   ├── scheduler.py
│   └── symbols.csv            # Stock symbols list
├── stock_analyzer.db          # SQLite database (~120MB)
└── requirements.txt           # Python dependencies
```

---

## 2. Database Models (models.py)

### 2.1 Stock Model

**Purpose**: Store basic stock information

```python
class Stock(db.Model):
    __tablename__ = 'stocks'
    
    # Primary Key
    id: Integer (PK, Auto-increment)
    
    # Fields
    symbol: String(10) UNIQUE NOT NULL  # e.g., "RELIANCE.NS"
    name: String(100) NOT NULL          # e.g., "Reliance Industries"
    sector: String(50)                  # e.g., "Energy"
    current_price: Float
    market_cap: Float
    last_updated: DateTime (Auto UTC)
    
    # Relationships
    transactions: One-to-Many → Transaction
    watchlists: One-to-Many → WatchList
```

**Methods**:
- `to_dict()` → Serializes model to JSON

---

### 2.2 OHLCV Model

**Purpose**: Store historical candlestick data

```python
class OHLCV(db.Model):
    __tablename__ = 'ohlcv_data'
    
    # Primary Key
    id: Integer (PK)
    
    # Fields
    symbol: String(20) NOT NULL INDEX
    timestamp: DateTime NOT NULL INDEX
    open: Float NOT NULL
    high: Float NOT NULL
    low: Float NOT NULL
    close: Float NOT NULL
    volume: BigInteger NOT NULL
    last_updated: DateTime
    
    # Constraints
    UNIQUE(symbol, timestamp)  # Composite unique constraint
```

**Indexes**:
- `symbol` - For fast symbol-based queries
- `timestamp` - For date range queries
- Composite `(symbol, timestamp)` - Prevents duplicates

**Data Volume**: ~632,520 records (502 stocks × ~1,260 days × 5 years)

---

### 2.3 Portfolio Model

```python
class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    
    id: Integer (PK)
    name: String(100) NOT NULL
    description: Text
    total_value: Float DEFAULT 0.0
    cash_balance: Float DEFAULT 0.0
    created_at: DateTime
    
    # Relationships
    transactions: One-to-Many → Transaction (CASCADE DELETE)
```

---

### 2.4 Transaction Model

```python
class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id: Integer (PK)
    portfolio_id: Integer FK → portfolios.id
    stock_id: Integer FK → stocks.id
    transaction_type: String(10)  # 'BUY' or 'SELL'
    quantity: Integer NOT NULL
    price: Float NOT NULL
    total_amount: Float NOT NULL   # Computed: quantity × price
    transaction_date: DateTime
    notes: Text
```

---

### 2.5 WatchList Model

```python
class WatchList(db.Model):
    __tablename__ = 'watchlists'
    
    id: Integer (PK)
    stock_id: Integer FK → stocks.id
    target_price: Float
    notes: Text
    added_at: DateTime
```

---

### 2.6 ShortlistedStock Model

**Purpose**: Store results from Weinstein screening

```python
class ShortlistedStock(db.Model):
    __tablename__ = 'shortlisted_stocks'
    
    id: Integer (PK)
    symbol: String(20) NOT NULL
    name: String(100)
    sector: String(50)
    shortlisted_at: DateTime         # When it was shortlisted
    price_at_shortlist: Float
    score: Integer                   # 0-100 (Weinstein score)
    stage: String(20)                # e.g., "Stage 2"
    ma30: Float                      # 30-week Moving Average
    rs: Float                        # Relative Strength
    notes: Text
```

---

### 2.7 Trade Model

**Purpose**: Track trades with Indian brokerage calculations

```python
class Trade(db.Model):
    __tablename__ = 'trades'
    
    id: Integer (PK)
    symbol: String(20) NOT NULL INDEX
    trade_type: String(10)  # 'BUY' or 'SELL'
    quantity: Integer NOT NULL
    price: Float NOT NULL
    trade_date: DateTime INDEX
    
    # Indian Market Charges
    brokerage: Float DEFAULT 0.0
    stt: Float DEFAULT 0.0              # Securities Transaction Tax
    exchange_charges: Float DEFAULT 0.0
    gst: Float DEFAULT 0.0              # 18% on brokerage + exchange charges
    sebi_charges: Float DEFAULT 0.0
    stamp_duty: Float DEFAULT 0.0       # 0.015% on buy side
    total_charges: Float DEFAULT 0.0    # Sum of all charges
    
    notes: Text
    created_at: DateTime
```

**Charge Calculation** (handled by `brokerage_calculator.py`):
```python
# Example for ₹100,000 trade (BUY)
Brokerage:        ₹20 (₹20 or 0.03%, whichever is lower)
STT:              ₹100 (0.1% on buy/sell)
Exchange Charges: ₹19.50 (0.0325% NSE)
GST:              ₹7.11 (18% on brokerage + exchange)
SEBI Charges:     ₹1
Stamp Duty:       ₹15 (0.015% on buy)
─────────────────
Total:            ₹162.61
```

---

## 3. API Routes

### 3.1 OHLCV Routes (`routes/ohlcv.py`)

#### **GET** `/api/ohlcv/data`
Get OHLCV data with filters

**Query Parameters**:
```
symbol: string (e.g., "RELIANCE.NS")
start_date: ISO date (e.g., "2023-01-01")
end_date: ISO date
limit: integer (default: 100)
```

**Response**:
```json
{
  "data": [
    {
      "id": 1,
      "symbol": "RELIANCE.NS",
      "timestamp": "2023-01-02T00:00:00",
      "open": 2650.0,
      "high": 2680.0,
      "low": 2640.0,
      "close": 2675.0,
      "volume": 5234567
    }
  ],
  "count": 100
}
```

---

#### **GET** `/api/ohlcv/latest`
Get latest OHLCV for all or specific symbol

**Query Parameters**:
```
symbol: string (optional)
```

**Response**:
```json
{
  "RELIANCE.NS": {
    "close": 2675.0,
    "timestamp": "2023-12-11T00:00:00",
    "volume": 5234567
  }
}
```

---

#### **POST** `/api/ohlcv/initialize`
Trigger 5-year data download for all stocks

**Request Body**: None

**Process**:
1. Clear existing OHLCV data
2. Read `services/symbols.csv` (502 symbols)
3. For each symbol:
   - Fetch 5 years daily data from Kite API
   - Skip records where `close = 0` (market closed)
   - Insert into database
   - Emit progress via WebSocket
4. Return completion status

**WebSocket Events Emitted**:
```javascript
'refresh_progress': {
  current: 245,
  total: 502,
  progress: 48,
  symbol: "TATAMOTORS.NS",
  records_added: 308750,
  status: "processing"
}
```

---

#### **GET** `/api/ohlcv/sector-heatmap`
Get sector-wise performance data

**Query Parameters**:
```
start_date: ISO date (optional)
end_date: ISO date (optional)
duration: string (1d|1w|1m|3m|6m|1y|ytd|custom)
```

**Algorithm**:
```python
1. Group stocks by sector
2. For each sector:
   - Get latest close price
   - Get price at start_date
   - Calculate % change: ((latest - start) / start) * 100
   - Calculate avg volume (20-day)
   - Calculate market cap sum
3. For each stock in sector:
   - Calculate individual % change
   - Sort by % change (descending)
   - Take top 10 movers
4. Return sector + stock data
```

**Response**:
```json
{
  "sectors": [
    {
      "name": "Energy",
      "change_percent": 12.5,
      "avg_volume": 125000000,
      "market_cap": 1500000000000,
      "stocks": [
        {
          "symbol": "RELIANCE.NS",
          "name": "Reliance Industries",
          "change_percent": 15.2,
          "current_price": 2675.0,
          "volume": 5234567
        }
      ]
    }
  ]
}
```

---

### 3.2 Analysis Routes (`routes/analysis.py`)

#### **GET** `/api/analysis/data`
Get technical analysis for all Nifty 500 stocks

**Algorithm**:
```python
1. Fetch all Nifty 500 symbols
2. For each symbol:
   - Get last 200 days OHLCV data
   - Calculate indicators:
     * RSI (14-period)
     * MACD (12, 26, 9)
     * EMA 21, 44, 200
   - Compute score (100-point scale):
     * RSI 30-70: +25 points
     * MACD Bullish: +25 points
     * EMA 21 > EMA 44: +25 points
     * Price > EMA 200: +25 points
3. Return sorted by score (descending)
```

**Response**:
```json
{
  "analysis_data": [
    {
      "symbol": "RELIANCE.NS",
      "name": "Reliance Industries",
      "sector": "Energy",
      "current_price": 2675.0,
      "rsi": 62.5,
      "macd_signal": "Bullish",
      "ema_crossover_21_44": "Yes",
      "price_above_ema_200": "Yes",
      "score": 100
    }
  ]
}
```

---

#### **GET** `/api/analysis/chart/<symbol>`
Get detailed chart data with indicators for a specific stock

**URL Parameters**:
```
symbol: string (e.g., "RELIANCE.NS")
```

**Algorithm**:
```python
1. Fetch ALL historical OHLCV data for symbol
2. Calculate technical indicators:
   - EMA: 21, 44, 200
   - RSI: 14-period
   - MACD: 12/26/9
   - MACD Histogram
3. Format for Plotly candlestick chart
4. Return all data
```

**Response**:
```json
{
  "symbol": "RELIANCE.NS",
  "data": [
    {
      "timestamp": "2023-01-02",
      "open": 2650.0,
      "high": 2680.0,
      "low": 2640.0,
      "close": 2675.0,
      "volume": 5234567,
      "ema_21": 2660.5,
      "ema_44": 2655.0,
      "ema_200": 2620.0,
      "rsi": 62.5,
      "macd": 12.5,
      "macd_signal": 10.2,
      "macd_histogram": 2.3
    }
  ]
}
```

---

### 3.3 Weinstein Routes (`routes/weinstein.py`)

#### **GET** `/api/weinstein/scores`
Get Weinstein scores for all stocks

**Algorithm** (implemented in `services/weinstein_screening.py`):

**Step 1: Daily to Weekly Conversion**
```python
def resample_to_weekly(df):
    """Convert daily OHLCV to weekly"""
    weekly = df.resample('W-FRI', on='timestamp').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    return weekly
```

**Step 2: Calculate Indicators**
```python
def compute_indicators(df, index_df):
    # 30-week Simple Moving Average
    df['ma30'] = df['close'].rolling(window=30).mean()
    
    # Relative Strength (vs NIFTY 50)
    df['stock_pct_change'] = df['close'].pct_change()
    df['index_pct_change'] = index_df['close'].pct_change()
    df['rs'] = (1 + df['stock_pct_change']) / (1 + df['index_pct_change'])
    df['rs'] = df['rs'].rolling(window=52).mean()
    
    # Stage determination
    df['stage'] = 'Unknown'
    df.loc[(df['close'] > df['ma30']) & (df['ma30'] > df['ma30'].shift(1)), 'stage'] = 'Stage 2'
    df.loc[(df['close'] < df['ma30']) & (df['ma30'] < df['ma30'].shift(1)), 'stage'] = 'Stage 4'
    
    return df
```

**Step 3: Apply Filters**
```python
def apply_filters(df):
    """Apply 3 Weinstein conditions"""
    latest_week = df.iloc[-1]
    
    # Condition 1: Stage 2 (Bullish trend)
    condition_1 = latest_week['stage'] == 'Stage 2'
    
    # Condition 2: Low resistance (close near high)
    resistance_percent = (latest_week['high'] - latest_week['close']) / latest_week['close'] * 100
    condition_2 = resistance_percent < 5  # Within 5% of high
    
    # Condition 3: Not overextended (not far above MA30)
    extension_percent = (latest_week['close'] - latest_week['ma30']) / latest_week['ma30'] * 100
    condition_3 = extension_percent < 20  # Not more than 20% above MA30
    
    # Scoring: 33.33 points per condition
    score = 0
    if condition_1: score += 33.33
    if condition_2: score += 33.33
    if condition_3: score += 33.34  # Total = 100
    
    return score
```

**Response**:
```json
{
  "scores": [
    {
      "symbol": "TATAMOTORS.NS",
      "name": "Tata Motors",
      "sector": "Automobiles",
      "score": 100,
      "stage": "Stage 2",
      "ma30": 650.5,
      "rs": 1.25,
      "current_price": 675.0,
      "condition_stage2": true,
      "condition_low_resistance": true,
      "condition_not_overextended": true
    }
  ],
  "shortlist": ["TATAMOTORS.NS", "RELIANCE.NS"]
}
```

---

#### **POST** `/api/weinstein/shortlist`
Add stock to shortlist

**Request Body**:
```json
{
  "symbol": "TATAMOTORS.NS"
}
```

**Process**:
1. Fetch current Weinstein score for symbol
2. Create ShortlistedStock record with current data
3. Return success

---

### 3.4 Kite Auth Routes (`routes/kite_auth.py`)

#### **GET** `/api/kite/auth/login`
Get Kite login URL

**Response**:
```json
{
  "login_url": "https://kite.zerodha.com/connect/login?api_key=..."
}
```

---

#### **GET** `/api/kite/auth/callback`
OAuth callback endpoint

**Query Parameters**:
```
request_token: string (from Kite)
status: success|error
```

**Process**:
1. Exchange request_token for access_token
2. Save access_token to `kite_token.json`
3. Redirect to frontend with status

---

#### **GET** `/api/kite/auth/status`
Check connection status

**Response**:
```json
{
  "connected": true,
  "token_file_exists": true,
  "error": null
}
```

---

### 3.5 Trades Routes (`routes/trades.py`)

#### **POST** `/api/trades`
Create new trade with brokerage calculation

**Request Body**:
```json
{
  "symbol": "RELIANCE.NS",
  "trade_type": "BUY",
  "quantity": 100,
  "price": 2675.0,
  "trade_date": "2023-12-11T10:30:00"
}
```

**Process**:
```python
1. Calculate total value = quantity × price
2. Call brokerage_calculator.calculate_charges(total_value, trade_type)
3. Create Trade record with all charges
4. Return trade with breakdown
```

**Response**:
```json
{
  "id": 1,
  "symbol": "RELIANCE.NS",
  "trade_type": "BUY",
  "quantity": 100,
  "price": 2675.0,
  "total_value": 267500.0,
  "charges": {
    "brokerage": 20.0,
    "stt": 267.5,
    "exchange_charges": 86.94,
    "gst": 19.25,
    "sebi_charges": 2.68,
    "stamp_duty": 40.13,
    "total_charges": 436.50
  },
  "net_amount": 267936.50
}
```

---

## 4. Services Layer

### 4.1 KiteClient (`services/kite_client.py`)

**Design Pattern**: Singleton

```python
class KiteClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self):
        """Initialize KiteConnect with API key"""
        self.kite = KiteConnect(api_key=Config.KITE_API_KEY)
        self.access_token = self._load_token()
        if self.access_token:
            self.kite.set_access_token(self.access_token)
```

**Key Methods**:

```python
def get_login_url(self) → str:
    """Generate Kite login URL"""
    return self.kite.login_url()

def generate_session(self, request_token) → dict:
    """
    Exchange request token for access token
    Returns: {access_token, user_id, user_name}
    """
    data = self.kite.generate_session(
        request_token, 
        api_secret=Config.KITE_API_SECRET
    )
    self.access_token = data['access_token']
    self._save_token()
    return data

def fetch_historical_data(self, symbol, from_date, to_date, interval='day') → DataFrame:
    """
    Fetch historical OHLCV data
    
    Args:
        symbol: Trading symbol (e.g., "RELIANCE")
        from_date: datetime
        to_date: datetime
        interval: 'minute', 'day', '5minute', '15minute', etc.
    
    Returns:
        pandas DataFrame with columns:
        [timestamp, open, high, low, close, volume]
    """
    instrument_token = self.get_instrument_token(symbol)
    records = self.kite.historical_data(
        instrument_token,
        from_date,
        to_date,
        interval
    )
    return pd.DataFrame(records)

def get_instrument_token(self, symbol) → int:
    """
    Get instrument token for symbol
    Uses cached instruments list
    """
    if not self.instruments_cache:
        self.fetch_instruments()
    
    # Match symbol (case-insensitive)
    matches = self.instruments_cache[
        self.instruments_cache['tradingsymbol'].str.upper() == symbol.upper()
    ]
    
    if matches.empty:
        raise ValueError(f"Symbol {symbol} not found")
    
    return matches.iloc[0]['instrument_token']
```

**Token Storage**:
```json
// kite_token.json
{
  "access_token": "abc123xyz...",
  "user_id": "XX1234",
  "saved_at": "2023-12-11T10:30:00"
}
```

---

### 4.2 Data Fetcher (`services/data_fetcher.py`)

**Main Function**: `download_5year_data()`

```python
def download_5year_data():
    """
    Download 5 years of daily OHLCV data for all stocks.
    Reads from services/symbols.csv
    """
    # 1. Read symbols from CSV
    symbols = []
    with open('services/symbols.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row['Symbol'].strip()
            if not symbol.endswith('.NS'):
                symbol = f"{symbol}.NS"
            symbols.append(symbol)
    
    # Remove duplicates
    symbols = list(dict.fromkeys(symbols))
    total = len(symbols)
    
    # 2. Clear existing data
    OHLCV.query.delete()
    db.session.commit()
    
    # 3. Download 5 years
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5*365)
    
    success_count = 0
    total_records = 0
    
    for idx, symbol in enumerate(symbols, 1):
        try:
            # Fetch from Kite
            kite_symbol = symbol.replace('.NS', '')
            df = kite_client.fetch_historical_data(
                kite_symbol, from_date, to_date, interval='day'
            )
            
            # Insert records
            for _, row in df.iterrows():
                if float(row['close']) == 0:
                    continue  # Skip market-closed days
                
                ohlcv = OHLCV(
                    symbol=symbol,
                    timestamp=row['timestamp'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume'])
                )
                db.session.add(ohlcv)
            
            db.session.commit()
            success_count += 1
            
            # Emit progress
            socketio.emit('refresh_progress', {
                'current': idx,
                'total': total,
                'progress': int((idx / total) * 100),
                'symbol': symbol,
                'status': 'processing'
            })
            
        except Exception as e:
            logger.error(f"Error for {symbol}: {e}")
            db.session.rollback()
    
    # Final status
    socketio.emit('refresh_progress', {
        'status': 'completed',
        'message': f'{success_count}/{total} stocks processed'
    })
```

---

### 4.3 Brokerage Calculator (`services/brokerage_calculator.py`)

```python
def calculate_charges(total_value, trade_type='BUY'):
    """
    Calculate Indian stock market charges
    
    Args:
        total_value: Total trade value (quantity × price)
        trade_type: 'BUY' or 'SELL'
    
    Returns:
        dict with breakdown
    """
    # Brokerage: ₹20 or 0.03%, whichever is lower
    brokerage = min(20, total_value * 0.0003)
    
    # STT: 0.1% on buy/sell
    stt = total_value * 0.001
    
    # Exchange Charges: 0.0325% (NSE)
    exchange_charges = total_value * 0.000325
    
    # GST: 18% on (brokerage + exchange charges)
    gst = (brokerage + exchange_charges) * 0.18
    
    # SEBI Charges: ₹10 per crore
    sebi_charges = (total_value / 10000000) * 10
    
    # Stamp Duty: 0.015% on buy side only
    stamp_duty = 0
    if trade_type == 'BUY':
        stamp_duty = total_value * 0.00015
    
    # Total
    total_charges = (
        brokerage + stt + exchange_charges + 
        gst + sebi_charges + stamp_duty
    )
    
    return {
        'brokerage': round(brokerage, 2),
        'stt': round(stt, 2),
        'exchange_charges': round(exchange_charges, 2),
        'gst': round(gst, 2),
        'sebi_charges': round(sebi_charges, 2),
        'stamp_duty': round(stamp_duty, 2),
        'total_charges': round(total_charges, 2)
    }
```

---

## 5. Frontend Architecture

### 5.1 Component Hierarchy

```
App.js (Root)
├── Header
│   ├── Title
│   └── KiteConnectionManager
├── Tabs Navigation
└── Main Content (Tab-based)
    ├── SectorHeatmap
    │   ├── DataDownload (Popup)
    │   ├── InitializationProgress (Popup)
    │   └── Heatmap Grid
    ├── Analysis
    │   ├── Analysis Table
    │   └── CandlestickChart (Conditional)
    ├── WiensteinScoring
    │   └── Scoring Table
    └── Shortlist
        └── Shortlist Table
```

---

### 5.2 Component Details

#### **App.js**

**State Management**:
```javascript
const [activeTab, setActiveTab] = useState('heatmap');
const [connectionStatus, setConnectionStatus] = useState({
  connected: false,
  checking: true,
  error: null
});
```

**Kite Auth Callback Handling**:
```javascript
useEffect(() => {
  const urlParams = new URLSearchParams(window.location.search);
  const kiteAuth = urlParams.get('kite_auth');
  
  if (kiteAuth === 'success') {
    // Trigger connection status refresh
    kiteManagerRef.current?.refreshStatus();
  }
}, []);
```

---

#### **SectorHeatmap.js**

**State**:
```javascript
const [sectors, setSectors] = useState([]);
const [expandedSector, setExpandedSector] = useState(null);
const [duration, setDuration] = useState('1w');
const [customDates, setCustomDates] = useState({
  start: '',
  end: ''
});
```

**Data Fetching**:
```javascript
const fetchHeatmapData = async (filterParams = {}) => {
  const params = new URLSearchParams({
    duration: filterParams.duration || duration,
    ...filterParams
  });
  
  const response = await fetch(`/api/ohlcv/sector-heatmap?${params}`);
  const data = await response.json();
  setSectors(data.sectors);
};
```

**Color Coding Algorithm**:
```javascript
const getColorForChange = (change) => {
  if (change >= 5) return '#006400';    // Dark Green
  if (change >= 2) return '#228B22';    // Green
  if (change >= 0) return '#90EE90';    // Light Green
  if (change >= -2) return '#FFB6C6';   // Light Red
  if (change >= -5) return '#FF6B6B';   // Red
  return '#8B0000';                     // Dark Red
};
```

---

#### **Analysis.js**

**Data Processing**:
```javascript
const loadAnalysisData = async () => {
  const data = await fetchAnalysisData();
  
  // Backend provides scores, no client calculation needed
  const sorted = data.analysis_data.sort((a, b) => 
    (b.score || 0) - (a.score || 0)
  );
  
  setFilteredData(sorted);
};
```

**Sorting**:
```javascript
const handleSort = (key) => {
  let direction = 'asc';
  if (sortConfig.key === key && sortConfig.direction === 'asc') {
    direction = 'desc';
  }
  
  const sorted = [...filteredData].sort((a, b) => {
    const aVal = a[key];
    const bVal = b[key];
    
    if (aVal === null) return 1;
    if (bVal === null) return -1;
    
    if (aVal < bVal) return direction === 'asc' ? -1 : 1;
    if (aVal > bVal) return direction === 'asc' ? 1 : -1;
    return 0;
  });
  
  setFilteredData(sorted);
  setSortConfig({ key, direction });
};
```

---

#### **CandlestickChart.js**

**Plotly Configuration**:
```javascript
const chartData = [
  // Candlestick trace
  {
    type: 'candlestick',
    x: data.map(d => d.timestamp),
    open: data.map(d => d.open),
    high: data.map(d => d.high),
    low: data.map(d => d.low),
    close: data.map(d => d.close),
    name: 'OHLC'
  },
  // EMA 21 trace
  {
    type: 'scatter',
    x: data.map(d => d.timestamp),
    y: data.map(d => d.ema_21),
    line: { color: 'blue', width: 1 },
    name: 'EMA 21'
  },
  // EMA 44 trace
  {
    type: 'scatter',
    x: data.map(d => d.timestamp),
    y: data.map(d => d.ema_44),
    line: { color: 'orange', width: 1 },
    name: 'EMA 44'
  },
  // EMA 200 trace
  {
    type: 'scatter',
    x: data.map(d => d.timestamp),
    y: data.map(d => d.ema_200),
    line: { color: 'red', width: 2 },
    name: 'EMA 200'
  }
];

const layout = {
  title: `${name} (${symbol})`,
  xaxis: { title: 'Date', rangeslider: { visible: false } },
  yaxis: { title: 'Price (₹)' },
  height: 600
};
```

**Subplots for Indicators**:
```javascript
// RSI Subplot (0-100 range)
{
  type: 'scatter',
  x: data.map(d => d.timestamp),
  y: data.map(d => d.rsi),
  yaxis: 'y2',
  line: { color: 'purple' },
  name: 'RSI'
}

// Layout with secondary Y-axis
layout.yaxis2 = {
  title: 'RSI',
  domain: [0, 0.2],  // Bottom 20% of chart
  range: [0, 100]
};
layout.shapes = [
  { type: 'line', y0: 30, y1: 30, x0: 0, x1: 1, yref: 'y2', line: { dash: 'dot', color: 'green' } },
  { type: 'line', y0: 70, y1: 70, x0: 0, x1: 1, yref: 'y2', line: { dash: 'dot', color: 'red' } }
];
```

---

#### **WiensteinScoring.js**

**Score Display**:
```javascript
const getScoreClass = (score) => {
  if (score === 100) return 'score-perfect';   // Green
  if (score >= 66) return 'score-good';        // Yellow
  if (score >= 33) return 'score-moderate';    // Orange
  return 'score-poor';                          // Red
};
```

---

#### **DataDownload.js**

**WebSocket Integration**:
```javascript
useEffect(() => {
  const socket = io();
  
  socket.on('refresh_progress', (data) => {
    setProgress(data.progress);
    setCurrentSymbol(data.symbol);
    setTotalRecords(data.records_added);
    
    if (data.status === 'completed') {
      setIsDownloading(false);
      onComplete?.();
    }
  });
  
  return () => socket.disconnect();
}, []);
```

---

## 6. Key Algorithms

### 6.1 RSI Calculation

```python
def calculate_rsi(prices, period=14):
    """
    Relative Strength Index
    
    Formula:
    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss
    """
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi
```

### 6.2 MACD Calculation

```python
def calculate_macd(prices, fast=12, slow=26, signal=9):
    """
    Moving Average Convergence Divergence
    
    MACD Line = EMA(12) - EMA(26)
    Signal Line = EMA(9) of MACD Line
    Histogram = MACD Line - Signal Line
    """
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }
```

### 6.3 EMA Calculation

```python
def calculate_ema(prices, period):
    """
    Exponential Moving Average
    
    EMA today = (Price today × multiplier) + (EMA yesterday × (1 - multiplier))
    where multiplier = 2 / (period + 1)
    """
    return prices.ewm(span=period, adjust=False).mean()
```

---

## 7. Database Queries (Optimization)

### 7.1 Efficient OHLCV Retrieval

```python
# Bad: Load all then filter in Python
all_data = OHLCV.query.all()
filtered = [d for d in all_data if d.symbol == 'RELIANCE.NS']

# Good: Filter at database level
filtered = OHLCV.query.filter_by(symbol='RELIANCE.NS')\\
    .filter(OHLCV.timestamp >= start_date)\\
    .filter(OHLCV.timestamp <= end_date)\\
    .order_by(OHLCV.timestamp.asc())\\
    .limit(200)\\
    .all()
```

### 7.2 Batch Inserts

```python
# Bad: Insert one by one (slow for 1260 records)
for row in df.iterrows():
    ohlcv = OHLCV(...)
    db.session.add(ohlcv)
    db.session.commit()  # SLOW!

# Good: Batch insert
for row in df.iterrows():
    ohlcv = OHLCV(...)
    db.session.add(ohlcv)
db.session.commit()  # Commit once at end
```

### 7.3 Aggregations

```python
# Get latest close price for all stocks
latest_prices = db.session.query(
    OHLCV.symbol,
    func.max(OHLCV.timestamp).label('latest_date')
).group_by(OHLCV.symbol).subquery()

results = db.session.query(OHLCV)\\
    .join(latest_prices, and_(
        OHLCV.symbol == latest_prices.c.symbol,
        OHLCV.timestamp == latest_prices.c.latest_date
    )).all()
```

---

## 8. Error Handling

### 8.1 API Error Responses

```python
# Consistent error format
@app.errorhandler(Exception)
def handle_error(error):
    return jsonify({
        'error': str(error),
        'type': type(error).__name__
    }), 500

# Route-level try-catch
@ohlcv_bp.route('/api/ohlcv/initialize', methods=['POST'])
def trigger_initialize_all():
    try:
        # ... implementation
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return jsonify({'error': str(e)}), 500
```

### 8.2 Frontend Error Handling

```javascript
const fetchAnalysisData = async () => {
  try {
    const response = await fetch('/api/analysis/data');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    return data;
    
  } catch (error) {
    console.error('Error fetching analysis:', error);
    alert('Failed to load analysis data. Please try again.');
    return { analysis_data: [] };
  }
};
```

---

## 9. Testing Considerations

### 9.1 Unit Tests (Backend)

```python
# tests/test_weinstein.py
def test_stage_determination():
    df = pd.DataFrame({
        'close': [100, 105, 110],
        'ma30': [95, 98, 102]
    })
    
    result = weinstein_screening.determine_stage(df)
    assert result == 'Stage 2'

def test_brokerage_calculation():
    charges = brokerage_calculator.calculate_charges(100000, 'BUY')
    
    assert charges['brokerage'] == 20.0
    assert charges['stt'] == 100.0
    assert 'total_charges' in charges
```

### 9.2 Integration Tests

```python
# tests/test_api.py
def test_ohlcv_endpoint(client):
    response = client.get('/api/ohlcv/data?symbol=RELIANCE.NS&limit=10')
    
    assert response.status_code == 200
    data = response.get_json()
    assert 'data' in data
    assert len(data['data']) <= 10
```

---

## 10. Performance Benchmarks

### 10.1 Expected Performance Metrics

| Operation | Records | Time (Expected) |
|-----------|---------|-----------------|
| Download 5-year data (502 stocks) | 632K | 15-20 minutes |
| Weinstein screening (full) | 502 stocks | 5-10 seconds |
| Analysis calculation (Nifty 500) | 500 stocks | 3-5 seconds |
| Sector heatmap generation | 12 sectors | 1-2 seconds |
| Single stock chart load | ~1260 points | <1 second |

### 10.2 Bottlenecks

1. **Kite API Rate Limit**: Max 3 requests/second
2. **SQLite Write Lock**: Single writer at a time
3. **Weekly Resampling**: Requires sorting entire dataset

---

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Author**: Stock Analyzer Development Team
