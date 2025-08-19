import json
import base64
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
import requests

# Import Google Cloud clients
from google.cloud import speech, translate_v2 as translate, texttospeech

from users.models import User

# --- AI AGENT SYSTEM PROMPT ---
FEMSEEK_SYSTEM_PROMPT = "..." # The full system prompt text from the previous response goes here

class TranslateConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Initialize clients once per connection
        self.speech_client = speech.SpeechAsyncClient()
        self.translate_client = translate.Client()
        self.tts_client = texttospeech.TextToSpeechAsyncClient()
        
        self.user = None
        self.target_lang = "en"
        
        # --- Pause Detection Logic ---
        self.audio_buffer = bytearray()
        self.pause_timer = None
        self.PAUSE_THRESHOLD = 1.5  # 1.5 seconds of silence

        await self.accept()

    async def disconnect(self, close_code):
        if self.user:
            self.user.trial_sessions_count += 1
            await self.user.asave()
        if self.pause_timer:
            self.pause_timer.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        # --- Handle JSON messages for config and payments ---
        if text_data:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'auth':
                await self.handle_auth(data)
            elif message_type == 'config':
                self.target_lang = data.get('target_lang', 'en')
            elif message_type == 'payment_verification':
                await self.verify_payment(data.get('reference'))

        # --- Handle raw audio data ---
        elif bytes_data:
            if not self.user or not await self.user.is_trial_active():
                # Send payment required message if trial is over
                await self.send(json.dumps({'type': 'payment_required'}))
                return

            # Append incoming audio to the buffer
            self.audio_buffer.extend(bytes_data)

            # Reset the pause timer every time new audio arrives
            if self.pause_timer:
                self.pause_timer.cancel()
            
            self.pause_timer = asyncio.create_task(self.detect_pause())

    async def handle_auth(self, data):
        try:
            self.user = await User.objects.get(email=data['email'])
            self.target_lang = data.get('target_lang', 'en')
        except User.DoesNotExist:
            await self.send_error("User not found. Please sign up again.")
            await self.close()

    async def detect_pause(self):
        """Waits for a pause and then triggers the translation process."""
        await asyncio.sleep(self.PAUSE_THRESHOLD)
        if len(self.audio_buffer) > 0:
            # A pause has been detected, process the buffered audio
            await self.process_translation(bytes(self.audio_buffer))
            # Clear the buffer for the next utterance
            self.audio_buffer.clear()

    async def process_translation(self, audio_data):
        """The core function orchestrating the three Google Cloud APIs."""
        try:
            # 1. Google Speech-to-Text (STT)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code="auto",  # Detect source language automatically
            )
            audio = speech.RecognitionAudio(content=audio_data)
            stt_response = await self.speech_client.recognize(config=config, audio=audio)

            if not stt_response.results or not stt_response.results[0].alternatives:
                return # Ignore if no speech was detected

            transcribed_text = stt_response.results[0].alternatives[0].transcript
            await self.send(json.dumps({'type': 'transcription_update', 'text': transcribed_text}))

            # 2. Google Translation API
            translation_result = self.translate_client.translate(transcribed_text, target_language=self.target_lang)
            translated_text = translation_result['translatedText']

            # 3. Google Text-to-Speech (TTS)
            synthesis_input = texttospeech.SynthesisInput(text=translated_text)
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=self.target_lang,
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            
            tts_response = await self.tts_client.synthesize_speech(
                input=synthesis_input, voice=voice_params, audio_config=audio_config
            )
            
            # Send the final result back to the client
            encoded_audio = base64.b64encode(tts_response.audio_content).decode('utf-8')
            await self.send(json.dumps({
                'type': 'translation_result',
                'text': translated_text,
                'audio': encoded_audio
            }))

        except Exception as e:
            print(f"An error occurred during translation: {e}")
            await self.send_error("Failed to process translation. Please try again.")

    async def verify_payment(self, reference):
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200 and response.json()['data']['status'] == 'success':
            self.user.is_subscribed = True
            await self.user.asave()

    async def send_error(self, message):
        await self.send(json.dumps({'type': 'error', 'message': message}))
