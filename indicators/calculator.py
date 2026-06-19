import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

def fetch_and_calculate_indicators(ticker_symbol: str, period: str = "60d"):
    """
    Downloads historical market data using yfinance and computes Bollinger Bands,
    RSI, and MACD using pandas_ta.
    """
    ticker_symbol = ticker_symbol.upper().strip()
    ticker = yf.Ticker(ticker_symbol)
    
    # Fetch historical daily data
    df = ticker.history(period=period)
    
    if df.empty:
        raise ValueError(f"No historical market data found for ticker '{ticker_symbol}'.")
        
    current_price = df['Close'].iloc[-1]
    
    # Calculate Bollinger Bands (length=20, std=2)
    # Adds BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
    bb = df.ta.bbands(length=20, std=2)
    if bb is not None:
        df = pd.concat([df, bb], axis=1)
        
    # Calculate RSI (length=14)
    # Adds RSI_14
    rsi = df.ta.rsi(length=14)
    if rsi is not None:
        df = pd.concat([df, rsi], axis=1)
        
    # Calculate MACD (fast=12, slow=26, signal=9)
    # Adds MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)
        
    return df, current_price

def generate_indicators_summary(df: pd.DataFrame) -> str:
    """
    Parses the latest row of the DataFrame into a structured text prompt for the LLM.
    """
    last_row = df.iloc[-1]
    close = last_row.get("Close", 0.0)
    
    # Bollinger Bands
    bbl = last_row.get("BBL_20_2.0")
    bbm = last_row.get("BBM_20_2.0")
    bbu = last_row.get("BBU_20_2.0")
    
    # RSI
    rsi = last_row.get("RSI_14")
    
    # MACD
    macd_val = last_row.get("MACD_12_26_9")
    macd_sig = last_row.get("MACDs_12_26_9")
    macd_hist = last_row.get("MACDh_12_26_9")
    
    bb_summary = "N/A"
    if bbl is not None and bbm is not None and bbu is not None:
        position = "within bands"
        if close > bbu:
            position = "above Upper Band (Overextended/Overbought)"
        elif close < bbl:
            position = "below Lower Band (Support/Oversold)"
        bb_summary = f"Upper: {bbu:.2f}, Middle (SMA 20): {bbm:.2f}, Lower: {bbl:.2f} (Current price is {position})"
        
    rsi_summary = "N/A"
    if rsi is not None:
        rsi_desc = "Neutral"
        if rsi >= 70:
            rsi_desc = "Overbought (Bearish indicator)"
        elif rsi <= 30:
            rsi_desc = "Oversold (Bullish reversal indicator)"
        rsi_summary = f"{rsi:.2f} ({rsi_desc})"
        
    macd_summary = "N/A"
    if macd_val is not None and macd_sig is not None and macd_hist is not None:
        crossover = "Neutral"
        if macd_hist > 0:
            crossover = "Bullish (MACD Line crossed above Signal Line)"
        elif macd_hist < 0:
            crossover = "Bearish (MACD Line crossed below Signal Line)"
        macd_summary = f"MACD: {macd_val:.4f}, Signal: {macd_sig:.4f}, Histogram: {macd_hist:.4f} ({crossover})"
        
    summary = (
        f"Technical Indicators (Latest Close: ${close:.2f}):\n"
        f"- Bollinger Bands (20, 2): {bb_summary}\n"
        f"- RSI (14): {rsi_summary}\n"
        f"- MACD (12, 26, 9): {macd_summary}\n"
    )
    return summary
