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
SUSCRIPTORES_CLIMA = {}
SUSCRIPTORES_SISMO = {}

MENSAJE_REGLAS = (
    "📜 *Reglas del Grupo*:\n\n"
    "1️⃣ Mantén el respeto hacia todos los miembros.\n"
    "2️⃣ No compartas enlaces de spam o contenido no solicitado.\n"
    "3️⃣ Usa los canales o temas adecuados para cada conversación.\n\n"
    "¡Disfruta tu estancia y participa con confianza! 🤖"
)

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

CODIGOS_LLUVIA = [51, 53, 55, 61, 63, 65, 80, 81, 82, 95]

def obtener_teclado_principal():
    teclado = [
        [KeyboardButton("🔢 /calc"), KeyboardButton("🔑 /pass")],
        [KeyboardButton("📝 /nota"), KeyboardButton("🌤 /tiempo")],
        [KeyboardButton("📲 /wa"), KeyboardButton("🆔 /id")],
        [KeyboardButton("🔔 /alerta_lluvia"), KeyboardButton("🚨 /alerta_sismo")],
        [KeyboardButton("📊 /estado"), KeyboardButton("⚡ /probar_alerta")],
        [KeyboardButton("📋 /ayuda")]
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

def obtener_coordenadas(ciudad):
    try:
        ciudad_encoded = urllib.parse.quote(ciudad)
        url_geo = f"https://geocoding-api.open-meteo.com/v1/search?name={ciudad_encoded}&count=1&language=es&format=json"
        req_geo = urllib.request.Request(url_geo, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_geo, timeout=10) as resp:
            data_geo = json.loads(resp.read().decode())
        
        if not data_geo.get("results"):
            return None, None, None
            
        lugar = data_geo["results"][0]
        return lugar["latitude"], lugar["longitude"], lugar.get("name", ciudad)
    except Exception:
        return None, None, None

def obtener_clima_real(ciudad):
    for intento in range(2):
        try:
            lat, lon, nombre_lugar = obtener_coordenadas(ciudad)
            if not lat:
                return f"❌ No se encontró la ciudad/país: *{ciudad}*", None, None
                
            url_weather = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            req_weather = urllib.request.Request(url_weather, headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(req_weather, timeout=15) as resp:
                data_weather = json.loads(resp.read().decode())
                
            current = data_weather.get("current_weather", {})
            temp = current.get("temperature", "N/A")
            wind = current.get("windspeed", "N/A")
            code = current.get("weathercode", 0)
            
            condicion = WEATHER_CODES.get(code, "🌡 Clima variable")
            reporte = f"🌤 *Clima actual en {nombre_lugar}:*\n\n• Estado: {condicion}\n• Temperatura: `{temp}°C`\n• Viento: `{wind} km/h`"
            return reporte, code, nombre_lugar
        except Exception:
            if intento == 1:
                return f"❌ Error de conexión al consultar el clima.", None, None
    return f"❌ Error de conexión al consultar el clima.", None, None

# --- FUNCIONES DE COMANDOS INDIVIDUALES ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "🤖 *Bienvenido al Menú Principal*\n\n"
        "Toca cualquiera de los botones de abajo o usa `/ayuda` para ver la lista de comandos disponibles."
    )
    await update.message.reply_text(
        mensaje,
        parse_mode="Markdown",
        reply_markup=obtener_teclado_principal()
    )

async def ayuda_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_ayuda = (
        "🛠 *Lista de Comandos Disponibles:*\n\n"
        "🔢 `/calc` - Calculadora rápida\n"
        "🔑 `/pass` - Generar contraseña segura\n"
        "📝 `/nota` - Guardar y consultar notas\n"
        "🌤 `/tiempo` - Consultar pronóstico del tiempo\n"
        "📲 `/wa` - Generar enlace de WhatsApp\n"
        "🆔 `/id` - Ver ID y perfil de Telegram\n"
        "🔔 `/alerta_lluvia` - Activar avisos automáticos de lluvia\n"
        "🚨 `/alerta_sismo` - Activar avisos automáticos de sismos\n"
        "📊 `/estado` - Ver tus alertas configuradas\n"
        "⚡ `/probar_alerta` - Enviar una alerta de prueba\n"
        "📜 `/reglas` - Ver las reglas del grupo"
    )
    await update.message.reply_text(texto_ayuda, parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def estado_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clima_activo = SUSCRIPTORES_CLIMA.get(user_id, "❌ No configurada")
    sismo_activo = SUSCRIPTORES_SISMO.get(user_id, {}).get("nombre", "❌ No configurada")

    mensaje = (
        "📊 *Estado de tus Alertas Automáticas*\n\n"
        f"🌧 *Alerta de Lluvia:* `{clima_activo}`\n"
        f"🚨 *Alerta de Sismos:* `{sismo_activo}`\n\n"
        "Si deseas cambiarlas, vuelve a usar `/alerta_lluvia` o `/alerta_sismo`."
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def probar_alerta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ *¡Prueba de alerta exitosa!*\nSi puedes ver este mensaje, las notificaciones automáticas y el canal de comunicación con tu bot funcionan perfectamente.",
        parse_mode="Markdown",
        reply_markup=obtener_teclado_principal()
    )

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ESTADOS_USUARIO[user_id] = "esperando_calc"
    await update.message.reply_text("🔢 *Calculadora Rápida*\nEscribe la operación matemática (Ejemplo: `50+20*2`):", parse_mode="Markdown")

async def pass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ESTADOS_USUARIO[user_id] = None
    caracteres = string.ascii_letters + string.digits + "!@#$%&*"
    password = ''.join(random.choice(caracteres) for _ in range(12))
    await update.message.reply_text(
        f"🔑 *Contraseña Segura Generada:*\n`{password}`",
        parse_mode="Markdown",
        reply_markup=obtener_teclado_principal()
    )

async def nota_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nota_actual = NOTAS_USUARIOS.get(user_id, "No tienes notas guardadas aún.")
    ESTADOS_USUARIO[user_id] = "esperando_nota"
    await update.message.reply_text(
        f"📝 *Tu nota actual:*\n{nota_actual}\n\nEscribe el nuevo texto que deseas guardar:",
        parse_mode="Markdown",
        reply_markup=obtener_teclado_principal()
    )

async def tiempo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ESTADOS_USUARIO[user_id] = "esperando_tiempo"
    await update.message.reply_text("🌤 *Pronóstico del tiempo*\nEscribe el nombre de la ciudad o país para consultar el clima real:", parse_mode="Markdown")

async def wa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ESTADOS_USUARIO[user_id] = "esperando_wa"
    await update.message.reply_text(
        "📲 *Generador de Enlace WhatsApp*\n\n"
        "Escribe el número de teléfono con el código de país (Ejemplo: `+5215512345678`):",
        parse_mode="Markdown"
    )

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
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

async def alerta_lluvia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ESTADOS_USUARIO[user_id] = "esperando_alerta_lluvia"
    await update.message.reply_text(
        "🔔 *Configurar Alerta Automática de Lluvia*\n\n"
        "Escribe el nombre de tu ciudad para avisarte automáticamente si comienza a llover:",
        parse_mode="Markdown"
    )

async def alerta_sismo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ESTADOS_USUARIO[user_id] = "esperando_alerta_sismo"
    await update.message.reply_text(
        "🚨 *Configurar Alerta Automática de Sismos*\n\n"
        "Escribe el nombre de tu ciudad o país para avisarte si ocurre un sismo relevante cerca:",
        parse_mode="Markdown"
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

# --- MANEJADOR DE TEXTOS Y ESTADOS PENDIENTES ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    texto = update.message.text.strip()
    estado = ESTADOS_USUARIO.get(user_id)

    # Capturar clics de botones del teclado táctil
    if texto in ["🔢 /calc", "/calc"]:
        await calc_command(update, context)
        return
    elif texto in ["🔑 /pass", "/pass"]:
        await pass_command(update, context)
        return
    elif texto in ["📝 /nota", "/nota"]:
        await nota_command(update, context)
        return
    elif texto in ["🌤 /tiempo", "/tiempo"]:
        await tiempo_command(update, context)
        return
    elif texto in ["📲 /wa", "/wa"]:
        await wa_command(update, context)
        return
    elif texto in ["🆔 /id", "/id"]:
        await id_command(update, context)
        return
    elif texto in ["🔔 /alerta_lluvia", "/alerta_lluvia"]:
        await alerta_lluvia_command(update, context)
        return
    elif texto in ["🚨 /alerta_sismo", "/alerta_sismo"]:
        await alerta_sismo_command(update, context)
        return
    elif texto in ["📊 /estado", "/estado"]:
        await estado_command(update, context)
        return
    elif texto in ["⚡ /probar_alerta", "/probar_alerta"]:
        await probar_alerta_command(update, context)
        return
    elif texto in ["📋 /ayuda", "/ayuda"]:
        await ayuda_command(update, context)
        return

    # Procesamiento de estados pendientes
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
        lat, lon, ubicacion_oficial = obtener_coordenadas(texto)
        if lat:
            SUSCRIPTORES_CLIMA[user_id] = ubicacion_oficial
            await update.message.reply_text(
                f"✅ *¡Alerta de lluvia activada!*\nTe avisaré si detecto precipitaciones en *{ubicacion_oficial}*.",
                parse_mode="Markdown",
                reply_markup=obtener_teclado_principal()
            )
        else:
            await update.message.reply_text(
                "❌ No pude verificar esa ciudad. Inténtalo de nuevo con `/alerta_lluvia`.",
                reply_markup=obtener_teclado_principal()
            )
        return

    elif estado == "esperando_alerta_sismo":
        ESTADOS_USUARIO[user_id] = None
        lat, lon, ubicacion_oficial = obtener_coordenadas(texto)
        if lat:
            SUSCRIPTORES_SISMO[user_id] = {"lat": lat, "lon": lon, "nombre": ubicacion_oficial}
            await update.message.reply_text(
                f"✅ *¡Alerta de sismos activada!*\nTe avisaré si ocurre un sismo relevante cerca de *{ubicacion_oficial}*.",
                parse_mode="Markdown",
                reply_markup=obtener_teclado_principal()
            )
        else:
            await update.message.reply_text(
                "❌ No pude ubicar esa zona. Inténtalo de nuevo con `/alerta_sismo`.",
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

    await update.message.reply_text(
        "Selecciona una opción del menú táctil o escribe `/ayuda` para ver las opciones disponibles:",
        reply_markup=obtener_teclado_principal()
    )

# --- TAREAS AUTOMÁTICAS EN SEGUNDO PLANO ---

def verificar_lluvia_background(application):
    if not SUSCRIPTORES_CLIMA:
        return
    loop = application.bot_data.get("loop")
    for user_id, ciudad in list(SUSCRIPTORES_CLIMA.items()):
        try:
            _, code, ubicacion_oficial = obtener_clima_real(ciudad)
            if code in CODIGOS_LLUVIA:
                mensaje_alerta = f"🌧 *¡Alerta de Lluvia!* 🌧\n\nSe detectaron precipitaciones actuales en *{ubicacion_oficial}* ({WEATHER_CODES.get(code)}). ¡Toma precauciones!"
                if loop and loop.is_running():
                    application.bot.send_message(chat_id=user_id, text=mensaje_alerta, parse_mode="Markdown")
        except Exception as e:
            print(f"❌ Error en alerta de lluvia: {e}")

def verificar_sismos_background(application):
    if not SUSCRIPTORES_SISMO:
        return
    loop = application.bot_data.get("loop")
    try:
        url_sismos = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.0_hour.geojson"
        req = urllib.request.Request(url_sismos, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            
        sismos = data.get("features", [])
        if not sismos:
            return

        import math
        def calcular_distancia(lat1, lon1, lat2, lon2):
            R = 6371
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            return R * c

        for user_id, datos in list(SUSCRIPTORES_SISMO.items()):
            u_lat = datos["lat"]
            u_lon = datos["lon"]
            u_nombre = datos["nombre"]

            for sismo in sismos:
                props = sismo.get("properties", {})
                coords = sismo.get("geometry", {}).get("coordinates", [0, 0, 0])
                s_lon, s_lat = coords[0], coords[1]
                mag = props.get("mag", 0)
                lugar_sismo = props.get("place", "Zona desconocida")
                
                distancia = calcular_distancia(u_lat, u_lon, s_lat, s_lon)
                if distancia <= 500:
                    mensaje_alerta = (
                        f"🚨 *¡ALERTA DE SISMO DETECTADO!* 🚨\n\n"
                        f"• *Magnitud:* `{mag}`\n"
                        f"• *Ubicación del Epicentro:* {lugar_sismo}\n"
                        f"• *Distancia aproximada a tu zona ({u_nombre}):* ~`{int(distancia)} km`\n\n"
                        f"Mantén la calma y sigue los protocolos de seguridad."
                    )
                    if loop and loop.is_running():
                        application.bot.send_message(chat_id=user_id, text=mensaje_alerta, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Error en alerta de sismos: {e}")

# --- FUNCIÓN PRINCIPAL ---

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Registro de todos los CommandHandlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ayuda", ayuda_command))
    app.add_handler(CommandHandler("calc", calc_command))
    app.add_handler(CommandHandler("pass", pass_command))
    app.add_handler(CommandHandler("nota", nota_command))
    app.add_handler(CommandHandler("tiempo", tiempo_command))
    app.add_handler(CommandHandler("wa", wa_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("alerta_lluvia", alerta_lluvia_command))
    app.add_handler(CommandHandler("alerta_sismo", alerta_sismo_command))
    app.add_handler(CommandHandler("estado", estado_command))
    app.add_handler(CommandHandler("probar_alerta", probar_alerta_command))
    app.add_handler(CommandHandler("reglas", reglas_command))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bienvenida_nuevo_usuario))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))

    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    app.bot_data["loop"] = loop

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: verificar_lluvia_background(app), 'interval', hours=1)
    scheduler.add_job(lambda: verificar_sismos_background(app), 'interval', minutes=10)
    scheduler.start()

    print("🤖 Bot con comandos de estado y prueba configurados...")
    app.run_polling()

if __name__ == "__main__":
    main()
