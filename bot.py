import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from google import genai

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Eres un asistente ejecutivo (secretario) altamente competente.
Tu tarea es ayudar al usuario a traducir textos a la perfección.
Si el usuario envía un texto sin especificar idioma, tradúcelo al español de forma natural y profesional.
"""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{SYSTEM_PROMPT}\n\nTexto a procesar:\n{user_text}"
        )
        reply_text = response.text
    except Exception as e:
        reply_text = "Disculpe, jefe. Ocurrió un error al procesar su solicitud."

    await update.message.reply_text(reply_text)

async def ia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    user_text = " ".join(context.args) if context.args else ""
    if not user_text:
        await update.message.reply_text("Por favor, escriba su pregunta después del comando. Ejemplo: /ia ¿Qué hora es?")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Responde de manera clara, profesional y directa a la siguiente consulta:\n{user_text}"
        )
        reply_text = response.text
    except Exception as e:
        reply_text = "Disculpe, jefe. Ocurrió un error al procesar su consulta."

    await update.message.reply_text(reply_text)

async def redactar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    user_text = " ".join(context.args) if context.args else ""
    if not user_text:
        await update.message.reply_text("Por favor, escriba o pegue el texto que desea corregir o redactar.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Mejora la ortografía, redacción y dale un tono profesional y natural al siguiente texto:\n{user_text}"
        )
        reply_text = response.text
    except Exception as e:
        reply_text = "Disculpe, jefe. Ocurrió un error al procesar la redacción."

    await update.message.reply_text(reply_text)

async def resumir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    user_text = " ".join(context.args) if context.args else ""
    if not user_text:
        await update.message.reply_text("Por favor, pegue el texto largo que desea que resuma.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Resume el siguiente texto extrayendo los puntos clave de manera clara y concisa:\n{user_text}"
        )
        reply_text = response.text
    except Exception as e:
        reply_text = "Disculpe, jefe. Ocurrió un error al procesar el resumen."

    await update.message.reply_text(reply_text)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("ia", ia_command))
    app.add_handler(CommandHandler("redactar", redactar_command))
    app.add_handler(CommandHandler("resumir", resumir_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot secretario con comandos en línea.")
    app.run_polling()

if __name__ == "__main__":
    main()
