import streamlit as st
import yfinance as yf
import pandas as pd
import altair as alt
import requests
from datetime import datetime

st.set_page_config(
    page_title="Professional Stock Screener",
    page_icon="📈",
    layout="wide"
)

# =========================
# Utility
# =========================
def fmt_num(v, digits=2):
    if v is None or pd.isna(v):
        return "-"
    return f"{v:,.{digits}f}"

def fmt_pct(v, digits=2):
    if v is None or pd.isna(v):
        return "-"
    return f"{v:,.{digits}f}%"

def recommendation_badge(rec):
    if rec == "BUY":
        return "🟢 BUY"
    if rec == "SELL":
        return "🔴 SELL"
    return "🟡 HOLD"

# =========================
# Search ticker
# =========================
@st.cache_data(ttl=86400)
def search_ticker(query: str):
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&lang=en-US"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        results = data.get("quotes", [])
        cleaned = []
        for item in results:
            symbol = item.get("symbol")
            name = item.get("shortname") or item.get("longname") or ""
            if symbol:
                cleaned.append({
                    "symbol": symbol,
                    "label": f"{symbol} - {name}"
                })
        return cleaned
    except Exception:
        return []

# =========================
# Batch history (anti rate-limit)
# =========================
@st.cache_data(ttl=3600)
def get_batch_history(tickers):
    try:
        if not tickers:
            return None, "Ticker kosong"

        data = yf.download(
            tickers=tickers,
            period="6mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=False
        )
        return data, None
    except Exception as e:
        return None, str(e)

def extract_price_data_from_batch(batch_data, ticker):
    try:
        if batch_data is None or batch_data.empty:
            return None, f"{ticker}: batch data kosong"

        # Multi ticker
        if isinstance(batch_data.columns, pd.MultiIndex):
            if ticker not in batch_data.columns.get_level_values(0):
                return None, f"{ticker}: tidak ada di hasil batch"

            hist = batch_data[ticker].copy().dropna(how="all")
        else:
            # Single ticker
            hist = batch_data.copy().dropna(how="all")

        if hist.empty or "Close" not in hist.columns:
            return None, f"{ticker}: history kosong"

        close_series = hist["Close"].dropna()
        if close_series.empty:
            return None, f"{ticker}: close kosong"

        price = float(close_series.iloc[-1])

        return {
            "ticker": ticker,
            "price": price,
            "hist": hist
        }, None

    except Exception as e:
        return None, f"{ticker}: {e}"

# =========================
# Optional fundamental detail
# Only called for 1 ticker in Detail tab
# =========================
@st.cache_data(ttl=3600)
def get_fundamental_detail(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        eps = info.get("trailingEps")
        pbv = info.get("priceToBook")
        roe_raw = info.get("returnOnEquity")
        roe = roe_raw * 100 if roe_raw is not None else None

        div_raw = info.get("dividendYield")
        dividend_yield = div_raw * 100 if div_raw is not None else None

        market_cap = info.get("marketCap")
        sector = info.get("sector")
        industry = info.get("industry")
        long_name = info.get("longName") or info.get("shortName") or ticker

        return {
            "name": long_name,
            "sector": sector,
            "industry": industry,
            "eps": eps,
            "pbv": pbv,
            "roe": roe,
            "dividend_yield": dividend_yield,
            "market_cap": market_cap,
        }, None
    except Exception as e:
        return None, str(e)

# =========================
# Scoring sederhana berbasis price momentum + optional valuation
# =========================
def classify_recommendation(price, fair_value=None):
    if fair_value is not None and price < fair_value:
        return "BUY"
    if fair_value is not None and price > fair_value * 1.2:
        return "SELL"
    return "HOLD"

def calculate_score(price_change_pct, upside_pct=None, roe=None, pbv=None, per=None, mode="Price Focus"):
    score = 0

    if price_change_pct is not None:
        if price_change_pct > 20:
            score += 30
        elif price_change_pct > 10:
            score += 20
        elif price_change_pct > 0:
            score += 10

    if upside_pct is not None:
        if upside_pct > 50:
            score += 20
        elif upside_pct > 30:
            score += 14
        elif upside_pct > 15:
            score += 8

    if roe is not None:
        if roe > 20:
            score += 20
        elif roe > 15:
            score += 14
        elif roe > 10:
            score += 8

    if pbv is not None:
        if pbv < 1:
            score += 15
        elif pbv < 1.5:
            score += 10
        elif pbv < 2:
            score += 5

    if per is not None:
        if per < 8:
            score += 15
        elif per < 12:
            score += 10
        elif per < 15:
            score += 5

    return score

# =========================
# Sidebar
# =========================
st.sidebar.title("📊 Stock Screener")

default_tickers = [
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK",
    "ASII.JK", "PTBA.JK", "ADRO.JK", "SIDO.JK"
]

if "saved_tickers" not in st.session_state:
    st.session_state["saved_tickers"] = ["BBCA.JK", "BBRI.JK", "BMRI.JK"]

selected = st.sidebar.multiselect(
    "Pilih ticker umum",
    options=sorted(default_tickers),
    default=st.session_state["saved_tickers"]
)

query = st.sidebar.text_input("Cari ticker Yahoo Finance")
if query:
    results = search_ticker(query)
    if results:
        search_selected = st.sidebar.multiselect(
            "Hasil pencarian",
            options=[x["symbol"] for x in results],
            format_func=lambda x: next((i["label"] for i in results if i["symbol"] == x), x)
        )
        selected.extend(search_selected)
    else:
        st.sidebar.warning("Ticker tidak ditemukan.")

manual_input = st.sidebar.text_input("Tambah ticker manual (pisahkan koma)")
if manual_input:
    manual_list = [t.strip().upper() for t in manual_input.split(",") if t.strip()]
    selected.extend(manual_list)

# Penting: batasi jumlah ticker untuk hindari rate limit
tickers = sorted(list(set(selected)))[:5]

if st.sidebar.button("💾 Simpan Pilihan"):
    st.session_state["saved_tickers"] = tickers
    st.sidebar.success("Pilihan disimpan.")

st.sidebar.markdown("---")
show_debug = st.sidebar.checkbox("Tampilkan debug", value=False)

# =========================
# Load batch price data
# =========================
batch_data, batch_err = get_batch_history(tickers)

rows = []
histories = []
debug_logs = []

if batch_err:
    debug_logs.append(f"Batch error: {batch_err}")

for ticker in tickers:
    data, err = extract_price_data_from_batch(batch_data, ticker)

    if err:
        debug_logs.append(err)
        continue

    hist = data["hist"].copy()
    close_series = hist["Close"].dropna()

    first_price = float(close_series.iloc[0]) if not close_series.empty else None
    last_price = float(close_series.iloc[-1]) if not close_series.empty else None

    price_change_pct = (
        ((last_price - first_price) / first_price) * 100
        if first_price is not None and first_price > 0 and last_price is not None
        else None
    )

    row = {
        "Ticker": ticker,
        "Name": ticker,
        "Price": last_price,
        "6M Change (%)": price_change_pct,
        "EPS": None,
        "PER": None,
        "PBV": None,
        "ROE (%)": None,
        "Dividend Yield (%)": None,
        "Fair Value": None,
        "Upside (%)": None,
        "Recommendation": "HOLD",
        "Score": calculate_score(price_change_pct),
        "Sector": None,
        "Industry": None,
        "Market Cap": None
    }
    rows.append(row)

    hist_reset = hist.reset_index()
    if not hist_reset.empty and "Close" in hist_reset.columns:
        base = hist_reset["Close"].iloc[0]
        if pd.notna(base) and base != 0:
            hist_reset["Indexed"] = (hist_reset["Close"] / base) * 100
            hist_reset["Ticker"] = ticker
            histories.append(hist_reset[["Date", "Ticker", "Close", "Indexed"]])

df = pd.DataFrame(rows)

# =========================
# Header
# =========================
st.title("📈 Professional Stock Screener")
st.caption(f"Updated from Yahoo Finance batch download | Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if df.empty:
    st.error("Belum ada data harga yang berhasil diambil.")
    if debug_logs:
        st.code("\n".join(debug_logs))
    st.info("Coba kurangi ticker menjadi 1-3 atau reload beberapa menit lagi.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Stocks", len(df))
avg_price_change = df["6M Change (%)"].dropna().mean() if not df["6M Change (%)"].dropna().empty else None
col2.metric("Avg 6M Change", fmt_pct(avg_price_change))
best_score = df["Score"].max() if not df.empty else None
col3.metric("Best Score", fmt_num(best_score, 0))

if show_debug and debug_logs:
    st.subheader("Debug Log")
    st.code("\n".join(debug_logs))

# =========================
# Download
# =========================
download_df = df.copy()
download_df["Recommendation"] = download_df["Recommendation"].map(recommendation_badge)
csv_data = download_df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="⬇️ Download CSV",
    data=csv_data,
    file_name="stock_screener_batch.csv",
    mime="text/csv"
)

# =========================
# Tabs
# =========================
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Ranking", "Charts", "Detail"])

with tab1:
    st.subheader("Overview")

    overview = df.copy()
    overview["Recommendation"] = overview["Recommendation"].map(recommendation_badge)

    display_overview = overview[[
        "Ticker", "Name", "Price", "6M Change (%)", "Recommendation", "Score"
    ]].copy()

    display_overview["Price"] = display_overview["Price"].apply(lambda x: fmt_num(x, 2))
    display_overview["6M Change (%)"] = display_overview["6M Change (%)"].apply(lambda x: fmt_pct(x, 2))
    display_overview["Score"] = display_overview["Score"].apply(lambda x: fmt_num(x, 0))

    st.dataframe(display_overview, use_container_width=True)

with tab2:
    st.subheader("Ranking")

    ranking_df = df.sort_values(
        by=["Score", "6M Change (%)"],
        ascending=[False, False],
        na_position="last"
    ).reset_index(drop=True)

    top_n = st.slider("Tampilkan Top N", 1, len(ranking_df), min(5, len(ranking_df)))

    ranking_show = ranking_df.head(top_n).copy()
    ranking_show["Recommendation"] = ranking_show["Recommendation"].map(recommendation_badge)

    display_ranking = ranking_show[[
        "Ticker", "Name", "Price", "6M Change (%)", "Recommendation", "Score"
    ]].copy()

    display_ranking["Price"] = display_ranking["Price"].apply(lambda x: fmt_num(x, 2))
    display_ranking["6M Change (%)"] = display_ranking["6M Change (%)"].apply(lambda x: fmt_pct(x, 2))
    display_ranking["Score"] = display_ranking["Score"].apply(lambda x: fmt_num(x, 0))

    st.dataframe(display_ranking, use_container_width=True)

    rank_chart = (
        alt.Chart(ranking_show)
        .mark_bar()
        .encode(
            x=alt.X("Score:Q", title="Score"),
            y=alt.Y("Ticker:N", sort="-x", title="Ticker"),
            tooltip=[
                "Ticker",
                alt.Tooltip("Price:Q", format=".2f"),
                alt.Tooltip("6M Change (%):Q", format=".2f"),
                alt.Tooltip("Score:Q", format=".0f"),
            ]
        )
        .properties(height=400)
    )
    st.altair_chart(rank_chart, use_container_width=True)

with tab3:
    st.subheader("Charts")

    if histories:
        all_hist = pd.concat(histories, ignore_index=True)

        comparison_chart = (
            alt.Chart(all_hist)
            .mark_line()
            .encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Indexed:Q", title="Indexed Performance (Base 100)"),
                color=alt.Color("Ticker:N"),
                tooltip=[
                    "Ticker:N",
                    "Date:T",
                    alt.Tooltip("Indexed:Q", format=".2f"),
                    alt.Tooltip("Close:Q", format=".2f"),
                ]
            )
            .properties(height=450)
            .interactive()
        )
        st.altair_chart(comparison_chart, use_container_width=True)

        st.subheader("Momentum Scatter")

        scatter_source = df.dropna(subset=["6M Change (%)"]).copy()
        scatter = (
            alt.Chart(scatter_source)
            .mark_circle(size=160)
            .encode(
                x=alt.X("Price:Q", title="Price"),
                y=alt.Y("6M Change (%):Q", title="6M Change (%)"),
                size=alt.Size("Score:Q", title="Score"),
                color=alt.Color("Ticker:N"),
                tooltip=[
                    "Ticker",
                    alt.Tooltip("Price:Q", format=".2f"),
                    alt.Tooltip("6M Change (%):Q", format=".2f"),
                    alt.Tooltip("Score:Q", format=".0f"),
                ]
            )
            .properties(height=420)
            .interactive()
        )
        st.altair_chart(scatter, use_container_width=True)
    else:
        st.info("Belum ada data chart yang bisa ditampilkan.")

with tab4:
    st.subheader("Detail")

    detail_options = df["Ticker"].tolist()
    selected_detail = st.selectbox("Pilih saham", detail_options)

    detail_row = df[df["Ticker"] == selected_detail].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Price", fmt_num(detail_row["Price"], 2))
    c2.metric("6M Change", fmt_pct(detail_row["6M Change (%)"], 2))
    c3.metric("Score", fmt_num(detail_row["Score"], 0))

    st.markdown("### Fundamental Detail")
    st.caption("Fundamental diambil hanya untuk 1 ticker agar lebih aman dari rate limit.")

    fund, fund_err = get_fundamental_detail(selected_detail)

    if fund_err:
        st.warning(f"Fundamental belum tersedia: {fund_err}")
    elif fund:
        eps = fund.get("eps")
        pbv = fund.get("pbv")
        roe = fund.get("roe")
        div_yield = fund.get("dividend_yield")
        market_cap = fund.get("market_cap")
        sector = fund.get("sector")
        industry = fund.get("industry")
        long_name = fund.get("name")

        price = detail_row["Price"]
        per = (price / eps) if (eps is not None and eps > 0 and price is not None) else None
        fair_value = (eps * 15) if (eps is not None and eps > 0) else None
        upside_pct = (
            ((fair_value - price) / price) * 100
            if fair_value is not None and price is not None and price > 0
            else None
        )
        recommendation = classify_recommendation(price, fair_value)

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("PER", fmt_num(per, 2))
        d2.metric("PBV", fmt_num(pbv, 2))
        d3.metric("ROE", fmt_pct(roe, 2))
        d4.metric("Dividend Yield", fmt_pct(div_yield, 2))

        d5, d6, d7 = st.columns(3)
        d5.metric("Fair Value", fmt_num(fair_value, 2))
        d6.metric("Upside", fmt_pct(upside_pct, 2))
        d7.metric("Recommendation", recommendation_badge(recommendation))

        st.write(f"**Name:** {long_name}")
        st.write(f"**Sector:** {sector or '-'}")
        st.write(f"**Industry:** {industry or '-'}")
        st.write(f"**Market Cap:** {fmt_num(market_cap, 0)}")

    st.markdown("### Historical Price")

    selected_hist = None
    for h in histories:
        if not h.empty and h["Ticker"].iloc[0] == selected_detail:
            selected_hist = h.copy()
            break

    if selected_hist is not None and not selected_hist.empty:
        detail_chart = (
            alt.Chart(selected_hist)
            .mark_line()
            .encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Close:Q", title="Close Price"),
                tooltip=[
                    "Date:T",
                    alt.Tooltip("Close:Q", format=".2f")
                ]
            )
            .properties(height=400)
            .interactive()
        )
        st.altair_chart(detail_chart, use_container_width=True)
    else:
        st.info("Data historis tidak tersedia.")

st.markdown("---")
st.caption(
    "Versi ini dioptimalkan untuk mengurangi rate limit Yahoo Finance dengan batch download harga. "
    "Fundamental hanya diambil saat membuka detail 1 ticker."
)
