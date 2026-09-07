import os
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

def obtener_teclado_principal():
    # Botones alineados exactamente a la lista registrada en BotFather
    teclado = [
        [KeyboardButton("🔠 /mayus"), KeyboardButton("🔡 /minus")],
        [KeyboardButton("🔢 /calc"), KeyboardButton("💱 /convertir")],
        [KeyboardButton("📋 /plantilla")]
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

    # Detección de selección de botón
    if texto == "🔠 /mayus" or texto == "/mayus":
        ESTADOS_USUARIO[user_id] = "esperando_mayus"
        await update.message.reply_text("Escribe el texto que deseas convertir a MAYÚSCULAS:")
        return

    elif texto == "🔡 /minus" or texto == "/minus":
        ESTADOS_USUARIO[user_id] = "esperando_minus"
        await update.message.reply_text("Escribe el texto que deseas convertir a minúsculas:")
        return

    elif texto == "🔢 /calc" or texto == "/calc":
        ESTADOS_USUARIO[user_id] = "esperando_calc"
        await update.message.reply_text("Escribe la operación matemática (Ejemplo: 50+20*2):")
        return

    elif texto == "💱 /convertir" or texto == "/convertir":
        ESTADOS_USUARIO[user_id] = "esperando_convertir"
        await update.message.reply_text("Escribe el monto y las monedas. Ejemplo: `10 usd eur`", parse_mode="Markdown")
        return

    elif texto == "📋 /plantilla" or texto == "/plantilla":
        ESTADOS_USUARIO[user_id] = "esperando_plantilla"
        await update.message.reply_text("Escribe qué plantilla necesitas: *correo*, *reunion* o *nota*", parse_mode="Markdown")
        return

    # Procesar respuesta del usuario
    estado = ESTADOS_USUARIO.get(user_id)

    if estado == "esperando_mayus":
        ESTADOS_USUARIO[user_id] = None
        await update.message.reply_text(texto.upper(), reply_markup=obtener_teclado_principal())

    elif estado == "esperando_minus":
        ESTADOS_USUARIO[user_id] = None
        await update.message.reply_text(texto.lower(), reply_markup=obtener_teclado_principal())

    elif estado == "esperando_calc":
        ESTADOS_USUARIO[user_id] = None
        try:
            caracteres_permitidos = "0123456789+-*/(). "
            if any(c not in caracteres_permitidos for c in texto):
                raise ValueError
            resultado = eval(texto)
            await update.message.reply_text(f"🔢 *Resultado:* {resultado}", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        except Exception:
            await update.message.reply_text("Operación matemática no válida.", reply_markup=obtener_teclado_principal())

    elif estado == "esperando_convertir":
        ESTADOS_USUARIO[user_id] = None
        partes = texto.split()
        if len(partes) >= 3:
            try:
                monto = float(partes[0])
                de = partes[1].lower()
                a = partes[2].lower()
                tasas = {("usd", "eur"): 0.92, ("eur", "usd"): 1.09, ("usd", "mxn"): 18.0, ("mxn", "usd"): 0.055}
                tasa = tasas.get((de, a))
                if tasa:
                    total = round(monto * tasa, 2)
                    await update.message.reply_text(f"💱 *Resultado:* {monto} {de.upper()} = {total} {a.upper()}", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
                else:
                    await update.message.reply_text("Conversión no disponible en el diccionario local.", reply_markup=obtener_teclado_principal())
            except ValueError:
                await update.message.reply_text("El monto debe ser un número válido.", reply_markup=obtener_teclado_principal())
        else:
            await update.message.reply_text("Faltan datos. Ejemplo de uso: 10 usd eur", reply_markup=obtener_teclado_principal())

    elif estado == "esperando_plantilla":
        ESTADOS_USUARIO[user_id] = None
        tipo = texto.lower()
        plantillas = {
            "correo": "Estimado/a [Nombre],\n\nEspero que se encuentre bien. Le escribo para...\n\nAtentamente,\n[Tu Nombre]",
            "reunion": "📋 *Minuta de Reunión*\n- Fecha:\n- Asistentes:\n- Puntos clave:\n- Acuerdos:",
            "nota": "📌 *Nota Ejecutiva*\n- Asunto:\n- Detalle:\n- Prioridad:"
        }
        if tipo in plantillas:
            await update.message.reply_text(plantillas[tipo], parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        else:
            await update.message.reply_text("Opción no válida. Usa: correo, reunion o nota", reply_markup=obtener_teclado_principal())

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
