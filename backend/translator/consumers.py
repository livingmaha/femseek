# backend/translator/consumers.py
import json
import base64
import asyncio
import os # Added for accessing env vars
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
import requests

# Import Google Cloud clients
from google.cloud import speech, translate_v2 as translate, texttospeech
from google.cloud.speech_v1 import RecognitionConfig, RecognitionAudio # For specific types

from users.models import User

# --- AI AGENT SYSTEM PROMPT ---
FEMSEEK_SYSTEM_PROMPT = """
You are Femseek, a hyper-efficient, culturally-aware, and low-latency AI agent for real-time voice translation.
Your primary purpose is to listen to live human speech, understand its intent, tone, and pauses, and provide a perfectly fluent, native-sounding translation in the target language.

Core Directives:
1.  **Empathy and Context**: Analyze the speaker's tone, emotion, and context to inform the translation. Do not perform a literal word-for-word translation. Instead, interpret the meaning and intent to provide a culturally appropriate and fluent translation. Ensure the translated output preserves the original sentiment and nuance.
2.  **Pause-Based Trigger**: You will receive chunks of speech. Your internal logic must detect a natural pause (a silence of at least 1.5 seconds). This pause is the signal to finalize the current utterance's translation and prepare for output.
3.  **Fluidity**: The translated voice must sound like a native speaker of the target language, not a robotic or stilted voice. Utilize the most natural-sounding voice options available (e.g., WaveNet or Neural2 voices if possible with the TTS API, ensure proper SSML for intonation if needed).
4.  **Efficiency**: Fetch and process all necessary API data (Speech-to-Text, Translation, Text-to-Speech) with maximum efficiency. Prioritize speed above all else to maintain the low-latency requirement. The translated sentence must be ready for playback within 2 seconds of the detected pause's start.
5.  **Languages**: Support translation to and from the following languages: English (en), Swahili (sw), Spanish (es), Portuguese (pt), Chinese (Mandarin) (zh), French (fr), and Hindi (hi). When detecting source language, use the most accurate detection possible.
6.  **Response Format**: Provide only the translated text and audio. Do not add conversational filler or explanations unless explicitly prompted for debugging.
"""


class TranslateConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Initialize clients once per connection
        # Google Cloud clients are typically thread-safe and can be reused
        self.speech_client = speech.SpeechAsyncClient()
        self.translate_client = translate.Client() # This client is synchronous, handle with run_until_complete or ThreadPoolExecutor
        self.tts_client = texttospeech.TextToSpeechAsyncClient()
        
        self.user = None
        self.target_lang = "en"
        
        # --- Pause Detection Logic ---
        self.audio_buffer = bytearray()
        self.pause_timer = None
        self.PAUSE_THRESHOLD = 1.5  # 1.5 seconds of silence
        self.recognition_config_initialized = False # Flag to ensure config is set once

        await self.accept()

    async def disconnect(self, close_code):
        if self.user:
            # Ensure asave is awaited
            await self.user.asave()
            print(f"User {self.user.email} trial sessions count updated to {self.user.trial_sessions_count}")
        if self.pause_timer:
            self.pause_timer.cancel()
        print(f"WebSocket disconnected with code: {close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        # --- Handle JSON messages for config and payments ---
        if text_data:
            try:
                data = json.loads(text_data)
                message_type = data.get('type')

                if message_type == 'auth':
                    await self.handle_auth(data)
                elif message_type == 'config':
                    self.target_lang = data.get('target_lang', 'en')
                    print(f"Target language set to: {self.target_lang}")
                elif message_type == 'payment_verification':
                    await self.verify_payment(data.get('reference'))
                else:
                    print(f"Unknown text message type: {message_type}")
            except json.JSONDecodeError:
                print(f"Received malformed JSON: {text_data}")
                await self.send_error("Invalid message format.")
            except Exception as e:
                print(f"Error handling text message: {e}")
                await self.send_error(f"Error processing message: {e}")

        # --- Handle raw audio data ---
        elif bytes_data:
            if not self.user:
                # User not authenticated yet, ask them to auth
                await self.send(json.dumps({'type': 'error', 'message': 'Please authenticate first.'}))
                return
            
            # Use await self.user.is_trial_active() since it's an async method in the model
            if not await self.user.is_trial_active():
                # Send payment required message if trial is over
                await self.send(json.dumps({'type': 'payment_required'}))
                return

            # Append incoming audio to the buffer
            self.audio_buffer.extend(bytes_data)

            # Reset the pause timer every time new audio arrives
            if self.pause_timer:
                self.pause_timer.cancel()
            
            # Create a new task for pause detection
            self.pause_timer = asyncio.create_task(self.detect_pause())

    async def handle_auth(self, data):
        try:
            # Use get_object_or_404 style for async ORM operations
            self.user = await User.objects.aget(email=data['email'])
            self.target_lang = data.get('target_lang', 'en')
            await self.send(json.dumps({'type': 'auth_success', 'message': 'Authentication successful.'}))
            print(f"User {self.user.email} authenticated. Trial active: {await self.user.is_trial_active()}")
        except User.DoesNotExist:
            print(f"Authentication failed for email: {data['email']}")
            await self.send_error("User not found. Please sign up or check your email.")
            # Do not close connection immediately, allow frontend to react
        except Exception as e:
            print(f"Error during authentication: {e}")
            await self.send_error(f"Authentication failed: {e}")

    async def detect_pause(self):
        """Waits for a pause and then triggers the translation process."""
        try:
            await asyncio.sleep(self.PAUSE_THRESHOLD)
            if len(self.audio_buffer) > 0:
                print(f"Pause detected. Processing {len(self.audio_buffer)} bytes of audio.")
                # A pause has been detected, process the buffered audio
                await self.process_translation(bytes(self.audio_buffer))
                # Clear the buffer for the next utterance
                self.audio_buffer.clear()
            else:
                print("Pause detected, but audio buffer is empty. Ignoring.")
        except asyncio.CancelledError:
            # Task was cancelled because new audio arrived
            pass
        except Exception as e:
            print(f"Error in detect_pause: {e}")
            await self.send_error(f"Internal error during pause detection: {e}")

    async def process_translation(self, audio_data):
        """The core function orchestrating the three Google Cloud APIs."""
        try:
            # 1. Google Speech-to-Text (STT)
            # Use WEBM_OPUS as specified in frontend
            # Set language_code to 'auto' for automatic detection as per prompt
            config = RecognitionConfig(
                encoding=RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code="auto",  # Detect source language automatically
                # Enable automatic punctuation for better transcription quality
                enable_automatic_punctuation=True,
                # Consider using diarization_config if speaker separation is ever needed
            )
            audio = RecognitionAudio(content=audio_data)
            
            print("Sending audio to STT...")
            stt_response = await self.speech_client.recognize(config=config, audio=audio)

            if not stt_response.results or not stt_response.results[0].alternatives:
                print("No speech detected or no alternatives found.")
                await self.send(json.dumps({'type': 'transcription_update', 'text': ''})) # Clear input area
                return # Ignore if no speech was detected

            transcribed_text = stt_response.results[0].alternatives[0].transcript
            print(f"Transcribed text: {transcribed_text}")
            await self.send(json.dumps({'type': 'transcription_update', 'text': transcribed_text}))

            # 2. Google Translation API (Synchronous call, run in executor)
            # The translate_v2.Client() is not async, so use run_until_complete
            print(f"Translating to {self.target_lang}: {transcribed_text}")
            loop = asyncio.get_event_loop()
            translation_result = await loop.run_in_executor(
                None, # Use default ThreadPoolExecutor
                lambda: self.translate_client.translate(transcribed_text, target_language=self.target_lang)
            )
            translated_text = translation_result['translatedText']
            print(f"Translated text: {translated_text}")


            # 3. Google Text-to-Speech (TTS)
            synthesis_input = texttospeech.SynthesisInput(text=translated_text)
            
            # Attempt to select a more natural voice using WaveNet or Neural2
            # Check available voices for your target_lang for best results
            # Example for English (en-US): 'en-US-Wavenet-D'
            # For other languages, list voices: gcloud text-to-speech list-voices --language-code=<lang_code>
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=self.target_lang,
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL, # Can be MALE, FEMALE, NEUTRAL
                name=f"{self.target_lang}-Wavenet-A" # Try WaveNet. Adjust as needed.
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                # Adjust speaking rate, pitch for naturalness
                speaking_rate=1.0, # 1.0 is normal
                pitch=0.0 # 0.0 is normal
            )
            
            print("Synthesizing speech...")
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
            print("Translation sent to frontend.")

            # Increment trial sessions count after successful translation
            if self.user and not self.user.is_subscribed:
                self.user.trial_sessions_count += 1
                await self.user.asave() # Await the async save
                print(f"Trial session count incremented for {self.user.email} to {self.user.trial_sessions_count}")


        except Exception as e:
            print(f"An error occurred during translation: {e}")
            await self.send_error(f"Failed to process translation: {e}. Please try again.")

    async def verify_payment(self, reference):
        if not self.user:
            await self.send_error("No user associated with this session for payment verification.")
            return

        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        
        # requests.get is synchronous, run in executor
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None, # Use default ThreadPoolExecutor
                lambda: requests.get(url, headers=headers, timeout=10) # Add timeout
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            response_json = response.json()

            if response_json['status'] and response_json['data']['status'] == 'success':
                self.user.is_subscribed = True
                self.user.trial_sessions_count = 0 # Reset trial count on subscription
                await self.user.asave()
                await self.send(json.dumps({'type': 'payment_success', 'message': 'Payment successful! Your access is restored.'}))
                print(f"Payment verified for {self.user.email}. User is now subscribed.")
            else:
                await self.send_error(f"Payment verification failed: {response_json.get('message', 'Unknown error')}")
                print(f"Payment verification failed for {self.user.email}: {response_json}")
        except requests.exceptions.RequestException as req_e:
            print(f"Network error during Paystack verification: {req_e}")
            await self.send_error(f"Network error during payment verification. Please try again.")
        except json.JSONDecodeError:
            print(f"Invalid JSON response from Paystack: {response.text}")
            await self.send_error("Could not parse payment verification response.")
        except Exception as e:
            print(f"An unexpected error occurred during payment verification: {e}")
            await self.send_error(f"Payment verification encountered an error: {e}")

    async def send_error(self, message):
        await self.send(json.dumps({'type': 'error', 'message': message}))
