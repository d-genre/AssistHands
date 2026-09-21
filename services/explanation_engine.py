from typing import Dict
from core.config import get_keys

def get_vernacular_explanation(risk_assessment, lang: str = "en", recipient: str = "Merchant", amount: float = 0.0, purpose: str = "Payment") -> str:
    """
    Generates a dynamic, transaction-specific rural explanation mentioning the recipient, amount, and purpose.
    Uses Gemini LLM if API key is available, or structured localized templates.
    """
    lang = lang if lang in ["en", "hi", "ta"] else "en"
    amt_str = f"{amount:,.0f}" if amount > 0 else ""
    recipient_name = str(recipient) if recipient else "Merchant"
    purpose_desc = str(purpose) if purpose else "General Payment"
    flag_reason_lower = str(getattr(risk_assessment, "flag_reason", "")).lower()
    risk_lvl = str(getattr(risk_assessment, "risk_level", "SAFE"))

    keys = get_keys()
    if keys["HAS_GEMINI"]:
        try:
            import google.generativeai as genai
            genai.configure(api_key=keys["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            target_lang_str = "Hindi" if lang == "hi" else ("Tamil" if lang == "ta" else "English")
            
            prompt = f"""
            You are a wise village elder advising a resident.
            The resident wants to transfer ₹{amt_str} to "{recipient_name}" for "{purpose_desc}".
            Risk status: {risk_lvl}. Details: "{flag_reason_lower}".
            
            Generate a short, 1-2 sentence caution or reassurance in {target_lang_str}.
            MUST explicitly mention the recipient "{recipient_name}" and amount "₹{amt_str}".
            CRITICAL CONSTRAINTS:
            1. Language: {target_lang_str} (native script if Hindi or Tamil).
            2. NO BANKING JARGON: Do NOT use words like 'fraud', 'anomaly', 'baseline', 'unauthorized'.
            """
            response = model.generate_content(prompt)
            if response.text and len(response.text.strip()) > 5:
                return response.text.strip()
        except Exception as e:
            print(f"[ExplanationEngine] Gemini explanation error: {e}")

    # Structured Dynamic Fallback Templates (Per Transaction)
    if "scam" in flag_reason_lower or "lottery" in flag_reason_lower or "telegram" in flag_reason_lower:
        if lang == "ta":
            return f"ஆபத்து எச்சரிக்கை! {recipient_name}-க்கு ₹{amt_str} அனுப்புவது போலி லாட்டரி அல்லது மோசடியாகும். உங்கள் சேமிப்பை அனுப்ப வேண்டாம்!"
        elif lang == "hi":
            return f"खतरा! {recipient_name} को ₹{amt_str} भेजना फर्जी लॉटरी या ठगी का फ्रॉड लगता है। अपनी कमाई न भेजें!"
        else:
            return f"DANGER: Sending ₹{amt_str} to {recipient_name} looks like an unverified prize scam! Do not send your savings."

    if risk_lvl == "SAFE":
        if lang == "ta":
            return f"{recipient_name}-க்கு {purpose_desc}-க்காக ₹{amt_str} அனுப்புவது பாதுகாப்பானது. வழக்கமான பட்ஜெட்டில் உங்களது தெரிந்த நபருக்கு செல்கிறது."
        elif lang == "hi":
            return f"{recipient_name} को {purpose_desc} के लिए ₹{amt_str} का भुगतान सुरक्षित है। यह आपके बजट में परिचित व्यक्ति को जा रहा है।"
        else:
            return f"Paying ₹{amt_str} to {recipient_name} for {purpose_desc} is safe. It matches your routine budget with a familiar contact."

    if risk_lvl == "CRITICAL":
        if lang == "ta":
            return f"எச்சரிக்கை! {recipient_name}-க்கு ₹{amt_str} மிகப்பெரிய தொகையாகும். இது உங்கள் வழக்கமான செலவு எல்லையை விட அதிகம். அனுப்பும் முன் யோசிக்கவும்."
        elif lang == "hi":
            return f"चेतावनी! {recipient_name} को ₹{amt_str} बहुत बड़ी रकम है। यह आपकी सामान्य खर्च सीमा से अधिक है। आगे बढ़ने से पहले रुकें।"
        else:
            return f"Warning! Sending ₹{amt_str} to {recipient_name} is a very high transfer exceeding your normal limit. Please verify first."

    # MODERATE
    if lang == "ta":
        return f"கவனிக்கவும்: {recipient_name} உங்களுக்கு அறிமுகமில்லாத புதிய நபர். {purpose_desc}-க்காக ₹{amt_str} அனுப்பும் முன் இருமுறை சரிபார்க்கவும்."
    elif lang == "hi":
        return f"ध्यान दें: {recipient_name} एक नया अजनबी संपर्क है। {purpose_desc} के लिए ₹{amt_str} भेजने से पहले कृपया दो बार जांच लें।"
    else:
        return f"Caution: {recipient_name} is an unfamiliar contact. Please double-check before transferring ₹{amt_str} for {purpose_desc}."
