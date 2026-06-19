# LocalAlpha AI Research Report: {{ ticker }}
**Execution Date:** {{ run_date }}
**Model Engine:** {{ provider }} ({{ model_name }})

---

## 1. Executive Summary
* **Reference Price:** ${{ "%.2f"|format(close_price) }}
* **Predicted Trend:** **{{ predicted_trend }}**
* **Rolling Accuracy Score (5-Run):** {% if rolling_accuracy is not none %}{{ "%.1f"|format(rolling_accuracy * 100) }}%{% else %}N/A (First Run/No Data){% endif %}
* **Agentic Reflection Cycles:** {{ revision_count }} / 2 Correction Loops

---

## 2. Technical Indicators Status
{{ indicators_summary }}

---

## 3. Broader Market & News Context
{{ news_summary }}

---

## 4. AI Agent Analysis & Synthesis
{{ researcher_draft }}

---

## 5. Reflection & Verification Logs
{% for log in revision_log %}
### Cycle {{ log.revision }}: Research Analysis Drafted
* **Trend Prediction Drafted:** {{ log.predicted_trend }}
* **Reviewer Audit Status:** {% if log.approved %}APPROVED{% else %}REJECTED BY REVIEWER{% endif %}
{% if not log.approved %}
* **Reviewer Critique Details:** 
  {{ log.critique }}
{% else %}
* **Reviewer Audit Details:** Mathematical validation confirmed complete compliance with technical indicators.
{% endif %}

---
{% endfor %}

---
*Report compiled automatically by LocalAlpha.*
