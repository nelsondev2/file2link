import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

# Configuración - ¡ACTUALIZA ESTA URL!
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = "https://nelson-file2link.onrender.com"  # Tu URL de Render
SERVER_DIR = "./server"

class FileManager:
    def __init__(self, user_id):
        self.user_id = str(user_id)
        self.base_dir = f"{SERVER_DIR}/{self.user_id}"
        self.downloads_dir = f"{self.base_dir}/Descargas"
        self._create_directories()
    
    def _create_directories(self):
        """Crear directorios del usuario si no existen"""
        for directory in [self.base_dir, self.downloads_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def sanitize_filename(self, filename):
        """Sanitizar nombre de archivo"""
        import re
        if not filename:
            return "archivo_sin_nombre"
        
        # Mantener solo caracteres seguros
        name = re.sub(r'[^\w\-_.]', '_', filename)
        name = name.strip('_.-')
        
        return name or "archivo"
    
    def save_uploaded_file(self, file_content, filename):
        """Guardar archivo subido por el usuario"""
        sanitized_name = self.sanitize_filename(filename)
        file_path = f"{self.downloads_dir}/{sanitized_name}"
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return file_path, sanitized_name
    
    def generate_download_link(self, file_path):
        """Generar enlace de descarga directa"""
        # Convertir ruta local a ruta web
        # Ejemplo: ./server/123456/Descargas/archivo.pdf → 123456/Descargas/archivo.pdf
        web_path = file_path.replace("./server/", "").lstrip('/')
        return f"{BASE_URL}/{web_path}"
    
    def get_file_info(self, file_path):
        """Obtener información del archivo"""
        import datetime
        import os
        
        if not os.path.exists(file_path):
            return None
        
        size = os.path.getsize(file_path)
        
        # Convertir tamaño a unidades legibles
        units = ['B', 'KB', 'MB', 'GB']
        human_size = size
        for unit in units:
            if human_size < 1024:
                break
            human_size /= 1024
        
        return {
            'name': os.path.basename(file_path),
            'size_bytes': size,
            'size_human': f"{human_size:.2f} {unit}",
            'created': datetime.datetime.now(),
            'download_link': self.generate_download_link(file_path)
        }

async def start_command(update, context):
    """Manejador del comando /start"""
    user = update.effective_user
    welcome_text = f"""
👋 ¡Hola {user.first_name}!

🤖 **Bot File2Link** - Sube archivos y obtén enlaces de descarga directa

⚡ **Características:**
• Sube archivos hasta 2GB
• Enlaces de descarga directa
• Rápido y sencillo

📁 **Cómo usar:**
1. Envíame cualquier archivo
2. Yo lo guardaré en la nube
3. Recibirás un enlace de descarga directa

¡Envía un archivo para comenzar!
    """
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update, context):
    """Manejador del comando /help"""
    help_text = f"""
📖 **Guía de Comandos - File2Link Bot**

**Subida de Archivos:**
• Simplemente envía cualquier archivo al bot

**Enlaces:**
• Cada archivo tendrá su enlace de descarga directa
• Los enlaces estarán disponibles en: {BASE_URL}

📝 **Formatos soportados:**
• Documentos (PDF, DOC, XLS, PPT, etc.)
• Imágenes (JPG, PNG, GIF, BMP, etc.)
• Videos (MP4, AVI, MKV, MOV, etc.)
• Audio (MP3, WAV, OGG, etc.)
• Archivos comprimidos (ZIP, RAR, 7Z, etc.)
• Código (PY, JS, HTML, CSS, etc.)

¡Simplemente envía tu archivo ahora!
    """
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def handle_file_upload(update, context):
    """Manejador para archivos subidos"""
    user_id = update.effective_user.id
    file_manager = FileManager(user_id)
    
    try:
        # Obtener el archivo según el tipo
        if update.message.document:
            file_obj = await update.message.document.get_file()
            filename = update.message.document.file_name or "documento.bin"
            file_type = "📄 Documento"
            
        elif update.message.photo:
            file_obj = await update.message.photo[-1].get_file()
            filename = f"foto_{file_obj.file_id}.jpg"
            file_type = "🖼️ Foto"
            
        elif update.message.video:
            file_obj = await update.message.video.get_file()
            filename = update.message.video.file_name or f"video_{file_obj.file_id}.mp4"
            file_type = "🎥 Video"
            
        elif update.message.audio:
            file_obj = await update.message.audio.get_file()
            filename = update.message.audio.file_name or f"audio_{file_obj.file_id}.mp3"
            file_type = "🎵 Audio"
            
        else:
            await update.message.reply_text("❌ Tipo de archivo no soportado")
            return
        
        # Descargar archivo
        status_msg = await update.message.reply_text("📥 Descargando archivo...")
        
        file_content = await file_obj.download_as_bytearray()
        
        await status_msg.edit_text("💾 Guardando en la nube...")
        
        file_path, sanitized_name = file_manager.save_uploaded_file(file_content, filename)
        
        # Obtener información del archivo
        file_info = file_manager.get_file_info(file_path)
        
        if not file_info:
            await status_msg.edit_text("❌ Error al procesar el archivo")
            return
        
        # Crear mensaje con información
        message_text = f"""
✅ **{file_type} subido exitosamente**

📁 **Nombre:** `{file_info['name']}`
📦 **Tamaño:** {file_info['size_human']}
📅 **Subido:** {file_info['created'].strftime('%Y-%m-%d %H:%M:%S')}

🔗 **Enlace de descarga:**
{file_info['download_link']}

💡 *Puedes compartir este enlace con anyone*
        """
        
        # Crear botones
        keyboard = [
            [InlineKeyboardButton("🔗 Abrir enlace", url=file_info['download_link'])]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await status_msg.edit_text(
            message_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=False
        )
        
        print(f"✅ Archivo guardado: {file_path}")
        print(f"🔗 Enlace generado: {file_info['download_link']}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        await update.message.reply_text(f"❌ Error al subir el archivo: {str(e)}")

async def main():
    """Función principal del bot"""
    # Crear directorio server si no existe
    os.makedirs(SERVER_DIR, exist_ok=True)
    print("=" * 50)
    print("🚀 Iniciando File2Link Bot")
    print("=" * 50)
    print(f"📁 Directorio servidor: {SERVER_DIR}")
    print(f"🌐 URL base: {BASE_URL}")
    
    # Verificar token
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN no configurado")
        print("💡 Configura la variable de entorno BOT_TOKEN en Render.com")
        print("💡 Ve a: Settings → Environment Variables")
        return
    
    # Crear aplicación del bot
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers de comandos
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("upload", help_command))
    
    # Handler de archivos
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
        handle_file_upload
    ))
    
    # Iniciar bot
    print("🤖 Iniciando Bot de Telegram...")
    print("✅ Bot funcionando correctamente!")
    print("💡 Envía /start al bot para comenzar")
    print("=" * 50)
    
    try:
        await application.run_polling()
    except Exception as e:
        print(f"❌ Error del bot: {e}")
    finally:
        print("🛑 Bot detenido")

if __name__ == "__main__":
    # Ejecutar el bot
    asyncio.run(main())
