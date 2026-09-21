import streamlit as st

DEFAULT_TRANSACTIONS = [
    {
        "id": "TXN_1001",
        "title": "Local Kirana Store",
        "category": "Daily Grocery",
        "amount": 450,
        "type": "debit",
        "date": "2026-09-18",
        "status": "Completed",
    },
    {
        "id": "TXN_1002",
        "title": "Milk Co-operative Society",
        "category": "Dairy Payout",
        "amount": 1200,
        "type": "debit",
        "date": "2026-09-15",
        "status": "Completed",
    },
    {
        "id": "TXN_1003",
        "title": "Fertilizer & Seed Depot",
        "category": "Agriculture Input",
        "amount": 1500,
        "type": "debit",
        "date": "2026-09-10",
        "status": "Completed",
    },
    {
        "id": "TXN_1004",
        "title": "Electricity Board",
        "category": "Utility Bill",
        "amount": 350,
        "type": "debit",
        "date": "2026-09-05",
        "status": "Completed",
    }
]

INCOME_CYCLES = ["Daily Cash", "Weekly Haat / Market", "Monthly / Periodic"]

DEFAULT_HOUSEHOLD_FINANCIALS = {
    "user_name": "Ramesh",
    "typical_spend": 1500,
    "income_cycle": "Daily Cash",
    "balance": 12450.0,
    "location": "Coimbatore District, TN",
}


def initialize_session():
    """Initializes default Streamlit session state keys if not already present."""
    if "lang" not in st.session_state:
        st.session_state["lang"] = "en"

    if "is_offline" not in st.session_state:
        st.session_state["is_offline"] = False

    if "offline_queue" not in st.session_state:
        st.session_state["offline_queue"] = []

    if "transaction_history" not in st.session_state:
        st.session_state["transaction_history"] = list(DEFAULT_TRANSACTIONS)

    if "household_financials" not in st.session_state:
        st.session_state["household_financials"] = dict(DEFAULT_HOUSEHOLD_FINANCIALS)

    # Onboarding State Machine
    if "is_onboarded" not in st.session_state:
        st.session_state["is_onboarded"] = False

    if "onboarding_step" not in st.session_state:
        st.session_state["onboarding_step"] = "ONBOARDING_LANG"

    # Household Asymmetric Role Verification
    if "household_role" not in st.session_state:
        st.session_state["household_role"] = "Youth"  # Options: "Youth" (Operator) or "Elder" (Approver)

    if "elder_passkey" not in st.session_state:
        st.session_state["elder_passkey"] = "1234"

    if "pending_elder_transactions" not in st.session_state:
        st.session_state["pending_elder_transactions"] = []


def get_current_balance() -> float:
    """Returns current balance from household financials state."""
    financials = st.session_state.get("household_financials", DEFAULT_HOUSEHOLD_FINANCIALS)
    return float(financials.get("balance", 12450.0))


def update_balance(new_balance: float):
    """Sets balance to exact value."""
    if "household_financials" in st.session_state:
        st.session_state["household_financials"]["balance"] = max(0.0, float(new_balance))


def add_to_balance(delta: float):
    """Adds delta amount to current balance."""
    current = get_current_balance()
    update_balance(current + delta)
