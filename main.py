import os
import uuid
from dotenv import load_dotenv
from flask import Flask, request, send_from_directory
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters, ContextTypes

# Cargar variables de entorno
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Flask(__name__)
bot = Bot(BOT_TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)

# Diccionario para almacenar temporalmente los archivos y sus IDs únicos
files_cache = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start."""
    await update.message.reply_text("¡Hola! Envíame un archivo para obtener un enlace de descarga temporal.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el reenvío de cualquier archivo multimedia."""
    message = update.message
    file_id = None
    file_name = "file"
    
    if message.photo:
        file_id = message.photo[-1].file_id
        file_name = "photo.jpg"
    elif message.video:
        file_id = message.video.file_id
        if message.video.file_name:
            file_name = message.video.file_name
    elif message.document:
        file_id = message.document.file_id
        if message.document.file_name:
            file_name = message.document.file_name
    else:
        await message.reply_text("Lo siento, solo puedo procesar fotos, videos o documentos.")
        return

    status_message = await message.reply_text("Procesando tu archivo... por favor espera. ⏳")

    try:
        telegram_file = await bot.get_file(file_id)
        # Crear una ruta de archivo única en el directorio temporal
        unique_id = str(uuid.uuid4())
        temp_dir = "/tmp"
        temp_file_path = os.path.join(temp_dir, f"{unique_id}-{file_name}")

        await telegram_file.download_to_drive(temp_file_path)

        # Almacenar la ruta del archivo en el caché
        files_cache[unique_id] = temp_file_path
        
        # Generar el enlace de descarga con el ID único
        # Reemplaza 'YOUR_RENDER_URL' con tu URL de Render
        download_link = f"https://YOUR_RENDER_URL.onrender.com/files/{unique_id}"

        await status_message.edit_text(
            f"✅ ¡Tu enlace de descarga temporal está listo!\n\n🔗 **Enlace:** {download_link}\n\n⚠️ **Nota:** Este enlace solo funcionará hasta que el servicio de Render se reinicie."
        )

    except Exception as e:
        await status_message.edit_text(f"❌ Ocurrió un error inesperado: {e}")

# Manejador para servir los archivos temporales
@app.route("/files/<unique_id>")
def serve_file(unique_id):
    if unique_id in files_cache:
        file_path = files_cache[unique_id]
        if os.path.exists(file_path):
            directory, filename = os.path.split(file_path)
            # send_from_directory gestiona la descarga de forma segura
            return send_from_directory(directory, filename, as_attachment=True)
    return "Archivo no encontrado o el enlace ha expirado.", 404

# Configuración del webhook (idéntica a ejemplos anteriores)
@app.route("/webhook", methods=["POST"])
def webhook_handler():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    return "ok"

@app.route("/")
def set_webhook():
    webhook_url = f"https://YOUR_RENDER_URL.onrender.com/webhook"
    s = bot.set_webhook(url=webhook_url)
    if s:
        return "Webhook configurado correctamente."
    else:
        return "Fallo al configurar el webhook."

if __name__ == "__main__":
    dispatcher.add_handler(CommandHandler("start", start_command))
    dispatcher.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_media))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
