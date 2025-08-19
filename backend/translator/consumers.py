import json
import asyncio
import base64
from channels.generic.websocket import AsyncWebsocketConsumer
from google.cloud import speech, translate_v2 as translate, texttospeech
from users.models import User
import requests
import os

class TranslateConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.speech_client = speech.SpeechAsyncClient()
        self.translate_client = translate.Client()
        self.tts_client = texttospeech.TextToSpeechAsyncClient()
        self.user = None
        self.target_lang = "en" # Default language

    async def disconnect(self, close_code):
        # On disconnect, increment the session count for the user
        if self.user:
            self.user.trial_sessions_count += 1
            await self.user.asave()

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            data = json.loads(text_data)
            # Handle initial auth and config messages
            if data.get('type') == 'auth':
                try:
                    self.user = await User.objects.get(email=data['email'])
                    self.target_lang = data.get('target_lang', 'en')
                    # Check trial status on connection
                    if not await self.user.is_trial_active():
                        await self.send(json.dumps({'type': 'payment_required'}))
                except User.DoesNotExist:
                    await self.close()

            elif data.get('type') == 'config':
                self.target_lang = data.get('target_lang', 'en')

            elif data.get('type') == 'payment_verification':
                await self.verify_payment(data['reference'])

        elif bytes_data:
            # Main audio processing logic
            if self.user and await self.user.is_trial_active():
                await self.process_audio(bytes_data)
            else:
                 await self.send(json.dumps({'type': 'payment_required'}))


    async def process_audio(self, audio_chunk):
        # In a real-world app, you would buffer audio and detect pauses (1.5s silence).
        # For this prototype, we'll process each chunk as a self-contained utterance for simplicity.
        # A more advanced implementation would use libraries like WebRTC VAD (Voice Activity Detection).

        try:
            # 1. Speech-to-Text
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000, # Common for web browsers
                language_code="auto", # Automatically detect source language
            )
            audio = speech.RecognitionAudio(content=audio_chunk)
            stt_response = await self.speech_client.recognize(config=config, audio=audio)

            if not stt_response.results or not stt_response.results[0].alternatives:
                return # No speech detected

            transcribed_text = stt_response.results[0].alternatives[0].transcript
            await self.send(json.dumps({'type': 'transcription', 'text': transcribed_text}))

            # 2. Translation
            translation_result = self.translate_client.translate(transcribed_text, target_language=self.target_lang)
            translated_text = translation_result['translatedText']
            await self.send(json.dumps({'type': 'translation', 'text': translated_text}))

            # 3. Text-to-Speech
            synthesis_input = texttospeech.SynthesisInput(text=translated_text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=self.target_lang,
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            tts_response = await self.tts_client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )

            # Send full audio file back, base64 encoded
            encoded_audio = base64.b64encode(tts_response.audio_content).decode('utf-8')
            await self.send(json.dumps({'type': 'audio_chunk', 'audio': encoded_audio}))

        except Exception as e:
            print(f"Error processing audio: {e}")
            await self.send(json.dumps({'type': 'error', 'message': str(e)}))

    async def verify_payment(self, reference):
        # Paystack Verification Logic
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {"Authorization": f"Bearer {os.environ.get('PAYSTACK_SECRET_KEY')}"}
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            res_data = response.json()
            if res_data['data']['status'] == 'success':
                self.user.is_subscribed = True
                await self.user.asave()
                # Optionally send a confirmation to the client
                await self.send(json.dumps({'type': 'payment_success'}))
