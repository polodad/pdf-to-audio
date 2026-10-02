chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "play-audio") {
        playTextWithAI(request.text);
    }
});

let currentAudio = null;
let playerContainer = null;

async function playTextWithAI(text) {
    if (currentAudio) {
        currentAudio.pause();
    }
    
    // Crear la UI flotante si no existe
    if (!playerContainer) {
        playerContainer = document.createElement('div');
        playerContainer.style.position = 'fixed';
        playerContainer.style.bottom = '20px';
        playerContainer.style.right = '20px';
        playerContainer.style.backgroundColor = '#ffffff';
        playerContainer.style.border = '1px solid #e5e7eb';
        playerContainer.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.1)';
        playerContainer.style.padding = '15px';
        playerContainer.style.borderRadius = '12px';
        playerContainer.style.zIndex = '999999';
        playerContainer.style.fontFamily = 'sans-serif';
        playerContainer.style.display = 'flex';
        playerContainer.style.flexDirection = 'column';
        playerContainer.style.gap = '10px';
        
        const title = document.createElement('div');
        title.innerHTML = '<strong>Audio IA</strong> 🎧 <span id="ia-status" style="color: #6b7280; font-size: 12px; margin-left: 10px;">Generando...</span>';
        
        const closeBtn = document.createElement('button');
        closeBtn.innerText = '✕';
        closeBtn.style.position = 'absolute';
        closeBtn.style.top = '10px';
        closeBtn.style.right = '10px';
        closeBtn.style.border = 'none';
        closeBtn.style.background = 'none';
        closeBtn.style.cursor = 'pointer';
        closeBtn.onclick = () => {
            if(currentAudio) currentAudio.pause();
            playerContainer.style.display = 'none';
        };

        const audioEl = document.createElement('audio');
        audioEl.controls = true;
        audioEl.id = 'ia-audio-player';
        audioEl.style.width = '250px';
        
        playerContainer.appendChild(title);
        playerContainer.appendChild(closeBtn);
        playerContainer.appendChild(audioEl);
        document.body.appendChild(playerContainer);
    }
    
    playerContainer.style.display = 'flex';
    document.getElementById('ia-status').innerText = 'Generando...';
    document.getElementById('ia-audio-player').src = '';

    try {
        // En un producto real de pago, aquí validarías la API Key del usuario o el token
        const response = await fetch('http://localhost:8000/api/tts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            document.getElementById('ia-status').innerText = '¡Listo!';
            const audioEl = document.getElementById('ia-audio-player');
            audioEl.src = data.audio_url;
            audioEl.play();
            currentAudio = audioEl;
        } else {
            document.getElementById('ia-status').innerText = 'Error';
            alert('Error al generar el audio: ' + data.detail);
        }
    } catch (e) {
        document.getElementById('ia-status').innerText = 'Error de conexión';
        console.error("Error contactando al servidor:", e);
    }
}
