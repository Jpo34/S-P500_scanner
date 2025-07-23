import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Configuration defaults
TICKERS_URL_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
TICKERS_URL_NASDAQ100 = "https://en.wikipedia.org/wiki/Nasdaq-100"
DEFAULT_SMA_SHORT = 20
DEFAULT_SMA_LONG = 50
DEFAULT_AROC_WEEKS = 20

@st.cache_data(show_spinner=False)
def get_sp500_tickers():
    try:
        tables = pd.read_html(TICKERS_URL_SP500)
        df = tables[0]
        return df["Symbol"].tolist()
    except Exception as e:
        st.error(f"Failed to fetch S&P 500 tickers: {e}")
        return []

@st.cache_data(show_spinner=False)
def get_nasdaq100_tickers():
    try:
        tables = pd.read_html(TICKERS_URL_NASDAQ100)
        # Find the table with the tickers
        for table in tables:
            for col in table.columns:
                if isinstance(col, str) and ('Ticker' in col or 'Symbol' in col):
                    return table[col].tolist()
        st.error("Could not find 'Ticker' or 'Symbol' column in Nasdaq 100 table.")
        return []
    except Exception as e:
        st.error(f"Failed to fetch Nasdaq 100 tickers: {e}")
        return []

def get_all_tickers():
    sp500 = get_sp500_tickers()
    nasdaq100 = get_nasdaq100_tickers()
    combined = list(set(sp500 + nasdaq100))
    combined.sort()
    return combined

@st.cache_data(show_spinner=False)
def fetch_data(ticker, weeks):
    end_date = datetime.now()
    start_date = end_date - timedelta(weeks=weeks)
    try:
        df = yf.download(ticker, start=start_date, end=end_date, interval='1d', progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        st.warning(f"Error fetching data for {ticker}: {e}")
        return None

def calc_indicators(df, sma_short, sma_long, aroc_weeks):
    try:
        df["SMA_short"] = df["Close"].rolling(window=sma_short).mean()
        df["SMA_long"] = df["Close"].rolling(window=sma_long).mean()
        window = aroc_weeks * 5  # Approx. trading days in N weeks
        df["20w_high"] = df["Close"].rolling(window=window).max()
        df["AROC"] = ((df["Close"] - df["Close"].shift(window)) / df["Close"].shift(window)) * 100
        return df
    except Exception as e:
        st.warning(f"Indicator calculation error: {e}")
        return df

def analyze_ticker(ticker, sma_short, sma_long, aroc_weeks):
    df = fetch_data(ticker, weeks=aroc_weeks+10)  # Fetch enough data
    if df is None or df.empty:
        return None
    df = calc_indicators(df, sma_short, sma_long, aroc_weeks)
    latest = df.iloc[-1]
    try:
        # Combined entry logic
        entry_signal = (
            latest["Close"] > latest["SMA_short"]
            and latest["SMA_short"] > latest["SMA_long"]
            and latest["Close"] >= 0.95 * latest["20w_high"]
            and latest["AROC"] > 5
        )
        if entry_signal:
            entry_price = latest["Close"]
            sma_exit = latest["SMA_short"]
            trailing_stop_exit = entry_price * 0.93  # 7% trailing stop
            sell_recommendation = max(sma_exit, trailing_stop_exit)
            return {
                "Ticker": ticker,
                "Date": df.index[-1].strftime("%Y-%m-%d"),
                "Close": latest["Close"],
                "SMA_short": latest["SMA_short"],
                "SMA_long": latest["SMA_long"],
                "20w_high": latest["20w_high"],
                "AROC": latest["AROC"],
                "Entry Recommendation": entry_price,
                "Sell Recommendation": sell_recommendation,
            }
    except Exception as e:
        st.warning(f"Error processing {ticker}: {e}")
    return None

def main():
    st.title("S&P 500 & Nasdaq 100 Technical Scanner")
    st.write("Scan S&P 500 and Nasdaq 100 stocks for bullish technical setups.")

    tickers = get_all_tickers()
    if not tickers:
        st.stop()

    with st.sidebar:
        st.header("Scan Settings")
        selected_tickers = st.multiselect(
            "Select tickers (leave empty for all)",
            options=tickers,
            default=[],
            help="Choose one or more tickers, or leave empty to scan all S&P 500 and Nasdaq 100."
        )
        sma_short = st.number_input("SMA Short Window", min_value=5, max_value=100, value=DEFAULT_SMA_SHORT)
        sma_long = st.number_input("SMA Long Window", min_value=10, max_value=200, value=DEFAULT_SMA_LONG)
        aroc_weeks = st.number_input("AROC/High Weeks", min_value=4, max_value=52, value=DEFAULT_AROC_WEEKS)
        run_scan = st.button("Run Scan")

    if run_scan:
        to_scan = selected_tickers if selected_tickers else tickers
        results = []
        progress = st.progress(0)
        status = st.empty()
        for i, ticker in enumerate(to_scan):
            status.text(f"Analyzing {ticker} ({i+1}/{len(to_scan)})...")
            result = analyze_ticker(ticker, sma_short, sma_long, aroc_weeks)
            if result:
                results.append(result)
            progress.progress((i+1)/len(to_scan))
        status.text("")
        progress.empty()
        if results:
            df_results = pd.DataFrame(results)
            st.success(f"Found {len(df_results)} matching tickers.")
            st.dataframe(df_results)
            csv = df_results.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "scan_output.csv", "text/csv")
        else:
            st.info("No tickers matched the criteria.")

if __name__ == "__main__":
    main()
