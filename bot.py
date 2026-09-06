import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai

# Credenciales leídas de forma segura desde las variables de entorno de la nube
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Eres un asistente ejecutivo (secretario) altamente eficiente, profesional y políglota, especializado en traducción simultánea y gestión de comunicaciones globales.
Tu tarea es ayudar al usuario a traducir textos a cualquier idioma de forma impecable.
Si el usuario envía un texto sin especificar idioma de destino, tradúcelo al español si está en otro idioma, o al inglés si está en español, manteniendo un tono formal, claro y ejecutivo. Organiza la respuesta de forma limpia y profesional.
"""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{SYSTEM_PROMPT}\n\nTexto del usuario a procesar:\n{user_text}"
        )
        reply_text = response.text
    except Exception as e:
        reply_text = f"Disculpe, jefe. Ocurrió un error al procesar la traducción: {str(e)}"

    await update.message.reply_text(reply_text)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🤖 Bot secretario en línea.")
    app.run_polling()

if __name__ == "__main__":
    main()
