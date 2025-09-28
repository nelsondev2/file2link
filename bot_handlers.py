import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

from config import BOT_TOKEN, BASE_URL
from file_manager import FileManager

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador del comando /start"""
    user = update.effective_user
    welcome_text = f"""
👋 ¡Hola {user.first_name}!

🤖 **Bot File2Link** - Sube archivos y obtén enlaces de descarga directa

📁 **Comandos disponibles:**
/start - Mostrar este mensaje
/upload - Subir un archivo (también puedes enviar el archivo directamente)
/files - Listar tus archivos
/help - Mostrar ayuda completa

⚡ **Características:**
• Sube archivos hasta 2GB
• Enlaces de descarga directa
• Compresión de carpetas
• División de archivos grandes
• Gestión completa de archivos

¡Envía un archivo para comenzar!
    """
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador del comando /help"""
    help_text = """
📖 **Guía de Comandos - File2Link Bot**

**Subida de Archivos:**
• Envía cualquier archivo directamente al bot
• O usa /upload para instrucciones

**Gestión de Archivos:**
/files - Listar todos tus archivos y carpetas
/files [carpeta] - Navegar subcarpetas

**Compresión:**
/compress [carpeta] - Comprimir carpeta en ZIP
/split [archivo] [tamaño] - Dividir archivo (ej: /split video.mp4 100)

**Enlaces:**
Cada archivo tiene su enlace de descarga directa
Los enlaces están disponibles en: {BASE_URL}

**Eliminación:**
/delete [ruta] - Eliminar archivo o carpeta
/clear [carpeta] - Vaciar carpeta

📝 **Ejemplos:**
/files Descargas
/compress MiCarpeta
/split video.mp4 50
/delete archivo.pdf
    """
    
    await update.message.reply_text(help_text.format(BASE_URL=BASE_URL), 
                                  parse_mode=ParseMode.MARKDOWN)

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para archivos subidos"""
    user_id = update.effective_user.id
    file_manager = FileManager(user_id)
    
    # Obtener el archivo
    if update.message.document:
        file = await update.message.document.get_file()
        filename = update.message.document.file_name
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
        filename = f"photo_{file.file_id}.jpg"
    elif update.message.video:
        file = await update.message.video.get_file()
        filename = update.message.video.file_name or f"video_{file.file_id}.mp4"
    elif update.message.audio:
        file = await update.message.audio.get_file()
        filename = update.message.audio.file_name or f"audio_{file.file_id}.mp3"
    else:
        await update.message.reply_text("❌ Tipo de archivo no soportado")
        return
    
    # Descargar archivo
    try:
        await update.message.reply_text("📥 Descargando archivo...")
        
        file_content = await file.download_as_bytearray()
        file_path, sanitized_name = file_manager.save_uploaded_file(file_content, filename)
        
        # Obtener información del archivo
        file_info = file_manager.get_file_info(file_path)
        
        # Crear mensaje con información
        message_text = f"""
✅ **Archivo subido exitosamente**

📁 **Nombre:** `{file_info['name']}`
📦 **Tamaño:** {file_info['size_human']}
📅 **Subido:** {file_info['created'].strftime('%Y-%m-%d %H:%M:%S')}
🔗 **Enlace de descarga:**
{file_info['download_link']}

💡 **Comandos útiles:**
/files - Ver todos tus archivos
/help - Mostrar ayuda completa
        """
        
        # Crear botones
        keyboard = [
            [InlineKeyboardButton("📁 Ver mis archivos", callback_data="list_files")],
            [InlineKeyboardButton("🔗 Abrir enlace", url=file_info['download_link'])]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message_text, 
                                      reply_markup=reply_markup,
                                      parse_mode=ParseMode.MARKDOWN,
                                      disable_web_page_preview=True)
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error al subir el archivo: {str(e)}")

async def list_files_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador del comando /files"""
    user_id = update.effective_user.id
    file_manager = FileManager(user_id)
    
    subdirectory = " ".join(context.args) if context.args else ""
    files = file_manager.list_user_files(subdirectory)
    
    if not files:
        await update.message.reply_text("📂 No hay archivos en esta carpeta")
        return
    
    # Construir mensaje
    if subdirectory:
        message_text = f"📁 **Contenido de: {subdirectory}**\n\n"
    else:
        message_text = "📁 **Tus archivos y carpetas**\n\n"
    
    for i, item in enumerate(files, 1):
        if item['type'] == 'folder':
            message_text += f"{i}. 📁 `{item['name']}`\n"
        else:
            message_text += f"{i}. 📄 `{item['name']}` - {item['size']}\n"
    
    message_text += f"\n📊 Total: {len(files)} elementos"
    
    # Botones de navegación
    keyboard = []
    if subdirectory:
        # Botón para volver atrás
        parent_dir = "/".join(subdirectory.split('/')[:-1])
        keyboard.append([InlineKeyboardButton("🔙 Atrás", callback_data=f"list_{parent_dir}")])
    
    keyboard.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"list_{subdirectory}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message_text, 
                                  reply_markup=reply_markup,
                                  parse_mode=ParseMode.MARKDOWN)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador de botones inline"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data.startswith("list_"):
        subdirectory = data[5:]  # Remover "list_"
        file_manager = FileManager(user_id)
        files = file_manager.list_user_files(subdirectory)
        
        # Reconstruir mensaje similar a list_files_command
        if subdirectory:
            message_text = f"📁 **Contenido de: {subdirectory}**\n\n"
        else:
            message_text = "📁 **Tus archivos y carpetas**\n\n"
        
        for i, item in enumerate(files, 1):
            if item['type'] == 'folder':
                message_text += f"{i}. 📁 `{item['name']}`\n"
            else:
                message_text += f"{i}. 📄 `{item['name']}` - {item['size']}\n"
        
        message_text += f"\n📊 Total: {len(files)} elementos"
        
        # Actualizar mensaje
        keyboard = []
        if subdirectory:
            parent_dir = "/".join(subdirectory.split('/')[:-1])
            keyboard.append([InlineKeyboardButton("🔙 Atrás", callback_data=f"list_{parent_dir}")])
        
        keyboard.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"list_{subdirectory}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message_text, 
                                    reply_markup=reply_markup,
                                    parse_mode=ParseMode.MARKDOWN)

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador del comando /upload"""
    help_text = """
📤 **Subir archivos**

Puedes subir archivos de dos formas:

1. **Envía el archivo directamente** al chat del bot
   - Documentos, fotos, videos, audio
   - Tamaño máximo: 2GB

2. **Usa el comando** /upload y sigue las instrucciones

📝 **Formatos soportados:**
• Documentos (PDF, DOC, XLS, etc.)
• Imágenes (JPG, PNG, GIF, etc.)
• Videos (MP4, AVI, etc.)
• Audio (MP3, WAV, etc.)
• Archivos comprimidos (ZIP, RAR, etc.)

¡Simplemente envía tu archivo ahora!
    """
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
