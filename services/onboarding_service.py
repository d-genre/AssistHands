import re
import streamlit as st
from services.voice_service import transcribe_speech, synthesize_speech
from services.translator import t

def parse_number_from_text(text: str, *args, **kwargs) -> float:
    """Extracts numeric value from spoken text."""
    if not text:
        return 1500.0
    text_lower = str(text).lower()
    
    mult = 1.0
    if "thousand" in text_lower or "hazaar" in text_lower or "hazar" in text_lower or "aayiram" in text_lower or "हजार" in text_lower or "ஆயிரம்" in text_lower:
        mult = 1000.0
    elif "hundred" in text_lower or "sau" in text_lower or "सौ" in text_lower or "நூறு" in text_lower:
        mult = 100.0

    nums = re.findall(r'[\d,]+(?:\.\d+)?', text_lower)
    if nums:
        try:
            val = float(nums[0].replace(',', ''))
            return val * mult if val < 100 and mult > 1 else val
        except ValueError:
            pass

    if mult > 1:
        return mult
    return 1500.0


def set_onboarding_lang(lang_code: str, *args, **kwargs):
    """Callback to record chosen language and advance step."""
    st.session_state["lang"] = lang_code
    st.session_state["onboarding_step"] = "ONBOARDING_NAME"


def complete_name_step(name_val: str, *args, **kwargs):
    """Callback to set name and advance to income step."""
    clean_name = str(name_val).strip().title() if name_val and len(str(name_val).strip()) > 0 else "User"
    st.session_state["household_financials"]["user_name"] = clean_name
    st.session_state["onboarding_step"] = "ONBOARDING_INCOME"


def complete_income_step(amount_val: float, *args, **kwargs):
    """Callback to set spend baseline and complete onboarding."""
    st.session_state["household_financials"]["typical_spend"] = max(200.0, float(amount_val))
    st.session_state["onboarding_step"] = "READY"
    st.session_state["is_onboarded"] = True


def render_onboarding_wizard(*args, **kwargs):
    """
    Renders 100% voice-driven & accessible onboarding assistant for low-literacy users.
    No preset names - users speak or type their actual real name.
    Step 1: Visual & Spoken Language Selection
    Step 2: Spoken Name Capture
    Step 3: Spoken Income & Spend Capture
    Step 4: Welcome & Audio Greeting
    """
    step = st.session_state.get("onboarding_step", "ONBOARDING_LANG")
    lang = st.session_state.get("lang", "en")

    st.markdown("""
    <div style="background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 100%); color: white; padding: 2rem; border-radius: 20px; text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #e9c46a; margin-bottom: 0.5rem;">🌾 AssistHands Voice Onboarding</h1>
        <p style="font-size: 1.1rem; opacity: 0.9;">Voice-Guided Setup for Rural Banking</p>
    </div>
    """, unsafe_allow_html=True)

    # --- STEP 1: LANGUAGE SELECTION ---
    if step == "ONBOARDING_LANG":
        st.markdown("### 🌐 **Step 1: Choose Your Language / மொழி / भाषा**")
        st.caption("Tap your language button or play spoken audio previews below.")

        # Multilingual Initial Spoken Audio Greeting
        initial_ta = synthesize_speech("தமிழ் வங்கி சேவைக்கு தமிழை தேர்ந்தெடுக்கவும்.", lang="ta")
        initial_hi = synthesize_speech("हिंदी वॉयस बैंकिंग के लिए हिंदी चुनें।", lang="hi")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.button(
                "🇬🇧 English", 
                type="primary", 
                use_container_width=True, 
                on_click=set_onboarding_lang, 
                args=("en",)
            )
            en_audio = synthesize_speech("Please select English for voice banking.", lang="en")
            st.audio(en_audio, format="audio/mp3")

        with col2:
            st.button(
                "🇮🇳 தமிழ் (Tamil)", 
                type="primary", 
                use_container_width=True, 
                on_click=set_onboarding_lang, 
                args=("ta",)
            )
            st.audio(initial_ta, format="audio/mp3", autoplay=True)

        with col3:
            st.button(
                "🇮🇳 हिन्दी (Hindi)", 
                type="primary", 
                use_container_width=True, 
                on_click=set_onboarding_lang, 
                args=("hi",)
            )
            st.audio(initial_hi, format="audio/mp3")

    # --- STEP 2: SPOKEN & TYPED REAL NAME CAPTURE (NO PRESET NAMES) ---
    elif step == "ONBOARDING_NAME":
        st.markdown(f"### 👤 **Step 2: Tell Us Your Name**")
        
        prompt_text = "What is your name?" if lang == "en" else ("आपका नाम क्या है?" if lang == "hi" else "உங்கள் பெயர் என்ன?")
        st.markdown(f"#### 🗣️ *\"{prompt_text}\"*")

        # Auto-play spoken audio prompt in chosen language
        audio_prompt = synthesize_speech(prompt_text, lang=lang)
        st.audio(audio_prompt, format="audio/mp3", autoplay=True)

        col_mic, col_typed = st.columns([1.3, 1.2])

        spoken_name = ""
        with col_mic:
            st.markdown("##### 🔴 Tap to Speak Your Name:")
            recorded_audio = st.audio_input("Record Your Name", key="onboarding_name_audio")
            
            if recorded_audio is not None:
                spoken_name = transcribe_speech(recorded_audio, lang=lang, context="name")
                if spoken_name and len(spoken_name.strip()) > 1:
                    st.success(f"Recognized Name: **{spoken_name}**")

        with col_typed:
            st.markdown("##### ⌨️ Or Type Your Name:")
            typed_name = st.text_input(
                "Enter Name:", 
                value=spoken_name if spoken_name else "", 
                placeholder="e.g. Divya / முருகன் / रमेश",
                key="onboarding_typed_name_input"
            )

        final_name = typed_name.strip() if typed_name and len(typed_name.strip()) > 0 else spoken_name.strip()
        if not final_name:
            final_name = "User" if lang == "en" else ("उपयोगकर्ता" if lang == "hi" else "பயனர்")

        st.markdown("<br>", unsafe_allow_html=True)
        st.button(
            f"✅ Confirm Name: \"{final_name}\"", 
            type="primary", 
            use_container_width=True,
            key="confirm_name_step_btn",
            on_click=complete_name_step, 
            args=(final_name,)
        )

    # --- STEP 3: SPOKEN & TYPED SPEND BASELINE ---
    elif step == "ONBOARDING_INCOME":
        st.markdown("### 💰 **Step 3: Tell Us Your Typical Spend**")
        
        prompt_text = "How much money do you usually spend in a week?" if lang == "en" else ("आप एक सप्ताह में आमतौर पर कितना खर्च करते हैं?" if lang == "hi" else "பொதுவாக வாரத்திற்கு எவ்வளவு செலவு செய்வீர்கள்?")
        st.markdown(f"#### 🗣️ *\"{prompt_text}\"*")

        # Auto-play spoken audio prompt
        audio_prompt = synthesize_speech(prompt_text, lang=lang)
        st.audio(audio_prompt, format="audio/mp3", autoplay=True)

        col_mic, col_typed = st.columns([1.3, 1.2])
        parsed_amt = 1500.0

        with col_mic:
            st.markdown("##### 🔴 Tap to Speak Amount:")
            recorded_audio = st.audio_input("Record Spend Amount", key="onboarding_spend_audio")
            
            if recorded_audio is not None:
                spoken_text = transcribe_speech(recorded_audio, lang=lang, context="spend")
                if spoken_text:
                    parsed_amt = parse_number_from_text(spoken_text)
                    st.success(f"Recognized Spend Baseline: **₹{parsed_amt:,.0f}**")

        with col_typed:
            st.markdown("##### 🔢 Or Set Spend Amount (₹):")
            custom_spend = st.number_input(
                "Weekly Spend (₹):", 
                min_value=200.0, 
                max_value=50000.0, 
                value=float(parsed_amt) if parsed_amt > 200 else 1500.0, 
                step=100.0,
                key="onboarding_spend_number_input"
            )

        st.markdown("<br>", unsafe_allow_html=True)
        st.button(
            f"✅ Confirm Spend Baseline: ₹{custom_spend:,.0f}", 
            type="primary", 
            use_container_width=True,
            key="confirm_spend_step_btn",
            on_click=complete_income_step, 
            args=(float(custom_spend),)
        )

    # --- STEP 4: READY & WELCOME GREETING ---
    elif step == "READY":
        user_name = st.session_state["household_financials"].get("user_name", "User")
        spend_val = st.session_state["household_financials"].get("typical_spend", 1500)

        st.success("🎉 **Setup Complete!**")
        
        welcome_text = f"Welcome {user_name}! Your rural banking assistant is ready." if lang == "en" else (f"स्वागत है {user_name}! आपका ग्रामीण बैंकिंग सहायक तैयार है।" if lang == "hi" else f"நல்வரவு {user_name}! உங்கள் கிராமப்புற வங்கி சேவை தயார்.")
        st.markdown(f"### 🔊 {welcome_text}")

        # Auto-play welcoming audio greeting
        welcome_audio = synthesize_speech(welcome_text, lang=lang)
        st.audio(welcome_audio, format="audio/mp3", autoplay=True)

        st.caption(f"Configured Household Baseline: **₹{spend_val:,.0f}** typical spend.")

        if st.button("🚀 Enter Main Dashboard", type="primary", use_container_width=True):
            st.session_state["is_onboarded"] = True
            st.rerun()
