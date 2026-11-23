
import streamlit as st
import ccxt
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="MEXC AI Cloud Bot",
    page_icon="📊",
    layout="wide"
)

st.title("MEXC Futures AI Signal Terminal")
st.caption("Cloud-based MEXC Futures Market Analysis")

st.warning(
    "Manual trading signals only. "
    "No automatic orders. No guaranteed profits."
)

@st.cache_resource
def get_exchange():
    exchange = ccxt.mexc({
        "enableRateLimit": True,
        "timeout": 20000,
        "options": {"defaultType": "swap"}
    })
    return exchange

@st.cache_data(ttl=300)
def get_symbols():
    exchange = get_exchange()
    markets = exchange.load_markets()

    symbols = [
        symbol for symbol, market in markets.items()
        if market.get("swap")
        and market.get("quote") == "USDT"
        and market.get("active", True)
    ]

    return sorted(symbols)

def analyze(symbol, timeframe):
    exchange = get_exchange()

    candles = exchange.fetch_ohlcv(
        symbol,
        timeframe=timeframe,
        limit=200
    )

    df = pd.DataFrame(
        candles,
        columns=[
            "time", "open", "high",
            "low", "close", "volume"
        ]
    )

    df["ema9"] = df["close"].ewm(
        span=9, adjust=False
    ).mean()

    df["ema20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/14, adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/14, adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["rsi"] = 100 - (100 / (1 + rs))

    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift()),
            abs(df["low"] - df["close"].shift())
        )
    )

    df["atr"] = df["tr"].ewm(
        alpha=1/14, adjust=False
    ).mean()

    return df.dropna()

try:
    symbols = get_symbols()

    if not symbols:
        st.error("No active USDT Futures symbols found.")
        st.stop()

    symbol = st.selectbox(
        "Select MEXC Futures Coin",
        symbols
    )

    if st.button("Analyze Market", type="primary"):
        with st.spinner("Analyzing live market data..."):

            results = {}

            for tf in ["5m", "15m", "1h"]:
                results[tf] = analyze(symbol, tf)

            scores = {"BUY": 0, "SELL": 0}

            for tf, df in results.items():
                last = df.iloc[-1]

                if last["ema9"] > last["ema20"]:
                    scores["BUY"] += 1
                else:
                    scores["SELL"] += 1

            main_df = results["5m"]
            last = main_df.iloc[-1]

            price = float(last["close"])
            atr = float(last["atr"])
            rsi = float(last["rsi"])

            st.subheader(f"Market Analysis: {symbol}")

            col1, col2, col3 = st.columns(3)

            col1.metric("Live Candle Price", f"{price:.8g}")
            col2.metric("RSI 14", f"{rsi:.2f}")
            col3.metric("ATR 14", f"{atr:.8g}")

            st.subheader("Multi-Timeframe Trend")

            for tf, df in results.items():
                last_tf = df.iloc[-1]

                trend = (
                    "BULLISH"
                    if last_tf["ema9"] > last_tf["ema20"]
                    else "BEARISH"
                )

                st.write(f"**{tf.upper()} Trend: {trend}**")

            st.subheader("Signal")

            if scores["BUY"] == 3 and 50 <= rsi <= 70:
                signal = "BUY"
            elif scores["SELL"] == 3 and 30 <= rsi <= 50:
                signal = "SELL"
            else:
                signal = "HOLD"

            if signal == "BUY":
                entry = price
                sl = entry - (1.5 * atr)
                tp1 = entry + (2 * atr)
                tp2 = entry + (3 * atr)

            elif signal == "SELL":
                entry = price
                sl = entry + (1.5 * atr)
                tp1 = entry - (2 * atr)
                tp2 = entry - (3 * atr)

            else:
                entry = sl = tp1 = tp2 = None

            st.header(signal)

            if signal != "HOLD":
                a, b, c, d = st.columns(4)

                a.metric("Entry", f"{entry:.8g}")
                b.metric("Stop Loss", f"{sl:.8g}")
                c.metric("Take Profit 1", f"{tp1:.8g}")
                d.metric("Take Profit 2", f"{tp2:.8g}")

            st.write(
                f"BUY Score: {scores['BUY']} / 3"
            )

            st.write(
                f"SELL Score: {scores['SELL']} / 3"
            )

            st.line_chart(
                main_df.set_index("time")[
                    ["close", "ema9", "ema20"]
                ]
            )

            st.caption(
                "Analysis uses candle data. "
                "Confirm current price, fees and risk before trading."
            )

except Exception as e:
    st.error(f"Market data error: {e}")
    st.info("Please try again after a short time.")
