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
from apscheduler.schedulers.background import BackgroundScheduler

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
# Diccionario para guardar la ciudad favorita de cada usuario para las alertas de lluvia: {user_id: "Ciudad"}
SUSCRIPTORES_CLIMA = {}

# Mensaje de bienvenida y reglas por defecto para grupos
MENSAJE_REGLAS = (
    "📜 *Reglas del Grupo*:\n\n"
    "1️⃣ Mantén el respeto hacia todos los miembros.\n"
    "2️⃣ No compartas enlaces de spam o contenido no solicitado.\n"
    "3️⃣ Usa los canales o temas adecuados para cada conversación.\n\n"
    "¡Disfruta tu estancia y participa con confianza! 🤖"
)

# Mapeo simple de códigos de clima de Open-Meteo
WEATHER_CODES = {
    0: "☀️ Despejado",
    1: "🌤 Principalmente despejado",
    2: "⛅ Parcialmente nublado",
    3: "☁️ Nublado",
    45: "🌫 Niebla",
    48: "🌫 Niebla con escarcha",
    51: "🌦 Llovizna ligera",
    53: "🌦 Llovizna moderada",
    55: "🌦 Llovizna densa",
    61: "🌧 Lluvia ligera",
    63: "🌧 Lluvia moderada",
    65: "🌧 Lluvia fuerte",
    71: "❄️ Nieve ligera",
    73: "❄️ Nieve moderada",
    75: "❄️ Nieve fuerte",
    80: "🌧 Chubascos ligeros",
    81: "🌧 Chubascos moderados",
    82: "🌧 Chubascos violentos",
    95: "🌩 Tormenta eléctrica"
}

# Códigos de Open-Meteo que se consideran lluvia o tormenta
CODIGOS_LLUVIA = [51, 53, 55, 61, 63, 65, 80, 81, 82, 95]

def obtener_teclado_principal():
    teclado = [
        [KeyboardButton("🔢 /calc"), KeyboardButton("🔑 /pass")],
        [KeyboardButton("📝 /nota"), KeyboardButton("🌤 /tiempo")],
        [KeyboardButton("📲 /wa"), KeyboardButton("🆔 /id")],
        [KeyboardButton("🔔 /alerta_lluvia")]
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

def obtener_clima_real(ciudad):
    try:
        ciudad_encoded = urllib.parse.quote(ciudad)
        url_geo = f"https://geocoding-api.open-meteo.com/v1/search?name={ciudad_encoded}&count=1&language=es&format=json"
        
        req_geo = urllib.request.Request(url_geo, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_geo, timeout=10) as resp:
            data_geo = json.loads(resp.read().decode())
        
        if not data_geo.get("results"):
            return f"❌ No se encontró la ciudad/país: *{ciudad}*", None, None
            
        lugar = data_geo["results"][0]
        lat = lugar["latitude"]
        lon = lugar["longitude"]
        nombre_lugar = lugar.get("name", ciudad)
        pais = lugar.get("country", "")
        
        url_weather = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req_weather = urllib.request.Request(url_weather, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_weather, timeout=10) as resp:
            data_weather = json.loads(resp.read().decode())
            
        current = data_weather.get("current_weather", {})
        temp = current.get("temperature", "N/A")
        wind = current.get("windspeed", "N/A")
        code = current.get("weathercode", 0)
        
        condicion = WEATHER_CODES.get(code, "🌡 Clima variable")
        ubicacion_str = f"{nombre_lugar}, {pais}" if pais else nombre_lugar
        
        reporte = f"🌤 *Clima actual en {ubicacion_str}:*\n\n• Estado: {condicion}\n• Temperatura: `{temp}°C`\n• Viento: `{wind} km/h`"
        return reporte, code, ubicacion_str
    except Exception as e:
        print(f"❌ Error detallado en clima para '{ciudad}': {repr(e)}")
        return f"❌ Error de conexión al consultar el clima.", None, None

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

async def reglas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(MENSAJE_REGLAS, parse_mode="Markdown")

async def bienvenida_nuevo_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
        
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue
            
        nombre = member.first_name or "Amigo"
        saludo = (
            f"👋 ¡Bienvenido/a al grupo, {nombre}!\n\n"
            f"{MENSAJE_REGLAS}"
        )
        await update.message.reply_text(saludo, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
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
            f"📝 *Tu nota actual:*\n{nota_actual}\n\nEscribe el nuevo texto que deseas guardar:",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return

    elif texto in ["🌤 /tiempo", "/tiempo"]:
        ESTADOS_USUARIO[user_id] = "esperando_tiempo"
        await update.message.reply_text("Escribe el nombre de la ciudad o país para consultar el clima real:")
        return

    elif texto in ["🔔 /alerta_lluvia", "/alerta_lluvia"]:
        ESTADOS_USUARIO[user_id] = "esperando_alerta_lluvia"
        await update.message.reply_text(
            "🔔 *Configurar Alerta Automática de Lluvia*\n\n"
            "Escribe el nombre de tu ciudad para avisarte automáticamente si comienza a llover:",
            parse_mode="Markdown"
        )
        return

    elif texto in ["📲 /wa", "/wa"]:
        ESTADOS_USUARIO[user_id] = "esperando_wa"
        await update.message.reply_text(
            "📲 *Generador de Enlace WhatsApp*\n\n"
            "Escribe el número de teléfono con el código de país (Ejemplo: `+5215512345678`):",
            parse_mode="Markdown"
        )
        return

    elif texto in ["🆔 /id", "/id"]:
        ESTADOS_USUARIO[user_id] = None
        username = f"@{user.username}" if user.username else "Sin username público"
        enlace_perfil = f"https://t.me/{user.username}" if user.username else "No disponible"
        
        info_perfil = (
            f"👤 *Información de tu Perfil de Telegram*\n\n"
            f"🆔 *ID Numérico:* `{user_id}`\n"
            f"👤 *Usuario:* {username}\n"
            f"🔗 *Enlace Directo:* {enlace_perfil}"
        )
        await update.message.reply_text(
            info_perfil,
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
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
            "✅ *¡Nota guardada con éxito!*",
            parse_mode="Markdown",
            reply_markup=obtener_teclado_principal()
        )
        return

    elif estado == "esperando_tiempo":
        ESTADOS_USUARIO[user_id] = None
        reporte_clima, _, _ = obtener_clima_real(texto)
        await update.message.reply_text(
            reporte_clima, 
            parse_mode="Markdown", 
            reply_markup=obtener_teclado_principal()
        )
        return

    elif estado == "esperando_alerta_lluvia":
        ESTADOS_USUARIO[user_id] = None
        _, _, ubicacion_oficial = obtener_clima_real(texto)
        if ubicacion_oficial:
            SUSCRIPTORES_CLIMA[user_id] = texto
            await update.message.reply_text(
                f"✅ *¡Alerta activada!*\nTe avisaré automáticamente si detecto lluvia o tormenta en *{ubicacion_oficial}*.",
                parse_mode="Markdown",
                reply_markup=obtener_teclado_principal()
            )
        else:
            await update.message.reply_text(
                "❌ No pude verificar esa ciudad. Inténtalo de nuevo con `/alerta_lluvia`.",
                reply_markup=obtener_teclado_principal()
            )
        return

    elif estado == "esperando_wa":
        ESTADOS_USUARIO[user_id] = None
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

# Función ejecutada en segundo plano por el planificador para revisar la lluvia
def verificar_lluvia_background(application):
    if not SUSCRIPTORES_CLIMA:
        return
        
    print("🔍 Ejecutando verificación automática de lluvia para los usuarios suscritos...")
    loop = application.bot_data.get("loop")
    
    for user_id, ciudad in list(SUSCRIPTORES_CLIMA.items()):
        try:
            _, code, ubicacion_oficial = obtener_clima_real(ciudad)
            if code in CODIGOS_LLUVIA:
                mensaje_alerta = f"🌧 *¡Alerta de Lluvia!* 🌧\n\nSe detectaron precipitaciones actuales en *{ubicacion_oficial}* ({WEATHER_CODES.get(code)}). ¡No olvides tu paraguas!"
                # Enviar mensaje asíncrono desde el hilo del planificador
                if loop and loop.is_running():
                    application.bot.send_message(chat_id=user_id, text=mensaje_alerta, parse_mode="Markdown")
        except Exception as e:
            print(f"❌ Error al verificar alerta automática para usuario {user_id}: {e}")

def main():
    # Hilo para Flask
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Comandos y eventos
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reglas", reglas_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bienvenida_nuevo_usuario))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))

    # Configurar el planificador en segundo plano (revisa el clima cada 1 hora automáticamente)
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    app.bot_data["loop"] = loop

    scheduler = BackgroundScheduler()
    # Intervalo de revisión: puedes cambiar 'hours=1' por 'minutes=30' si deseas que revise más seguido
    scheduler.add_job(lambda: verificar_lluvia_background(app), 'interval', hours=1)
    scheduler.start()

    print("🤖 Bot y sistemas de tareas en segundo plano iniciados correctamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
