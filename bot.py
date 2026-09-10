import os
import re
import random
import string
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 Bot Asistente Activo (Modo Local)."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

ESTADOS_USUARIO = {}
NOTAS_USUARIOS = {}

def obtener_teclado_principal():
    teclado = [
        [KeyboardButton("🔢 /calc"), KeyboardButton("🔑 /pass")],
        [KeyboardButton("📝 /nota"), KeyboardButton("🌤 /tiempo")],
        [KeyboardButton("📲 /wa")]
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🤖 *Bienvenido al Menú Principal*\n\n"
        "Toca cualquiera de los botones de abajo para ejecutar una función al instante."
    )
    await update.message.reply_text(
        mensaje,
        parse_mode="Markdown",
        reply_markup=obtener_teclado_principal()
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.voice:
        return

    user_id = update.effective_user.id
    processing_msg = await update.message.reply_text("🎙️ Guardando nota de voz...")

    file_path = f"/tmp/temp_voice_{user_id}.ogg"
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        await file.download_to_drive(file_path)

        NOTAS_USUARIOS[user_id] = f"[Nota de voz guardada: {voice.duration} seg]"

        if os.path.exists(file_path):
            os.remove(file_path)

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"✅ ¡Nota de voz guardada! ({voice.duration} segundos)",
            reply_markup=obtener_teclado_principal()
        )
    except Exception as e:
        print(f"ERROR EN VOZ: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text="❌ Error al procesar el archivo de voz.",
            reply_markup=obtener_teclado_principal()
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    texto = update.message.text.strip()
    estado = ESTADOS_USUARIO.get(user_id)

    # 1. COMANDOS DEL MENÚ PRINCIPAL
    if texto in ["🔢 /calc", "/calc"]:
        ESTADOS_USUARIO[user_id] = "esperando_calc"
        await update.message.reply_text("Escribe la operación matemática (Ejemplo: 50+20*2):")
        return

    elif texto in ["🔑 /pass", "/pass"]:
        ESTADOS_USUARIO[user_id] = None
        caracteres = string.ascii_letters + string.digits + "!@#$%&*"
        password = ''.join(random.choice(caracteres) for _ in range(12))
        await update.message.reply_text(
            f"🔑 *Contraseña Segura Generada:*\n`{password}`",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return

    elif texto in ["📝 /nota", "/nota"]:
        nota_actual = NOTAS_USUARIOS.get(user_id, "No tienes notas guardadas aún.")
        ESTADOS_USUARIO[user_id] = "esperando_nota"
        await update.message.reply_text(
            f"📝 Tu nota actual:\n{nota_actual}\n\nEscribe el nuevo texto que deseas guardar:",
            reply_markup=obtener_teclado_principal()
        )
        return

    elif texto in ["🌤 /tiempo", "/tiempo"]:
        ESTADOS_USUARIO[user_id] = "esperando_tiempo"
        await update.message.reply_text("Escribe el nombre de la ciudad para consultar el pronóstico:")
        return

    elif texto in ["📲 /wa", "/wa"]:
        ESTADOS_USUARIO[user_id] = "esperando_wa"
        await update.message.reply_text(
            "📲 *Generador de Enlace WhatsApp*\n\n"
            "Escribe el número de teléfono con el código de país (Ejemplo: `+5215512345678` o `18091234567`):",
            parse_mode="Markdown"
        )
        return

    # 2. PROCESAMIENTO DE ESTADOS PENDIENTES
    if estado == "esperando_calc":
        ESTADOS_USUARIO[user_id] = None
        try:
            caracteres_permitidos = "0123456789+-*/(). "
            if any(c not in caracteres_permitidos for c in texto):
                raise ValueError
            resultado = eval(texto)
            await update.message.reply_text(
                f"🔢 *Resultado:* `{resultado}`", 
                parse_mode="Markdown", 
                reply_markup=obtener_teclado_principal()
            )
        except Exception:
            await update.message.reply_text(
                "❌ Operación matemática no válida.", 
                reply_markup=obtener_teclado_principal()
            )
        return

    elif estado == "esperando_nota":
        ESTADOS_USUARIO[user_id] = None
        NOTAS_USUARIOS[user_id] = texto
        await update.message.reply_text(
            "✅ *¡Nota guardada con éxito!* Toca de nuevo `/nota` cuando quieras consultarla.",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return

    elif estado == "esperando_tiempo":
        ESTADOS_USUARIO[user_id] = None
        clima_simulado = f"🌤 Clima actual en *{texto.capitalize()}*: 24°C, Parcialmente nublado. Viento a 12 km/h."
        await update.message.reply_text(
            clima_simulado, 
            parse_mode="Markdown", 
            reply_markup=obtener_teclado_principal()
        )
        return

    elif estado == "esperando_wa":
        ESTADOS_USUARIO[user_id] = None
        # Limpiar el número dejando solo dígitos
        solo_numeros = re.sub(r"\D", "", texto)
        if len(solo_numeros) >= 7:
            link_wa = f"https://wa.me/{solo_numeros}"
            await update.message.reply_text(
                f"📲 *Enlace listo para chatear:*\n\n{link_wa}",
                parse_mode="Markdown",
                reply_markup=obtener_teclado_principal()
            )
        else:
            await update.message.reply_text(
                "❌ El número ingresado es muy corto o no es válido.",
                reply_markup=obtener_teclado_principal()
            )
        return

    # 3. RESPUESTA POR DEFECTO
    await update.message.reply_text(
        "Selecciona una opción del menú táctil para comenzar:",
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
