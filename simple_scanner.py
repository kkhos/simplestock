import yfinance as yf
import pandas as pd
import datetime

# --- 설정 (Config) ---
RSI_THRESHOLD_LOW = 30   # 과매도 (매수 고려)
RSI_THRESHOLD_HIGH = 70  # 과매수 (매도 고려)
RSI_PERIOD = 14
TREND_FAST_EMA = 50
TREND_SLOW_EMA = 200
VOLUME_SPIKE_MULTIPLIER = 1.5
ATR_PERIOD = 14

# --- 감시 대상 종목 (Watchlist) ---
# 한국 주식 (KOSPI Top 10 + 주요 종목)
watchlist_kr = {
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

# 미국 주식 (S&P 500 Top 10 + 주요 기술주)
watchlist_us = {
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

        # 하락추세에서의 낙폭과대 시그널을 줄이기 위한 추세 필터
        if not (last_price > ema200 and ema50 > ema200):
            return None

        score = 0
        reasons = []

        # --- 매수 신호 (Score 계산) ---
        # 1. RSI 과매도 구간 (30점)
        if last_rsi <= RSI_THRESHOLD_LOW:
            score += 30
            reasons.append(f"RSI 과매도({last_rsi:.1f})")
        elif last_rsi <= 40:
            score += 10
            reasons.append(f"RSI 저점({last_rsi:.1f})")

        # 2. MACD 골든크로스 (40점)
        # (어제는 MACD < Signal 이었는데, 오늘은 MACD > Signal)
        if prev_row['MACD'] < prev_row['Signal_Line'] and last_macd > last_signal:
            score += 40
            reasons.append("MACD 골든크로스(상승전환)")
        elif last_macd > last_signal:
            score += 10 # 정배열 유지 중

        # 3. 볼린저 밴드 하단 터치 (30점)
        # 주가가 하단 밴드 근처(3% 이내)에 있거나 터치함
        if last_price <= lower_band * 1.03:
            score += 30
            reasons.append("볼린저밴드 하단 근접(반등기대)")

        # 4. 거래량 급증 확인 (신호 강화)
        if last_volume >= volume_ma20 * VOLUME_SPIKE_MULTIPLIER:
            score += 15
            reasons.append(f"거래량 급증({last_volume / volume_ma20:.1f}x)")
        
        # --- 매도 신호 (Score 차감) ---
        if last_rsi >= RSI_THRESHOLD_HIGH:
            score -= 20
            reasons.append("RSI 과매수(주의)")
        
        if last_price >= upper_band * 0.97:
             score -= 10
             reasons.append("볼린저밴드 상단 근접(저항)")


        if score >= 40: # 유의미한 매수 신호만 리턴
            return {
                'ticker': ticker,
                'name': name,
                'market': market,
                'price': last_price,
                'score': score,
                'reasons': reasons,
                'rsi': last_rsi,
                'atr': atr14,
                'stop_loss': max(last_price - (1.5 * atr14), 0),
                'take_profit_1': last_price + (2 * atr14),
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

    # 1. 한국 주식 스캔
    print("🇰🇷 Scanning KOSPI...")
    for ticker, name in watchlist_kr.items():
        result = analyze_stock(ticker, name, 'KR')
        if result:
            signals.append(result)

    # 2. 미국 주식 스캔
    print("🇺🇸 Scanning US Tech...")
    for ticker, name in watchlist_us.items():
        result = analyze_stock(ticker, name, 'US')
        if result:
            signals.append(result)

    print("-" * 50)
    
    # 점수 높은 순 정렬
    signals.sort(key=lambda x: x['score'], reverse=True)

    if not signals:
        print("✅ **특이사항 없음** (관망세)")
    else:
        print(f"🚨 **Found {len(signals)} Buying Opportunities!**\n")
        
        for s in signals:
            currency = "₩" if s['market'] == 'KR' else "$"
            icon = "🚀" if s['score'] >= 60 else "👀"
            
            print(f"{icon} **{s['name']} ({s['ticker']})**")
            print(f"   Score: {s['score']}점")
            print(f"   Price: {currency}{s['price']:,.0f}")
            print(f"   Risk: ATR14 {s['atr']:.2f} | SL {currency}{s['stop_loss']:,.0f} | TP1 {currency}{s['take_profit_1']:,.0f}")
            print(f"   Signals: {', '.join(s['reasons'])}")
            print("")

if __name__ == "__main__":
    main()
