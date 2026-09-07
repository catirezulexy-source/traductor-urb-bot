import os
import threading
import unicodedata
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from google import genai

# Forzar codificación UTF-8 en el entorno
os.environ["PYTHONIOENCODING"] = "utf-8"

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 Bot activo y funcionando correctamente."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Eres un asistente ejecutivo (secretario) altamente competente.
Tu tarea es ayudar al usuario a traducir textos a la perfección.
Si el usuario envía un texto sin especificar idioma, tradúcelo al español de forma natural y profesional.
"""

def clean_text(text: str) -> str:
    """Remueve caracteres invisibles de formato Unicode (\u200e, etc.) y normaliza a UTF-8."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    return "".join(c for c in text if unicodedata.category(c) != "Cf").strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = clean_text(update.message.text)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{SYSTEM_PROMPT}\n\nTexto a procesar:\n{user_text}"
        )
        reply_text = clean_text(response.text)
    except Exception:
        reply_text = "Disculpe, jefe. Ocurrió un error al procesar la solicitud con la IA."

    await update.message.reply_text(reply_text)

async def ia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = " ".join(context.args) if context.args else ""
    user_text = clean_text(raw_text)

    if not user_text:
        await update.message.reply_text("Por favor, escriba su pregunta después del comando.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Responde de manera clara, profesional y directa:\n{user_text}"
        )
        reply_text = clean_text(response.text)
    except Exception:
        reply_text = "Disculpe, jefe. Ocurrió un error al procesar su consulta."

    await update.message.reply_text(reply_text)

async def redactar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = " ".join(context.args) if context.args else ""
    user_text = clean_text(raw_text)

    if not user_text:
        await update.message.reply_text("Por favor, escriba el texto que desea corregir.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Mejora la ortografía y redacción de este texto:\n{user_text}"
        )
        reply_text = clean_text(response.text)
    except Exception:
        reply_text = "Disculpe, jefe. Ocurrió un error al redactar el texto."

    await update.message.reply_text(reply_text)

async def resumir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = " ".join(context.args) if context.args else ""
    user_text = clean_text(raw_text)

    if not user_text:
        await update.message.reply_text("Por favor, pegue el texto que desea resumir.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Resume extrayendo los puntos clave:\n{user_text}"
        )
        reply_text = clean_text(response.text)
    except Exception:
        reply_text = "Disculpe, jefe. Ocurrió un error al resumir el texto."

    await update.message.reply_text(reply_text)

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("ia", ia_command))
    app.add_handler(CommandHandler("redactar", redactar_command))
    app.add_handler(CommandHandler("resumir", resumir_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
