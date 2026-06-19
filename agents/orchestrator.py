import re
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

# Import config and prompts
import config
from agents.prompts import (
    RESEARCHER_SYSTEM_PROMPT,
    RESEARCHER_USER_PROMPT_TEMPLATE,
    REVIEWER_SYSTEM_PROMPT,
    REVIEWER_USER_PROMPT_TEMPLATE
)

# Helper function to parse XML tags from model output
def parse_xml_tag(text: str, tag: str) -> str:
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""

# Definition of the state structure
class AgentState(TypedDict):
    ticker: str
    run_date: str
    indicators_summary: str
    news_summary: str
    historical_context: str
    rolling_accuracy: float
    researcher_draft: str
    predicted_trend: str
    reviewer_critique: str
    approved: bool
    revision_count: int
    revision_log: List[Dict[str, Any]]

# Resilient LLM factory
def get_llm():
    provider = config.PROVIDER_OVERRIDE or config.LLM_PROVIDER
    
    if provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        model = config.MODEL_OVERRIDE or config.OLLAMA_MODEL
        return ChatOllama(
            base_url=config.OLLAMA_BASE_URL,
            model=model,
            temperature=0.2
        )
    elif provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            from langchain_community.chat_models import ChatOpenAI
        key = config.API_KEY_OVERRIDE or config.OPENAI_API_KEY
        model = config.MODEL_OVERRIDE or config.OPENAI_MODEL
        return ChatOpenAI(
            model=model,
            api_key=key,
            temperature=0.2
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        key = config.API_KEY_OVERRIDE or config.ANTHROPIC_API_KEY
        model = config.MODEL_OVERRIDE or config.ANTHROPIC_MODEL
        return ChatAnthropic(
            model_name=model,
            anthropic_api_key=key,
            temperature=0.2
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        key = config.API_KEY_OVERRIDE or config.GEMINI_API_KEY
        model = config.MODEL_OVERRIDE or config.GEMINI_MODEL
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=key,
            temperature=0.2
        )
    else:
        raise ValueError(f"Unknown LLM provider configured: {provider}")

# 1. Researcher Node
def research_node(state: AgentState) -> dict:
    # Handle mock mode execution for offline testing/verification
    if config.MOCK:
        # Search for RSI value in the indicators_summary text
        rsi_match = re.search(r"RSI \(14\): ([\d\.]+)", state["indicators_summary"])
        rsi_val = float(rsi_match.group(1)) if rsi_match else 50.0
        
        if state.get("revision_count", 0) == 0:
            # First draft: if RSI is overbought, intentionally trigger Reviewer critique
            if rsi_val > 70:
                content = f"""
                <analysis>
                <predicted_trend>Bullish</predicted_trend>
                <sentiment_summary>News sentiment is highly positive and indicators suggest powerful upward breakout momentum.</sentiment_summary>
                <highlights>
                - Momentum is accelerating despite overbought readings.
                - Strong industry catalysts drive investor optimism.
                - Technical setup is extremely supportive.
                </highlights>
                <rationale>The stock exhibits extremely strong bullish momentum. Although the RSI is at {rsi_val:.1f} which technically signals an overbought state, the strong news and volume support a continuation of the upward rally, bypassing traditional overbought resistance.</rationale>
                </analysis>
                """
            else:
                content = f"""
                <analysis>
                <predicted_trend>Bullish</predicted_trend>
                <sentiment_summary>News sentiment is constructive with positive growth drivers.</sentiment_summary>
                <highlights>
                - Solid technical indicators showing stable trend.
                - Media coverage indicates rising market share.
                - Institutional demand remains steady.
                </highlights>
                <rationale>The technical indicators and indicators summary are supportive, with RSI at {rsi_val:.1f} in a healthy range. News sentiment is positive, justifying a Bullish outlook.</rationale>
                </analysis>
                """
        else:
            # Revision loop: Researcher corrects predicted trend to Neutral to resolve overbought conditions
            if rsi_val > 70:
                content = f"""
                <analysis>
                <predicted_trend>Neutral</predicted_trend>
                <sentiment_summary>Market sentiment is positive but technical indicators show overextension warnings.</sentiment_summary>
                <highlights>
                - RSI is at {rsi_val:.1f}, indicating extremely overbought conditions.
                - Price is trading near or above the Upper Bollinger Band.
                - Volume support is strong but consolidation is likely.
                </highlights>
                <rationale>Corrected from the previous draft: Although news remains positive, the mathematical indicators (RSI at {rsi_val:.1f} and Upper Bollinger Band resistance) indicate that the stock is severely overbought and due for consolidation. A Neutral trend is predicted in the short term to account for overextension risks.</rationale>
                </analysis>
                """
            else:
                content = f"""
                <analysis>
                <predicted_trend>Bullish</predicted_trend>
                <sentiment_summary>Market sentiment is highly positive with strong breakout structures.</sentiment_summary>
                <highlights>
                - Technical indicators confirm a stable upward trend.
                - Positive news headlines support growth projections.
                - Crossover confirmed on MACD.
                </highlights>
                <rationale>Addressing reviewer comments: Checked all key technical indicators and verified that RSI at {rsi_val:.1f} is well within neutral parameters. Momentum indicators match the qualitative highlights, justifying a Bullish trend.</rationale>
                </analysis>
                """
    else:
        from langchain_core.messages import SystemMessage, HumanMessage
        
        llm = get_llm()
        
        # Prepare revision critique if this is a correction loop
        revision_instruction = ""
        if state.get("revision_count", 0) > 0:
            revision_instruction = (
                f"\nREVISION REQUEST: The Reviewer audited your previous draft and rejected it with the following critique:\n"
                f"'{state.get('reviewer_critique')}'\n"
                f"Please revise your analysis to address this critique. Check for logical consistency between text claims and mathematical indicators."
            )
            
        user_prompt = RESEARCHER_USER_PROMPT_TEMPLATE.format(
            ticker=state["ticker"],
            run_date=state["run_date"],
            indicators_summary=state["indicators_summary"],
            news_summary=state["news_summary"],
            historical_context=state["historical_context"],
            rolling_accuracy=f"{state['rolling_accuracy']:.2%}" if state["rolling_accuracy"] is not None else "N/A (First Run)",
            revision_instruction=revision_instruction
        )
        
        messages = [
            SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content
    
    # Parse outputs
    predicted_trend = parse_xml_tag(content, "predicted_trend")
    if not predicted_trend or predicted_trend.lower() not in ["bullish", "bearish", "neutral"]:
        # Fallback to regex text search
        lower_content = content.lower()
        if "bullish" in lower_content:
            predicted_trend = "Bullish"
        elif "bearish" in lower_content:
            predicted_trend = "Bearish"
        else:
            predicted_trend = "Neutral"
            
    sentiment_summary = parse_xml_tag(content, "sentiment_summary")
    if not sentiment_summary:
        sentiment_summary = "News and trend sentiment is neutral or could not be parsed."
        
    highlights = parse_xml_tag(content, "highlights")
    if not highlights:
        highlights = "- Strong market volatility noted.\n- Technical patterns present mixed signals."
        
    rationale = parse_xml_tag(content, "rationale")
    if not rationale:
        rationale = content  # Fallback to full response content if tag missing
        
    predicted_trend = predicted_trend.capitalize()
    
    draft = f"### Sentiment Summary\n{sentiment_summary}\n\n### Highlights\n{highlights}\n\n### Rationale\n{rationale}"
    
    return {
        "researcher_draft": draft,
        "predicted_trend": predicted_trend
    }

# 2. Reviewer Node
def reviewer_node(state: AgentState) -> dict:
    # Handle mock mode execution for offline testing/verification
    if config.MOCK:
        trend = state.get("predicted_trend", "Neutral")
        rsi_match = re.search(r"RSI \(14\): ([\d\.]+)", state["indicators_summary"])
        rsi_val = float(rsi_match.group(1)) if rsi_match else 50.0
        
        # Critique if Researcher claims Bullish while RSI is overbought (>70) on the first draft
        if trend == "Bullish" and rsi_val > 70 and state.get("revision_count", 0) == 0:
            content = f"""
            <review>
            <approved>False</approved>
            <critique>The Researcher predicted a Bullish trend, but the RSI is at {rsi_val:.1f} which is in the overbought zone (>70). This is a logical contradiction. Please revise the predicted trend to Neutral or Bearish to reflect technical resistance and consolidation risk.</critique>
            </review>
            """
        else:
            content = """
            <review>
            <approved>True</approved>
            <critique>Approved. The qualitative text matches the mathematical indicators. RSI and Bollinger Band ranges are aligned with the predicted trend.</critique>
            </review>
            """
    else:
        from langchain_core.messages import SystemMessage, HumanMessage
        
        llm = get_llm()
        
        user_prompt = REVIEWER_USER_PROMPT_TEMPLATE.format(
            indicators_summary=state["indicators_summary"],
            researcher_draft=state["researcher_draft"]
        )
        
        messages = [
            SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content
    
    # Parse Reviewer tags
    approved_str = parse_xml_tag(content, "approved")
    approved = approved_str.lower().strip() == "true"
    
    critique = parse_xml_tag(content, "critique")
    if not critique:
        critique = "Approved" if approved else "Indicator contradictions identified in text analysis."
        
    new_revision_log = list(state.get("revision_log") or [])
    new_revision_log.append({
        "revision": state.get("revision_count", 0),
        "draft": state.get("researcher_draft", ""),
        "predicted_trend": state.get("predicted_trend", "Neutral"),
        "critique": critique,
        "approved": approved
    })
    
    next_revision_count = state.get("revision_count", 0)
    if not approved:
        next_revision_count += 1
        
    return {
        "approved": approved,
        "reviewer_critique": critique,
        "revision_log": new_revision_log,
        "revision_count": next_revision_count
    }

# 3. Router Edge Logic
def should_continue(state: AgentState):
    if state.get("approved") is True:
        return "end"
    if state.get("revision_count", 0) >= 2:
        return "end"
    return "continue"

# Graph builder
def build_research_graph():
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("researcher", research_node)
    workflow.add_node("reviewer", reviewer_node)
    
    # Set Entry Point
    workflow.set_entry_point("researcher")
    
    # Define Transitions
    workflow.add_edge("researcher", "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        should_continue,
        {
            "continue": "researcher",
            "end": END
        }
    )
    
    return workflow.compile()

# Workflow Execution Entrypoint
def run_research_workflow(ticker: str, run_date: str, indicators_summary: str,
                          news_summary: str, historical_context: str, rolling_accuracy: float) -> dict:
    graph = build_research_graph()
    
    initial_state = {
        "ticker": ticker.upper().strip(),
        "run_date": run_date,
        "indicators_summary": indicators_summary,
        "news_summary": news_summary,
        "historical_context": historical_context or "No previous runs recorded for context.",
        "rolling_accuracy": rolling_accuracy,
        "researcher_draft": "",
        "predicted_trend": "Neutral",
        "reviewer_critique": "",
        "approved": False,
        "revision_count": 0,
        "revision_log": []
    }
    
    # Execute Graph
    final_state = graph.invoke(initial_state)
    return final_state
