import sqlite3
from datetime import datetime
from contextlib import contextmanager
from config import DB_PATH

@contextmanager
def get_db_connection():
    """
    Context manager for SQLite connections that commits transactions on success,
    rolls back on failure, and guarantees the connection is closed.
    """
    conn = sqlite3.connect(str(DB_PATH))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Table 1: research_runs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            run_date TEXT NOT NULL,
            close_price REAL NOT NULL,
            predicted_trend TEXT NOT NULL,
            actual_close_price REAL,
            accuracy_score REAL,
            sentiment_summary TEXT NOT NULL,
            highlights TEXT NOT NULL,
            revision_count INTEGER NOT NULL
        )
        """)
        
        # Table 2: portfolio
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            ticker TEXT PRIMARY KEY,
            added_date TEXT NOT NULL
        )
        """)

def add_to_portfolio(ticker: str):
    ticker = ticker.upper().strip()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO portfolio (ticker, added_date) VALUES (?, ?)",
            (ticker, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

def remove_from_portfolio(ticker: str):
    ticker = ticker.upper().strip()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker,))

def get_portfolio():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticker FROM portfolio ORDER BY ticker")
        return [row[0] for row in cursor.fetchall()]

def save_research_run(ticker: str, run_date: str, close_price: float, predicted_trend: str,
                       sentiment_summary: str, highlights: str, revision_count: int):
    ticker = ticker.upper().strip()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO research_runs (
            ticker, run_date, close_price, predicted_trend, sentiment_summary, highlights, revision_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ticker, run_date, close_price, predicted_trend, sentiment_summary, highlights, revision_count))
        return cursor.lastrowid

def get_pending_predictions(ticker: str):
    ticker = ticker.upper().strip()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, run_date, close_price, predicted_trend 
        FROM research_runs 
        WHERE ticker = ? AND actual_close_price IS NULL
        """, (ticker,))
        return [
            {
                "id": row[0],
                "run_date": row[1],
                "close_price": row[2],
                "predicted_trend": row[3]
            }
            for row in cursor.fetchall()
        ]

def update_prediction_accuracy(run_id: int, actual_close_price: float, accuracy_score: float):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE research_runs 
        SET actual_close_price = ?, accuracy_score = ? 
        WHERE id = ?
        """, (actual_close_price, accuracy_score, run_id))

def get_ticker_context(ticker: str):
    ticker = ticker.upper().strip()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Find latest completed or pending run to show as context
        cursor.execute("""
        SELECT run_date, predicted_trend, highlights, actual_close_price, accuracy_score
        FROM research_runs 
        WHERE ticker = ? 
        ORDER BY run_date DESC, id DESC 
        LIMIT 1
        """, (ticker,))
        row = cursor.fetchone()
        if row:
            return {
                "run_date": row[0],
                "predicted_trend": row[1],
                "highlights": row[2],
                "actual_close_price": row[3],
                "accuracy_score": row[4]
            }
        return None

def get_rolling_accuracy(ticker: str, limit: int = 5):
    ticker = ticker.upper().strip()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT accuracy_score 
        FROM research_runs 
        WHERE ticker = ? AND accuracy_score IS NOT NULL 
        ORDER BY run_date DESC, id DESC 
        LIMIT ?
        """, (ticker, limit))
        rows = cursor.fetchall()
        if not rows:
            return None
        scores = [row[0] for row in rows]
        return sum(scores) / len(scores)

def get_portfolio_status():
    portfolio_tickers = get_portfolio()
    results = []
    # Query within a single connection to optimize resources and avoid nesting locks
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for ticker in portfolio_tickers:
            # Get latest run details
            cursor.execute("""
            SELECT run_date, close_price, predicted_trend, highlights, sentiment_summary
            FROM research_runs 
            WHERE ticker = ? 
            ORDER BY run_date DESC, id DESC 
            LIMIT 1
            """, (ticker,))
            row = cursor.fetchone()
            
            # Get rolling accuracy of last 5 runs
            cursor.execute("""
            SELECT accuracy_score 
            FROM research_runs 
            WHERE ticker = ? AND accuracy_score IS NOT NULL 
            ORDER BY run_date DESC, id DESC 
            LIMIT 5
            """, (ticker,))
            acc_rows = cursor.fetchall()
            rolling_acc = None
            if acc_rows:
                rolling_acc = sum([r[0] for r in acc_rows]) / len(acc_rows)
            
            if row:
                results.append({
                    "ticker": ticker,
                    "last_run_date": row[0],
                    "last_close_price": row[1],
                    "predicted_trend": row[2],
                    "highlights": row[3],
                    "sentiment_summary": row[4],
                    "rolling_accuracy": rolling_acc
                })
            else:
                results.append({
                    "ticker": ticker,
                    "last_run_date": "N/A",
                    "last_close_price": 0.0,
                    "predicted_trend": "N/A",
                    "highlights": "No research run yet.",
                    "sentiment_summary": "N/A",
                    "rolling_accuracy": None
                })
    return results
