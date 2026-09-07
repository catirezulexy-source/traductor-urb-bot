import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 Bot Asistente Activo."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- COMANDOS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🤖 *Bienvenido a tu Asistente Local*\n\n"
        "Comandos disponibles:\n"
        "• /mayus <texto> - Convierte texto a MAYÚSCULAS\n"
        "• /minus <texto> - Convierte texto a minúsculas\n"
        "• /calc <operación> - Realiza cálculos matemáticos\n"
        "• /convertir <monto> <de> <a_moneda> - Conversor básico\n"
        "• /plantilla <tipo> - Genera plantillas (correo, reunion, nota)"
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def mayus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = " ".join(context.args) if context.args else ""
    if not user_text:
        await update.message.reply_text("Escribe el texto a convertir. Ejemplo: /mayus hola mundo")
        return
    await update.message.reply_text(user_text.upper())

async def minus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = " ".join(context.args) if context.args else ""
    if not user_text:
        await update.message.reply_text("Escribe el texto a convertir. Ejemplo: /minus HOLA MUNDO")
        return
    await update.message.reply_text(user_text.lower())

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expr = " ".join(context.args) if context.args else ""
    if not expr:
        await update.message.reply_text("Escribe una operación. Ejemplo: /calc (50+20)*2")
        return

    try:
        caracteres_permitidos = "0123456789+-*/(). "
        if any(c not in caracteres_permitidos for c in expr):
            raise ValueError
        resultado = eval(expr)
        await update.message.reply_text(f"🔢 *Resultado:* {resultado}", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("Operación matemática no válida.")

async def convertir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ejemplo sencillo: conversión de unidades / monedas con tasa fija orientativa
    if len(context.args) < 3:
        await update.message.reply_text(
            "Formato no válido. Usa: `/convertir <monto> <de> <a_moneda>`\n"
            "Ejemplo: `/convertir 100 usd eur` o `/convertir 50 eur usd`",
            parse_mode="Markdown"
        )
        return

    try:
        monto = float(context.args[0])
        de = context.args[1].lower()
        a = context.args[2].lower()

        # Tasas de referencia fijas
        tasas = {
            ("usd", "eur"): 0.92,
            ("eur", "usd"): 1.09,
            ("usd", "mxn"): 18.0,
            ("mxn", "usd"): 0.055,
        }

        tasa = tasas.get((de, a))
        if tasa:
            total = round(monto * tasa, 2)
            await update.message.reply_text(f"💱 *Conversión:* {monto} {de.upper()} = {total} {a.upper()}", parse_mode="Markdown")
        else:
            await update.message.reply_text("Par de conversión no soportado de forma local. Prueba USD/EUR o USD/MXN.")
    except ValueError:
        await update.message.reply_text("El monto ingresado debe ser un número válido.")

async def plantilla_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = context.args[0].lower() if context.args else ""
    plantillas = {
        "correo": "Estimado/a [Nombre],\n\nEspero que se encuentre bien. Le escribo para...\n\nAtentamente,\n[Tu Nombre]",
        "reunion": "📋 *Minuta de Reunión*\n- Fecha:\n- Asistentes:\n- Puntos clave:\n- Acuerdos:",
        "nota": "📌 *Nota Ejecutiva*\n- Asunto:\n- Detalle:\n- Prioridad:"
    }
    if tipo in plantillas:
        await update.message.reply_text(plantillas[tipo], parse_mode="Markdown")
    else:
        await update.message.reply_text("Usa: `/plantilla correo`, `/plantilla reunion` o `/plantilla nota`", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text("Usa /start para ver las herramientas disponibles.")

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("mayus", mayus_command))
    app.add_handler(CommandHandler("minus", minus_command))
    app.add_handler(CommandHandler("calc", calc_command))
    app.add_handler(CommandHandler("convertir", convertir_command))
    app.add_handler(CommandHandler("plantilla", plantilla_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
