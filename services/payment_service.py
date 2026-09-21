import uuid
import streamlit as st
from services.voice_service import synthesize_speech
from services.translator import t
from core.state import get_current_balance, update_balance
from datetime import datetime

def HAS_RAZORPAY_SDK() -> bool:
    try:
        import razorpay
        return True
    except ImportError:
        return False

def HAS_STRIPE_SDK() -> bool:
    try:
        import stripe
        return True
    except ImportError:
        return False


def initiate_payment(amount: float, recipient: str, purpose: str = "", *args, **kwargs) -> dict:
    """
    Defensively initiates payment processing.
    Supports Stripe API, Razorpay API, or built-in keyless test payment simulator fallback.
    Accepts *args, **kwargs for total signature safety.
    """
    amount = float(amount)
    recipient = str(recipient) if recipient else "Merchant"
    purpose = str(purpose) if purpose else "General Payment"
    
    payment_id = f"pay_test_rural_{uuid.uuid4().hex[:6]}"

    # Check Stripe Key Support
    stripe_key = kwargs.get("stripe_key") or kwargs.get("STRIPE_API_KEY")
    if HAS_STRIPE_SDK() and stripe_key:
        try:
            import stripe
            stripe.api_key = stripe_key
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100), # Amount in cents/paise
                currency="inr",
                description=f"Payment to {recipient} for {purpose}",
                metadata={
                    "recipient": recipient,
                    "purpose": purpose,
                    "customer_name": st.session_state.get("household_financials", {}).get("user_name", "Rural Resident")
                }
            )
            return {
                "payment_id": intent.get("id", payment_id),
                "amount": amount,
                "recipient": recipient,
                "purpose": purpose,
                "payment_url": "",
                "status": "created",
                "mode": "stripe_live_sandbox"
            }
        except Exception as e:
            print(f"[PaymentService] Stripe creation note: {e}. Falling back to embedded simulator.")

    # Check Razorpay Key Support
    rzp_key = kwargs.get("razorpay_key") or kwargs.get("RAZORPAY_KEY_ID")
    rzp_sec = kwargs.get("razorpay_secret") or kwargs.get("RAZORPAY_KEY_SECRET")
    if HAS_RAZORPAY_SDK() and rzp_key and rzp_sec:
        try:
            import razorpay
            client = razorpay.Client(auth=(rzp_key, rzp_sec))
            link_data = client.payment_link.create({
                "amount": int(amount * 100), # Amount in paise
                "currency": "INR",
                "accept_partial": False,
                "description": f"Payment to {recipient} for {purpose}",
                "customer": {
                    "name": st.session_state.get("household_financials", {}).get("user_name", "Rural Resident"),
                    "contact": "+919876543210"
                },
                "notify": {"sms": True, "email": False},
                "reminder_enable": False,
                "callback_url": "http://localhost:8522",
                "callback_method": "get"
            })
            return {
                "payment_id": link_data.get("id", payment_id),
                "amount": amount,
                "recipient": recipient,
                "purpose": purpose,
                "payment_url": link_data.get("short_url", ""),
                "status": "created",
                "mode": "razorpay_live_sandbox"
            }
        except Exception as e:
            print(f"[PaymentService] Razorpay SDK creation error: {e}. Falling back to embedded simulator.")

    # Embedded Simulator Fallback (Keyless Mode)
    return {
        "payment_id": payment_id,
        "amount": amount,
        "recipient": recipient,
        "purpose": purpose,
        "status": "created",
        "mode": "simulator"
    }


def execute_payment_fulfillment(payment_payload: dict, lang: str = "en", *args, **kwargs) -> bool:
    """
    Finalizes payment fulfillment: deducts balance, logs transaction, and plays audio confirmation.
    Accepts *args, **kwargs.
    """
    amount = float(payment_payload.get("amount", 0.0))
    recipient = payment_payload.get("recipient", "Merchant")
    purpose = payment_payload.get("purpose", "General Payment")

    current_bal = get_current_balance()
    if current_bal < amount:
        st.session_state["payment_error"] = f"❌ Insufficient wallet balance! Current: ₹{current_bal:,.2f}, Required: ₹{amount:,.2f}."
        return False

    # Deduct balance
    new_bal = current_bal - amount
    update_balance(new_bal)

    # Insert transaction log
    new_txn = {
        "id": payment_payload.get("payment_id", f"TXN_{uuid.uuid4().hex[:6].upper()}"),
        "title": recipient,
        "category": purpose,
        "amount": amount,
        "type": "debit",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "Completed"
    }
    st.session_state["transaction_history"].insert(0, new_txn)

    # Audio Confirmation
    if lang == "ta":
        audio_msg = f"{recipient}-க்கு ₹{amount:,.0f} செலுத்துதல் வெற்றிகரமாக முடிந்தது."
        success_txt = f"✅ {recipient}-க்கு ₹{amount:,.2f} செலுத்தப்பட்டது. மீதி இருப்பு: ₹{new_bal:,.2f}."
    elif lang == "hi":
        audio_msg = f"{recipient} को ₹{amount:,.0f} का भुगतान सफल रहा।"
        success_txt = f"✅ {recipient} को ₹{amount:,.2f} का भुगतान सफल। शेष: ₹{new_bal:,.2f}।"
    else:
        audio_msg = f"Payment of {amount:,.0f} rupees to {recipient} successful."
        success_txt = f"✅ Payment of ₹{amount:,.2f} to {recipient} successful. Remaining balance: ₹{new_bal:,.2f}."

    st.session_state["payment_success"] = success_txt
    st.session_state["spoken_fulfillment_audio"] = audio_msg
    return True


def render_payment_simulator_card(payment_payload: dict, lang: str = "en", *args, **kwargs):
    """Renders interactive Razorpay payment simulator card/modal for test execution."""
    payment_id = payment_payload.get("payment_id", "pay_test_rural_1001")
    amount = float(payment_payload.get("amount", 0.0))
    recipient = payment_payload.get("recipient", "Merchant")
    purpose = payment_payload.get("purpose", "General Payment")

    st.markdown(f"""
    <div style="background: white; border: 3px solid #2b9348; border-radius: 16px; padding: 1.5rem; margin-top: 1rem; box-shadow: 0 6px 16px rgba(43,147,72,0.15);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div style="font-size: 1.1rem; font-weight: 800; color: #1b4332;">💳 Razorpay Test Sandbox Simulator</div>
            <div style="background: #e8f0e6; color: #1b4332; padding: 4px 12px; border-radius: 12px; font-weight: 700; font-size: 0.85rem;">ID: {payment_id}</div>
        </div>
        <div style="font-size: 1.15rem; margin-bottom: 6px;"><b>Recipient:</b> {recipient}</div>
        <div style="font-size: 1.3rem; font-weight: 800; color: #d90429; margin-bottom: 6px;">Amount: ₹{amount:,.2f}</div>
        <div style="font-size: 0.95rem; color: gray;">Category / Purpose: {purpose}</div>
    </div>
    """, unsafe_allow_html=True)

    if payment_payload.get("payment_url"):
        st.markdown(f"🔗 [Open Live Razorpay Link]({payment_payload['payment_url']})")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 Authorize & Complete Test Payment", type="primary", use_container_width=True, key="authorize_sim_pay_btn"):
        if execute_payment_fulfillment(payment_payload, lang=lang):
            st.rerun()
