import os
import re
import random
import string
import threading
import urllib.parse
import urllib.request
import json
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

WEATHER_CODES = {
    0: "☀️ Despejado", 1: "🌤 Principalmente despejado", 2: "⛅ Parcialmente nublado",
    3: "☁️ Nublado", 45: "🌫 Niebla", 48: "🌫 Niebla con escarcha",
    51: "🌦 Llovizna ligera", 53: "🌦 Llovizna moderada", 55: "🌦 Llovizna densa",
    61: "🌧 Lluvia ligera", 63: "🌧 Lluvia moderada", 65: "🌧 Lluvia fuerte",
    71: "❄️ Nieve ligera", 73: "❄️ Nieve moderada", 75: "❄️ Nieve fuerte",
    80: "🌧 Chubascos ligeros", 81: "🌧 Chubascos moderados", 82: "🌧 Chubascos violentos",
    95: "🌩 Tormenta eléctrica"
}

def obtener_teclado_principal():
    teclado = [
        [KeyboardButton("🔢 /calc"), KeyboardButton("🔑 /pass")],
        [KeyboardButton("📝 /nota"), KeyboardButton("🌤 /tiempo")],
        [KeyboardButton("📲 /wa"), KeyboardButton("🆔 /id")],
        [KeyboardButton("🔗 /short")]
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

def acortar_para_downloader(url_larga):
    try:
        url_encoded = urllib.parse.quote(url_larga)
        api_url = f"https://is.gd/create.php?format=json&url={url_encoded}"
        
        req = urllib.request.Request(
            api_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            shorturl = data.get("shorturl", "")
            
            if shorturl:
                # Omitimos el protocolo para facilitar la escritura en la TV
                url_limpia = shorturl.replace("https://", "").replace("http://", "")
                
                return (
                    f"✅ *¡Enlace generado con éxito!*\n\n"
                    f"🌐 *Escribe en Downloader:* `{url_limpia}`\n\n"
                    f"💡 _En la app Downloader de tu TV ingresa `{url_limpia}` en la barra superior para iniciar la descarga directamente._"
                )

        return "⚠️ No se pudo generar el enlace acortado."

    except Exception as e:
        print(f"Error acortando URL: {e}")
        return "❌ Hubo un error al conectar con el servicio de acortado."

def obtener_clima_real(ciudad):
    try:
        ciudad_encoded = urllib.parse.quote(ciudad)
        url_geo = f"https://geocoding-api.open-meteo.com/v1/search?name={ciudad_encoded}&count=1&language=es&format=json"

        req_geo = urllib.request.Request(url_geo, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_geo, timeout=5) as resp:
            data_geo = json.loads(resp.read().decode())

        if not data_geo.get("results"):
            return f"❌ No se encontró la ciudad/país: *{ciudad}*"

        lugar = data_geo["results"][0]
        lat, lon = lugar["latitude"], lugar["longitude"]
        nombre_lugar = lugar.get("name", ciudad)
        pais = lugar.get("country", "")

        url_weather = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req_weather = urllib.request.Request(url_weather, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_weather, timeout=5) as resp:
            data_weather = json.loads(resp.read().decode())

        current = data_weather.get("current_weather", {})
        temp = current.get("temperature", "N/A")
        wind = current.get("windspeed", "N/A")
        code = current.get("weathercode", 0)

        condicion = WEATHER_CODES.get(code, "🌡 Clima variable")
        ubicacion_str = f"{nombre_lugar}, {pais}" if pais else nombre_lugar
        return f"🌤 *Clima actual en {ubicacion_str}:*\n\n• Estado: {condicion}\n• Temperatura: `{temp}°C`\n• Viento: `{wind} km/h`"
    except Exception as e:
        print(f"Error consultando clima: {e}")
        return "❌ Hubo un problema al consultar el servicio de clima."

# FUNCIONES INDEPENDIENTES PARA COMANDOS Y BOTONES
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = "🤖 *Bienvenido al Menú Principal*\n\nToca cualquiera de los botones o usa el menú para ejecutar una función al instante."
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def cmd_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_calc"
    await update.message.reply_text("Escribe la operación matemática (Ejemplo: 50+20*2):")

async def cmd_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = None
    caracteres = string.ascii_letters + string.digits + "!@#$%&*"
    password = ''.join(random.choice(caracteres) for _ in range(12))
    await update.message.reply_text(f"🔑 *Contraseña Segura Generada:*\n`{password}`", parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def cmd_nota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nota_actual = NOTAS_USUARIOS.get(user_id, "No tienes notas guardadas aún.")
    ESTADOS_USUARIO[user_id] = "esperando_nota"
    await update.message.reply_text(f"📝 *Tu nota actual:*\n{nota_actual}\n\nEscribe el nuevo texto que deseas guardar:", parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def cmd_tiempo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_tiempo"
    await update.message.reply_text("Escribe el nombre de la ciudad o país para consultar el clima real:")

async def cmd_wa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_wa"
    await update.message.reply_text("📲 *Generador de Enlace WhatsApp*\n\nEscribe el número de teléfono con el código de país (Ejemplo: `+5215512345678`):", parse_mode="Markdown")

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ESTADOS_USUARIO[user.id] = None
    username = f"@{user.username}" if user.username else "Sin username público"
    enlace_perfil = f"https://t.me/{user.username}" if user.username else "No disponible (crea un @username en tus ajustes)"

    info_perfil = (
        f"👤 *Información de tu Perfil de Telegram*\n\n"
        f"🆔 *ID Numérico:* `{user.id}`\n"
        f"👤 *Usuario:* {username}\n"
        f"🔗 *Enlace Directo:* {enlace_perfil}"
    )
    await update.message.reply_text(info_perfil, parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def cmd_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_short"
    await update.message.reply_text("🔗 *Acortador para Downloader*\n\nEscribe o pega el enlace URL largo que deseas acortar:", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    texto = update.message.text.strip()
    estado = ESTADOS_USUARIO.get(user_id)

    # Detección de botones táctiles con emojis
    if texto == "🔢 /calc":
        await cmd_calc(update, context)
        return
    elif texto == "🔑 /pass":
        await cmd_pass(update, context)
        return
    elif texto == "📝 /nota":
        await cmd_nota(update, context)
        return
    elif texto == "🌤 /tiempo":
        await cmd_tiempo(update, context)
        return
    elif texto == "📲 /wa":
        await cmd_wa(update, context)
        return
    elif texto == "🆔 /id":
        await cmd_id(update, context)
        return
    elif texto == "🔗 /short":
        await cmd_short(update, context)
        return

    # Procesamiento de estados pendientes de entrada de texto
    if estado == "esperando_calc":
        ESTADOS_USUARIO[user_id] = None
        try:
            caracteres_permitidos = "0123456789+-*/(). "
            if any(c not in caracteres_permitidos for c in texto):
                raise ValueError
            resultado = eval(texto)
            await update.message.reply_text(f"🔢 *Resultado:* `{resultado}`", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        except Exception:
            await update.message.reply_text("❌ Operación matemática no válida.", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_nota":
        ESTADOS_USUARIO[user_id] = None
        NOTAS_USUARIOS[user_id] = texto
        await update.message.reply_text("✅ *¡Nota guardada con éxito!* Toca de nuevo `/nota` cuando quieras consultarla.", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_tiempo":
        ESTADOS_USUARIO[user_id] = None
        reporte_clima = obtener_clima_real(texto)
        await update.message.reply_text(reporte_clima, parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_wa":
        ESTADOS_USUARIO[user_id] = None
        solo_numeros = re.sub(r"\D", "", texto)
        if len(solo_numeros) >= 7:
            await update.message.reply_text(f"📲 *Enlace listo para chatear:*\n\nhttps://wa.me/{solo_numeros}", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        else:
            await update.message.reply_text("❌ El número ingresado es muy corto o no es válido.", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_short":
        ESTADOS_USUARIO[user_id] = None
        if texto.startswith("http://") or texto.startswith("https://"):
            respuesta_short = acortar_para_downloader(texto)
            await update.message.reply_text(respuesta_short, parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        else:
            await update.message.reply_text("❌ URL no válida. Asegúrate de incluir `http://` o `https://`.", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        return

    await update.message.reply_text("Selecciona una opción del menú para comenzar:", reply_markup=obtener_teclado_principal())

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Manejadores explícitos para comandos del menú azul
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("calc", cmd_calc))
    app.add_handler(CommandHandler("pass", cmd_pass))
    app.add_handler(CommandHandler("nota", cmd_nota))
    app.add_handler(CommandHandler("tiempo", cmd_tiempo))
    app.add_handler(CommandHandler("wa", cmd_wa))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("short", cmd_short))

    # Manejador para botones del teclado táctil e ingreso de datos
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
