import io
import re
import hashlib
from gtts import gTTS
from core.config import get_keys

TTS_CACHE = {}

def transcribe_speech(audio_file, lang: str = "en", **kwargs) -> str:
    """
    Transcribes recorded audio from browser microphone.
    Accepts audio_file, lang, and **kwargs.
    Never returns hardcoded preset transaction phrases on fallback.
    """
    if "selected_lang" in kwargs:
        lang = kwargs["selected_lang"]
        
    try:
        keys = get_keys()
        
        # Read raw audio bytes
        audio_bytes = b""
        filename = "audio.webm"
        if hasattr(audio_file, "read"):
            audio_bytes = audio_file.read()
            filename = getattr(audio_file, "name", "audio.webm")
        elif isinstance(audio_file, bytes):
            audio_bytes = audio_file
        elif hasattr(audio_file, "getvalue"):
            audio_bytes = audio_file.getvalue()

        if not audio_bytes or len(audio_bytes) < 50:
            print("[VoiceService] Empty audio payload provided.")
            return ""

        # Detect container mime type from magic bytes
        mime_type = "audio/webm"
        if audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
            mime_type = "audio/webm"
        elif audio_bytes.startswith(b"OggS"):
            mime_type = "audio/ogg"
        elif audio_bytes.startswith(b"RIFF"):
            mime_type = "audio/wav"
        elif audio_bytes.startswith(b"ID3") or audio_bytes.startswith(b"\xff\xfb"):
            mime_type = "audio/mp3"

        # 1. Try Gemini Multimodal STT first (Handles raw WebM, OGG, WAV natively)
        if keys["HAS_GEMINI"] and audio_bytes:
            try:
                import google.generativeai as genai
                genai.configure(api_key=keys["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                context_hint = kwargs.get("context", "transaction")
                prompt = f"Transcribe this Indian voice recording into exact text for {context_hint}. Target language: {lang}. Return ONLY the verbatim transcribed words."
                response = model.generate_content([
                    prompt,
                    {"mime_type": mime_type, "data": audio_bytes}
                ])
                if response.text and response.text.strip():
                    return response.text.strip()
            except Exception as e:
                print(f"[VoiceService] Gemini audio STT error: {e}")

        # 2. Try Groq Whisper STT if configured
        if keys["HAS_GROQ"] and audio_bytes:
            try:
                from groq import Groq
                client = Groq(api_key=keys["GROQ_API_KEY"])
                
                kw = {
                    "file": (filename, audio_bytes),
                    "model": "whisper-large-v3",
                    "response_format": "json",
                    "temperature": 0.0
                }
                if lang in ["hi", "ta"]:
                    kw["language"] = lang

                transcription = client.audio.transcriptions.create(**kw)
                if transcription.text and transcription.text.strip():
                    return transcription.text.strip()
            except Exception as e:
                print(f"[VoiceService] Groq STT error: {e}")

        # 3. Try SpeechRecognition (Google Web Speech API for WAV audio)
        if audio_bytes:
            try:
                import speech_recognition as sr
                from pydub import AudioSegment
                
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
                wav_io = io.BytesIO()
                audio_segment.export(wav_io, format="wav")
                wav_io.seek(0)
                
                r = sr.Recognizer()
                with sr.AudioFile(wav_io) as source:
                    audio_data = r.record(source)
                
                lang_map = {"hi": "hi-IN", "ta": "ta-IN", "en": "en-IN"}
                target_lang = lang_map.get(lang, "en-IN")
                
                transcription = r.recognize_google(audio_data, language=target_lang)
                if transcription and transcription.strip():
                    return transcription.strip()
            except Exception as e:
                print(f"[VoiceService] SpeechRecognition error: {e}")

        # Return empty string if no speech engine could parse the recording
        return ""

    except Exception as e:
        print(f"[VoiceService] Overall transcribe_speech error: {e}")
        return ""


def transcribe_audio(audio_bytes, lang: str = "en", **kwargs) -> str:
    """Alias for transcribe_speech to support both function names smoothly."""
    return transcribe_speech(audio_bytes, lang=lang, **kwargs)


def sanitize_text_for_lang(text: str, target_lang: str) -> str:
    """Pre-processes text to ensure English terms (like 'SAFE alert') are converted into native script before gTTS synthesis."""
    text_str = str(text) if text is not None else ""

    clean = re.sub(r'<[^>]+>', '', text_str)
    clean = re.sub(r'[\*\#\_\[\]\`]', '', clean)

    if target_lang == "ta":
        clean = clean.replace("SAFE alert.", "பாதுகாப்பான பரிவர்த்தனை அறிவிப்பு.")
        clean = clean.replace("SAFE alert", "பாதுகாப்பான பரிவர்த்தனை அறிவிப்பு.")
        clean = clean.replace("CRITICAL alert.", "எச்சரிக்கை! இது அதிக ஆபத்தான பரிவர்த்தனை.")
        clean = clean.replace("CRITICAL alert", "எச்சரிக்கை! இது அதிக ஆபத்தான பரிவர்த்தனை.")
        clean = clean.replace("MODERATE alert.", "கவனமாக சரிபார்க்கவும்.")
        clean = clean.replace("MODERATE alert", "கவனமாக சரிபார்க்கவும்.")
        clean = re.sub(r'[^\w\s\.\,\₹\$\%\-\:\?\u0B80-\u0BFF0-9]', '', clean, flags=re.UNICODE).strip()
    elif target_lang == "hi":
        clean = clean.replace("SAFE alert.", "सुरक्षित लेन-देन सूचना।")
        clean = clean.replace("SAFE alert", "सुरक्षित लेन-देन सूचना।")
        clean = clean.replace("CRITICAL alert.", "चेतावनी! यह उच्च जोखिम भरा लेन-देन है।")
        clean = clean.replace("CRITICAL alert", "चेतावनी! यह उच्च जोखिम भरा लेन-देन है।")
        clean = clean.replace("MODERATE alert.", "सावधानीपूर्वक जांच करें।")
        clean = clean.replace("MODERATE alert", "सावधानीपूर्वक जांच करें।")
        clean = re.sub(r'[^\w\s\.\,\₹\$\%\-\:\?\u0900-\u097F0-9]', '', clean, flags=re.UNICODE).strip()
    else:
        clean = re.sub(r'[^\w\s\.\,\₹\$\%\-\:\?]', '', clean).strip()

    return clean


def synthesize_speech(text: str, lang: str = "en", **kwargs) -> io.BytesIO:
    """
    Generates MP3 audio using gTTS into an in-memory BytesIO buffer with fast dictionary caching.
    Accepts text, lang, and **kwargs.
    """
    if "selected_lang" in kwargs:
        lang = kwargs["selected_lang"]
    if "lang_code" in kwargs:
        lang = kwargs["lang_code"]

    gtts_lang_map = {
        "en": "en",
        "hi": "hi",
        "ta": "ta"
    }
    target_lang = gtts_lang_map.get(lang, "en")
    
    clean_text = sanitize_text_for_lang(text, target_lang)
    
    cache_key = (clean_text, target_lang)
    if cache_key in TTS_CACHE:
        return io.BytesIO(TTS_CACHE[cache_key])

    fp = io.BytesIO()
    try:
        if not clean_text:
            clean_text = "No text provided for speech synthesis." if target_lang == "en" else ("कोई पाठ प्रदान नहीं किया गया।" if target_lang == "hi" else "ஒலி பெற உரை எதுவும் வழங்கப்படவில்லை.")
        tts = gTTS(text=clean_text, lang=target_lang, slow=False)
        tts.write_to_fp(fp)
        audio_data = fp.getvalue()
        TTS_CACHE[cache_key] = audio_data
        return io.BytesIO(audio_data)
    except Exception as e:
        print(f"[VoiceService] gTTS Error: {e}")
        return io.BytesIO(b"")
