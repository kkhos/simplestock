import yfinance as yf
import pandas as pd
import subprocess
import sys
import math
import os

def calculate_indicators(prices):
    if len(prices) < 50: return None
    # RSI
    RSI_PERIOD = 14
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        if delta > 0: gains.append(delta); losses.append(0)
        else: gains.append(0); losses.append(abs(delta))
    
    avg_gain = sum(gains[:RSI_PERIOD]) / RSI_PERIOD
    avg_loss = sum(losses[:RSI_PERIOD]) / RSI_PERIOD
    
    if avg_loss == 0:
        rsi = 100
    else:
        rsi = 100 - (100 / (1 + (avg_gain / avg_loss)))
    
    for i in range(RSI_PERIOD, len(gains)):
        avg_gain = (avg_gain * (RSI_PERIOD - 1) + gains[i]) / RSI_PERIOD
        avg_loss = (avg_loss * (RSI_PERIOD - 1) + losses[i]) / RSI_PERIOD
        if avg_loss == 0:
            rsi = 100
        else:
            rsi = 100 - (100 / (1 + (avg_gain / avg_loss)))

    # MACD
    def ema(data, period):
        k = 2 / (period + 1)
        res = [data[0]]
        for i in range(1, len(data)):
            res.append(data[i] * k + res[-1] * (1-k))
        return res
    
    ema_12 = ema(prices, 12)
    ema_26 = ema(prices, 26)
    macd_line = [a - b for a, b in zip(ema_12, ema_26)]
    signal_line = ema(macd_line, 9)

    # BB
    BB_PERIOD = 20
    BB_STD_DEV = 2
    sma_20 = sum(prices[-BB_PERIOD:]) / BB_PERIOD
    variance = sum([(x - sma_20) ** 2 for x in prices[-BB_PERIOD:]]) / BB_PERIOD
    std_dev = math.sqrt(variance)
    upper_band = sma_20 + (std_dev * BB_STD_DEV)
    lower_band = sma_20 - (std_dev * BB_STD_DEV)

    return {
        'price': prices[-1],
        'rsi': rsi,
        'macd': macd_line[-1],
        'signal': signal_line[-1],
        'macd_prev': macd_line[-2],
        'signal_prev': signal_line[-2],
        'upper': upper_band,
        'lower': lower_band,
        'sma20': sma_20
    }

def get_stock_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        if df.empty:
            return None
        closes = df['Close'].tolist()
        inds = calculate_indicators(closes)
        if inds:
            inds['ticker'] = ticker
        return inds
    except:
        return None

def main():
    if len(sys.argv) < 4:
        print("사용법: python3 compare_stocks.py TICKER1 TICKER2 TICKER3")
        sys.exit(1)
    
    tickers = sys.argv[1:4]
    print(f"[{tickers[0]}, {tickers[1]}, {tickers[2]}] 데이터 수집 및 분석 중...")
    
    data = []
    for t in tickers:
        info = get_stock_info(t)
        if info:
            data.append(info)
        else:
            print(f"경고: {t} 의 데이터를 가져올 수 없습니다.")
            
    if len(data) < 2:
        print("비교할 데이터가 부족합니다.")
        return

    data_str = ""
    for d in data:
        data_str += f"- Ticker: {d['ticker']}\n"
        data_str += f"  Price: {d['price']:.2f}\n"
        data_str += f"  RSI (14): {d['rsi']:.2f}\n"
        data_str += f"  MACD Line: {d['macd']:.2f}, Signal Line: {d['signal']:.2f} (Prev MACD: {d['macd_prev']:.2f}, Prev Signal: {d['signal_prev']:.2f})\n"
        data_str += f"  Bollinger Bands: Lower {d['lower']:.2f}, Mid {d['sma20']:.2f}, Upper {d['upper']:.2f}\n\n"

    prompt = f"""
당신은 'AI 투자 위원회(AI Investment Committee)'의 최고 의장입니다.
이 위원회는 서로 다른 투자 성향을 가진 두 명의 전문가(Expert)와 최종 결정을 내리는 의장(Moderator)으로 구성되어 있습니다.

[위원회 구성원 소개]
1. 전문가 A (The Chartist - 수석 기술적 전략가)
- 성향: 예리함(Sharp), 타이밍 중시(Timing), 단기/중기 추세 추종.
- 역할: 현재 당장의 '매수/매도 타이밍'과 '패턴'을 찾습니다. "지금 들어가야 수익을 낸다"고 주장하며 상승 목표가에 집중합니다.

2. 전문가 B (The Believer - 장기 투자자 & 매집 전략가)
- 성향: 진득함(Patient), 조정 시 매수(Buy the Dip) 전문가.
- 역할: 대세 상승장이나 하락장에서의 '바겐세일(추가 매수 기회)'을 찾아냅니다. 단기 변동성보다는 장기적 관점에서 비중 확대의 관점을 제시합니다.

3. 의장 (The Moderator - 당신의 역할)
- 두 전문가(A와 B)의 팽팽한 의견을 종합하여, 가장 매수하기 좋은 종목 1픽을 선정하고 클라이언트에게 최종 리포트를 제출합니다.

클라이언트가 다음 제시된 주식들 중 하나를 매수하려고 합니다. 제공된 기술적 지표를 바탕으로 두 전문가의 가상 토론을 거친 후, 최종적으로 가장 매수하기 좋은 종목 딱 1개를 선택하고 리포트를 작성하십시오.

[분석 대상 종목의 기술적 데이터]
{data_str}

[분석 가이드라인]
1. 각 종목의 RSI(과매도/과매수 여부), MACD(추세 전환 여부, 골든크로스 등), 볼린저 밴드(현재 가격이 밴드 하단에 가까운지 상단에 가까운지)를 정밀하게 비교하십시오.
2. 현재 시점에서 단기 상승 잠재력이 가장 높거나, 하방 리스크가 적어 '가장 진입하기 좋은 1픽(Top Pick)'을 명확히 꼽아주십시오.
3. 나머지 종목들은 왜 1픽에서 밀렸는지, 현재 기술적 위치의 한계나 리스크가 무엇인지 설명하십시오.
4. 전문적이고 단호한 톤으로 리포트를 작성하십시오.

[출력 양식]
## 🏆 AI 투자 위원회: 종목 비교 분석 리포트

### 🗣️ 위원회 난상 토론 요약
- **전문가 A (기술적 관점)**: (각 종목의 단기 타이밍에 대한 코멘트 1~2줄)
- **전문가 B (매집 관점)**: (각 종목의 장기 매수 기회에 대한 코멘트 1~2줄)

### 🥇 Top Pick (가장 추천하는 종목)
- **종목명**: 
- **현재가**: 
- **의장의 추천 사유**: (기술적 근거 3가지 이상 상세 설명)

### 📊 나머지 종목 분석
- **[종목명2] 평가**: (현재 상태 및 Top Pick에서 밀린 이유)
- **[종목명3] 평가**: (현재 상태 및 Top Pick에서 밀린 이유)

### 💡 최종 매매 전략 (Top Pick 기준)
- **진입 전략**: (예: 현재가 부근 분할 매수, 볼린저 하단 지지 확인 후 매수 등)
- **리스크 관리**: (어떤 지표가 무너지면 손절해야 하는지)
"""
    try:
        my_env = os.environ.copy()
        my_env["PATH"] = my_env.get("PATH", "") + ":/usr/sbin:/sbin"
        
        result = subprocess.run(['gemini', '-p', prompt], capture_output=True, text=True, env=my_env)
        if result.returncode == 0:
            print("\n" + "="*50)
            print(result.stdout)
            print("="*50 + "\n")
        else:
            print(f"gemini 실행 중 오류 발생:\n{result.stderr}")
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()