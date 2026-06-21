import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# High-signal event keywords for M&A / corp dev
MATERIAL_EVENT_PATTERNS = [
    (r"\bmerger\b|\bacquisition\b|\b buys \b|\bpurchased\b|\bacquired\b", "M&A", 95),
    (r"\btermination\b|\bcancelled\b|\bterminated\b|\bdiscontinuing\b", "Termination", 90),
    (r"\bpartnership\b|\bjoint venture\b|\bcollaboration\b|\blicense agreement\b", "Partnership", 88),
    (r"\bCEO\b|\bChief Executive\b|\btransition\b|\bresignation\b|\bappointed\b", "Leadership", 85),
    (r"\bbankruptcy\b|\breorganization\b|\breceivership\b|\bliquidation\b", "Bankruptcy", 98),
    (r"\bconsent decree\b|\bsettlement\b|\bjudgment\b|\bfine\b|\bpenalty\b", "Regulatory Action", 92),
    (r"\bIPO\b|\binitial public\b|\bgoing public\b|\bspin-off\b|\bspinoff\b", "Public Market Event", 94),
]

# Ticker-like patterns: NYSE/NASDAQ style 1-5 uppercase, avoid common false positives
TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")

STOPWORDS = {
    "SEC", "EDGAR", "FORM", "ITEM", "EXHIBIT", "COMPANY", "INC",
    "CORP", "LLC", "THE", "AND", "FOR", "WITH", "FROM", "THIS",
    "THAT", "WILL", "NOT", "HAVE", "WERE", "THEIR", "ABOUT", "BEEN",
    "WERE", "HAVE", "THIS", "THAT", "WILL", "YOU", "YOUR", "MORE",
    "SOME", "SUCH", "INTO", "THEM", "THAN", "THEN", "ALSO", "JUST",
}

def extract_tickers(text: str) -> List[str]:
    upper = text.upper()
    candidates = set(TICKER_RE.findall(upper))
    tickers = [t for t in candidates if t not in STOPWORDS and len(t) >= 2]
    return sorted(tickers)[:8]


def classify_event(text: str) -> tuple[str, int]:
    low = text.lower()
    for pattern, label, base_conf in MATERIAL_EVENT_PATTERNS:
        if re.search(pattern, low, re.I):
            return label, base_conf
    return "Material Event", 78


def compute_market_impact(text: str, tickers: List[str]) -> Dict[str, Any]:
    """Heuristic impact score. In production this would pull option flow or correlation."""
    score = 0
    reasons = []
    low = text.lower()
    # verbosity of material event
    for pattern, label, conf in MATERIAL_EVENT_PATTERNS:
        if re.search(pattern, low, re.I):
            score += 15
            reasons.append(label)
            break
    if tickers:
        score += 10
    if any(w in low for w in ("crypto", "bitcoin", "ethereum", "sec", "fed", "rate", "tariff", "sanction")):
        score += 10
    score = min(score, 100)
    tier = "high" if score >= 75 else ("medium" if score >= 40 else "low")
    return {"score": score, "tier": tier, "reasons": reasons}


def enrich_item(item: Dict[str, Any]) -> Dict[str, Any]:
    text = f"{item.get('headline', '')} {' '.join(item.get('bullet_points', []))}"
    tickers = extract_tickers(text)
    event_label, base_conf = classify_event(text)
    impact = compute_market_impact(text, tickers)
    # Blend confidence: source confidence + event confidence + impact
    conf = int((item.get("confidence", 80) * 0.4) + (base_conf * 0.35) + (impact["score"] * 0.25))
    conf = max(60, min(99, conf))
    enriched = dict(item)
    enriched["tickers"] = tickers
    enriched["event_type"] = event_label
    enriched["market_impact"] = impact
    enriched["confidence"] = conf
    return enriched
