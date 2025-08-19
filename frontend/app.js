document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    // ❗ IMPORTANT: Replace these with your actual deployed URLs before launching!
    const API_BASE_URL = 'https://your-backend-app-engine-url.a.run.app';
    const WEBSOCKET_URL = 'wss://your-backend-app-engine-url.a.run.app/ws/translate/';
    const PAYSTACK_PUBLIC_KEY = 'pk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxx'; // Load from your .env and replace

    // --- Global State & DOM Elements ---
    let mediaRecorder;
    let websocket;
    let userEmail;
    let translatedAudioBlob;

    const welcomeScreen = document.getElementById('welcome-screen');
    const authScreen = document.getElementById('auth-screen');
    const mainApp = document.getElementById('main-app');
    const getStartedBtn = document.getElementById('get-started-btn');
    const signupForm = document.getElementById('signup-form');
    const downloadBtn = document.getElementById('download-btn');
    const micVisualizer = document.querySelector('.mic-visualizer');
    const inputArea = document.getElementById('input-area');
    const outputArea = document.getElementById('output-area');
    const targetLanguageSelect = document.getElementById('target-language');

    // --- UI Navigation ---
    const showScreen = (screen) => {
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        screen.classList.add('active');
    };

    getStartedBtn.addEventListener('click', () => showScreen(authScreen));

    // --- User Signup ---
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fullName = document.getElementById('full-name').value;
        const email = document.getElementById('email').value;
        const usagePurpose = document.getElementById('usage-purpose').value;
        
        try {
            const response = await fetch(`${API_BASE_URL}/users/signup/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: fullName, email, usage_purpose: usagePurpose }),
            });

            if (!response.ok) throw new Error('Signup failed.');
            const userData = await response.json();
            userEmail = userData.email;
            showScreen(mainApp);
            initializeTranslator();
        } catch (error) {
            console.error('Signup Error:', error);
            alert('Could not create account. Please try again.');
        }
    });

    // --- Core Translator Logic ---
    const initializeTranslator = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            setupWebSocket();
            setupMediaRecorder(stream);
        } catch (error) {
            console.error('Microphone access denied:', error);
            alert('Microphone access is required to use the translator.');
        }
    };

    const setupWebSocket = () => {
        websocket = new WebSocket(WEBSOCKET_URL);

        // 1. Connection Opened: Authenticate the user and set the target language.
        websocket.onopen = () => {
            console.log('WebSocket connection established.');
            websocket.send(JSON.stringify({
                type: 'auth',
                email: userEmail,
                target_lang: targetLanguageSelect.value
            }));
            mediaRecorder.start(1000); // Start recording, sending data every second.
        };

        // 4. Message Received: Handle incoming data from the backend.
        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };
        
        websocket.onclose = () => console.log('WebSocket connection closed.');
        websocket.onerror = (error) => console.error('WebSocket error:', error);

        // 2b. Language Change: Send updated configuration to the backend.
        targetLanguageSelect.addEventListener('change', () => {
            if (websocket.readyState === WebSocket.OPEN) {
                websocket.send(JSON.stringify({
                    type: 'config',
                    target_lang: targetLanguageSelect.value
                }));
            }
        });
    };

    const setupMediaRecorder = (stream) => {
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        
        // 2a. Audio Data: Send raw audio chunks to the backend as they become available.
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0 && websocket.readyState === WebSocket.OPEN) {
                websocket.send(event.data);
            }
        };

        mediaRecorder.onstart = () => micVisualizer.style.animationPlayState = 'running';
        mediaRecorder.onstop = () => micVisualizer.style.animationPlayState = 'paused';
    };

    const handleWebSocketMessage = (data) => {
        // This function acts as a router for messages from the backend
        switch (data.type) {
            case 'transcription_update': // Real-time transcription
                inputArea.textContent = data.text;
                break;
            case 'translation_result': // Final translated text and audio
                outputArea.textContent = data.text;
                const audioData = atob(data.audio); // Decode base64 audio
                const audioBytes = new Uint8Array(audioData.length);
                for (let i = 0; i < audioData.length; i++) {
                    audioBytes[i] = audioData.charCodeAt(i);
                }
                translatedAudioBlob = new Blob([audioBytes], { type: 'audio/mpeg' });
                const audio = new Audio(URL.createObjectURL(translatedAudioBlob));
                audio.play();
                downloadBtn.disabled = false;
                break;
            case 'payment_required': // Trial has expired
                mediaRecorder.stop();
                triggerPaystackPopup();
                break;
            case 'error': // An error occurred on the backend
                console.error('Backend Error:', data.message);
                alert(`An error occurred: ${data.message}`);
                break;
        }
    };

    // --- Download & Payment ---
    downloadBtn.addEventListener('click', () => {
        if (!translatedAudioBlob) return;
        const filenameInput = document.getElementById('audio-filename');
        const filename = filenameInput.value.trim() || `femseek-translation-${Date.now()}`;
        
        const url = URL.createObjectURL(translatedAudioBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${filename}.mp3`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
    });

    const triggerPaystackPopup = () => {
        const handler = PaystackPop.setup({
            key: PAYSTACK_PUBLIC_KEY,
            email: userEmail,
            amount: 500000, // 5000 NGN in kobo
            currency: 'NGN',
            ref: 'femseek-' + Math.floor((Math.random() * 1000000000) + 1),
            callback: function(response) {
                if (websocket.readyState === WebSocket.OPEN) {
                    websocket.send(JSON.stringify({ type: 'payment_verification', reference: response.reference }));
                }
                alert('Payment successful! Your access has been restored. Please refresh the page.');
                mediaRecorder.start(1000);
            },
            onClose: function() {
                alert('Subscription is required to continue using Femseek.');
            },
        });
        handler.openIframe();
    };

    showScreen(welcomeScreen);
});
