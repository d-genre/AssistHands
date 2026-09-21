from pydantic import BaseModel
from typing import List, Dict, Any

class RiskAssessment(BaseModel):
    risk_level: str = "SAFE" # "SAFE", "MODERATE", "CRITICAL"
    flag_reason: str = ""
    is_exempt: bool = False

def evaluate_risk(amount: float, recipient: str, purpose: str = "", financials: Dict[str, Any] = None, history: List[Dict[str, Any]] = None, *args, **kwargs) -> RiskAssessment:
    """
    Evaluates transaction risk purely on financial patterns, spending baselines, cash flow cycles, and recipient familiarity.
    Accepts *args, **kwargs for complete signature safety.
    Completely job/occupation-agnostic.
    """
    if financials is None:
        financials = {"typical_spend": 1500, "income_cycle": "Daily Cash"}
    if history is None:
        history = []

    assessment = RiskAssessment()
    amount = float(amount)
    recipient_lower = str(recipient).lower()
    purpose_lower = str(purpose).lower()

    # Check 0: Digital Scam & Unverified Prize Schemes (Highest Risk)
    scam_keywords = ["lottery", "telegram", "prize", "jackpot", "unverified", "claim", "winner", "लॉटरी", "டெலிகிராம்"]
    if any(k in recipient_lower or k in purpose_lower for k in scam_keywords):
        assessment.risk_level = "CRITICAL"
        assessment.flag_reason = f"Digital scam pattern detected: Recipient '{recipient}' involves unverified prize/lottery scheme."
        return assessment

    # Check 1: Recipient Familiarity Check
    is_familiar = any(txn.get("title", "").lower() == recipient_lower for txn in history)

    # Check 2: Pure Financial Anomaly Spike Detection
    typical_spend = float(financials.get("typical_spend", 1500))
    income_cycle = financials.get("income_cycle", "Daily Cash")

    # Multipliers for cash flow volatility threshold
    cycle_multipliers = {
        "Daily Cash": 3.0,
        "Weekly Haat / Market": 5.0,
        "Monthly / Periodic": 8.0
    }
    allowed_multiplier = cycle_multipliers.get(income_cycle, 3.0)
    spike_threshold = typical_spend * allowed_multiplier

    is_spike = amount > spike_threshold

    if not is_familiar and is_spike:
        assessment.risk_level = "CRITICAL"
        assessment.flag_reason = f"Unfamiliar contact '{recipient}' with high amount (₹{amount:,.0f}), exceeding {allowed_multiplier:g}x typical spend baseline (₹{typical_spend:,.0f})."
    elif not is_familiar:
        assessment.risk_level = "MODERATE"
        assessment.flag_reason = f"Unfamiliar contact '{recipient}' missing from past transfer history."
    elif is_spike:
        assessment.risk_level = "CRITICAL"
        assessment.flag_reason = f"High spending spike: Transfer ₹{amount:,.0f} exceeds {allowed_multiplier:g}x typical spend baseline (₹{typical_spend:,.0f}) for {income_cycle} cycle."
    else:
        assessment.risk_level = "SAFE"

    return assessment
