import os
import random
import string
import threading
import asyncio
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

def obtener_teclado_principal():
    teclado = [
        [KeyboardButton("🔢 /calc"), KeyboardButton("🔑 /pass")],
        [KeyboardButton("📝 /nota"), KeyboardButton("🌤 /tiempo")]
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🤖 *Bienvenido al Menú Principal*\n\n"
        "Toca cualquiera de los botones de abajo para ejecutar una función o envíame una nota de voz para guardarla automáticamente."
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

        # Ejecutamos Gemini en un hilo separado para no bloquear el bot
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
            "Selecciona una opción del menú táctil de abajo:",
            reply_markup=obtener_teclado_principal()
        )

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
