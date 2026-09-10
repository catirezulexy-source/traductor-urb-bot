import os
import random
import string
import threading
import asyncio
import zipfile
import struct
from flask import Flask
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 Bot Asistente Activo."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

ESTADOS_USUARIO = {}
NOTAS_USUARIOS = {}

# --- LÓGICA DE ANÁLISIS DEX ---
HIGH_CONFIDENCE_KEYWORDS = [
    b"Lcom/android/billingclient/api/",
    b"com.android.vending.BILLING",
    b"Lcom/revenuecat/purchases/",
    b"Lcom/qonversion/android/sdk/",
]

MEDIUM_CONFIDENCE_KEYWORDS = [
    b"isSubscribed", b"isPremium", b"isProUser", 
    b"getPurchasedItems", b"checkLicense", b"queryPurchases"
]

LOW_CONFIDENCE_KEYWORDS = [
    b"isPro", b"isVip", b"is_pro", b"isLocked", b"hasAccess"
]

def parse_dex_header(dex_bytes):
    if len(dex_bytes) < 112 or not dex_bytes.startswith(b"dex\n"):
        return None
    string_ids_size = struct.unpack_from("<I", dex_bytes, 56)[0]
    string_ids_off = struct.unpack_from("<I", dex_bytes, 60)[0]
    return {
        "string_ids_size": string_ids_size,
        "string_ids_off": string_ids_off
    }

def extract_dex_strings(dex_bytes, header):
    strings = set()
    size = header["string_ids_size"]
    off = header["string_ids_off"]
    
    for i in range(size):
        if off + (i * 4) + 4 > len(dex_bytes):
            break
        str_data_off = struct.unpack_from("<I", dex_bytes, off + (i * 4))[0]
        if str_data_off >= len(dex_bytes):
            continue
            
        pos = str_data_off
        length = 0
        shift = 0
        while True:
            if pos >= len(dex_bytes):
                break
            byte = dex_bytes[pos]
            pos += 1
            length |= (byte & 0x7f) << shift
            if not (byte & 0x80):
                break
            shift += 7
            
        str_bytes = dex_bytes[pos:pos + length]
        strings.add(str_bytes)
        
    return strings

def _analizar_apk_file(apk_path):
    high_matches = set()
    med_matches = set()
    low_matches = set()
    dex_count = 0

    with zipfile.ZipFile(apk_path, 'r') as apk_zip:
        dex_files = [f for f in apk_zip.infolist() if f.filename.endswith(".dex")]
        dex_count = len(dex_files)
        
        for file_info in dex_files:
            dex_bytes = apk_zip.read(file_info.filename)
            header = parse_dex_header(dex_bytes)
            if not header:
                continue
                
            extracted_strings = extract_dex_strings(dex_bytes, header)
            for s in extracted_strings:
                for kw in HIGH_CONFIDENCE_KEYWORDS:
                    if kw in s:
                        high_matches.add(s.decode('utf-8', errors='ignore'))
                for kw in MEDIUM_CONFIDENCE_KEYWORDS:
                    if kw == s:
                        med_matches.add(s.decode('utf-8', errors='ignore'))
                for kw in LOW_CONFIDENCE_KEYWORDS:
                    if kw == s:
                        low_matches.add(s.decode('utf-8', errors='ignore'))

    score = (len(high_matches) * 10) + (len(med_matches) * 3) + (len(low_matches) * 1)
    
    # Construcción del informe de texto
    informe = f"📦 *Análisis Estructurado DEX*\n"
    informe += f"📁 Archivos DEX analizados: `{dex_count}`\n\n"
    
    if high_matches:
        informe += "🚨 *SDKs de Facturación (Alta Confianza):*\n"
        for m in sorted(list(high_matches))[:5]:
            informe += f"• `{m}`\n"
        informe += "\n"

    if med_matches:
        informe += "⚠️ *Métodos/Variables (Confianza Media):*\n"
        for m in sorted(list(med_matches))[:5]:
            informe += f"• `{m}`\n"
        informe += "\n"

    informe += f"📈 *Puntuación de Confianza:* `{score}`\n"
    if score >= 10:
        informe += "🔴 *Veredicto:* Alta probabilidad de contener facturación en la app."
    elif score >= 3:
        informe += "🟡 *Veredicto:* Presencia de comprobaciones locales o atributos de versión pro."
    else:
        informe += "🟢 *Veredicto:* Poca o ninguna evidencia de facturación estándar."

    return informe

# --- FIN LÓGICA DEX ---

def obtener_teclado_principal():
    teclado = [
        [KeyboardButton("🔢 /calc"), KeyboardButton("🔑 /pass")],
        [KeyboardButton("📝 /nota"), KeyboardButton("🌤 /tiempo")]
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🤖 *Bienvenido al Menú Principal*\n\n"
        "Toca cualquiera de los botones de abajo para ejecutar una función, envíame una nota de voz o sube un archivo APK para escanearlo."
    )
    await update.message.reply_text(
        mensaje,
        parse_mode="Markdown",
        reply_markup=obtener_teclado_principal()
    )

def _transcribir_con_gemini(file_path):
    audio_file_ref = genai.upload_file(file_path)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content([
        audio_file_ref,
        "Transcribe este audio de manera exacta al idioma en el que se habla, devolviendo únicamente el texto de lo que se dice sin comentarios adicionales."
    ])
    texto = response.text.strip() if response.text else "[Audio vacío]"
    return audio_file_ref, texto

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.voice:
        return

    user_id = update.effective_user.id
    processing_msg = await update.message.reply_text("🎙️ Procesando nota de voz con Gemini...")

    file_path = f"/tmp/temp_voice_{user_id}.ogg"
    audio_file_ref = None
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        await file.download_to_drive(file_path)

        audio_file_ref, texto_transcrito = await asyncio.to_thread(_transcribir_con_gemini, file_path)

        if len(texto_transcrito) > 4000:
            texto_transcrito = texto_transcrito[:4000] + "..."

        NOTAS_USUARIOS[user_id] = texto_transcrito

        if os.path.exists(file_path):
            os.remove(file_path)

        if audio_file_ref:
            try:
                genai.delete_file(audio_file_ref.name)
            except:
                pass

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"✅ ¡Nota transcrita con Gemini!\n\n{texto_transcrito}",
            reply_markup=obtener_teclado_principal()
        )
    except Exception as e:
        print(f"ERROR EN VOZ GEMINI: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        if audio_file_ref:
            try:
                genai.delete_file(audio_file_ref.name)
            except:
                pass
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=processing_msg.message_id,
                text=f"❌ Error al procesar el audio: {e}",
                reply_markup=obtener_teclado_principal()
            )
        except Exception as edit_err:
            print(f"No se pudo editar el mensaje: {edit_err}")

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        return

    doc = update.message.document
    if not (doc.file_name.endswith('.apk') or doc.mime_type == 'application/vnd.android.package-archive'):
        return

    user_id = update.effective_user.id
    processing_msg = await update.message.reply_text("🔍 Analizando el archivo APK...")

    file_path = f"/tmp/temp_app_{user_id}_{random.randint(1000, 9999)}.apk"
    try:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(file_path)

        # Análisis ejecutado en hilo secundario no bloqueante
        resultado_informe = await asyncio.to_thread(_analizar_apk_file, file_path)

        if os.path.exists(file_path):
            os.remove(file_path)

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=resultado_informe,
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
    except zipfile.BadZipFile:
        if os.path.exists(file_path):
            os.remove(file_path)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text="❌ El archivo enviado no es un paquete APK/ZIP válido.",
            reply_markup=obtener_teclado_principal()
        )
    except Exception as e:
        print(f"ERROR EN ESCANEO APK: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"❌ Ocurrió un error durante el escaneo del APK: {e}",
            reply_markup=obtener_teclado_principal()
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    texto = update.message.text.strip()

    if texto == "🔢 /calc" or texto == "/calc":
        ESTADOS_USUARIO[user_id] = "esperando_calc"
        await update.message.reply_text("Escribe la operación matemática (Ejemplo: 50+20*2):")
        return

    elif texto == "🔑 /pass" or texto == "/pass":
        ESTADOS_USUARIO[user_id] = None
        caracteres = string.ascii_letters + string.digits + "!@#$%&*"
        password = ''.join(random.choice(caracteres) for _ in range(12))
        await update.message.reply_text(
            f"🔑 *Contraseña Segura Generada:*\n`{password}`",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return

    elif texto == "📝 /nota" or texto == "/nota":
        nota_actual = NOTAS_USUARIOS.get(user_id, "No tienes notas guardadas aún.")
        ESTADOS_USUARIO[user_id] = "esperando_nota"
        await update.message.reply_text(
            f"📝 Tu nota actual:\n{nota_actual}\n\nEscribe el nuevo texto que deseas guardar (o envíame una nota de voz):",
            reply_markup=obtener_teclado_principal()
        )
        return

    elif texto == "🌤 /tiempo" or texto == "/tiempo":
        ESTADOS_USUARIO[user_id] = "esperando_tiempo"
        await update.message.reply_text("Escribe el nombre de la ciudad para consultar el pronóstico:")
        return

    estado = ESTADOS_USUARIO.get(user_id)

    if estado == "esperando_calc":
        ESTADOS_USUARIO[user_id] = None
        try:
            caracteres_permitidos = "0123456789+-*/(). "
            if any(c not in caracteres_permitidos for c in texto):
                raise ValueError
            resultado = eval(texto)
            await update.message.reply_text(f"🔢 *Resultado:* {resultado}", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        except Exception:
            await update.message.reply_text("Operación matemática no válida.", reply_markup=obtener_teclado_principal())

    elif estado == "esperando_nota":
        ESTADOS_USUARIO[user_id] = None
        NOTAS_USUARIOS[user_id] = texto
        await update.message.reply_text(
            "✅ *¡Nota guardada con éxito!* Toca de nuevo `/nota` cuando quieras consultarla.",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )

    elif estado == "esperando_tiempo":
        ESTADOS_USUARIO[user_id] = None
        clima_simulado = f"🌤 Clima actual en *{texto.capitalize()}*: 24°C, Parcialmente nublado. Viento a 12 km/h."
        await update.message.reply_text(clima_simulado, parse_mode="Markdown", reply_markup=obtener_teclado_principal())

    else:
        await update.message.reply_text(
            "Selecciona una opción del menú táctil de abajo o sube un APK para escanearlo:",
            reply_markup=obtener_teclado_principal()
        )

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.MimeType("application/vnd.android.package-archive") | filters.Document.FileExtension("apk"), handle_apk))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
