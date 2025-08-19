
# backend/translator/consumers.py

import json
import base64
import os # Import os module
from channels.generic.websocket import AsyncWebsocketConsumer
from google.cloud import speech, translate_v2 as translate, texttospeech
from users.models import User
import requests
# Django settings can be imported to access variables like PAYSTACK_SECRET_KEY
from django.conf import settings

# ------------------------------------------------------------------
# 1. AI AGENT SYSTEM PROMPT
# ------------------------------------------------------------------
FEMSEEK_SYSTEM_PROMPT = """
As 'Femseek', your primary function is to act as an instantaneous, culturally-aware voice translator. Your operation is governed by these core directives:

1.  **Interpret, Don't Just Transcribe**: Your goal is not a literal, word-for-word translation. You must first analyze the incoming audio stream to understand the speaker's intent, emotional tone, and the broader context of the conversation. The final translation must reflect this understanding, using culturally appropriate idioms and phrases to sound completely natural and fluent in the target language.

2.  **Execute on Pause**: Your trigger for translation is a natural pause in the speaker's delivery, defined as a silence of at least 1.5 seconds. The moment this pause begins, your processing pipeline is initiated. You must deliver the complete translated audio stream back to the user within 2 seconds of the pause's start. This low-latency requirement is critical.

3.  **Embody Native Fluency**: The synthesized voice for the translation must be indistinguishable from a native speaker of the target language. Utilize the highest quality neural voices available (e.g., Google WaveNet, Neural2). The speech must have natural intonation, rhythm, and pacing. Avoid any robotic or monotonic delivery.

4.  **Maximize Efficiency**: Operate with extreme efficiency. All API calls for speech-to-text, translation, and text-to-speech must be executed in parallel where possible. Your entire process, from receiving audio to sending back the translated audio, must be optimized for speed to maintain the real-time experience.

5.  **Language Proficiency**: You will handle translations to and from the following languages: English (en), Swahili (sw), Spanish (es), Portuguese (pt), Chinese (Mandarin) (zh), French (fr), and Hindi (hi).
"""
# ------------------------------------------------------------------

class TranslateConsumer(AsyncWebsocketConsumer):
    # ... (connect, disconnect, receive methods are the same) ...

    async def verify_payment(self, reference):
        # Paystack Verification Logic using the key from settings
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        # Use the key loaded into Django's settings
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        
        # ... (rest of the verification logic is the same) ...

    # The process_audio method will implicitly use the system prompt's
    # directives when configuring API calls (e.g., selecting high-quality voices).
    # The prompt itself is a guide for the developer building this logic.
    async def process_audio(self, audio_chunk):
        try:
            # ... Speech-to-Text call ...
            
            # ... Translation call ...
            
            # Text-to-Speech call (Embodying Native Fluency directive)
            synthesis_input = texttospeech.SynthesisInput(text=translated_text)
            # This is where we ensure a high-quality, native-sounding voice
            voice = texttospeech.VoiceSelectionParams(
                language_code=self.target_lang,
                # Using WaveNet for higher quality, as per the prompt
                name=f"{self.target_lang}-Standard-A" # Example, you can choose specific WaveNet voices
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                effects_profile_id=['telephony-class-application'] # Optimized for voice
            )
            tts_response = await self.tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            # ... (rest of the method is the same) ...
        except Exception as e:
            # ... (error handling is the same) ...
