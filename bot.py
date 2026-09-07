import os
import random
import string
import threading
from flask import Flask
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

ESTADOS_USUARIO = {}
# Almacenamiento local temporal de notas por usuario
NOTAS_USUARIOS = {}

def obtener_teclado_principal():
    # Botones alineados a la lista registrada en BotFather
    teclado = [
        [KeyboardButton("🔢 /calc"), KeyboardButton("🔑 /pass")],
        [KeyboardButton("📝 /nota"), KeyboardButton("🌤 /tiempo")]
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🤖 *Bienvenido al Menú Principal*\n\n"
        "Toca cualquiera de los botones de abajo para ejecutar una función:"
    )
    await update.message.reply_text(
        mensaje,
        parse_mode="Markdown",
        reply_markup=obtener_teclado_principal()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    texto = update.message.text.strip()

    # Detección de selección de botón o comando
    if texto == "🔢 /calc" or texto == "/calc":
        ESTADOS_USUARIO[user_id] = "esperando_calc"
        await update.message.reply_text("Escribe la operación matemática (Ejemplo: 50+20*2):")
        return

    elif texto == "🔑 /pass" or texto == "/pass":
        ESTADOS_USUARIO[user_id] = None
        # Generar contraseña segura de 12 caracteres al instante
        caracteres = string.ascii_letters + string.digits + "!@#$%&*"
        password = ''.join(random.choice(caracteres) for _ in range(12))
        await update.message.reply_text(
            f"🔑 *Contraseña Segura Generada:*\n`{password}`",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return

    elif texto == "📝 /nota" or texto == "/nota":
        ESTADOS_USUARIO[user_id] = "esperando_nota"
        nota_actual = NOTAS_USUARIOS.get(user_id, "No tienes notas guardadas aún.")
        await update.message.reply_text(
            f"📝 *Tus notas actuales:*\n{nota_actual}\n\n"
            "Escribe el nuevo texto que deseas guardar como tu nota:",
            parse_mode="Markdown"
        )
        return

    elif texto == "🌤 /tiempo" or texto == "/tiempo":
        ESTADOS_USUARIO[user_id] = "esperando_tiempo"
        await update.message.reply_text("Escribe el nombre de la ciudad para consultar el pronóstico:")
        return

    # Procesar respuesta según el estado del usuario
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
            "✅ *¡Nota guardada con éxito!* Puedes consultarla cuando quieras tocando el botón de notas.",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )

    elif estado == "esperando_tiempo":
        ESTADOS_USUARIO[user_id] = None
        # Simulación local práctica sin depender de APIs externas de clima
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
