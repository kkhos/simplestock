import yfinance as yf
import pandas as pd
import datetime

# --- 설정 (Config) ---
RSI_THRESHOLD = 30  # 과매도 기준 (RSI 30 이하 = 매수 고려)
RSI_PERIOD = 14     # RSI 계산 기간 (14일)

# --- 감시 대상 종목 (Watchlist) ---
# yfinance용 티커 포맷으로 변경 (한국 주식은 .KS)
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

def calculate_rsi(series, period=14):
    """RSI 지표 직접 계산"""
    delta = series.diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def analyze_stock(ticker, name, market):
    """개별 종목 분석 및 신호 포착"""
    try:
        # yfinance로 통합 데이터 수집
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")

        if df.empty or len(df) < RSI_PERIOD + 2:
            return None

        # RSI 계산
        df['RSI'] = calculate_rsi(df['Close'], RSI_PERIOD)

        # 마지막 날의 RSI 값 확인
        last_rsi = df['RSI'].iloc[-1]
        last_price = df['Close'].iloc[-1]
        last_date = df.index[-1].strftime('%Y-%m-%d')

        if pd.isna(last_rsi):
            return None

        # 조건 충족 여부 (RSI <= 30)
        if last_rsi <= RSI_THRESHOLD:
            return {
                'ticker': ticker,
                'name': name,
                'market': market,
                'rsi': round(last_rsi, 2),
                'price': last_price,
                'date': last_date,
                'signal': 'BUY (Oversold)'
            }
        # (옵션) 과매수 구간 (RSI >= 70) 체크
        elif last_rsi >= 70:
             return {
                'ticker': ticker,
                'name': name,
                'market': market,
                'rsi': round(last_rsi, 2),
                'price': last_price,
                'date': last_date,
                'signal': 'SELL (Overbought)'
            }
        
        return None

    except Exception as e:
        # print(f"Error analyzing {name} ({ticker}): {e}")
        return None

def main():
    print(f"📊 **Stock Scanner Report** ({datetime.date.today()})")
    print(f"Condition: RSI(14) <= {RSI_THRESHOLD} (Oversold)")
    print("-" * 40)

    signals = []

    # 1. 한국 주식 스캔
    print("🇰🇷 Scanning KOSPI Top 10...")
    for ticker, name in watchlist_kr.items():
        result = analyze_stock(ticker, name, 'KR')
        if result:
            signals.append(result)

    # 2. 미국 주식 스캔
    print("🇺🇸 Scanning S&P 500 Top 10...")
    for ticker, name in watchlist_us.items():
        result = analyze_stock(ticker, name, 'US')
        if result:
            signals.append(result)

    print("-" * 40)
    
    if not signals:
        print("✅ No signals found today. Market is stable.")
    else:
        print(f"🚨 **Found {len(signals)} Signals!**")
        for s in signals:
            icon = "🟢" if "BUY" in s['signal'] else "🔴"
            currency = "KRW" if s['market'] == 'KR' else "USD"
            print(f"{icon} **{s['name']} ({s['ticker']})**")
            print(f"   Signal: {s['signal']}")
            print(f"   RSI: {s['rsi']}")
            print(f"   Price: {s['price']:,.0f} {currency}")
            print("")

if __name__ == "__main__":
    main()



def main():
    print(f"📊 **Stock Scanner Report** ({datetime.date.today()})")
    print(f"Condition: RSI(14) <= {RSI_THRESHOLD} (Oversold)")
    print("-" * 40)

    signals = []

    # 1. 한국 주식 스캔
    print("🇰🇷 Scanning KOSPI Top 10...")
    for ticker, name in watchlist_kr.items():
        result = analyze_stock(ticker, name, 'KR')
        if result:
            signals.append(result)

    # 2. 미국 주식 스캔
    print("🇺🇸 Scanning S&P 500 Top 10...")
    for ticker, name in watchlist_us.items():
        result = analyze_stock(ticker, name, 'US')
        if result:
            signals.append(result)

    print("-" * 40)
    
    if not signals:
        print("✅ No signals found today. Market is stable.")
    else:
        print(f"🚨 **Found {len(signals)} Signals!**")
        for s in signals:
            icon = "🟢" if "BUY" in s['signal'] else "🔴"
            currency = "KRW" if s['market'] == 'KR' else "USD"
            print(f"{icon} **{s['name']} ({s['ticker']})**")
            print(f"   Signal: {s['signal']}")
            print(f"   RSI: {s['rsi']}")
            print(f"   Price: {s['price']:,.0f} {currency}")
            print("")

if __name__ == "__main__":
    main()
