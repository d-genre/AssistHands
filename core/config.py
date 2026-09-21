import os
import streamlit as st
import dotenv

# Load .env if present
dotenv.load_dotenv()


def get_secret_or_env(key: str, default: str = "") -> str:
    """Safely fetch a secret from st.secrets, os.environ, or return empty string."""
    # First check session state for runtime user input override
    session_key = f"runtime_{key}"
    if session_key in st.session_state and st.session_state[session_key]:
        return st.session_state[session_key]
    
    # Second check os.environ
    val = os.getenv(key)
    if val:
        return val

    # Alias check for GROQ vs GROK
    if "GROQ" in key:
        alt_val = os.getenv(key.replace("GROQ", "GROK"))
        if alt_val:
            return alt_val
    elif "GROK" in key:
        alt_val = os.getenv(key.replace("GROK", "GROQ"))
        if alt_val:
            return alt_val

    # Third check st.secrets
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    return default

def get_keys():
    """Returns the effective API keys considering environment, secrets, and runtime inputs."""
    gemini_key = get_secret_or_env("GEMINI_API_KEY")
    groq_key = get_secret_or_env("GROQ_API_KEY") or get_secret_or_env("GROK_API_KEY")
    stripe_key = get_secret_or_env("STRIPE_API_KEY") or get_secret_or_env("STRIPE_SECRET_KEY")
    razorpay_id = get_secret_or_env("RAZORPAY_KEY_ID")
    razorpay_secret = get_secret_or_env("RAZORPAY_KEY_SECRET")
    
    has_gemini = bool(gemini_key and gemini_key.strip())
    has_groq = bool(groq_key and groq_key.strip())
    has_stripe = bool(stripe_key and stripe_key.strip())
    has_razorpay = bool(razorpay_id and razorpay_id.strip() and razorpay_secret and razorpay_secret.strip())
    
    return {
        "GEMINI_API_KEY": gemini_key,
        "GROQ_API_KEY": groq_key,
        "GROK_API_KEY": groq_key,
        "STRIPE_API_KEY": stripe_key,
        "RAZORPAY_KEY_ID": razorpay_id,
        "RAZORPAY_KEY_SECRET": razorpay_secret,
        "HAS_GEMINI": has_gemini,
        "HAS_GROQ": has_groq,
        "HAS_STRIPE": has_stripe,
        "HAS_RAZORPAY": has_razorpay,
    }

# Module-level dynamic attribute evaluation for HAS_GEMINI, HAS_GROQ, HAS_STRIPE, HAS_RAZORPAY
def __getattr__(name: str):
    if name == "HAS_GEMINI":
        return get_keys()["HAS_GEMINI"]
    if name == "HAS_GROQ":
        return get_keys()["HAS_GROQ"]
    if name == "HAS_STRIPE":
        return get_keys()["HAS_STRIPE"]
    if name == "HAS_RAZORPAY":
        return get_keys()["HAS_RAZORPAY"]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def render_api_key_settings_sidebar():
    """Renders an expandable sidebar section for runtime API Key input and updates state."""
    with st.sidebar.expander("⚙️ API Key Settings", expanded=False):
        st.markdown("<small>Configure or override API keys for live mode execution.</small>", unsafe_allow_html=True)
        
        current_gemini = get_secret_or_env("GEMINI_API_KEY")
        current_groq = get_secret_or_env("GROQ_API_KEY")
        current_stripe = get_secret_or_env("STRIPE_API_KEY")
        current_rzp_id = get_secret_or_env("RAZORPAY_KEY_ID")
        current_rzp_sec = get_secret_or_env("RAZORPAY_KEY_SECRET")

        new_gemini = st.text_input("Gemini API Key", value=current_gemini, type="password", key="input_gemini")
        new_groq = st.text_input("Groq / Grok API Key", value=current_groq, type="password", key="input_groq")
        new_stripe = st.text_input("Stripe Secret Key (sk_test_...)", value=current_stripe, type="password", key="input_stripe")
        new_rzp_id = st.text_input("Razorpay Key ID", value=current_rzp_id, type="password", key="input_rzp_id")
        new_rzp_sec = st.text_input("Razorpay Key Secret", value=current_rzp_sec, type="password", key="input_rzp_sec")

        if st.button("Save API Keys", key="btn_save_keys"):
            st.session_state["runtime_GEMINI_API_KEY"] = new_gemini
            st.session_state["runtime_GROQ_API_KEY"] = new_groq
            st.session_state["runtime_STRIPE_API_KEY"] = new_stripe
            st.session_state["runtime_RAZORPAY_KEY_ID"] = new_rzp_id
            st.session_state["runtime_RAZORPAY_KEY_SECRET"] = new_rzp_sec
            st.success("API keys updated dynamically!")
            st.rerun()

        # Display status badges
        keys_status = get_keys()
        st.markdown("---")
        st.caption("Active Key Status:")
        st.markdown(f"• **Gemini:** {'🟢 Active' if keys_status['HAS_GEMINI'] else '🔴 Keyless Fallback'}")
        st.markdown(f"• **Groq / Grok:** {'🟢 Active' if keys_status['HAS_GROQ'] else '🔴 Keyless Fallback'}")
        st.markdown(f"• **Stripe:** {'🟢 Active' if keys_status['HAS_STRIPE'] else '🔴 Simulator Fallback'}")
        st.markdown(f"• **Razorpay:** {'🟢 Active' if keys_status['HAS_RAZORPAY'] else '🔴 Simulated Payment'}")
