import os
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import fitz  # PyMuPDF
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permitir peticiones de la extensión
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

TEMP_AUDIO_DIR = "temp_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

class TextRequest(BaseModel):
    text: str

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
    
    with open(pdf_path, "wb") as f:
        content = await file.read()
        f.write(content)
        
    text = extract_text_from_pdf(pdf_path)
    if not text:
        os.remove(pdf_path)
        raise HTTPException(status_code=400, detail="No se pudo extraer texto.")
        
    voice = "es-MX-DaliaNeural"
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(audio_path)
    except Exception as e:
        os.remove(pdf_path)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
        
    os.remove(pdf_path)
    return {"audio_url": f"http://localhost:8000/api/audio/{file_id}.mp3"}

@app.post("/api/tts")
async def convert_text_to_audio(request: TextRequest):
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="El texto está vacío")
        
    file_id = str(uuid.uuid4())
    audio_path = os.path.join(TEMP_AUDIO_DIR, f"{file_id}.mp3")
    
    voice = "es-MX-DaliaNeural"
    try:
        communicate = edge_tts.Communicate(request.text, voice)
        await communicate.save(audio_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
        
    return {"audio_url": f"http://localhost:8000/api/audio/{file_id}.mp3"}

@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    file_path = os.path.join(TEMP_AUDIO_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/mpeg")
    raise HTTPException(status_code=404, detail="Audio no encontrado")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
