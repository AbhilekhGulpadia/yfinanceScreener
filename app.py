import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

st.set_page_config(page_title="NIFTY 500 Downloader + Analysis (Yahoo Finance)", layout="wide")

# -----------------------------
# Indicators
# -----------------------------
def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def dema(series: pd.Series, span: int) -> pd.Series:
    e = ema(series, span)
    ee = ema(e, span)
    return 2*e - ee

def rsi_wilder(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0.0)

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

# -----------------------------
# Downloader helpers
# -----------------------------
def _ensure_single_symbol(symbol: str) -> str:
    if not symbol:
        return symbol
    parts = [p for chunk in str(symbol).split(",") for p in chunk.split() if p]
    return parts[0] if parts else str(symbol)

def _pick_best_column(columns, base: str, symbol: str):
    cols = list(columns)
    sym_key = (symbol or "").lower().replace(".", "_").replace("-", "_")
    priorities = [base, f"{base}_{sym_key}", f"{sym_key}_{base}"]
    for p in priorities:
        if p in cols:
            return p
    for c in cols:
        if c.endswith("_" + base):
            return c
    for c in cols:
        if base in c:
            return c
    return None

def _get_series(df: pd.DataFrame, base: str, symbol: str) -> pd.Series:
    best = _pick_best_column(df.columns, base, symbol)
    if best is not None:
        val = df[best]
        if isinstance(val, pd.DataFrame):
            return val.iloc[:, 0]
        return val
    options = [c for c in df.columns if (c != "date" and base in c)]
    if options:
        val = df[options[0]]
        if isinstance(val, pd.DataFrame):
            return val.iloc[:, 0]
        return val
    return pd.Series([np.nan]*len(df), index=df.index)

def _normalize_ohlcv_columns(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(symbol, axis=1, level=1, drop_level=True)
        except Exception:
            try:
                df = df.xs(symbol, axis=1, level=0, drop_level=True)
            except Exception:
                df.columns = ["_".join([str(x) for x in tup if x is not None]) for tup in df.columns]
    df = df.reset_index()
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    date_col = None
    for cand in ["date", "datetime", "index"]:
        if cand in df.columns:
            date_col = cand
            break
    if date_col is None:
        date_col = df.columns[0]
    df = df.rename(columns={date_col: "date"})
    if not np.issubdtype(df["date"].dtype, np.datetime64):
        df["date"] = pd.to_datetime(df["date"])

    out = pd.DataFrame({"symbol": [symbol]*len(df), "date": df["date"]})
    out["open"] = _get_series(df, "open", symbol).astype(float)
    out["high"] = _get_series(df, "high", symbol).astype(float)
    out["low"]  = _get_series(df, "low", symbol).astype(float)
    out["close"] = _get_series(df, "close", symbol).astype(float)
    adj = _get_series(df, "adj_close", symbol)
    if adj.isna().all():
        adj = out["close"]
    out["adj_close"] = adj.astype(float)
    vol = _get_series(df, "volume", symbol)
    out["volume"] = pd.to_numeric(vol, errors="coerce")
    out = out.sort_values(["symbol","date"]).reset_index(drop=True)
    return out[["symbol","date","open","high","low","close","adj_close","volume"]]

@st.cache_data(show_spinner=False)
def fetch_one(symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    symbol = _ensure_single_symbol(symbol)
    df = yf.download(symbol, start=start, end=end, interval=interval, progress=False, auto_adjust=False, group_by="column")
    if (df is None or df.empty) and interval not in ["1d","5d","1wk","1mo","3mo"]:
        df = yf.download(symbol, period="59d", interval=interval, progress=False, auto_adjust=False, group_by="column")
    return _normalize_ohlcv_columns(df, symbol)

def normalize_symbols(df: pd.DataFrame) -> pd.Series:
    for preferred in ["yfinance_symbol","symbol","ticker","Ticker","YF","yf"]:
        if preferred in df.columns:
            return df[preferred].astype(str).str.strip()
    return df.iloc[:,0].astype(str).str.strip()

# -----------------------------
# Analysis helpers
# -----------------------------
def last_cross_days(close: pd.Series, baseline: pd.Series) -> tuple[int, bool]:
    """
    Returns (days_since_cross, has_cross) where cross is bullish: close > baseline and previous <= baseline.
    If never crossed, returns (10**9, False).
    """
    cond = (close > baseline) & (close.shift(1) <= baseline.shift(1))
    # find last True
    idx = cond[::-1].idxmax() if cond.any() else None
    if idx is None or not cond.any():
        return 10**9, False
    # days since last true = number of rows after idx
    last_pos = cond.index.get_loc(idx)
    days_since = len(cond) - 1 - last_pos
    return int(days_since), True

def last_bullish_macd_days(macd_line: pd.Series, signal_line: pd.Series) -> tuple[int, bool]:
    cond = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    idx = cond[::-1].idxmax() if cond.any() else None
    if idx is None or not cond.any():
        return 10**9, False
    last_pos = cond.index.get_loc(idx)
    days_since = len(cond) - 1 - last_pos
    return int(days_since), True

def rank_symbols(ohlcv: pd.DataFrame) -> pd.DataFrame:
    # Work per symbol
    out_rows = []
    for sym, df in ohlcv.groupby("symbol"):
        df = df.sort_values("date").reset_index(drop=True)
        if len(df) < 50:
            continue  # skip too-short histories

        df["dema200"] = dema(df["close"], 200)
        df["rsi14"] = rsi_wilder(df["close"], 14)
        macd_line, signal_line, _ = macd(df["close"])

        d200_days, has200 = last_cross_days(df["close"], df["dema200"])
        macd_days, has_macd = last_bullish_macd_days(macd_line, signal_line)

        latest = df.iloc[-1]
        rsi_val = float(latest["rsi14"]) if pd.notna(latest["rsi14"]) else np.inf

        out_rows.append({
            "symbol": sym,
            "last_date": latest["date"],
            "close": float(latest["close"]),
            "rsi14": rsi_val,
            "has_200_dema_cross": has200,
            "days_since_200_dema_cross": d200_days,
            "has_macd_bull_cross": has_macd,
            "days_since_macd_bull_cross": macd_days,
        })

    rankdf = pd.DataFrame(out_rows)
    if rankdf.empty:
        return rankdf

    # Sort by strict priority:
    # 200 DEMA cross (has desc, days asc) >
    # MACD recent cross (has desc, days asc) >
    # RSI low (asc)
    rankdf = rankdf.sort_values(
        by=[
            "has_200_dema_cross", "days_since_200_dema_cross",
            "has_macd_bull_cross", "days_since_macd_bull_cross",
            "rsi14"
        ],
        ascending=[False, True, False, True, True]
    ).reset_index(drop=True)

    # Provide a simple "rank" number
    rankdf.insert(0, "rank", range(1, len(rankdf)+1))
    return rankdf

# -----------------------------
# UI
# -----------------------------
st.title("NIFTY 500 OHLCV Downloader + Analysis (Yahoo Finance)")

tab_dl, tab_an = st.tabs(["📥 Downloader", "📊 Analysis"])

with tab_dl:
    with st.sidebar:
        st.header("Download Inputs")
        uploaded = st.file_uploader("Upload CSV of yfinance symbols", type=["csv"], help="Use nifty500_yfinance_symbols.csv with a yfinance_symbol column.")
        default_start = datetime.now() - timedelta(days=365)
        start_date = st.date_input("Start date", value=default_start.date(), key="dl_start")
        end_date = st.date_input("End date", value=datetime.now().date(), key="dl_end")
        interval = st.selectbox("Interval", ["1d","1wk","1mo","1h","30m","15m","5m","1m"], index=0, key="dl_interval")
        run = st.button("Download All", key="dl_run")

    if run:
        if not uploaded:
            st.error("Please upload a CSV of yfinance symbols first.")
        else:
            syms_df = pd.read_csv(uploaded)
            # Normalize symbols
            def normalize_symbols(df: pd.DataFrame) -> pd.Series:
                for preferred in ["yfinance_symbol","symbol","ticker","Ticker","YF","yf"]:
                    if preferred in df.columns:
                        return df[preferred].astype(str).str.strip()
                return df.iloc[:,0].astype(str).str.strip()

            symbols = normalize_symbols(syms_df).dropna()
            symbols = symbols.apply(lambda s: s if "." in s or "^" in s else s + ".NS")
            symbols = symbols[symbols.str.len() > 0].drop_duplicates().tolist()

            if len(symbols) == 0:
                st.error("No symbols found in the uploaded CSV.")
            else:
                st.success(f"Loaded {len(symbols)} symbols.")
                progress = st.progress(0)
                status = st.empty()
                rows = []
                for i, sym in enumerate(symbols, start=1):
                    status.text(f"Fetching {sym} ({i}/{len(symbols)}) …")
                    try:
                        part = fetch_one(sym, str(start_date), str(end_date), interval)
                        if not part.empty:
                            rows.append(part)
                    except Exception as e:
                        st.warning(f"{sym}: {e}")
                    progress.progress(int(i * 100 / len(symbols)))
                status.text("Done.")
                if rows:
                    out = pd.concat(rows, ignore_index=True)
                    st.session_state["ohlcv"] = out  # save for Analysis tab
                    st.dataframe(out.tail(1000), use_container_width=True, height=400)
                    csv = out.to_csv(index=False).encode("utf-8")
                    st.download_button("Download Tidy CSV", data=csv, file_name=f"nifty500_ohlcv_tidy_{interval}.csv", mime="text/csv")
                    st.success("Saved to session for Analysis tab.")
                else:
                    st.error("No data downloaded. Try different dates/interval.")

with tab_an:
    st.subheader("Ranking — EMA Crossovers > MACD Bullish Cross (recent) > Low RSI")
    # Data source selection
    source = st.radio("Choose data source", ["Use data from Downloader tab (session)", "Upload a combined OHLCV CSV"], index=0)
    df_input = None
    if source == "Use data from Downloader tab (session)":
        df_input = st.session_state.get("ohlcv")
        if df_input is None:
            st.info("No session data found. Please run the Downloader first or upload a CSV below.")
    else:
        up_csv = st.file_uploader("Upload combined OHLCV CSV (columns: symbol,date,open,high,low,close,adj_close,volume)", type=["csv"], key="an_upload")
        if up_csv is not None:
            df_input = pd.read_csv(up_csv, parse_dates=["date"])

    if df_input is not None and not df_input.empty:
        # Light validation and typing
        need_cols = {"symbol","date","close"}
        if not need_cols.issubset(set(df_input.columns)):
            st.error("CSV is missing required columns. Needs at least: symbol, date, close.")
        else:
            df = df_input.copy()
            if not np.issubdtype(df["date"].dtype, np.datetime64):
                df["date"] = pd.to_datetime(df["date"])
            # Optional date filter
            col1, col2 = st.columns(2)
            with col1:
                min_date = pd.to_datetime(df["date"].min()).date()
                max_date = pd.to_datetime(df["date"].max()).date()
                start_f = st.date_input("Analysis start date", value=min_date, min_value=min_date, max_value=max_date, key="an_start")
            with col2:
                end_f = st.date_input("Analysis end date", value=max_date, min_value=min_date, max_value=max_date, key="an_end")

            filt = (df["date"] >= pd.to_datetime(start_f)) & (df["date"] <= pd.to_datetime(end_f))
            df = df.loc[filt].sort_values(["symbol","date"])

            with st.spinner("Computing indicators and ranking..."):
                ranking = rank_symbols(df)

            if ranking.empty:
                st.warning("No symbols qualified for ranking (not enough history or no crossovers in the window). Try widening the date range.")
            else:
                st.success(f"Ranked {len(ranking)} symbols.")
                st.dataframe(ranking.head(200), use_container_width=True, height=560)
                csv_rank = ranking.to_csv(index=False).encode("utf-8")
                st.download_button("Download Ranking CSV", data=csv_rank, file_name="analysis_ranking.csv", mime="text/csv")

            with st.expander("Ranking Logic (for reference)"):
                st.markdown("""
                        - **Priority 1:** Most recent **Price > 200 DEMA** bullish cross (presence first, then fewer days since cross).
                        - **Priority 2:** **MACD bullish cross** (presence, then recency; any recent cross ranks above none).
                        - **Priority 3:** **RSI(14)** — lower RSI ranks higher when all else equal.
                """)
    else:
        st.info("Upload/Download data to proceed with Analysis.")
