import os
import re
import random
import string
import urllib.parse
import urllib.request
import json
import asyncio
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# --- CONFIGURACIÓN DE TOKEN ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or "8805767451:AAEqvJW_hBBtiJROciMD7-R4zPykRaraLWE"
TU_ID_DE_ADMINISTRADOR = 7694542888

ESTADOS_USUARIO = {}
ULTIMO_CLIMA_USUARIO = {}

# --- CONFIGURACIÓN DE LA BASE DE DATOS SQLITE ---
def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS notas (user_id INTEGER PRIMARY KEY, nota TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS clima (user_id INTEGER PRIMARY KEY, ciudad TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS sismos (user_id INTEGER PRIMARY KEY, lat REAL, lon REAL, nombre TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS usuarios_totales (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

init_db()

def registrar_usuario_db(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO usuarios_totales (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def contar_usuarios_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios_totales")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def guardar_nota_db(user_id, texto):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO notas (user_id, nota) VALUES (?, ?)", (user_id, texto))
    conn.commit()
    conn.close()

def obtener_nota_db(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nota FROM notas WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "No tienes notas guardadas aún."

def guardar_clima_db(user_id, ciudad):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO clima (user_id, ciudad) VALUES (?, ?)", (user_id, ciudad))
    conn.commit()
    conn.close()

def obtener_clima_db(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT ciudad FROM clima WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def obtener_todos_clima_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, ciudad FROM clima")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def guardar_sismo_db(user_id, lat, lon, nombre):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO sismos (user_id, lat, lon, nombre) VALUES (?, ?, ?, ?)", (user_id, lat, lon, nombre))
    conn.commit()
    conn.close()

def obtener_sismo_db(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT lat, lon, nombre FROM sismos WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return {"lat": row[0], "lon": row[1], "nombre": row[2]} if row else None

def obtener_todos_sismos_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, lat, lon, nombre FROM sismos")
    rows = cursor.fetchall()
    conn.close()
    return {r[0]: {"lat": r[1], "lon": r[2], "nombre": r[3]} for r in rows}

MENSAJE_REGLAS = (
    "📜 *Reglas del Grupo*:\n\n"
    "1️⃣ Mantén el respeto hacia todos los miembros.\n"
    "2️⃣ No compartas enlaces de spam o contenido no solicitado.\n"
    "3️⃣ Usa los canales o temas adecuados para cada conversación.\n\n"
    "¡Disfruta tu estancia y participa con confianza! 🤖"
)

WEATHER_CODES = {
    0: "☀️ Despejado", 1: "🌤 Principalmente despejado", 2: "⛅ Parcialmente nublado",
    3: "☁️ Nublado", 45: "🌫 Niebla", 48: "🌫 Niebla con escarcha",
    51: "🌦 Llovizna ligera", 53: "🌦 Llovizna moderada", 55: "🌦 Llovizna densa",
    61: "🌧 Lluvia ligera", 63: "🌧 Lluvia moderada", 65: "🌧 Lluvia fuerte",
    71: "❄️ Nieve ligera", 73: "❄ Nieve moderada", 75: "❄ Nieve fuerte",
    80: "🌧 Chubascos ligeros", 81: "🌧 Chubascos moderados", 82: "🌧 Chubascos violentos",
    95: "🌩 Tormenta eléctrica"
}
CODIGOS_LLUVIA = [51, 53, 55, 61, 63, 65, 80, 81, 82, 95]

def obtener_teclado_principal():
    teclado = [
        [KeyboardButton("🔢 /calc"), KeyboardButton("🔑 /pass")],
        [KeyboardButton("📝 /nota"), KeyboardButton("🌤 /tiempo")],
        [KeyboardButton("📅 /manana"), KeyboardButton("📲 /wa")],
        [KeyboardButton("🆔 /id"), KeyboardButton("🔔 /alerta_lluvia")],
        [KeyboardButton("🚨 /alerta_sismo"), KeyboardButton("📊 /estado")],
        [KeyboardButton("⚡ /probar_alerta"), KeyboardButton("📋 /ayuda")]
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
    try:
        lat, lon, nombre_lugar = obtener_coordenadas(ciudad)
        if not lat:
            return f"❌ No se encontró la ciudad: *{ciudad}*", None, None
        url_weather = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req = urllib.request.Request(url_weather, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        current = data.get("current_weather", {})
        reporte = f"🌤 *Clima en {nombre_lugar}:* {WEATHER_CODES.get(current.get('weathercode', 0))} | Temp: `{current.get('temperature')}°C`"
        return reporte, current.get("weathercode", 0), nombre_lugar
    except Exception:
        return "❌ Error al consultar el clima.", None, None

def obtener_pronostico_manana(ciudad):
    try:
        lat, lon, nombre_lugar = obtener_coordenadas(ciudad)
        if not lat:
            return f"❌ No se encontró la ciudad: *{ciudad}*"
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weathercode,precipitation_probability_max&timezone=auto"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        daily = data.get("daily", {})
        if len(daily.get("time", [])) > 1:
            return f"📅 *Mañana en {nombre_lugar}*: {WEATHER_CODES.get(daily['weathercode'][1], 'Variable')} | Lluvia: `{daily['precipitation_probability_max'][1]}%`"
        return "❌ Sin pronóstico."
    except Exception:
        return "❌ Error de conexión."

# --- TRADUCTOR UNIVERSAL AUTOMÁTICO (Estilo Translator) ---
def traducir_texto(texto, idioma_destino="es"):
    try:
        texto_encoded = urllib.parse.quote(texto)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={idioma_destino}&dt=t&q={texto_encoded}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data and data[0]:
            traduccion = "".join([sentence[0] for sentence in data[0] if sentence[0]])
            return traduccion
    except Exception:
        pass
    return texto

# --- COMANDOS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    registrar_usuario_db(update.effective_user.id)
    await update.message.reply_text("🤖 *Bot Activo*\nUsa el menú inferior o `/ayuda`.", parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def usuarios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TU_ID_DE_ADMINISTRADOR:
        return
    await update.message.reply_text(f"📊 Total usuarios: `{contar_usuarios_db()}`", parse_mode="Markdown")

async def ayuda_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛠 *Comandos:* `/calc`, `/pass`, `/nota`, `/tiempo`, `/manana`, `/wa`, `/id`, `/estado`, `/reglas`", parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def estado_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = obtener_clima_db(update.effective_user.id)
    rep = obtener_clima_real(c)[0] if c else "No configurado"
    await update.message.reply_text(f"📊 *Estado Clima:*\n{rep}", parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def probar_alerta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡ *¡Prueba OK!*", parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_calc"
    await update.message.reply_text("🔢 Escribe la operación (Ej: `50+20`):", parse_mode="Markdown")

async def pass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pwd = ''.join(random.choice(string.ascii_letters + string.digits + "!@#$%&*") for _ in range(12))
    await update.message.reply_text(f"🔑 `{pwd}`", parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def nota_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_nota"
    await update.message.reply_text(f"📝 Nota actual:\n{obtener_nota_db(update.effective_user.id)}\n\nEnvía la nueva nota:", parse_mode="Markdown")

async def tiempo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_tiempo"
    await update.message.reply_text("🌤 Escribe tu ciudad:", parse_mode="Markdown")

async def manana_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_manana"
    await update.message.reply_text("📅 Escribe tu ciudad para mañana:", parse_mode="Markdown")

async def wa_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_wa"
    await update.message.reply_text("📲 Escribe el número con código de país:", parse_mode="Markdown")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await update.message.reply_text(f"🆔 ID: `{u.id}`\n👤 @{u.username or 'N/A'}", parse_mode="Markdown", reply_markup=obtener_teclado_principal())

async def alerta_lluvia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_alerta_lluvia"
    await update.message.reply_text("🔔 Escribe tu ciudad para alertas de clima:", parse_mode="Markdown")

async def alerta_sismo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ESTADOS_USUARIO[update.effective_user.id] = "esperando_alerta_sismo"
    await update.message.reply_text("🚨 Escribe tu ciudad para alertas de sismos:", parse_mode="Markdown")

async def reglas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(MENSAJE_REGLAS, parse_mode="Markdown")

async def bienvenida_nuevo_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.new_chat_members:
        for m in update.message.new_chat_members:
            if m.id != context.bot.id:
                await update.message.reply_text(f"👋 ¡Bienvenido/a {m.first_name}!\n\n{MENSAJE_REGLAS}", parse_mode="Markdown")

# --- MANEJADOR DE MENSAJES Y TRADUCCIÓN AUTOMÁTICA COMPACTA ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_type = update.effective_chat.type
    user_id = update.effective_user.id
    texto = update.message.text.strip()

    # GRUPOS: Traducción automática directa, universal y compacta (en una sola línea)
    if chat_type != "private":
        if texto.startswith("/"):
            return
        
        traduccion = traducir_texto(texto, "es")
        # Si la traducción es distinta al original (significa que estaba en otro idioma), se responde en formato alargado y compacto
        if traduccion and traduccion.strip().lower() != texto.strip().lower():
            await update.message.reply_text(f"🌐 *Traducción:* {traduccion}", parse_mode="Markdown")
        return

    # PRIVADOS: Menús y estados
    estado = ESTADOS_USUARIO.get(user_id)
    if estado == "esperando_calc":
        ESTADOS_USUARIO[user_id] = None
        try:
            res = eval(re.sub(r"[^0-9+\-*/(). ]", "", texto))
            await update.message.reply_text(f"🔢 Resultado: `{res}`", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        except:
            await update.message.reply_text("❌ Operación inválida.", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_nota":
        ESTADOS_USUARIO[user_id] = None
        guardar_nota_db(user_id, texto)
        await update.message.reply_text("✅ ¡Nota guardada!", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_tiempo":
        ESTADOS_USUARIO[user_id] = None
        await update.message.reply_text(obtener_clima_real(texto)[0], parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_manana":
        ESTADOS_USUARIO[user_id] = None
        await update.message.reply_text(obtener_pronostico_manana(texto), parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_alerta_lluvia":
        ESTADOS_USUARIO[user_id] = None
        lat, _, nom = obtener_coordenadas(texto)
        if lat:
            guardar_clima_db(user_id, nom)
            await update.message.reply_text(f"✅ Alerta de clima activada para *{nom}*.", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        else:
            await update.message.reply_text("❌ Ciudad no encontrada.", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_alerta_sismo":
        ESTADOS_USUARIO[user_id] = None
        lat, lon, nom = obtener_coordenadas(texto)
        if lat:
            guardar_sismo_db(user_id, lat, lon, nom)
            await update.message.reply_text(f"✅ Alerta de sismos activada para *{nom}*.", parse_mode="Markdown", reply_markup=obtener_teclado_principal())
        else:
            await update.message.reply_text("❌ Zona no encontrada.", reply_markup=obtener_teclado_principal())
        return

    elif estado == "esperando_wa":
        ESTADOS_USUARIO[user_id] = None
        nums = re.sub(r"\D", "", texto)
        if len(nums) >= 7:
            await update.message.reply_text(f"📲 Enlace: https://wa.me/{nums}", reply_markup=obtener_teclado_principal())
        else:
            await update.message.reply_text("❌ Número muy corto.", reply_markup=obtener_teclado_principal())
        return

    # Comandos por texto de botones
    comandos_map = {
        "🔢 /calc": calc_command, "/calc": calc_command,
        "🔑 /pass": pass_command, "/pass": pass_command,
        "📝 /nota": nota_command, "/nota": nota_command,
        "🌤 /tiempo": tiempo_command, "/tiempo": tiempo_command,
        "📅 /manana": manana_command, "/manana": manana_command,
        "📲 /wa": wa_command, "/wa": wa_command,
        "🆔 /id": id_command, "/id": id_command,
        "🔔 /alerta_lluvia": alerta_lluvia_command, "/alerta_lluvia": alerta_lluvia_command,
        "🚨 /alerta_sismo": alerta_sismo_command, "/alerta_sismo": alerta_sismo_command,
        "📊 /estado": estado_command, "/estado": estado_command,
        "⚡ /probar_alerta": probar_alerta_command, "/probar_alerta": probar_alerta_command,
        "📋 /ayuda": ayuda_command, "/ayuda": ayuda_command
    }

    if texto in comandos_map:
        await comandos_map[texto](update, context)
        return

    await update.message.reply_text("Selecciona una opción del menú:", reply_markup=obtener_teclado_principal())

# --- TAREAS EN SEGUNDO PLANO ---
def verificar_lluvia_background(app):
    suscriptores = obtener_todos_clima_db()
    if not suscriptores: return
    async def run():
        for uid, ciu in suscriptores.items():
            try:
                _, code, nom = obtener_clima_real(ciu)
                if code is not None:
                    last = ULTIMO_CLIMA_USUARIO.get(uid)
                    if last is None:
                        ULTIMO_CLIMA_USUARIO[uid] = code
                        continue
                    if code != last:
                        ULTIMO_CLIMA_USUARIO[uid] = code
                        if code in [0, 1]:
                            await app.bot.send_message(uid, f"☀️ El clima en *{nom}* ahora está despejado.", parse_mode="Markdown")
                        elif code in CODIGOS_LLUVIA:
                            await app.bot.send_message(uid, f"🌧 ¡Alerta de lluvia en *{nom}*!", parse_mode="Markdown")
            except: pass
    loop = app.bot_data.get("loop")
    if loop and loop.is_running(): asyncio.run_coroutine_threadsafe(run(), loop)

def verificar_sismos_background(app):
    suscriptores = obtener_todos_sismos_db()
    if not suscriptores: return
    async def run():
        try:
            url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.0_hour.geojson"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            sismos = data.get("features", [])
            if not sismos: return
            import math
            for uid, dat in suscriptores.items():
                for s in sismos:
                    props = s.get("properties", {})
                    coords = s.get("geometry", {}).get("coordinates", [0, 0])
                    dist = 6371 * math.acos(min(1.0, max(-1.0, math.sin(math.radians(dat["lat"])) * math.sin(math.radians(coords[1])) + math.cos(math.radians(dat["lat"])) * math.cos(math.radians(coords[1])) * math.cos(math.radians(coords[0]) - math.radians(dat["lon"])))))
                    if dist <= 500:
                        await app.bot.send_message(uid, f"🚨 *Sismo M{props.get('mag')}* cerca de *{dat['nombre']}* (~{int(dist)} km).", parse_mode="Markdown")
        except: pass
    loop = app.bot_data.get("loop")
    if loop and loop.is_running(): asyncio.run_coroutine_threadsafe(run(), loop)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    for cmd in ["start", "usuarios", "ayuda", "calc", "pass", "nota", "tiempo", "manana", "wa", "id", "alerta_lluvia", "alerta_sismo", "estado", "probar_alerta", "reglas"]:
        app.add_handler(CommandHandler(cmd, globals()[f"{cmd}_command"]))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bienvenida_nuevo_usuario))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def post_init(application):
        application.bot_data["loop"] = asyncio.get_running_loop()
    app.post_init = post_init

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: verificar_lluvia_background(app), 'interval', minutes=5)
    scheduler.add_job(lambda: verificar_sismos_background(app), 'interval', minutes=5)
    scheduler.start()

    print("🤖 Bot iniciado correctamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
