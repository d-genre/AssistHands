# 🌾 AssistHands - Inclusive Rural Banking Assistant

**AssistHands** is a zero-text, 100% voice-driven financial service platform designed for low-literacy rural communities. It enables seamless digital banking, voice transaction execution, vernacular risk explanations, asymmetric household authorization, and reactive offline synchronization across **English**, **Hindi (हिन्दी)**, and **Tamil (தமிழ்)**.

---

## ✨ Key Features & Architecture

### 🎙️ 1. Zero-Text Voice Onboarding Assistant
- **Spoken Audio Guided Setup**: Guides first-time users step-by-step through voice audio prompts (`gTTS`).
- **Interactive Speech Recognition**: Captures user's real spoken name, preferred language, and spending baselines without static preset choices.
- **Vernacular Audio Previews**: Step-by-step voice guidance in English, Hindi, and Tamil.

### 🚫 2. 100% Job/Occupation-Agnostic Financial Risk Engine
- Evaluates transaction safety strictly on **pure financial patterns** (zero reliance on job/occupation stereotypes):
  - **Unfamiliar Contact**: Checks against past transaction history.
  - **Financial Spike Anomaly**: Detects amounts exceeding $3\times$ the user's spoken `typical_spend` baseline.
  - **Digital Scam Detection**: Scans for lottery, Telegram prize, or jackpot scam schemes.

### 🗣️ 3. Complete Vernacular Audio & Visual Parity
- Full UI catalog in [`services/translator.py`](services/translator.py) translating every button, card, header, alert, and toast message in **English**, **Hindi**, and **Tamil**.
- High-visibility **"🔊 Listen"** audio buttons on every section header and card so non-literate users can hear any screen prompt or warning out loud.

### 🏠 4. Asymmetric Household Role Controls (Youth vs. Elder)
- **Youth Profile (Operator)**: Initiates transactions. Any transaction exceeding ₹2,000 or flagged as a spend anomaly is automatically held for Elder verification.
- **Elder Profile (Approver)**: Displays visual and spoken audio caution banners. Approves held transfers using a 4-Digit PIN (Default: `1234`).

### 📡 5. Reactive Offline Auto-Flushing
- **Simulate Offline Mode**: Toggling offline mode ON queues voice transaction requests locally.
- **Automatic Sync Trap**: Toggling offline mode OFF auto-flushes queued items, updates balance & transaction logs, displays an `st.toast`, and plays spoken completion audio (*"Internet restored. [X] offline requests processed."*).

### 💳 6. Razorpay Sandbox & Keyless Simulator
- Integrated with the `razorpay` Python SDK.
- Functions keylessly out of the box using built-in simulated test callbacks (`pay_test_rural_xxxx`).

---

## 📋 Evaluator & Demo Guide

The app includes a collapsible **"📋 Demo & Evaluation Guide"** in the sidebar:

1. **Step 1 (Voice Onboarding)**: Click *"Restart Voice Setup Wizard"* in the sidebar to test 100% voice setup.
2. **Step 2 (Offline Sync)**: Turn *"Simulate Offline Mode"* ON $\rightarrow$ record a voice command $\rightarrow$ inspect offline queue $\rightarrow$ toggle OFF to watch automatic reactive queue flushing.
3. **Step 3 (Risk Engine)**: Test a safe transaction (*"Pay ₹450 to Kirana Store"*) vs a high-risk anomaly (*"Send ₹45,000 to Telegram Lottery"*).
4. **Step 4 (Asymmetric Authorization)**: Switch active role to **Youth** $\rightarrow$ request a ₹2,500 transfer $\rightarrow$ switch role to **Elder** $\rightarrow$ enter PIN `1234` to approve payment.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Internet connection (for Google Text-to-Speech audio synthesis and optional Gemini/Groq LLM queries).

### Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/d-genre/AssistHands.git
   cd AssistHands
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Keys (Optional)**:
   Create a `.env` file or configure via the app sidebar under **⚙️ API Key Settings**:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   GROQ_API_KEY=your_groq_api_key
   ```
   *(Note: The app runs keylessly with fallback heuristics if API keys are omitted).*

4. **Launch the Application**:
   ```bash
   streamlit run app.py
   ```
   Open `http://localhost:8522` in your browser.

---

## 📁 Project Structure

```
AssistHands/
├── app.py                      # Main Streamlit UI & state flow
├── core/
│   ├── config.py               # API key management & env loader
│   └── state.py                # Session state schema & balance management
├── services/
│   ├── onboarding_service.py   # Voice wizard & onboarding state machine
│   ├── voice_service.py        # Speech recognition & gTTS audio synthesis
│   ├── intent_parser.py        # NLU intent parser (Gemini / regex fallback)
│   ├── risk_engine.py          # Financial spike & scam risk evaluation
│   ├── explanation_engine.py   # Vernacular elder analogy generator
│   ├── payment_service.py      # Razorpay integration & test simulator
│   └── translator.py           # Multilingual catalog (EN, HI, TA)
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

---

## 📜 License
Licensed under the MIT License.
