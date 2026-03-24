import yfinance as yf
import pandas as pd
import datetime
import re
import requests
from bs4 import BeautifulSoup
import csv
import os

# --- 설정 (Config) ---
RSI_THRESHOLD_LOW = 30   # 과매도 (매수 고려)
RSI_THRESHOLD_HIGH = 70  # 과매수 (매도 고려)
RSI_PERIOD = 14
TREND_FAST_EMA = 50
TREND_SLOW_EMA = 200
VOLUME_SPIKE_MULTIPLIER = 1.5
ATR_PERIOD = 14

FALLBACK_US = {
    'AAPL': 'Apple',
    'MSFT': 'Microsoft',
    'GOOGL': 'Alphabet (Google)',
    'AMZN': 'Amazon',
    'TSLA': 'Tesla',
    'NVDA': 'NVIDIA',
    'META': 'Meta (Facebook)',
    'NFLX': 'Netflix',
    'AMD': 'AMD',
    'INTC': 'Intel'
}

FALLBACK_KR = {
    '005930.KS': '삼성전자',
    '373220.KS': 'LG에너지솔루션',
    '000660.KS': 'SK하이닉스',
    '207940.KS': '삼성바이오로직스',
    '005380.KS': '현대차',
    '006400.KS': '삼성SDI',
    '051910.KS': 'LG화학',
    '000270.KS': '기아',
    '035420.KS': 'NAVER',
    '035720.KS': '카카오'
}


def fetch_us_top100():
    """
    미국 시가총액 상위 100개 (S&P500 시총 순 정렬 기준) 티커를 수집.
    """
    url = "https://www.slickcharts.com/sp500"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table.table tbody tr")
    if not rows:
        return None

    result = {}
    for row in rows:
        tds = row.select("td")
        if len(tds) < 3:
            continue
        name = tds[1].get_text(strip=True)
        ticker = tds[2].get_text(strip=True).replace(".", "-")
        if ticker:
            result[ticker] = name
        if len(result) >= 100:
            break

    return result if len(result) >= 100 else None


def fetch_kr_top100():
    """
    한국 시가총액 상위 100개 (네이버 금융 KOSPI 시총 순) 티커를 수집.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    result = {}

    excluded_keywords = ("ETF", "ETN", "스팩", "SPAC")

    for page in range(1, 21):
        url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page={page}"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.select("a.tltle")
        for link in links:
            name = link.get_text(strip=True)
            if any(keyword in name for keyword in excluded_keywords):
                continue
            href = link.get("href", "")
            match = re.search(r"code=(\d{6})", href)
            if not match:
                continue

            ticker = f"{match.group(1)}.KS"
            result[ticker] = name
            if len(result) >= 100:
                return result

    return result if len(result) >= 100 else None


def build_watchlists():
    """
    동적 Top100 watchlist를 구성하고, 실패 시 fallback 사용.
    """
    watchlist_us = FALLBACK_US.copy()
    watchlist_kr = FALLBACK_KR.copy()

    try:
        dynamic_us = fetch_us_top100()
        if dynamic_us:
            watchlist_us = dynamic_us
    except Exception:
        pass

    try:
        dynamic_kr = fetch_kr_top100()
        if dynamic_kr:
            watchlist_kr = dynamic_kr
    except Exception:
        pass

    return watchlist_kr, watchlist_us

def calculate_indicators(df):
    """
    RSI, MACD, Bollinger Bands, EMA, Volume MA, ATR 계산
    """
    if df.empty or len(df) < TREND_SLOW_EMA + 20:
        return None

    # 1. RSI (Relative Strength Index)
    delta = df['Close'].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=RSI_PERIOD).mean()
    avg_loss = loss.rolling(window=RSI_PERIOD).mean()

    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 2. MACD (Moving Average Convergence Divergence)
    # EMA(12) - EMA(26)
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # 3. Bollinger Bands (20일 이동평균, 표준편차 2배)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['Upper_Band'] = df['MA20'] + (df['STD20'] * 2)
    df['Lower_Band'] = df['MA20'] - (df['STD20'] * 2)

    # 4. Trend filter / Volume filter
    df['EMA50'] = df['Close'].ewm(span=TREND_FAST_EMA, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=TREND_SLOW_EMA, adjust=False).mean()
    df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()

    # 5. ATR(14): 변동성 기반 리스크 관리
    prev_close = df['Close'].shift(1)
    tr_components = pd.concat(
        [
            (df['High'] - df['Low']).abs(),
            (df['High'] - prev_close).abs(),
            (df['Low'] - prev_close).abs(),
        ],
        axis=1,
    )
    df['TR'] = tr_components.max(axis=1)
    df['ATR14'] = df['TR'].rolling(window=ATR_PERIOD).mean()

    return df

def analyze_stock(ticker, name, market):
    """개별 종목 분석 및 신호 포착"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")

        df = calculate_indicators(df)
        if df is None:
            return None

        # 마지막 데이터 확인
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] # 전일 데이터 (크로스 확인용)

        last_rsi = last_row['RSI']
        last_macd = last_row['MACD']
        last_signal = last_row['Signal_Line']
        last_price = last_row['Close']
        lower_band = last_row['Lower_Band']
        upper_band = last_row['Upper_Band']
        ema50 = last_row['EMA50']
        ema200 = last_row['EMA200']
        last_volume = last_row['Volume']
        volume_ma20 = last_row['Volume_MA20']
        atr14 = last_row['ATR14']

        if pd.isna(last_rsi) or pd.isna(ema50) or pd.isna(ema200) or pd.isna(volume_ma20) or pd.isna(atr14):
            return None

        high_52w = df['High'].rolling(window=252, min_periods=100).max().iloc[-1]

        score = 0
        short_score = 0
        reasons = []
        short_reasons = []

        # --- 1. 롱(Buy) 포지션 스캔 ---
        # 상승추세 필터 (정배열)
        if last_price > ema200 and ema50 > ema200:
            if last_rsi <= RSI_THRESHOLD_LOW:
                score += 30
                reasons.append(f"RSI 과매도({last_rsi:.1f})")
            elif last_rsi <= 40:
                score += 10
                reasons.append(f"RSI 저점({last_rsi:.1f})")

            if prev_row['MACD'] < prev_row['Signal_Line'] and last_macd > last_signal:
                score += 40
                reasons.append("MACD 골든크로스(상승전환)")
            elif last_macd > last_signal:
                score += 10 # 정배열 유지 중

            if last_price <= lower_band * 1.03:
                score += 30
                reasons.append("볼린저밴드 하단 근접(반등기대)")

            if last_volume >= volume_ma20 * VOLUME_SPIKE_MULTIPLIER:
                score += 15
                reasons.append(f"거래량 급증({last_volume / volume_ma20:.1f}x)")
            
            if last_rsi >= RSI_THRESHOLD_HIGH:
                score -= 20
                reasons.append("RSI 과매수(주의)")
            
            if last_price >= upper_band * 0.97:
                 score -= 10
                 reasons.append("볼린저밴드 상단 근접(저항)")

        # --- 2. 숏(Short) 포지션 스캔 (윌리엄 오닐 기법) ---
        # 조건: 고점 대비 15% 이상 하락 & 50일선 아래 & 50일선으로 거래량 없이 반등(Pullback)
        is_former_leader = (last_price < high_52w * 0.85)
        is_below_50 = last_price < ema50
        is_pullback_to_50 = (last_price >= ema50 * 0.96) # 50일선 4% 이내로 근접
        is_low_volume = last_volume < volume_ma20 * 0.8 # 거래량 부진 (가짜 반등)

        if is_former_leader and is_below_50 and is_pullback_to_50:
            short_score += 40
            short_reasons.append("50일선 저항/가짜 반등(O'Neil Short)")
            if is_low_volume:
                short_score += 20
                short_reasons.append(f"거래량 부진({last_volume / volume_ma20:.1f}x)")
            if ema50 < ema200:
                short_score += 10
                short_reasons.append("역배열(Death Cross 상태)")

        # 둘 중 더 강한 시그널을 리턴
        if score >= 40 and score >= short_score:
            return {
                'ticker': ticker,
                'name': name,
                'market': market,
                'price': last_price,
                'score': score,
                'reasons': reasons,
                'rsi': last_rsi,
                'atr': atr14,
                'type': 'LONG (매수)',
                'stop_loss': max(last_price - (1.5 * atr14), 0),
                'take_profit_1': last_price + (2 * atr14),
            }
        elif short_score >= 50:
            return {
                'ticker': ticker,
                'name': name,
                'market': market,
                'price': last_price,
                'score': short_score,
                'reasons': short_reasons,
                'rsi': last_rsi,
                'atr': atr14,
                'type': 'SHORT (공매도)',
                'stop_loss': last_price + (1.5 * atr14),
                'take_profit_1': max(last_price - (3 * atr14), 0),
            }
        
        return None

    except Exception as e:
        # print(f"Error analyzing {name}: {e}")
        return None

def main():
    print(f"📊 **Smart Stock Radar (Trend + RSI + MACD + Bollinger + ATR)**")
    print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)

    signals = []
    watchlist_kr, watchlist_us = build_watchlists()
    print(f"Universe: KR {len(watchlist_kr)}개 / US {len(watchlist_us)}개")

    # 1. 한국 주식 스캔
    print("🇰🇷 Scanning KOSPI Top100...")
    for ticker, name in watchlist_kr.items():
        result = analyze_stock(ticker, name, 'KR')
        if result:
            signals.append(result)

    # 2. 미국 주식 스캔
    print("🇺🇸 Scanning US Top100...")
    for ticker, name in watchlist_us.items():
        result = analyze_stock(ticker, name, 'US')
        if result:
            signals.append(result)

    print("-" * 50)
    
    # 점수 높은 순 정렬
    signals.sort(key=lambda x: x['score'], reverse=True)

    # --- 가상 매매(Paper Trading) 기록 로직 ---
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    trade_log_file = 'paper_trades.csv'
    logged_tickers = set()
    
    if os.path.exists(trade_log_file):
        with open(trade_log_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None) # skip header
            for row in reader:
                if row and row[0] == today_str:
                    logged_tickers.add(row[1])

    if not signals:
        print("✅ **특이사항 없음** (관망세)")
    else:
        print(f"🚨 **Found {len(signals)} Actionable Setups!**\n")
        
        for s in signals:
            # 60점 이상 강력 신호는 가상 매매 장부에 기록 (하루 1회 제한)
            if s['score'] >= 60 and s['ticker'] not in logged_tickers:
                file_exists = os.path.isfile(trade_log_file)
                with open(trade_log_file, mode='a', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(['Date', 'Ticker', 'Name', 'Market', 'Type', 'Entry_Price', 'SL', 'TP', 'Score', 'Reasons'])
                    writer.writerow([
                        today_str, s['ticker'], s['name'], s['market'], s.get('type', 'LONG'),
                        round(s['price'], 2), round(s['stop_loss'], 2), round(s['take_profit_1'], 2),
                        s['score'], " | ".join(s['reasons'])
                    ])

            currency = "₩" if s['market'] == 'KR' else "$"

            currency = "₩" if s['market'] == 'KR' else "$"
            
            if "SHORT" in s.get('type', ''):
                icon = "🩸" if s['score'] >= 60 else "📉"
            else:
                icon = "🚀" if s['score'] >= 60 else "👀"
            
            print(f"{icon} **[{s.get('type', 'LONG')}] {s['name']} ({s['ticker']})**")
            print(f"   Score: {s['score']}점")
            if s['market'] == 'KR':
                print(f"   Price: {currency}{s['price']:,.0f}")
                print(f"   Risk: ATR14 {s['atr']:.0f} | SL {currency}{s['stop_loss']:,.0f} | TP1 {currency}{s['take_profit_1']:,.0f}")
            else:
                print(f"   Price: {currency}{s['price']:,.2f}")
                print(f"   Risk: ATR14 {s['atr']:.2f} | SL {currency}{s['stop_loss']:,.2f} | TP1 {currency}{s['take_profit_1']:,.2f}")
            print(f"   Signals: {', '.join(s['reasons'])}")
            print("")

if __name__ == "__main__":
    main()
