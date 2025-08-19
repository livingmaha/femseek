document.addEventListener('DOMContentLoaded', () => {
    // --- Global State & DOM Elements ---
    const API_BASE_URL = 'https://your-backend-url.com'; // Replace with your deployed Django URL
    const WEBSOCKET_URL = 'wss://your-backend-url.com/ws/translate/'; // Replace with your deployed WebSocket URL
    const PAYSTACK_PUBLIC_KEY = 'YOUR_PAYSTACK_PUBLIC_KEY'; // Replace with your Paystack Public Key

    let mediaRecorder;
    let audioChunks = [];
    let websocket;
    let userEmail; // To be set after signup
    let translatedAudioBlob; // To store received audio data

    // Screens
    const welcomeScreen = document.getElementById('welcome-screen');
    const authScreen = document.getElementById('auth-screen');
    const mainApp = document.getElementById('main-app');

    // Buttons & Forms
    const getStartedBtn = document.getElementById('get-started-btn');
    const signupForm = document.getElementById('signup-form');
    const downloadBtn = document.getElementById('download-btn');

    // UI Elements
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

            userEmail = email;
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

        websocket.onopen = () => {
            console.log('WebSocket connection established.');
            // Send initial auth info
            websocket.send(JSON.stringify({
                type: 'auth',
                email: userEmail,
                target_lang: targetLanguageSelect.value
            }));
            mediaRecorder.start(500); // Start recording and send data every 500ms
        };

        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };
        
        websocket.onclose = () => {
            console.log('WebSocket connection closed.');
            // Optional: Implement reconnection logic here
        };

        websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        // Update target language on change
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
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0 && websocket.readyState === WebSocket.OPEN) {
                websocket.send(event.data);
            }
        };

        mediaRecorder.onstart = () => {
            micVisualizer.style.display = 'flex';
        };

        mediaRecorder.onstop = () => {
            micVisualizer.style.display = 'none';
        };
    };

    const handleWebSocketMessage = (data) => {
        switch (data.type) {
            case 'transcription':
                inputArea.textContent = data.text;
                break;
            case 'translation':
                outputArea.textContent = data.text;
                break;
            case 'audio_chunk':
                // The backend now sends the full audio file at once
                const audioData = atob(data.audio); // Decode base64
                const audioBytes = new Uint8Array(audioData.length);
                for (let i = 0; i < audioData.length; i++) {
                    audioBytes[i] = audioData.charCodeAt(i);
                }
                translatedAudioBlob = new Blob([audioBytes], { type: 'audio/mpeg' });
                const audio = new Audio(URL.createObjectURL(translatedAudioBlob));
                audio.play();
                downloadBtn.disabled = false;
                break;
            case 'payment_required':
                triggerPaystackPopup();
                break;
            case 'error':
                console.error('Backend Error:', data.message);
                alert(`An error occurred: ${data.message}`);
                break;
        }
    };

    // --- Download Logic ---
    downloadBtn.addEventListener('click', () => {
        if (!translatedAudioBlob) return;
        const filenameInput = document.getElementById('audio-filename');
        const filename = filenameInput.value.trim() || `femseek-translation-${Date.now()}`;
        
        const url = URL.createObjectURL(translatedAudioBlob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `${filename}.mp3`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    });

    // --- Payment Integration ---
    const triggerPaystackPopup = () => {
        const handler = PaystackPop.setup({
            key: PAYSTACK_PUBLIC_KEY,
            email: userEmail,
            amount: 500000, // Amount in kobo (e.g., 5000 NGN)
            currency: 'NGN', // Or your preferred currency
            ref: '' + Math.floor((Math.random() * 1000000000) + 1), // generates a pseudo-unique reference
            callback: function(response) {
                // Send transaction reference to backend for verification
                if (websocket.readyState === WebSocket.OPEN) {
                    websocket.send(JSON.stringify({
                        type: 'payment_verification',
                        reference: response.reference
                    }));
                }
                alert('Payment successful! Your access has been restored.');
            },
            onClose: function() {
                alert('Transaction was not completed. Please subscribe to continue using the service.');
            },
        });
        handler.openIframe();
    };

    // Initial check to see if we should start on the welcome screen or main app
    // In a real app, you'd check for a session token here.
    showScreen(welcomeScreen);
});
