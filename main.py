import argparse
import sys
import os
import re
import time
from datetime import datetime
import pandas as pd
import yfinance as yf
from jinja2 import Environment, FileSystemLoader

# Import LocalAlpha modules
import config
from database.manager import (
    init_db,
    add_to_portfolio,
    remove_from_portfolio,
    get_portfolio,
    save_research_run,
    get_ticker_context,
    get_rolling_accuracy,
    get_portfolio_status
)
from indicators.calculator import fetch_and_calculate_indicators, generate_indicators_summary
from utils.search import fetch_latest_news
from agents.orchestrator import run_research_workflow, parse_xml_tag
from visualization.chart import generate_interactive_chart

# Simple markdown-to-HTML parser for LLM text rendering
def markdown_to_html(md_text: str) -> str:
    # Remove HTML tags to prevent injections
    html = re.sub(r'<[^>]*>', '', md_text)
    # Convert headers
    html = re.sub(r'^### (.*?)$', r'<h3 style="margin-top: 1rem; margin-bottom: 0.5rem; color: var(--primary);">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2 style="margin-top: 1.5rem; margin-bottom: 0.75rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.25rem;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*?)$', r'<h1 style="margin-top: 2rem; margin-bottom: 1rem;">\1</h1>', html, flags=re.MULTILINE)
    # Convert bold markdown
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    # Convert bullets
    html = re.sub(r'^\s*-\s+(.*?)$', r'<li style="margin-left: 1.25rem; margin-bottom: 0.5rem;">\1</li>', html, flags=re.MULTILINE)
    # Wrap list items in <ul>
    html = re.sub(r'(<li style=".*?">.*?</li>)+', lambda m: f'<ul style="margin-bottom: 1rem;">{m.group(0)}</ul>', html, flags=re.DOTALL)
    # Convert paragraphs by double newline
    paragraphs = []
    for part in html.split('\n\n'):
        part = part.strip()
        if not part:
            continue
        if part.startswith('<h') or part.startswith('<ul'):
            paragraphs.append(part)
        else:
            paragraphs.append(f'<p style="margin-bottom: 1rem; text-align: justify; color: var(--text-primary);">{part.replace("\n", "<br>")}</p>')
    return '\n'.join(paragraphs)

# Resolves previous runs where actual_close_price is NULL
def resolve_pending_predictions(ticker: str):
    from database.manager import get_pending_predictions, update_prediction_accuracy
    
    pending = get_pending_predictions(ticker)
    if not pending:
        return
        
    print(f"[*] Found {len(pending)} pending prediction(s) for {ticker}. Resolving today...")
    
    # Download pricing to resolve
    ticker_obj = yf.Ticker(ticker)
    earliest_date = min(p["run_date"] for p in pending)
    
    # Fetch historical data starting from the earliest pending run date
    df = ticker_obj.history(start=earliest_date)
    if df.empty:
        print(f"[!] Could not fetch historical data to resolve predictions for {ticker}.")
        return
        
    df.index = df.index.strftime('%Y-%m-%d')
    
    for p in pending:
        run_id = p["id"]
        run_date = p["run_date"]
        initial_price = p["close_price"]
        trend = p["predicted_trend"]
        
        # Check next available trading day's close price (strictly after run_date)
        sub_df = df[df.index > run_date]
        if sub_df.empty:
            print(f"[*] Trading day after {run_date} is not yet completed/available. Keeping pending.")
            continue
            
        actual_price = sub_df['Close'].iloc[0]
        actual_date = sub_df.index[0]
        
        # Evaluate accuracy
        if trend == "Bullish":
            accuracy = 1.0 if actual_price > initial_price else 0.0
        elif trend == "Bearish":
            accuracy = 1.0 if actual_price < initial_price else 0.0
        else:  # Neutral
            accuracy = 0.5
            
        update_prediction_accuracy(run_id, actual_price, accuracy)
        print(f"[+] Resolved prediction ID {run_id} ({run_date}): Initial: ${initial_price:.2f}, "
              f"Actual next close ({actual_date}): ${actual_price:.2f}, Predicted: {trend} -> Score: {accuracy:.1f}")

# Seed historical mock data for testing loops
def execute_backfill(ticker: str):
    from database.manager import save_research_run, update_prediction_accuracy
    ticker = ticker.upper().strip()
    print(f"[*] Seeding historical runs database mock-ups for {ticker} to bootstrap accuracy metrics...")
    
    # We will seed 3 mock entries
    mock_runs = [
        {"date": "2026-06-15", "close": 150.0, "trend": "Bullish", "actual_close": 153.2, "acc": 1.0, "highlights": "- Bullish signals from MA crossovers\n- Robust news catalyst"},
        {"date": "2026-06-16", "close": 153.2, "trend": "Bearish", "actual_close": 155.0, "acc": 0.0, "highlights": "- Bearish RSI divergence\n- Growth projection downgrade"},
        {"date": "2026-06-17", "close": 155.0, "trend": "Bullish", "actual_close": 157.8, "acc": 1.0, "highlights": "- Oversold support bounce\n- Positive sector earnings spillover"}
    ]
    
    for run in mock_runs:
        run_id = save_research_run(
            ticker=ticker,
            run_date=run["date"],
            close_price=run["close"],
            predicted_trend=run["trend"],
            sentiment_summary="Mock sentiment summary for testing feedback loops.",
            highlights=run["highlights"],
            revision_count=1
        )
        update_prediction_accuracy(run_id, run["actual_close"], run["acc"])
        
    print("[+] Backfill complete. Generated 3 historical runs (rolling accuracy: 66.7%).")

# Execution of a single research run
def execute_research_run(ticker: str, industry: str = None, run_date: str = None) -> dict:
    if not run_date:
        run_date = datetime.now().strftime("%Y-%m-%d")
        
    ticker = ticker.upper().strip()
    print(f"\n==========================================")
    print(f"[*] Running LocalAlpha Research for {ticker} ({run_date})")
    print(f"==========================================")
    
    # 1. Resolve past predictions first
    resolve_pending_predictions(ticker)
    
    # 2. Fetch and calculate technical indicators
    print("[*] Fetching historical pricing and calculating indicators...")
    try:
        df, current_price = fetch_and_calculate_indicators(ticker)
    except Exception as e:
        print(f"[!] Error downloading yfinance data for {ticker}: {e}")
        return None
        
    indicators_summary = generate_indicators_summary(df)
    
    # 3. Retrieve DB context
    db_context = get_ticker_context(ticker)
    rolling_accuracy = get_rolling_accuracy(ticker)
    
    hist_context_text = "None"
    if db_context:
        hist_context_text = (
            f"Run date: {db_context['run_date']}, Predicted Trend: {db_context['predicted_trend']}, "
            f"Close Price: ${db_context['actual_close_price'] if db_context['actual_close_price'] else 'N/A'}"
        )
        
    # 4. Fetch news
    print("[*] Scraping news headlines and trends...")
    news_summary = fetch_latest_news(ticker, industry)
    
    # 5. Run LangGraph Workflow
    print("[*] Activating LangGraph multi-agent loop...")
    try:
        final_state = run_research_workflow(
            ticker=ticker,
            run_date=run_date,
            indicators_summary=indicators_summary,
            news_summary=news_summary,
            historical_context=hist_context_text,
            rolling_accuracy=rolling_accuracy
        )
    except Exception as e:
        print(f"[!] Critical Error in LangGraph agents loop: {e}")
        return None
        
    # 6. Generate Plotly Subplot HTML snippet
    print("[*] Drawing interactive charts...")
    chart_div = generate_interactive_chart(df, ticker)
    
    # 7. Compile and save templates
    print("[*] Rendering reports...")
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATES_DIR)))
    
    # Format researcher draft markdown into clean HTML structure
    researcher_draft_html = markdown_to_html(final_state["researcher_draft"])
    
    # Render HTML individual report
    html_template = env.get_template("report_template.html")
    html_report = html_template.render(
        ticker=ticker,
        run_date=run_date,
        provider=config.LLM_PROVIDER,
        model_name=config.OLLAMA_MODEL if config.LLM_PROVIDER == "ollama" else getattr(config, f"{config.LLM_PROVIDER.upper()}_MODEL"),
        close_price=current_price,
        predicted_trend=final_state["predicted_trend"],
        rolling_accuracy=rolling_accuracy,
        historical_context_data=db_context,
        revision_count=final_state["revision_count"],
        chart_div=chart_div,
        researcher_draft_html=researcher_draft_html,
        revision_log=final_state["revision_log"]
    )
    
    html_report_path = config.REPORTS_DIR / f"{ticker}_report_{run_date}.html"
    with open(html_report_path, "w", encoding="utf-8") as f:
        f.write(html_report)
        
    # Render Markdown individual report
    md_template = env.get_template("report_template.md")
    md_report = md_template.render(
        ticker=ticker,
        run_date=run_date,
        provider=config.LLM_PROVIDER,
        model_name=config.OLLAMA_MODEL if config.LLM_PROVIDER == "ollama" else getattr(config, f"{config.LLM_PROVIDER.upper()}_MODEL"),
        close_price=current_price,
        predicted_trend=final_state["predicted_trend"],
        rolling_accuracy=rolling_accuracy,
        indicators_summary=indicators_summary,
        news_summary=news_summary,
        researcher_draft=final_state["researcher_draft"],
        revision_count=final_state["revision_count"],
        revision_log=final_state["revision_log"]
    )
    
    md_report_path = config.REPORTS_DIR / f"{ticker}_report_{run_date}.md"
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write(md_report)
        
    # 8. Record the run inside database
    save_research_run(
        ticker=ticker,
        run_date=run_date,
        close_price=current_price,
        predicted_trend=final_state["predicted_trend"],
        sentiment_summary=parse_xml_tag(final_state["researcher_draft"], "sentiment_summary") or "Sentiment summary resolved by AI agents.",
        highlights=final_state["researcher_draft"],
        revision_count=final_state["revision_count"]
    )
    
    print(f"[+] Saved individual stock report: {html_report_path}")
    print(f"[+] Saved markdown fallback report: {md_report_path}")
    
    return {
        "ticker": ticker,
        "run_date": run_date,
        "predicted_trend": final_state["predicted_trend"],
        "close_price": current_price
    }

# Render consolidated portfolio dashboard report
def render_portfolio_dashboard():
    run_date = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[*] Compiling unified portfolio dashboard HTML...")
    
    status_list = get_portfolio_status()
    
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATES_DIR)))
    template = env.get_template("portfolio_template.html")
    
    dashboard_html = template.render(
        stocks=status_list,
        run_date=run_date
    )
    
    dashboard_path = config.REPORTS_DIR / f"portfolio_report_{run_date}.html"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(dashboard_html)
        
    print(f"[+] Consolidated portfolio report generated at: {dashboard_path}")

# Run scheduled cron tasks
def run_cron_daemon(time_str: str):
    import schedule
    print(f"[*] Starting LocalAlpha scheduled cron daemon...")
    print(f"[*] Trigger frequency: Run portfolio analysis daily at {time_str}")
    print("[*] Press Ctrl+C to terminate the daemon process.")
    
    def job():
        print(f"\n[*] Scheduled trigger fired at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        portfolio = get_portfolio()
        if not portfolio:
            print("[*] Portfolio is empty. Skipping research run.")
            return
            
        for ticker in portfolio:
            execute_research_run(ticker)
        render_portfolio_dashboard()
        
    schedule.every().day.at(time_str).do(job)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n[*] Terminating scheduled cron daemon.")
            sys.exit(0)

# Register OS cron/scheduler details
def setup_os_cron():
    script_path = os.path.abspath(__file__)
    python_exe = sys.executable
    
    print("\n==========================================")
    print("OS Scheduler Settings (Cron Setup)")
    print("==========================================")
    print("\n[LINUX / MACOS (crontab)]")
    print("Add the following entry to your crontab using 'crontab -e':")
    print(f"0 17 * * * {python_exe} {script_path} --portfolio-run")
    print("*(Runs every day at 5:00 PM)")
    
    print("\n[WINDOWS (Task Scheduler)]")
    print("Run the following command in an Administrator PowerShell terminal to register a daily task:")
    print(f'schtasks /create /tn "LocalAlphaDaily" /tr "{python_exe} {script_path} --portfolio-run" /sc daily /st 17:00')
    print("*(Runs every day at 17:00)")
    print("==========================================\n")

# Entrypoint parser logic
def main():
    parser = argparse.ArgumentParser(description="LocalAlpha - Local LLM & Multi-Agent Stock Research Portfolio System.")
    
    # Portfolio commands
    parser.add_argument("--portfolio-add", type=str, help="Add a ticker symbol to the tracked portfolio.")
    parser.add_argument("--portfolio-remove", type=str, help="Remove a ticker symbol from the tracked portfolio.")
    parser.add_argument("--portfolio-list", action="store_true", help="Print all symbols tracked in the portfolio.")
    parser.add_argument("--portfolio-run", action="store_true", help="Run quantitative analysis & agent critique loops on the complete portfolio.")
    
    # Single run commands
    parser.add_argument("--ticker", type=str, help="Analyze a single ticker manually.")
    parser.add_argument("--industry", type=str, help="Broad industry context for the ticker search analysis.")
    
    # Model configuration arguments
    parser.add_argument("--provider", type=str, choices=["ollama", "openai", "gemini", "anthropic"], help="LLM Provider override.")
    parser.add_argument("--api-key", type=str, help="LLM API Key override.")
    parser.add_argument("--model", type=str, help="LLM Model name override.")
    parser.add_argument("--mock", action="store_true", help="Enable simulated mock mode for offline verification.")
    
    # Utility commands
    parser.add_argument("--backfill", type=str, help="Pre-populate mock historical prediction runs for a ticker to bootstrap accuracy metrics.")
    parser.add_argument("--cron", type=str, help="Start persistent scheduler daemon daily at time. Example: '17:00'.")
    parser.add_argument("--setup-cron", action="store_true", help="Generate command lines for setting up standard OS cron jobs.")
    
    args = parser.parse_args()
    
    # Configure dynamic overrides
    if args.provider:
        config.PROVIDER_OVERRIDE = args.provider
    if args.api_key:
        config.API_KEY_OVERRIDE = args.api_key
    if args.model:
        config.MODEL_OVERRIDE = args.model
    if args.mock:
        config.MOCK = True
        print("[*] Simulated mock execution enabled. Nodes will execute simulated research.")
        
    # Verify API key inputs for non-ollama providers
    provider = config.PROVIDER_OVERRIDE or config.LLM_PROVIDER
    if not config.MOCK and provider != "ollama":
        key = config.API_KEY_OVERRIDE or getattr(config, f"{provider.upper()}_API_KEY", None)
        if not key:
            print(f"\n[!] LLM Provider is set to '{provider}', but no API key was found in environment or arguments.")
            try:
                key_input = input(f"Please enter your {provider.upper()} API key: ").strip()
                if not key_input:
                    print("[!] No API key provided. Exiting.")
                    sys.exit(1)
                config.API_KEY_OVERRIDE = key_input
            except (KeyboardInterrupt, EOFError):
                print("\n[!] Input cancelled. Exiting.")
                sys.exit(1)
                
    # Initialize DB
    init_db()
    
    # Execute commands
    if args.portfolio_add:
        add_to_portfolio(args.portfolio_add)
        print(f"[+] Added {args.portfolio_add.upper()} to the research portfolio database.")
        sys.exit(0)
        
    elif args.portfolio_remove:
        remove_from_portfolio(args.portfolio_remove)
        print(f"[-] Removed {args.portfolio_remove.upper()} from the research portfolio database.")
        sys.exit(0)
        
    elif args.portfolio_list:
        portfolio = get_portfolio()
        print(f"\n[*] Current Tracked Portfolio Tickers ({len(portfolio)} symbols):")
        for ticker in portfolio:
            print(f"- {ticker}")
        print()
        sys.exit(0)
        
    elif args.backfill:
        execute_backfill(args.backfill)
        sys.exit(0)
        
    elif args.setup_cron:
        setup_os_cron()
        sys.exit(0)
        
    elif args.cron:
        # Validate time format (HH:MM)
        if not re.match(r"^\d{2}:\d{2}$", args.cron):
            print("[!] Invalid time format for --cron. Use HH:MM format (e.g. '17:30').")
            sys.exit(1)
        run_cron_daemon(args.cron)
        sys.exit(0)
        
    elif args.portfolio_run:
        portfolio = get_portfolio()
        if not portfolio:
            print("[!] Your portfolio is empty. Add stocks first using '--portfolio-add TICKER'.")
            sys.exit(1)
            
        print(f"[*] Starting batch portfolio execution for {len(portfolio)} stocks...")
        for ticker in portfolio:
            try:
                execute_research_run(ticker)
            except Exception as e:
                print(f"[!] Error executing analysis for {ticker}: {e}")
        render_portfolio_dashboard()
        sys.exit(0)
        
    elif args.ticker:
        # Executing a single ticker research run
        res = execute_research_run(args.ticker, args.industry)
        if res:
            # Also compile the portfolio dashboard so that individual links work correctly
            # (Adding the ticker temporarily to show up in dashboard, or just render with whatever exists)
            render_portfolio_dashboard()
        sys.exit(0)
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
