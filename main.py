import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status, Request, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import edge_tts
import fitz  # PyMuPDF
import stripe
from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt

# Cargar variables de entorno
load_dotenv()
stripe.api_key = os.getenv("STRIPE_API_KEY", "sk_test_placeholder")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")

# --- CONFIGURACIÓN DE BASE DE DATOS (SQLite) ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./audioia.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    credits = Column(Integer, default=5) 

Base.metadata.create_all(bind=engine)

# --- CONFIGURACIÓN DE SEGURIDAD Y JWT ---
SECRET_KEY = "tu_clave_super_secreta_para_jwt_cambiar_en_produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 semana

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- MODELOS PYDANTIC ---
class UserCreate(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TextRequest(BaseModel):
    text: str

class CheckoutRequest(BaseModel):
    plan: str

# --- DEPENDENCIA PARA OBTENER USUARIO ACTUAL ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(UserDB).filter(UserDB.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# --- FASTAPI APP ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

TEMP_AUDIO_DIR = "temp_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

# --- RUTAS DE STRIPE ---
@app.post("/api/create-checkout-session")
async def create_checkout_session(req: CheckoutRequest, current_user: UserDB = Depends(get_current_user)):
    # Definimos el precio según el plan
    if req.plan == "credits_50":
        # Paquete de 50 créditos por $5.00 USD
        amount = 500 # Centavos ($5.00)
        product_name = "50 Créditos de AudioIA"
        metadata = {"user_email": current_user.email, "credits_to_add": 50}
    elif req.plan == "pro_subscription":
        # Suscripción Pro por $9.00 USD (Para simplificar ahora lo hacemos como pago único de recarga gigante)
        # En Stripe real usarías price_id de un producto recurrente
        amount = 900
        product_name = "Suscripción Pro (1 Mes)"
        metadata = {"user_email": current_user.email, "credits_to_add": 1000} # 1000 créditos = "ilimitado" práctico
    else:
        raise HTTPException(status_code=400, detail="Plan inválido")

    try:
        session = stripe.checkout.Session.create(
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product_name,
                    },
                    'unit_amount': amount,
                },
                'quantity': 1,
            }],
            mode='payment',
            metadata=metadata,
            success_url=FRONTEND_URL + "/?success=true",
            cancel_url=FRONTEND_URL + "/?canceled=true",
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content={"message": "Invalid payload"})
    except stripe.error.SignatureVerificationError as e:
        return JSONResponse(status_code=400, content={"message": "Invalid signature"})
        
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_email = session['metadata'].get('user_email')
        credits_to_add = int(session['metadata'].get('credits_to_add', 0))
        
        if user_email and credits_to_add > 0:
            user = db.query(UserDB).filter(UserDB.email == user_email).first()
            if user:
                user.credits += credits_to_add
                db.commit()
                print(f"✅ Se añadieron {credits_to_add} créditos al usuario {user_email}.")
                
    return {"status": "success"}

# --- RUTAS DE AUTENTICACIÓN ---
@app.post("/api/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    hashed_pw = get_password_hash(user.password)
    new_user = UserDB(email=user.email, hashed_password=hashed_pw, credits=5)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Usuario creado exitosamente"}

@app.post("/api/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Email o contraseña incorrectos")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me")
def read_users_me(current_user: UserDB = Depends(get_current_user)):
    credits_to_show = "∞" if current_user.email == "reyesmonroyemilianoleopoldo@gmail.com" else current_user.credits
    return {"email": current_user.email, "credits": credits_to_show}

# --- RUTAS DE AUDIO ---
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
async def convert_pdf_to_audio(
    file: UploadFile = File(...), 
    current_user: UserDB = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.credits <= 0:
        raise HTTPException(status_code=402, detail="No tienes créditos suficientes. Por favor, recarga tu cuenta.")
        
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
        
        # Descontar crédito solo si no es el administrador
        if current_user.email != "reyesmonroyemilianoleopoldo@gmail.com":
            current_user.credits -= 1
            db.commit()
    except Exception as e:
        os.remove(pdf_path)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
        
    os.remove(pdf_path)
    
    # Mostrar créditos infinitos para el admin en la respuesta
    credits_to_show = "∞" if current_user.email == "reyesmonroyemilianoleopoldo@gmail.com" else current_user.credits
    return {"audio_url": f"/api/audio/{file_id}.mp3", "credits_remaining": credits_to_show}

@app.post("/api/tts")
async def convert_text_to_audio(
    request: TextRequest, 
    current_user: UserDB = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.credits <= 0:
        raise HTTPException(status_code=402, detail="No tienes créditos suficientes.")
        
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="El texto está vacío")
        
    file_id = str(uuid.uuid4())
    audio_path = os.path.join(TEMP_AUDIO_DIR, f"{file_id}.mp3")
    
    voice = "es-MX-DaliaNeural"
    try:
        communicate = edge_tts.Communicate(request.text, voice)
        await communicate.save(audio_path)
        
        if current_user.email != "reyesmonroyemilianoleopoldo@gmail.com":
            current_user.credits -= 1
            db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
        
    credits_to_show = "∞" if current_user.email == "reyesmonroyemilianoleopoldo@gmail.com" else current_user.credits
    return {"audio_url": f"http://localhost:8000/api/audio/{file_id}.mp3", "credits_remaining": credits_to_show}

# Variables globales para el modelo XTTS
tts_model = None
xtts_loaded = False

@app.post("/api/clone-voice")
async def clone_voice(
    text: str = Form(...),
    file: UploadFile = File(...),
    current_user: UserDB = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    global tts_model, xtts_loaded
    
    if current_user.credits <= 4 and current_user.email != "reyesmonroyemilianoleopoldo@gmail.com":
        raise HTTPException(status_code=402, detail="No tienes suficientes créditos (Cuesta 5 créditos).")
        
    try:
        if not xtts_loaded:
            import torch
            from TTS.api import TTS
            print("Cargando modelo XTTS en memoria (esto tomará unos segundos)...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
            xtts_loaded = True
            print("¡Modelo XTTS cargado exitosamente en", device, "!")
    except ImportError:
        raise HTTPException(status_code=501, detail="La clonación de voz está desactivada temporalmente (faltan librerías TTS).")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cargando el modelo de IA: {str(e)}")

    file_id = str(uuid.uuid4())
    ref_audio_path = os.path.join(TEMP_AUDIO_DIR, f"{file_id}_ref.wav")
    output_audio_path = os.path.join(TEMP_AUDIO_DIR, f"{file_id}_cloned.wav")
    
    with open(ref_audio_path, "wb") as f:
        content = await file.read()
        f.write(content)
        
    try:
        # Generar audio clonado
        tts_model.tts_to_file(
            text=text, 
            speaker_wav=ref_audio_path, 
            language="es", 
            file_path=output_audio_path
        )
        
        if current_user.email != "reyesmonroyemilianoleopoldo@gmail.com":
            current_user.credits -= 5
            db.commit()
    except Exception as e:
        os.remove(ref_audio_path)
        raise HTTPException(status_code=500, detail=f"Error en clonación: {str(e)}")
        
    os.remove(ref_audio_path)
    
    credits_to_show = "∞" if current_user.email == "reyesmonroyemilianoleopoldo@gmail.com" else current_user.credits
    return {"audio_url": f"/api/audio/{file_id}_cloned.wav", "credits_remaining": credits_to_show}

@app.get("/api/audio/{filename}")
async def get_audio(filename: str):
    file_path = os.path.join(TEMP_AUDIO_DIR, filename)
    if os.path.exists(file_path):
        media_type = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
        return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Audio no encontrado")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
