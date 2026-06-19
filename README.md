# LocalAlpha 📈

LocalAlpha is a local, CLI-executable Python application that automates stock and industry research. It combines quantitative mathematical analysis (technical indicators) with qualitative market intelligence (web news scraping) using a local LLM or API keys. 

The application utilizes **LangGraph** to manage a multi-agent reflection cycle (Researcher + Reviewer), compiles an interactive multi-tier **Plotly** subplot chart, tracks historical predictions in a **SQLite** database to evaluate accuracy over time, and generates a polished **Jinja2** HTML portfolio dashboard.

---

## 🛠️ Technology Stack
* **LLM Engine:** Ollama (running `llama3.2` or `mistral` locally) or external API keys (OpenAI, Gemini, Anthropic).
* **Orchestration:** LangGraph (for state-centric agent loops and conditional edges).
* **Quantitative Math:** `yfinance` (market data feed) and `pandas_ta` (Bollinger Bands, RSI, MACD calculation).
* **Visualization:** Plotly (for interactive HTML charts and synchronized subplots).
* **Database & State:** SQLite (for user portfolio tracking, prediction logging, and rolling accuracy feedback).
* **Templating:** Jinja2 (compiling interactive stock reports and unified portfolio summary pages).

---

## 🚀 Quick Start Guide

### 1. Installation
Clone the repository and install all dependencies:
```bash
python -m pip install -r requirements.txt
```
*Dependencies are listed in [requirements.txt](file:///D:/distributed-crawler/LocalAlpha/requirements.txt).*

### 2. Seeding Sandbox Data (Highly Recommended)
Since prediction tracking calculates accuracy based on previous trading days' price movements, seed the database with simulated historical runs to immediately bootstrap rolling accuracy metrics:
```bash
python main.py --backfill AAPL
python main.py --backfill NVDA
```

### 3. Dry-Run Verification (Offline Mode)
Verify the entire system end-to-end (scrapers, database connections, indicators, Plotly charting, LangGraph revision loops, and Jinja2 rendering) offline:
```bash
python main.py --ticker AAPL --mock
```
*Check the compiled HTML report in the generated `reports/AAPL_report_YYYY-MM-DD.html` file.*

---

## 💻 CLI Commands Usage Reference

### Portfolio Management
Manage your tracked stock assets list within the SQLite database:
```bash
# Add a stock symbol to the portfolio
python main.py --portfolio-add AAPL
python main.py --portfolio-add NVDA

# List all currently tracked portfolio symbols
python main.py --portfolio-list

# Remove a symbol
python main.py --portfolio-remove AAPL
```

### Execution Commands
```bash
# Run analysis on a single stock using local Ollama
python main.py --ticker AAPL --provider ollama

# Run analysis on a single stock using Gemini (prompts for key if missing)
python main.py --ticker AAPL --provider gemini

# Run batch research loops sequentially on all portfolio stocks
python main.py --portfolio-run --mock
```

### Scheduling & Automation
To schedule recurring portfolio updates (e.g. triggered by cron jobs or task schedulers):
```bash
# Start a persistent daemon executing daily portfolio analysis at 5:00 PM
python main.py --cron "17:00"

# Print task scheduler creation lines for Linux/macOS (cron) or Windows (Task Scheduler)
python main.py --setup-cron
```

---

## 📁 Project Directory Layout
* [main.py](file:///D:/distributed-crawler/LocalAlpha/main.py): CLI interface, batch workflow manager, and report assembler.
* [config.py](file:///D:/distributed-crawler/LocalAlpha/config.py): Configuration settings (base paths, default LLM, credentials).
* [database/manager.py](file:///D:/distributed-crawler/LocalAlpha/database/manager.py): SQLite session context managers, run logs, and rolling accuracy algorithms.
* [indicators/calculator.py](file:///D:/distributed-crawler/LocalAlpha/indicators/calculator.py): Technical indicator computations (Bollinger Bands, RSI, MACD).
* [agents/orchestrator.py](file:///D:/distributed-crawler/LocalAlpha/agents/orchestrator.py): LangGraph node declarations, routing conditional edges, and mock agent simulations.
* [agents/prompts.py](file:///D:/distributed-crawler/LocalAlpha/agents/prompts.py): System instructions and prompt templates.
* [visualization/chart.py](file:///D:/distributed-crawler/LocalAlpha/visualization/chart.py): Plotly subplots compiler overlaying candlestick charts and oscillators.
* [utils/search.py](file:///D:/distributed-crawler/LocalAlpha/utils/search.py): DuckDuckGo news scraper.
* **`templates/`**: HTML/Markdown Jinja2 report templates ([Individual Report](file:///D:/distributed-crawler/LocalAlpha/templates/report_template.html), [Portfolio Dashboard](file:///D:/distributed-crawler/LocalAlpha/templates/portfolio_template.html)).
* **`reports/`**: Destination directory for compiled HTML/MD analysis reports.