import yfinance as yf
import pandas as pd
import csv
import os
from datetime import datetime

def check_portfolio():
    trade_log_file = 'paper_trades.csv'
    
    if not os.path.exists(trade_log_file):
        print("📭 아직 가상 매매 기록(paper_trades.csv)이 없습니다.")
        return

    df = pd.read_csv(trade_log_file)
    if df.empty:
        print("📭 가상 매매 기록이 비어있습니다.")
        return

    print(f"📈 **가상 포트폴리오 수익률 중간 점검 (Paper Trading)**")
    print(f"기준일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)

    total_profit_pct = 0
    active_trades = 0

    for index, row in df.iterrows():
        ticker = row['Ticker']
        entry_price = float(row['Entry_Price'])
        trade_type = row['Type']
        sl = float(row['SL'])
        tp = float(row['TP'])
        
        # 현재가 조회
        try:
            stock = yf.Ticker(ticker)
            current_price = stock.history(period="1d")['Close'].iloc[-1]
        except Exception as e:
            print(f"⚠️ {ticker} 현재가 조회 실패: {e}")
            continue
            
        # 롱 / 숏에 따른 수익률 계산
        if "SHORT" in trade_type:
            # 숏은 가격이 내려가야 수익
            profit_pct = ((entry_price - current_price) / entry_price) * 100
        else:
            # 롱은 가격이 올라가야 수익
            profit_pct = ((current_price - entry_price) / entry_price) * 100

        total_profit_pct += profit_pct
        active_trades += 1
        
        currency = "₩" if row['Market'] == 'KR' else "$"
        
        # 청산 조건 확인
        status = "🟢 진행중"
        if "LONG" in trade_type:
            if current_price <= sl:
                status = "🛑 손절(SL) 도달"
            elif current_price >= tp:
                status = "🎯 익절(TP) 도달"
        else: # SHORT
            if current_price >= sl:
                status = "🛑 숏 스퀴즈 손절(SL)"
            elif current_price <= tp:
                status = "🎯 숏 커버링 익절(TP)"

        icon = "🚀" if "LONG" in trade_type else "🩸"
        sign = "+" if profit_pct > 0 else ""
        
        print(f"{icon} [{row['Date']}] {row['Name']} ({ticker}) - {trade_type}")
        print(f"   진입가: {currency}{entry_price:,.2f}  ->  현재가: {currency}{current_price:,.2f} ({status})")
        print(f"   수익률: {sign}{profit_pct:.2f}% (SL: {currency}{sl:,.2f} / TP: {currency}{tp:,.2f})")
        print(f"   진입근거: {row['Reasons']}")
        print("")

    print("-" * 70)
    if active_trades > 0:
        avg_profit = total_profit_pct / active_trades
        sign = "+" if avg_profit > 0 else ""
        print(f"💰 **포트폴리오 평균 수익률: {sign}{avg_profit:.2f}%**")

if __name__ == "__main__":
    check_portfolio()
