
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

def macd_lines(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
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
# Analysis helpers with controls
# -----------------------------
def compute_cross_flags(close: pd.Series, baseline: pd.Series, direction: str):
    if direction == "Bullish":
        crossed = (close > baseline) & (close.shift(1) <= baseline.shift(1))
    elif direction == "Bearish":
        crossed = (close < baseline) & (close.shift(1) >= baseline.shift(1))
    else:  # Both
        crossed = ((close > baseline) & (close.shift(1) <= baseline.shift(1))) |                   ((close < baseline) & (close.shift(1) >= baseline.shift(1)))
    return crossed.fillna(False)

def last_cross_recency(close: pd.Series, baseline: pd.Series, direction: str):
    crossed = compute_cross_flags(close, baseline, direction)
    if not crossed.any():
        return 10**9, False
    idx = crossed[::-1].idxmax()
    pos = crossed.index.get_loc(idx)
    days_since = len(crossed) - 1 - pos
    return int(days_since), True

def last_bullish_macd_recency(macd_line: pd.Series, signal_line: pd.Series):
    crossed = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    if not crossed.any():
        return 10**9, False
    idx = crossed[::-1].idxmax()
    pos = crossed.index.get_loc(idx)
    days_since = len(crossed) - 1 - pos
    return int(days_since), True

def rank_symbols(ohlcv: pd.DataFrame,
                 ema_kind: str,
                 ema_spans: list[int],
                 ema_direction: str,
                 macd_fast: int, macd_slow: int, macd_signal: int,
                 rsi_period: int,
                 lookback_sessions: int,
                 rsi_filter_range: tuple[int,int] | None):
    rows = []
    for sym, df in ohlcv.groupby("symbol"):
        df = df.sort_values("date").reset_index(drop=True)
        if len(df) < max(ema_spans + [macd_slow, rsi_period, 50]):
            continue

        if ema_kind == "DEMA":
            ema_map = {n: dema(df["close"], n) for n in ema_spans}
        else:
            ema_map = {n: ema(df["close"], n) for n in ema_spans}
        rsi_series = rsi_wilder(df["close"], rsi_period)
        macd_line, signal_line, _ = macd_lines(df["close"], fast=macd_fast, slow=macd_slow, signal=macd_signal)

        ema_results = {}
        for n in ema_spans:
            days_since, has_cross = last_cross_recency(df["close"], ema_map[n], ema_direction)
            ema_results[n] = (days_since, has_cross)

        macd_days, macd_has = last_bullish_macd_recency(macd_line, signal_line)

        latest = df.iloc[-1]
        rsi_val = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else np.inf

        passes_rsi = True
        if rsi_filter_range is not None:
            lo, hi = rsi_filter_range
            passes_rsi = (lo <= rsi_val <= hi)

        def within_window(days, has):
            return has and (days <= lookback_sessions)

        sort_key = []
        for n in ema_spans:
            d, h = ema_results[n]
            sort_key.extend([within_window(d, h), d])
        sort_key.extend([within_window(macd_days, macd_has), macd_days, rsi_val])

        rows.append({
            "symbol": sym,
            "last_date": latest["date"],
            "close": float(latest["close"]),
            "rsi": rsi_val,
            **{f"has_{n}_{ema_kind.lower()}_cross": within_window(*ema_results[n]) for n in ema_spans},
            **{f"days_since_{n}_{ema_kind.lower()}_cross": ema_results[n][0] for n in ema_spans},
            "has_macd_bull_cross": within_window(macd_days, macd_has),
            "days_since_macd_bull_cross": macd_days,
            "passes_rsi_filter": passes_rsi,
            "_sort_key": tuple(sort_key)
        })

    rankdf = pd.DataFrame(rows)
    if rankdf.empty:
        return rankdf

    if rsi_filter_range is not None:
        rankdf = rankdf[rankdf["passes_rsi_filter"]]

    def key_to_cols(tup):
        arr = []
        for v in tup:
            if isinstance(v, (bool, np.bool_)):
                arr.append(0 if v else 1)
            else:
                arr.append(v)
        return arr

    keys = rankdf["_sort_key"].apply(key_to_cols).tolist()
    kdf = pd.DataFrame(keys, index=rankdf.index)
    rankdf = pd.concat([rankdf, kdf.add_prefix("k_")], axis=1)
    rank_cols = [c for c in rankdf.columns if c.startswith("k_")]
    rankdf = rankdf.sort_values(by=rank_cols + ["rsi"], ascending=[True]*len(rank_cols) + [True]).reset_index(drop=True)
    rankdf.insert(0, "rank", range(1, len(rankdf)+1))
    return rankdf.drop(columns=["_sort_key"] + rank_cols)

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
    st.subheader("Ranking — configurable EMA crossovers, MACD, RSI")
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
        st.markdown("#### Analysis Parameters")
        c1, c2, c3 = st.columns(3)
        with c1:
            ema_kind = st.selectbox("EMA type", ["DEMA", "EMA"], index=0, help="Choose DEMA (double EMA) or EMA (single).")
            ema_spans_input = st.text_input("EMA spans (priority order, comma-separated)", value="200,44,21",
                                            help="Enter spans like 200,44,21. First is highest priority.")
            ema_direction = st.selectbox("Crossover direction", ["Bullish", "Bearish", "Both"], index=0)
        with c2:
            macd_fast = st.number_input("MACD fast", min_value=2, max_value=50, value=12, step=1)
            macd_slow = st.number_input("MACD slow", min_value=5, max_value=100, value=26, step=1)
            macd_signal = st.number_input("MACD signal", min_value=2, max_value=50, value=9, step=1)
        with c3:
            rsi_period = st.number_input("RSI period", min_value=2, max_value=100, value=14, step=1)
            lookback_sessions = st.number_input("Lookback sessions (bars)", min_value=1, max_value=252, value=5, step=1,
                                                help="Only crossovers within this many most recent bars are considered 'present'.")
            use_rsi_range = st.checkbox("Apply RSI range filter", value=False)
            rsi_range = st.slider("RSI range", min_value=0, max_value=100, value=(0, 100)) if use_rsi_range else None

        try:
            ema_spans = [int(x.strip()) for x in ema_spans_input.split(",") if x.strip()]
            ema_spans = [n for n in ema_spans if n > 0]
            if not ema_spans:
                st.error("Please provide at least one valid EMA span."); st.stop()
        except Exception:
            st.error("Invalid EMA spans. Use comma-separated integers like 200,44,21"); st.stop()

        need_cols = {"symbol","date","close"}
        df = df_input.copy()
        if not need_cols.issubset(set(df.columns)):
            st.error("CSV is missing required columns. Needs at least: symbol, date, close.")
        else:
            if not np.issubdtype(df["date"].dtype, np.datetime64):
                df["date"] = pd.to_datetime(df["date"])

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
                ranking = rank_symbols(
                    df,
                    ema_kind=ema_kind,
                    ema_spans=ema_spans,
                    ema_direction=ema_direction,
                    macd_fast=int(macd_fast), macd_slow=int(macd_slow), macd_signal=int(macd_signal),
                    rsi_period=int(rsi_period),
                    lookback_sessions=int(lookback_sessions),
                    rsi_filter_range=(rsi_range if use_rsi_range else None)
                )

            if ranking.empty:
                st.warning("No symbols qualified for ranking. Increase lookback or widen the date range.")
            else:
                st.success(f"Ranked {len(ranking)} symbols.")
                st.dataframe(ranking.head(300), use_container_width=True, height=560)
                csv_rank = ranking.to_csv(index=False).encode("utf-8")
                st.download_button("Download Ranking CSV", data=csv_rank, file_name="analysis_ranking.csv", mime="text/csv")

            with st.expander("Ranking Logic (current settings)"):
                st.markdown(
                    f"- **EMA type:** {ema_kind} | **Direction:** {ema_direction} | **Spans (priority):** {ema_spans}\n"
                    f"- **Lookback sessions:** {lookback_sessions}\n"
                    f"- **MACD:** fast {macd_fast}, slow {macd_slow}, signal {macd_signal}\n"
                    f"- **RSI period:** {rsi_period}" + (f" | **RSI range filter:** {rsi_range}" if use_rsi_range else "")
                )
    else:
        st.info("Upload/Download data to proceed with Analysis.")
