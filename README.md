# PDF a Audio (Text-to-Speech) 🎧

Una aplicación web sencilla que permite subir un archivo PDF, extraer su texto y generar un archivo de audio (MP3) utilizando inteligencia artificial de voz de alta calidad (voces neuronales de Microsoft Azure vía Edge TTS).

## Características ✨
- Interfaz gráfica limpia e intuitiva (Tailwind CSS).
- Procesamiento rápido con FastAPI.
- Voces ultrarrealistas y gratuitas sin necesidad de API Keys.
- Permite reproducir y descargar el audio generado.

## Tecnologías Utilizadas 🛠️
- **Backend:** Python, FastAPI, Uvicorn, PyMuPDF.
- **Frontend:** HTML5, JS Vanilla, Tailwind CSS.
- **IA (TTS):** edge-tts (Voces Neuronales).

## Instalación y Ejecución 🚀

1. Clona este repositorio:
   ```bash
   git clone https://github.com/TU-USUARIO/pdf-to-audio.git
   cd pdf-to-audio
   ```

2. Crea y activa un entorno virtual:
   ```bash
   python -m venv venv
   # En Windows:
   .\venv\Scripts\activate
   # En Mac/Linux:
   source venv/bin/activate
   ```

3. Instala las dependencias:
   ```bash
   pip install fastapi uvicorn python-multipart edge-tts PyMuPDF
   ```

4. Ejecuta el servidor:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. Abre tu navegador y ve a: [http://localhost:8000](http://localhost:8000)
