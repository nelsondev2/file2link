import os
from flask import Flask, request, send_from_directory
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Variables de entorno
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")  # Ej: https://File2Link.onrender.com
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
FILES_DIR = "files"

# Crear carpeta de archivos si no existe
os.makedirs(FILES_DIR, exist_ok=True)

# Flask para servir archivos y recibir webhooks
app = Flask(__name__)

# Inicializar bot
application = Application.builder().token(BOT_TOKEN).build()

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Envíame un archivo y te daré un enlace directo desde este servidor.")

# Manejo de archivos
async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_obj = None
    filename = None

    if update.message.document:
        file_obj = update.message.document
        filename = file_obj.file_name
    elif update.message.photo:
        file_obj = update.message.photo[-1]
        filename = f"photo_{file_obj.file_unique_id}.jpg"
    elif update.message.video:
        file_obj = update.message.video
        filename = file_obj.file_name or f"video_{file_obj.file_unique_id}.mp4"
    elif update.message.audio:
        file_obj = update.message.audio
        filename = file_obj.file_name
    else:
        await update.message.reply_text("Formato no soportado.")
        return

    # Descargar archivo a carpeta local
    file = await context.bot.get_file(file_obj.file_id)
    file_path = os.path.join(FILES_DIR, filename)
    await file.download_to_drive(file_path)

    # Generar enlace directo
    direct_link = f"{BASE_URL}/files/{filename}"
    await update.message.reply_text(f"📎 Enlace directo:\n{direct_link}")

# Registrar handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, file_handler))

# Endpoint para recibir actualizaciones de Telegram
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

# Servir archivos desde /files
@app.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):
    return send_from_directory(FILES_DIR, filename)

# Endpoint raíz opcional
@app.route("/", methods=["GET"])
def index():
    return "Bot activo y sirviendo archivos", 200

if __name__ == "__main__":
    # Configurar webhook en arranque
    application.bot.set_webhook(url=f"{BASE_URL}{WEBHOOK_PATH}")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
