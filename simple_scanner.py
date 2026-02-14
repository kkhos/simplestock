import json
import urllib.request
import datetime
import ssl
import time
import math

# SSL 인증서 오류 방지
ssl._create_default_https_context = ssl._create_unverified_context

# --- 설정 ---
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD_DEV = 2

# --- 감시 대상 (Top 100) ---
tickers_kr = [
    '005930.KS', '373220.KS', '000660.KS', '207940.KS', '005380.KS',
    '006400.KS', '051910.KS', '000270.KS', '035420.KS', '035720.KS',
    '005490.KS', '012330.KS', '028260.KS', '105560.KS', '055550.KS',
    '068270.KS', '032830.KS', '096770.KS', '003550.KS', '015760.KS',
    '034020.KS', '086790.KS', '033780.KS', '009150.KS', '017670.KS',
    '018260.KS', '010130.KS', '003490.KS', '034730.KS', '036570.KS',
    '009830.KS', '011200.KS', '051900.KS', '090430.KS', '010950.KS',
    '000810.KS', '024110.KS', '030200.KS', '011170.KS', '011070.KS',
    '005830.KS', '034220.KS', '001450.KS', '004020.KS', '047810.KS',
    '028050.KS', '000100.KS', '071050.KS', '086280.KS', '002790.KS'
]

tickers_us = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX', 'AMD', 'INTC',
    'AVGO', 'CSCO', 'PEP', 'COST', 'TMUS', 'ADBE', 'TXN', 'CMCSA', 'QCOM', 'HON',
    'INTU', 'AMGN', 'SBUX', 'GILD', 'MDLZ', 'BKNG', 'ADI', 'ADP', 'ISRG', 'REGN',
    'VRTX', 'FISV', 'LRCX', 'ATVI', 'MU', 'MELI', 'CSX', 'PANW', 'MRNA', 'SNPS',
    'CDNS', 'ASML', 'KLAC', 'MAR', 'CTAS', 'KDP', 'AEP', 'NXPI', 'ORLY', 'DXCM'
]

watchlist = [{'ticker': t, 'market': 'KR'} for t in tickers_kr] + \
            [{'ticker': t, 'market': 'US'} for t in tickers_us]

def get_price_history(ticker):
    """Yahoo Finance API 호출"""
    # 충분한 데이터 확보 (MACD, 볼린저 밴드 계산 위해 6개월치)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=6mo"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            result = data['chart']['result'][0]
            quote = result['indicators']['quote'][0]
            closes = quote['close']
            return [c for c in closes if c is not None]
        except Exception:
            time.sleep(1)
    return []

def calculate_indicators(prices):
    """RSI, MACD, Bollinger Band 계산"""
    if len(prices) < 50: return None # 데이터 부족

    # 1. RSI
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        if delta > 0: gains.append(delta); losses.append(0)
        else: gains.append(0); losses.append(abs(delta))
    
    avg_gain = sum(gains[:RSI_PERIOD]) / RSI_PERIOD
    avg_loss = sum(losses[:RSI_PERIOD]) / RSI_PERIOD
    
    rsi = 100 - (100 / (1 + (avg_gain / avg_loss if avg_loss != 0 else 0)))
    
    for i in range(RSI_PERIOD, len(gains)):
        avg_gain = (avg_gain * (RSI_PERIOD - 1) + gains[i]) / RSI_PERIOD
        avg_loss = (avg_loss * (RSI_PERIOD - 1) + losses[i]) / RSI_PERIOD
        rsi = 100 - (100 / (1 + (avg_gain / avg_loss if avg_loss != 0 else 0)))

    # 2. MACD (EMA 방식)
    def ema(data, period):
        k = 2 / (period + 1)
        res = [data[0]]
        for i in range(1, len(data)):
            res.append(data[i] * k + res[-1] * (1-k))
        return res

    ema_12 = ema(prices, MACD_FAST)
    ema_26 = ema(prices, MACD_SLOW)
    macd_line = [a - b for a, b in zip(ema_12, ema_26)] # MACD Line
    signal_line = ema(macd_line, MACD_SIGNAL)           # Signal Line
    
    # 3. Bollinger Bands (SMA 방식)
    sma_20 = sum(prices[-BB_PERIOD:]) / BB_PERIOD
    variance = sum([(x - sma_20) ** 2 for x in prices[-BB_PERIOD:]]) / BB_PERIOD
    std_dev = math.sqrt(variance)
    
    upper_band = sma_20 + (std_dev * BB_STD_DEV)
    lower_band = sma_20 - (std_dev * BB_STD_DEV)

    return {
        'rsi': rsi,
        'macd': macd_line[-1],
        'signal': signal_line[-1],
        'macd_prev': macd_line[-2],
        'signal_prev': signal_line[-2],
        'upper': upper_band,
        'lower': lower_band,
        'price': prices[-1]
    }

def analyze_stock(ticker, market):
    prices = get_price_history(ticker)
    if not prices: return None
    
    ind = calculate_indicators(prices)
    if not ind: return None
    
    score = 0
    reasons = []
    
    # 1. RSI (30점)
    if ind['rsi'] <= 30:
        score += 30
        reasons.append(f"RSI 과매도({ind['rsi']:.1f})")
    elif ind['rsi'] <= 40:
        score += 15
        reasons.append(f"RSI 저점({ind['rsi']:.1f})")

    # 2. MACD (40점) - 골든크로스 발생
    # (어제는 MACD < Signal 이었는데, 오늘은 MACD > Signal)
    if ind['macd_prev'] < ind['signal_prev'] and ind['macd'] > ind['signal']:
        score += 40
        reasons.append("MACD 골든크로스(상승전환)")
    elif ind['macd'] > ind['signal']:
        score += 10 # 정배열 유지 중

    # 3. Bollinger Band (30점) - 하단 터치 근접
    pct_b = (ind['price'] - ind['lower']) / (ind['upper'] - ind['lower'])
    if pct_b <= 0.05: # 하단 밴드 5% 이내 근접
        score += 30
        reasons.append("볼린저밴드 하단 터치(반등기대)")
    elif pct_b >= 1.0: # 상단 돌파
        score -= 20 # 과매수 경고
        reasons.append("볼린저밴드 상단 돌파(과열)")

    return {
        'ticker': ticker,
        'market': market,
        'price': ind['price'],
        'score': score,
        'reasons': reasons,
        'indicators': ind
    }

def main():
    print(f"📊 **Smart Stock Radar (MACD+RSI+Bollinger)**")
    print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    strong_buys = []
    buys = []
    
    total = len(watchlist)
    
    for idx, item in enumerate(watchlist):
        if idx % 10 == 0: time.sleep(1) # 부하 조절
            
        res = analyze_stock(item['ticker'], item['market'])
        if not res: continue
        
        if res['score'] >= 60: # 강력 매수
            strong_buys.append(res)
        elif res['score'] >= 40: # 매수 관심
            buys.append(res)

    # 결과 출력
    if not strong_buys and not buys:
        print("✅ **특이사항 없음** (뚜렷한 매수 신호 미포착)")
    else:
        if strong_buys:
            print(f"\n🚀 **STRONG BUY (Score 60+)**")
            for s in strong_buys:
                currency = "₩" if s['market'] == 'KR' else "$"
                print(f"**{s['ticker']}** ({currency}{s['price']:,.0f})")
                print(f"   Score: {s['score']}점 / {', '.join(s['reasons'])}")
                
        if buys:
            print(f"\n👀 **Watch List (Score 40+)**")
            for s in buys[:5]: # 너무 많으면 5개만
                currency = "₩" if s['market'] == 'KR' else "$"
                print(f"- **{s['ticker']}**: {', '.join(s['reasons'])}")

if __name__ == "__main__":
    main()
