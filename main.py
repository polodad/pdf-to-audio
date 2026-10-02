import os
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import fitz  # PyMuPDF

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

TEMP_AUDIO_DIR = "temp_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text.strip()

@app.post("/api/convert")
async def convert_pdf_to_audio(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")
        
    file_id = str(uuid.uuid4())
    pdf_path = os.path.join(TEMP_AUDIO_DIR, f"{file_id}.pdf")
    audio_path = os.path.join(TEMP_AUDIO_DIR, f"{file_id}.mp3")
    
    # Guardar el PDF subido
    with open(pdf_path, "wb") as f:
        content = await file.read()
        f.write(content)
        
    # Extraer texto
    text = extract_text_from_pdf(pdf_path)
    if not text:
        os.remove(pdf_path)
        raise HTTPException(status_code=400, detail="No se pudo extraer texto del PDF o el PDF está vacío.")
        
    # Generar el audio usando edge-tts (voz de Dalia, México)
    voice = "es-MX-DaliaNeural"
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(audio_path)
    except Exception as e:
        os.remove(pdf_path)
        raise HTTPException(status_code=500, detail=f"Error generando audio: {str(e)}")
        
    # Limpiar el archivo PDF original para ahorrar espacio
    os.remove(pdf_path)
    
    # Devolver la ruta al archivo de audio
    return {"audio_url": f"/api/audio/{file_id}.mp3"}

@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    file_path = os.path.join(TEMP_AUDIO_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio no encontrado")

# Redireccionar la ruta raíz al index.html
@app.get("/")
async def root():
    return FileResponse("static/index.html")
