import uuid
import hashlib
from datetime import datetime
import streamlit as st

from core.state import (
    initialize_session, 
    get_current_balance, 
    update_balance, 
    add_to_balance, 
    INCOME_CYCLES, 
    DEFAULT_HOUSEHOLD_FINANCIALS
)
from core.config import render_api_key_settings_sidebar, get_keys
from services.translator import t
from services.voice_service import transcribe_speech, synthesize_speech
from services.intent_parser import parse_transaction_request
from services.risk_engine import evaluate_risk
from services.explanation_engine import get_vernacular_explanation
from services.onboarding_service import render_onboarding_wizard
from services.payment_service import initiate_payment, execute_payment_fulfillment, render_payment_simulator_card

# Configure Streamlit page layout
st.set_page_config(
    page_title="AssistHands - Inclusive Rural Banking",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for high-visibility low-literacy accessibility
st.markdown("""
<style>
    :root {
        --primary-green: #1b4332;
        --accent-gold: #e9c46a;
    }

    .main {
        background: linear-gradient(135deg, #f4f7f4 0%, #e8f0e6 100%);
    }

    .balance-card {
        background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 100%);
        color: white;
        padding: 1.2rem 1.6rem;
        border-radius: 16px;
        box-shadow: 0 6px 16px rgba(27, 67, 50, 0.25);
        text-align: center;
    }

    .balance-amount {
        font-size: 2.2rem;
        font-weight: 800;
        color: #e9c46a;
    }

    .stButton>button {
        border-radius: 12px;
        font-weight: 700;
        padding: 0.6rem 1rem;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    .banner-safe {
        background-color: #d8f3dc;
        border-left: 8px solid #2b9348;
        padding: 1.2rem;
        border-radius: 12px;
        margin-top: 1rem;
    }

    .banner-moderate {
        background-color: #fff3cd;
        border-left: 8px solid #ffb703;
        padding: 1.2rem;
        border-radius: 12px;
        margin-top: 1rem;
    }

    .banner-critical {
        background-color: #ffe5ec;
        border-left: 8px solid #d90429;
        padding: 1.2rem;
        border-radius: 12px;
        margin-top: 1rem;
    }

    .elder-lock-banner {
        background-color: #ede0d4;
        border-left: 8px solid #7f5539;
        padding: 1.2rem;
        border-radius: 12px;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# 1. Initialize session state
initialize_session()

# Check Onboarding status: If not onboarded, display voice wizard!
if not st.session_state.get("is_onboarded", False):
    render_onboarding_wizard()
    
    st.markdown("---")
    if st.button("⏩ Skip Voice Setup & Launch App", type="secondary"):
        st.session_state["is_onboarded"] = True
        st.rerun()
    st.stop()

# --- Callback Helpers (Executed BEFORE Widget Instantiation) ---

def set_command_phrase(cmd_text: str, *args, **kwargs):
    """Callback for quick action buttons to set active transaction phrase."""
    st.session_state["active_phrase"] = cmd_text
    st.session_state["user_typed_phrase"] = cmd_text

def set_spoken_balance(*args, **kwargs):
    """Callback for Hear Balance button."""
    lang = st.session_state.get("lang", "en")
    bal_msg = f"Your current wallet balance is {get_current_balance():,.0f} rupees." if lang == "en" else (f"आपका वर्तमान बैलेंस {get_current_balance():,.0f} रुपये है।" if lang == "hi" else f"உங்கள் தற்போதைய கணக்கு இருப்பு {get_current_balance():,.0f} ரூபாய்.")
    st.session_state["spoken_fulfillment_audio"] = bal_msg

def trigger_payment_request(recipient: str, amount: float, category: str, *args, **kwargs):
    """
    Handles Payment Request.
    Enforces Youth vs Elder Asymmetric Verification rules:
    - If Youth operator and amount > ₹2,000 or spend anomaly: Holds transaction as PENDING_ELDER_APPROVAL.
    - Otherwise initiates Razorpay / simulator payment.
    """
    lang = st.session_state.get("lang", "en")
    role = st.session_state.get("household_role", "Youth")
    amount = float(amount)

    if amount <= 0:
        st.session_state["payment_error"] = "❌ " + ("Please enter a valid payment amount." if lang == "en" else ("कृपया वैध राशि दर्ज करें।" if lang == "hi" else "செல்லுபடியாகும் தொகையை உள்ளிடவும்."))
        return

    current_bal = get_current_balance()
    if current_bal < amount:
        st.session_state["payment_error"] = f"❌ Insufficient wallet balance! Current: ₹{current_bal:,.2f}, Required: ₹{amount:,.2f}." if lang == "en" else (f"❌ अपर्याप्त बैलेंस! वर्तमान: ₹{current_bal:,.2f}, आवश्यक: ₹{amount:,.2f}।" if lang == "hi" else f"❌ போதிய இருப்பு இல்லை! தற்போதைய இருப்பு: ₹{current_bal:,.2f}.")
        return

    # Check Youth Asymmetric Verification Threshold
    typical_spend = float(st.session_state.get("household_financials", {}).get("typical_spend", 1500))
    is_anomaly = amount > (typical_spend * 3.0) or amount > 2000.0

    if role == "Youth" and is_anomaly:
        # Hold transaction for Elder Verification
        pending_item = {
            "id": f"PEND_{uuid.uuid4().hex[:6].upper()}",
            "recipient": recipient,
            "amount": amount,
            "purpose": category,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        st.session_state["pending_elder_transactions"].append(pending_item)
        st.session_state["payment_info"] = f"🔒 Transfer Held: Amount (₹{amount:,.0f}) exceeds ₹2,000 threshold. Switch to Elder Profile in sidebar to verify."
        st.session_state["active_phrase"] = ""
        st.session_state["user_typed_phrase"] = ""
        return

    # Direct / Elder execution via Payment Service
    keys = get_keys()
    payload = initiate_payment(
        amount=amount, 
        recipient=recipient, 
        purpose=category,
        stripe_key=keys.get("STRIPE_API_KEY"),
        razorpay_key=keys.get("RAZORPAY_KEY_ID"),
        razorpay_secret=keys.get("RAZORPAY_KEY_SECRET")
    )
    
    execute_payment_fulfillment(payload, lang=lang)
    st.session_state["active_phrase"] = ""
    st.session_state["user_typed_phrase"] = ""

def approve_elder_pending_transaction(pending_item: dict, entered_pin: str, *args, **kwargs):
    """Verifies Elder PIN and approves pending transaction."""
    lang = st.session_state.get("lang", "en")
    correct_pin = st.session_state.get("elder_passkey", "1234")

    if str(entered_pin).strip() != correct_pin:
        st.session_state["payment_error"] = "❌ Incorrect 4-Digit Elder PIN! Access denied."
        return

    # PIN Correct: Fulfill Payment
    keys = get_keys()
    payload = initiate_payment(
        amount=pending_item["amount"],
        recipient=pending_item["recipient"],
        purpose=pending_item["purpose"],
        stripe_key=keys.get("STRIPE_API_KEY"),
        razorpay_key=keys.get("RAZORPAY_KEY_ID"),
        razorpay_secret=keys.get("RAZORPAY_KEY_SECRET")
    )
    
    if execute_payment_fulfillment(payload, lang=lang):
        # Remove from pending queue
        st.session_state["pending_elder_transactions"] = [
            t_item for t_item in st.session_state["pending_elder_transactions"] if t_item["id"] != pending_item["id"]
        ]

def reject_elder_pending_transaction(pending_id: str, *args, **kwargs):
    """Rejects pending transaction by Elder."""
    st.session_state["pending_elder_transactions"] = [
        t_item for t_item in st.session_state["pending_elder_transactions"] if t_item["id"] != pending_id
    ]
    st.session_state["payment_info"] = "ℹ️ Pending transaction rejected by Elder."

def cancel_active_payment(*args, **kwargs):
    """Cancels current pending payment."""
    lang = st.session_state.get("lang", "en")
    st.session_state["payment_info"] = "ℹ️ Payment canceled." if lang == "en" else ("ℹ️ भुगतान रद्द कर दिया गया।" if lang == "hi" else "ℹ️ பரிவர்த்தனை ரத்து செய்யப்பட்டது.")
    st.session_state["active_phrase"] = ""
    st.session_state["user_typed_phrase"] = ""

def sync_offline_queue(*args, **kwargs):
    """Processes all offline queued transactions into live history and balance."""
    queue = st.session_state.get("offline_queue", [])
    if not queue:
        st.session_state["payment_info"] = "ℹ️ Offline queue is empty."
        return

    lang = st.session_state.get("lang", "en")
    synced_count = 0
    total_deducted = 0.0

    for item in list(queue):
        raw_text = item.get("raw_text", "")
        intent = parse_transaction_request(raw_text, lang=lang)
        
        recipient = intent.get("recipient", "Offline Merchant") if isinstance(intent, dict) else getattr(intent, "recipient", "Offline Merchant")
        amount = float(intent.get("amount", 0.0)) if isinstance(intent, dict) else float(getattr(intent, "amount", 0.0))
        purpose = intent.get("purpose", "General Payment") if isinstance(intent, dict) else getattr(intent, "purpose", "General Payment")

        if amount <= 0:
            amount = 450.0

        current_bal = get_current_balance()
        if current_bal >= amount:
            update_balance(current_bal - amount)
            total_deducted += amount
            
            synced_txn = {
                "id": f"TXN_{uuid.uuid4().hex[:6].upper()}",
                "title": recipient,
                "category": purpose,
                "amount": amount,
                "type": "debit",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "status": "Completed (Synced Offline)"
            }
            st.session_state["transaction_history"].insert(0, synced_txn)
            synced_count += 1

    st.session_state["offline_queue"] = []
    
    if lang == "hi":
        toast_msg = f"इंटरनेट बहाल हुआ। {synced_count} ऑफ़लाइन अनुरोध संसाधित हुए।"
    elif lang == "ta":
        toast_msg = f"இணையம் மீட்டமைக்கப்பட்டது. {synced_count} ஆஃப்லைன் கோரிக்கைகள் செயலாக்கப்பட்டன."
    else:
        toast_msg = f"Internet restored. {synced_count} offline request(s) processed."

    st.toast(toast_msg, icon="🌐")
    st.session_state["spoken_fulfillment_audio"] = toast_msg

def handle_manual_balance_change(*args, **kwargs):
    """Updates balance directly from sidebar input widget."""
    val = st.session_state.get("manual_balance_field", get_current_balance())
    update_balance(val)
    st.session_state["payment_success"] = f"💳 Balance updated to ₹{get_current_balance():,.2f}"

def topup_balance(amount: float, *args, **kwargs):
    """Tops up balance by specified delta."""
    add_to_balance(amount)
    st.session_state["payment_success"] = f"💵 Added ₹{amount:,.0f}! New Balance: ₹{get_current_balance():,.2f}"

def restart_onboarding_wizard(*args, **kwargs):
    """Restarts voice onboarding wizard."""
    st.session_state["onboarding_step"] = "ONBOARDING_LANG"
    st.session_state["is_onboarded"] = False

# 2. Render Sidebar Configuration & Fully Translated Controls
with st.sidebar:
    st.title(t("setup_title", st.session_state.get("lang", "en")))

    # Language Selector
    lang_options = {"en": "English 🇬🇧", "hi": "हिन्दी 🇮🇳", "ta": "தமிழ் 🇮🇳"}
    selected_lang = st.selectbox(
        "🌐 Language / भाषा / மொழி",
        options=list(lang_options.keys()),
        format_func=lambda x: lang_options[x],
        index=list(lang_options.keys()).index(st.session_state.get("lang", "en"))
    )
    st.session_state["lang"] = selected_lang
    lang = selected_lang

    st.markdown("---")

    # --- Household Role Selector (Youth vs Elder) ---
    st.subheader("🏠 Household Role Profile")
    current_role = st.session_state.get("household_role", "Youth")
    role_choice = st.selectbox(
        "Active User Role:",
        options=["Youth", "Elder"],
        index=0 if current_role == "Youth" else 1,
        help="Youth = Initiator/Operator. Elder = Approver with PIN code."
    )
    st.session_state["household_role"] = role_choice

    if role_choice == "Youth":
        st.caption("📱 Mode: **Youth (Operator)**. Transfers > ₹2,000 held for Elder PIN.")
    else:
        st.caption("👵 Mode: **Elder (Approver)**. Verification PIN active.")

    st.button("🔄 Restart Voice Setup Wizard", on_click=restart_onboarding_wizard, use_container_width=True)

    st.markdown("---")

    # --- Balance Management Controls ---
    st.subheader(t("wallet_editor", lang))
    current_b = get_current_balance()
    
    st.number_input(
        t("set_exact_balance", lang),
        min_value=0.0,
        max_value=1000000.0,
        value=float(current_b),
        step=500.0,
        key="manual_balance_field",
        on_change=handle_manual_balance_change
    )
    
    st.caption(t("quick_add_funds", lang))
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("+ ₹500", use_container_width=True, on_click=topup_balance, args=(500.0,)):
            pass
        if st.button("+ ₹5,000", use_container_width=True, on_click=topup_balance, args=(5000.0,)):
            pass
    with col_t2:
        if st.button("+ ₹1,000", use_container_width=True, on_click=topup_balance, args=(1000.0,)):
            pass
        if st.button("+ ₹10,000", use_container_width=True, on_click=topup_balance, args=(10000.0,)):
            pass

    st.markdown("---")

    # Income & Spending Baseline Controls
    st.subheader(t("financial_baseline", lang))
    financials = st.session_state["household_financials"]
    
    typical_spend_val = st.number_input(
        t("typical_spend", lang),
        min_value=200,
        max_value=50000,
        value=int(financials.get("typical_spend", 1500)),
        step=100
    )
    st.session_state["household_financials"]["typical_spend"] = typical_spend_val

    cycle_idx = INCOME_CYCLES.index(financials.get("income_cycle", "Daily Cash")) if financials.get("income_cycle") in INCOME_CYCLES else 0
    selected_cycle = st.selectbox(
        t("income_cycle", lang),
        options=INCOME_CYCLES,
        index=cycle_idx
    )
    st.session_state["household_financials"]["income_cycle"] = selected_cycle

    # Offline Mode Switcher with Reactive Auto-Flush Trap
    st.markdown("---")
    st.subheader(t("connection_status", lang))
    
    prev_offline = st.session_state.get("is_offline", False)
    is_offline_toggle = st.toggle(t("simulate_offline", lang), value=prev_offline)
    
    # REACTIVE AUTO-FLUSH TRAP: When toggled from True (Offline) -> False (Online)
    if prev_offline and not is_offline_toggle:
        queue = st.session_state.get("offline_queue", [])
        if queue:
            synced_count = 0
            total_deducted = 0.0
            for item in list(queue):
                raw_text = item.get("raw_text", "")
                intent = parse_transaction_request(raw_text, lang=lang)
                
                recipient = intent.get("recipient", "Offline Merchant") if isinstance(intent, dict) else getattr(intent, "recipient", "Offline Merchant")
                amount = float(intent.get("amount", 0.0)) if isinstance(intent, dict) else float(getattr(intent, "amount", 0.0))
                purpose = intent.get("purpose", "General Payment") if isinstance(intent, dict) else getattr(intent, "purpose", "General Payment")

                if amount <= 0:
                    amount = 450.0

                current_bal = get_current_balance()
                if current_bal >= amount:
                    update_balance(current_bal - amount)
                    total_deducted += amount
                    
                    synced_txn = {
                        "id": f"TXN_{uuid.uuid4().hex[:6].upper()}",
                        "title": recipient,
                        "category": purpose,
                        "amount": amount,
                        "type": "debit",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "status": "Completed (Auto-Synced)"
                    }
                    st.session_state["transaction_history"].insert(0, synced_txn)
                    synced_count += 1

            st.session_state["offline_queue"] = []
            
            if lang == "hi":
                toast_msg = f"इंटरनेट बहाल हुआ। {synced_count} ऑफ़लाइन अनुरोध संसाधित हुए।"
            elif lang == "ta":
                toast_msg = f"இணையம் மீட்டமைக்கப்பட்டது. {synced_count} ஆஃப்லைன் கோரிக்கைகள் செயலாக்கப்பட்டன."
            else:
                toast_msg = f"Internet restored. {synced_count} offline request(s) processed."

            st.toast(toast_msg, icon="🌐")
            st.session_state["spoken_fulfillment_audio"] = toast_msg

    st.session_state["is_offline"] = is_offline_toggle
    
    if st.session_state["is_offline"]:
        st.error(t("status_offline_badge", lang))
        st.info(f"{t('queued_items', lang)}: {len(st.session_state['offline_queue'])}")
        if st.session_state['offline_queue']:
            st.button(t("sync_now_btn", lang), on_click=sync_offline_queue, type="primary", key="sidebar_sync_btn")
    else:
        st.success(t("status_online_badge", lang))

    # --- Evaluator Walkthrough Container ---
    st.markdown("---")
    with st.expander(t("demo_guide_title", lang), expanded=False):
        st.markdown(f"""
        **{t("demo_step1", lang)}**
        
        ---
        **{t("demo_step2", lang)}**
        
        ---
        **{t("demo_step3", lang)}**
        
        ---
        **{t("demo_step4", lang)}**
        """)

    render_api_key_settings_sidebar()

# 3. Top Header & Interactive Balance Banner
col_head1, col_head2 = st.columns([2.5, 1.2])
fin = st.session_state["household_financials"]

with col_head1:
    st.title(f"🌾 {t('app_title', lang)}")
    name_display = fin.get('user_name', 'Ramesh')
    loc_display = fin.get('location', 'Coimbatore District, TN')
    st.subheader(f"👤 {name_display} ({st.session_state['household_role']}) • {loc_display}")
    st.caption(f"{t('typical_spend', lang)}: **₹{fin['typical_spend']:,.0f}** | **{fin['income_cycle']}**")
    
    if st.button(f"🔊 {t('listen_btn', lang)}", key="listen_top_header"):
        bal_t = get_current_balance()
        h_text = f"Welcome {name_display}. Your account balance is {bal_t:,.0f} rupees." if lang == "en" else (f"नमस्ते {name_display}। आपका खाता शेष {bal_t:,.0f} रुपये है।" if lang == "hi" else f"வணக்கம் {name_display}. உங்கள் கணக்கு இருப்பு {bal_t:,.0f} ரூபாய்.")
        st.session_state["spoken_fulfillment_audio"] = h_text

with col_head2:
    st.markdown(f"""
    <div class="balance-card">
        <div style="font-size: 0.95rem; text-transform: uppercase; letter-spacing: 1px;">{t("wallet_balance", lang)}</div>
        <div class="balance-amount">₹{get_current_balance():,.2f}</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">{t("typical_spend", lang)}: ₹{fin['typical_spend']:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Spoken Audio Confirmations / Audio Player
if "spoken_fulfillment_audio" in st.session_state and st.session_state["spoken_fulfillment_audio"]:
    ful_text = st.session_state["spoken_fulfillment_audio"]
    ful_audio = synthesize_speech(ful_text, lang=lang)
    st.audio(ful_audio, format="audio/mp3", autoplay=True)
    st.session_state["spoken_fulfillment_audio"] = ""

# Flash Message Banners
if "payment_success" in st.session_state and st.session_state["payment_success"]:
    st.success(st.session_state["payment_success"])
    st.session_state["payment_success"] = ""

if "payment_error" in st.session_state and st.session_state["payment_error"]:
    st.error(st.session_state["payment_error"])
    st.session_state["payment_error"] = ""

if "payment_info" in st.session_state and st.session_state["payment_info"]:
    st.info(st.session_state["payment_info"])
    st.session_state["payment_info"] = ""

# --- ELDER ASYMMETRIC APPROVAL PANEL ---
pending_elder_items = st.session_state.get("pending_elder_transactions", [])
if st.session_state.get("household_role") == "Elder" and pending_elder_items:
    st.markdown("### 🚨 **Action Required: Youth Pending Transfer Approval**")
    
    for item in list(pending_elder_items):
        amt_val = item["amount"]
        rec_val = item["recipient"]
        purp_val = item["purpose"]
        
        # Risk assessment for explanation
        risk_eval = evaluate_risk(amt_val, rec_val, purp_val, st.session_state["household_financials"], st.session_state["transaction_history"])
        analogy = get_vernacular_explanation(risk_eval, lang=lang, recipient=rec_val, amount=amt_val, purpose=purp_val)
        
        st.markdown(f"""
        <div class="elder-lock-banner">
            <div style="font-size: 1.25rem; font-weight: 800; color: #7f5539;">👵 Youth Requested Transfer: ₹{amt_val:,.2f} to {rec_val}</div>
            <div style="font-size: 1.05rem; margin-top: 6px;"><b>Purpose:</b> {purp_val} &nbsp;|&nbsp; <b>Time:</b> {item['timestamp']}</div>
            <div style="margin-top: 10px; font-size: 1.05rem; font-style: italic; background: rgba(255,255,255,0.8); padding: 10px; border-radius: 8px;">
                🗣️ <b>Elder Spoken Caution:</b> "{analogy}"
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Auto-play spoken audio warning for Elder
        warn_audio = synthesize_speech(analogy, lang=lang)
        st.audio(warn_audio, format="audio/mp3", autoplay=True)

        col_pin, col_act1, col_act2 = st.columns([1.5, 1, 1])
        with col_pin:
            pin_input = st.text_input(f"Enter 4-Digit Elder PIN (Default: 1234):", type="password", key=f"pin_in_{item['id']}")
        
        with col_act1:
            st.button(
                "✅ Approve & Pay", 
                type="primary", 
                use_container_width=True, 
                key=f"approve_btn_{item['id']}",
                on_click=approve_elder_pending_transaction, 
                args=(item, pin_input)
            )
        
        with col_act2:
            st.button(
                "❌ Reject", 
                use_container_width=True, 
                key=f"reject_btn_{item['id']}",
                on_click=reject_elder_pending_transaction, 
                args=(item["id"],)
            )

# 4. Primary Voice & Text Inputs
col_vtitle, col_vlisten = st.columns([4, 1])
with col_vtitle:
    st.markdown(f"### {t('voice_command_title', lang)}")
with col_vlisten:
    if st.button(f"🔊 {t('listen_btn', lang)}", key="listen_voice_assistant"):
        st.session_state["spoken_fulfillment_audio"] = t("tap_to_speak_caption", lang)

st.caption(t("tap_to_speak_caption", lang))

col_audio, col_text_alt = st.columns([1.2, 1])
raw_command_text = ""

with col_audio:
    st.markdown(f"#### {t('tap_to_speak', lang)}")
    audio_data = st.audio_input("Record Voice Command", key="voice_recorder_widget")
    
    if audio_data is not None:
        with st.spinner("Processing spoken voice..."):
            raw_command_text = transcribe_speech(audio_data, lang=lang)
            if raw_command_text:
                st.success(f"🗣️ **Recognized:** *\"{raw_command_text}\"*")

with col_text_alt:
    st.markdown(f"#### {t('or_type_phrase', lang)}")
    typed_text = st.text_input(
        "Type transaction request:", 
        value=st.session_state.get("active_phrase", ""), 
        key="user_typed_phrase",
        placeholder=t("type_placeholder", lang)
    )
    if typed_text and not raw_command_text:
        raw_command_text = typed_text

# 5. Visual Quick Action Touch Cards
st.markdown("---")
col_qtitle, col_qlisten = st.columns([4, 1])
with col_qtitle:
    st.markdown(f"### {t('quick_actions_title', lang)}")
with col_qlisten:
    if st.button(f"🔊 {t('listen_btn', lang)}", key="listen_quick_actions"):
        q_msg = "Touch any card to pay Kirana, Milk Co-op, or Seeds Depot." if lang == "en" else ("किराना, डेयरी या खाद डिपो का भुगतान करने के लिए कार्ड छुएं।" if lang == "hi" else "மளிகை, பால் சங்கம் அல்லது உரக் கடைக்கு பணம் செலுத்த தொடுங்கள்.")
        st.session_state["spoken_fulfillment_audio"] = q_msg

col_q1, col_q2, col_q3, col_q4, col_q5 = st.columns(5)

with col_q1:
    st.button(t("pay_kirana", lang), use_container_width=True, on_click=set_command_phrase, args=("Send 450 rupees to Local Kirana Store" if lang == "en" else ("किराना दुकान को 450 रुपये भेजें" if lang == "hi" else "மளிகைக் கடைக்கு 450 ரூபாய் அனுப்பு"),))

with col_q2:
    st.button(t("pay_milk", lang), use_container_width=True, on_click=set_command_phrase, args=("Transfer 1200 rupees to Milk Co-operative Society" if lang == "en" else ("डेयरी समिति को 1200 रुपये भेजें" if lang == "hi" else "பால் கூட்டுறவு சங்கத்திற்கு 1200 ரூபாய் அனுப்பு"),))

with col_q3:
    st.button(t("pay_seeds", lang), use_container_width=True, on_click=set_command_phrase, args=("Pay 1500 rupees to Fertilizer Depot" if lang == "en" else ("खाद डिपो को 1500 रुपये भेजें" if lang == "hi" else "உரக் கடைக்கு 1500 ரூபாய் அனுப்பு"),))

with col_q4:
    st.button(t("hear_balance", lang), use_container_width=True, on_click=set_spoken_balance)

with col_q5:
    st.button(t("test_scam", lang), use_container_width=True, on_click=set_command_phrase, args=("Send 45000 rupees to Telegram Lottery Winner" if lang == "en" else ("टेलीग्राम लॉटरी विजेता को 45000 रुपये भेजें" if lang == "hi" else "டெலிகிராம் லாட்டரிக்கு 45000 ரூபாய் அனுப்பு"),))

# 6. Pipeline Execution (Offline vs Live Payment)
if raw_command_text and raw_command_text.strip():
    st.markdown("---")
    st.subheader(t("analysis_title", lang))
    
    if st.session_state["is_offline"]:
        offline_id = f"OFF_{uuid.uuid4().hex[:6].upper()}"
        offline_entry = {
            "id": offline_id,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "raw_text": raw_command_text,
            "status": "Queued Offline"
        }
        st.session_state["offline_queue"].append(offline_entry)
        
        st.warning(f"📡 **Offline:** *\"{raw_command_text}\"* stored in queue (`{offline_id}`).")
        off_msg = "Network is offline. Voice command saved in offline queue." if lang == "en" else ("नेटवर्क ऑफ़लाइन है। वॉयस कमांड सेव हो गया है।" if lang == "hi" else "நெட்வொர்க் ஆஃப்லைனில் உள்ளது. குரல் கட்டளை சேமிக்கப்பட்டது.")
        off_audio = synthesize_speech(off_msg, lang=lang)
        st.audio(off_audio, format="audio/mp3", autoplay=True)
    else:
        intent = parse_transaction_request(raw_command_text, lang=lang)
        
        recipient = intent.get("recipient", "Merchant") if isinstance(intent, dict) else getattr(intent, "recipient", "Merchant")
        amount = float(intent.get("amount", 0.0)) if isinstance(intent, dict) else float(getattr(intent, "amount", 0.0))
        purpose = intent.get("purpose", "General Payment") if isinstance(intent, dict) else getattr(intent, "purpose", "General Payment")
        needs_clarification = intent.get("needs_clarification", False) if isinstance(intent, dict) else getattr(intent, "needs_clarification", False)
        clarification_prompt = intent.get("clarification_prompt", "") if isinstance(intent, dict) else getattr(intent, "clarification_prompt", "")

        if needs_clarification and clarification_prompt:
            st.error(f"❓ **Clarification Needed:** {clarification_prompt}")
            clarify_audio = synthesize_speech(clarification_prompt, lang=lang)
            st.audio(clarify_audio, format="audio/mp3", autoplay=True)
        else:
            risk_assessment = evaluate_risk(
                amount=amount, 
                recipient=recipient, 
                purpose=purpose, 
                financials=st.session_state["household_financials"], 
                history=st.session_state["transaction_history"]
            )
            
            analogy_text = get_vernacular_explanation(risk_assessment, lang=lang, recipient=recipient, amount=amount, purpose=purpose)
            
            risk_class = "banner-safe" if risk_assessment.risk_level == "SAFE" else ("banner-moderate" if risk_assessment.risk_level == "MODERATE" else "banner-critical")
            risk_icon = t("safe_badge", lang) if risk_assessment.risk_level == "SAFE" else (t("caution_badge", lang) if risk_assessment.risk_level == "MODERATE" else t("critical_badge", lang))
            
            st.markdown(f"""
            <div class="{risk_class}">
                <div style="font-size: 1.2rem; font-weight: 800;">{risk_icon}</div>
                <div style="font-size: 1.1rem; margin-top: 6px;"><b>{t('label_recipient', lang)}:</b> {recipient} &nbsp;|&nbsp; <b>{t('label_amount', lang)}:</b> ₹{amount:,.2f} &nbsp;|&nbsp; <b>{t('label_category', lang)}:</b> {purpose}</div>
                <div style="margin-top: 10px; font-size: 1.05rem; font-style: italic; background: rgba(255,255,255,0.7); padding: 10px; border-radius: 8px;">
                    {t('elder_analogy', lang)} "{analogy_text}"
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # AUTOMATIC SPOKEN AUDIO FEEDBACK
            if lang == "ta":
                status_speak = "பாதுகாப்பான பரிவர்த்தனை." if risk_assessment.risk_level == "SAFE" else ("எச்சரிக்கை பரிவர்த்தனை." if risk_assessment.risk_level == "MODERATE" else "ஆபத்தான மோசடி பரிவர்த்தனை.")
            elif lang == "hi":
                status_speak = "सुरक्षित भुगतान सूचना।" if risk_assessment.risk_level == "SAFE" else ("सावधानी सूचना।" if risk_assessment.risk_level == "MODERATE" else "उच्च जोखिम चेतावनी।")
            else:
                status_speak = f"{risk_assessment.risk_level} alert."

            audio_text = f"{status_speak} {analogy_text}"
            alert_audio = synthesize_speech(audio_text, lang=lang)
            st.audio(alert_audio, format="audio/mp3", autoplay=True)

            st.markdown("<br>", unsafe_allow_html=True)
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if risk_assessment.risk_level != "CRITICAL":
                    st.button(
                        t("confirm_payment_btn", lang).format(amount=f"{amount:,.0f}"), 
                        type="primary", 
                        use_container_width=True,
                        key="confirm_payment_intent_btn",
                        on_click=trigger_payment_request,
                        args=(recipient, amount, purpose)
                    )
                else:
                    st.button(
                        t("proceed_risk_btn", lang).format(amount=f"{amount:,.0f}"), 
                        type="secondary", 
                        use_container_width=True,
                        key="proceed_risk_intent_btn",
                        on_click=trigger_payment_request,
                        args=(recipient, amount, purpose)
                    )

            with col_btn2:
                st.button(
                    t("cancel_payment_btn", lang), 
                    use_container_width=True,
                    key="cancel_payment_intent_btn",
                    on_click=cancel_active_payment
                )

# 7. Direct Manual Transfer Box
st.markdown("---")
with st.expander(f"💸 **{t('direct_form_title', lang)}**", expanded=False):
    col_d1, col_d2, col_d3 = st.columns([1.5, 1, 1])
    with col_d1:
        d_rec = st.text_input(f"{t('label_recipient', lang)}:", value="Local Kirana Store")
    with col_d2:
        d_amt = st.number_input(f"{t('label_amount', lang)} (₹):", min_value=1.0, max_value=50000.0, value=450.0, step=50.0)
    with col_d3:
        d_cat = st.selectbox(f"{t('label_category', lang)}:", options=["Daily Grocery", "Utility Bill", "Dairy Payout", "Agriculture Input", "Medical"])
    
    st.button(
        t("confirm_payment_btn", lang).format(amount=f"{d_amt:,.0f}"), 
        type="primary", 
        use_container_width=True,
        key="direct_manual_pay_btn",
        on_click=trigger_payment_request,
        args=(d_rec, d_amt, d_cat)
    )

# 8. Recent Transactions & Persistent Offline Queue Execution
st.markdown("---")
col_log1, col_log2 = st.columns([1.6, 1])

with col_log1:
    col_rtitle, col_rlisten = st.columns([3, 1])
    with col_rtitle:
        st.subheader(t("recent_txns_title", lang))
    with col_rlisten:
        if st.button(f"🔊 {t('listen_btn', lang)}", key="listen_recent_txns"):
            txns = st.session_state["transaction_history"]
            if txns:
                latest = txns[0]
                r_msg = f"Recent transaction: {latest['title']}, {latest['amount']:,.0f} rupees." if lang == "en" else (f"हाल का लेन-देन: {latest['title']}, {latest['amount']:,.0f} रुपये।" if lang == "hi" else f"சமீபத்திய பரிவர்த்தனை: {latest['title']}, {latest['amount']:,.0f} ரூபாய்.")
            else:
                r_msg = "No past transactions found." if lang == "en" else ("कोई हाल का लेन-देन नहीं मिला।" if lang == "hi" else "சமீபத்திய பரிவர்த்தனைகள் எதுவும் இல்லை.")
            st.session_state["spoken_fulfillment_audio"] = r_msg

    txns = st.session_state["transaction_history"]
    if txns:
        for t_item in txns[:8]:
            col_t1, col_t2, col_t3 = st.columns([2, 1, 1])
            col_t1.markdown(f"**{t_item['title']}**  \n<span style='color:gray; font-size:0.85rem;'>{t_item['category']} • {t_item['date']}</span>", unsafe_allow_html=True)
            col_t2.markdown(f"<span style='color:#d90429; font-weight:700;'>-₹{t_item['amount']:,.2f}</span>", unsafe_allow_html=True)
            col_t3.caption(f"✅ {t_item['status']}")
            st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)
    else:
        st.info("No past transactions found.")

with col_log2:
    col_otitle, col_olisten = st.columns([3, 1])
    with col_otitle:
        st.subheader(t("offline_queue_title", lang))
    with col_olisten:
        if st.button(f"🔊 {t('listen_btn', lang)}", key="listen_offline_queue"):
            off_q = st.session_state["offline_queue"]
            q_msg = f"Offline queue has {len(off_q)} pending items." if lang == "en" else (f"ऑफ़लाइन कतार में {len(off_q)} आइटम हैं।" if lang == "hi" else f"ஆஃப்லைன் வரிசையில் {len(off_q)} பொருட்கள் உள்ளன.")
            st.session_state["spoken_fulfillment_audio"] = q_msg

    off_queue = st.session_state["offline_queue"]
    if off_queue:
        st.warning(f"Pending Items: {len(off_queue)}")
        for q_item in off_queue:
            st.markdown(f"• **[{q_item['timestamp']}]** *\"{q_item['raw_text']}\"*")
        st.button(
            t("sync_now_btn", lang), 
            type="primary", 
            use_container_width=True, 
            key="sync_queue_main_btn",
            on_click=sync_offline_queue
        )
    else:
        st.success("Queue empty. All transactions synced.")
