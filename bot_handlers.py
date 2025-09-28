import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
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
/upload - Subir un archivo
/files - Listar tus archivos
/help - Mostrar ayuda completa

⚡ **Características:**
• Sube archivos hasta 2GB
• Enlaces de descarga directa: {BASE_URL}
• Compresión de carpetas
• Gestión completa de archivos

¡Envía un archivo para comenzar!
    """
    
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador del comando /help"""
    help_text = f"""
📖 **Guía de Comandos - File2Link Bot**

**Subida de Archivos:**
• Envía cualquier archivo directamente al bot
• O usa /upload para instrucciones

**Gestión de Archivos:**
/files - Listar todos tus archivos y carpetas
/files [carpeta] - Navegar subcarpetas

**Compresión:**
/compress [carpeta] - Comprimir carpeta en ZIP

**Enlaces:**
Cada archivo tiene su enlace de descarga directa
Los enlaces están disponibles en: {BASE_URL}

**Eliminación:**
/delete [ruta] - Eliminar archivo o carpeta
/clear [carpeta] - Vaciar carpeta

📝 **Ejemplos:**
/files Descargas
/compress MiCarpeta
/delete archivo.pdf
    """
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para archivos subidos"""
    user_id = update.effective_user.id
    file_manager = FileManager(user_id)
    
    try:
        # Obtener el archivo según el tipo
        if update.message.document:
            file_obj = await update.message.document.get_file()
            filename = update.message.document.file_name or "documento.bin"
            file_type = "documento"
            
        elif update.message.photo:
            # Usar la foto de mayor calidad
            file_obj = await update.message.photo[-1].get_file()
            filename = f"foto_{file_obj.file_id}.jpg"
            file_type = "foto"
            
        elif update.message.video:
            file_obj = await update.message.video.get_file()
            filename = update.message.video.file_name or f"video_{file_obj.file_id}.mp4"
            file_type = "video"
            
        elif update.message.audio:
            file_obj = await update.message.audio.get_file()
            filename = update.message.audio.file_name or f"audio_{file_obj.file_id}.mp3"
            file_type = "audio"
            
        else:
            await update.message.reply_text("❌ Tipo de archivo no soportado")
            return
        
        # Descargar archivo
        status_msg = await update.message.reply_text("📥 Descargando archivo...")
        
        file_content = await file_obj.download_as_bytearray()
        
        await status_msg.edit_text("💾 Guardando archivo...")
        
        file_path, sanitized_name = file_manager.save_uploaded_file(file_content, filename)
        
        # Obtener información del archivo
        file_info = file_manager.get_file_info(file_path)
        
        if not file_info:
            await status_msg.edit_text("❌ Error al procesar el archivo")
            return
        
        # Crear mensaje con información
        message_text = f"""
✅ **Archivo subido exitosamente**

📁 **Nombre:** `{file_info['name']}`
📦 **Tamaño:** {file_info['size_human']}
📅 **Subido:** {file_info['created'].strftime('%Y-%m-%d %H:%M:%S')}
🔗 **Enlace de descarga:**
`{file_info['download_link']}`

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
        
        await status_msg.edit_text(
            message_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    except Exception as e:
        error_msg = await update.message.reply_text("❌ Error al procesar el archivo")
        await error_msg.edit_text(f"❌ Error al subir el archivo: {str(e)}")

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
    
    for i, item in enumerate(files[:50], 1):  # Limitar a 50 elementos
        if item['type'] == 'folder':
            message_text += f"{i}. 📁 `{item['name']}`\n"
        else:
            message_text += f"{i}. 📄 `{item['name']}` - {item['size']}\n"
    
    if len(files) > 50:
        message_text += f"\n... y {len(files) - 50} más"
    
    message_text += f"\n📊 Total: {len(files)} elementos"
    
    # Botones de navegación
    keyboard = []
    if subdirectory:
        # Botón para volver atrás
        parent_dir = "/".join(subdirectory.split('/')[:-1])
        keyboard.append([InlineKeyboardButton("🔙 Atrás", callback_data=f"list_{parent_dir}")])
    
    keyboard.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"list_{subdirectory}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message_text, 
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

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
        
        if not files:
            await query.edit_message_text("📂 No hay archivos en esta carpeta")
            return
        
        # Reconstruir mensaje
        if subdirectory:
            message_text = f"📁 **Contenido de: {subdirectory}**\n\n"
        else:
            message_text = "📁 **Tus archivos y carpetas**\n\n"
        
        for i, item in enumerate(files[:50], 1):
            if item['type'] == 'folder':
                message_text += f"{i}. 📁 `{item['name']}`\n"
            else:
                message_text += f"{i}. 📄 `{item['name']}` - {item['size']}\n"
        
        if len(files) > 50:
            message_text += f"\n... y {len(files) - 50} más"
        
        message_text += f"\n📊 Total: {len(files)} elementos"
        
        # Actualizar botones
        keyboard = []
        if subdirectory:
            parent_dir = "/".join(subdirectory.split('/')[:-1])
            keyboard.append([InlineKeyboardButton("🔙 Atrás", callback_data=f"list_{parent_dir}")])
        
        keyboard.append([InlineKeyboardButton("🔄 Actualizar", callback_data=f"list_{subdirectory}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador del comando /upload"""
    help_text = f"""
📤 **Subir archivos**

Puedes subir archivos de dos formas:

1. **Envía el archivo directamente** al chat del bot
   - Documentos, fotos, videos, audio
   - Tamaño máximo: 2GB

2. **Los enlaces de descarga estarán en:**
{BASE_URL}

📝 **Formatos soportados:**
• Documentos (PDF, DOC, XLS, etc.)
• Imágenes (JPG, PNG, GIF, etc.)
• Videos (MP4, AVI, etc.)
• Audio (MP3, WAV, etc.)
• Archivos comprimidos (ZIP, RAR, etc.)

¡Simplemente envía tu archivo ahora!
    """
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def compress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comprimir carpeta"""
    if not context.args:
        await update.message.reply_text("❌ Uso: /compress [nombre_carpeta]")
        return
    
    folder_name = " ".join(context.args)
    user_id = update.effective_user.id
    file_manager = FileManager(user_id)
    
    folder_path = f"{file_manager.base_dir}/{folder_name}"
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        await update.message.reply_text("❌ La carpeta no existe")
        return
    
    try:
        status_msg = await update.message.reply_text("🗜️ Comprimiendo carpeta...")
        
        zip_path, zip_filename = file_manager.compress_folder(folder_path)
        
        if not zip_path:
            await status_msg.edit_text("❌ Error al comprimir la carpeta")
            return
        
        download_link = file_manager.generate_download_link(zip_path)
        
        message_text = f"""
✅ **Carpeta comprimida exitosamente**

📦 **Archivo:** `{zip_filename}`
🔗 **Enlace de descarga:**
`{download_link}`

La carpeta se comprimió en: {file_manager.compressed_dir}
        """
        
        await status_msg.edit_text(message_text, parse_mode=ParseMode.MARKDOWN)
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error al comprimir: {str(e)}")

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eliminar archivo o carpeta"""
    if not context.args:
        await update.message.reply_text("❌ Uso: /delete [nombre_archivo_o_carpeta]")
        return
    
    target_name = " ".join(context.args)
    user_id = update.effective_user.id
    file_manager = FileManager(user_id)
    
    target_path = f"{file_manager.base_dir}/{target_name}"
    
    if file_manager.delete_file(target_path):
        await update.message.reply_text(f"✅ `{target_name}` eliminado correctamente", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ No se pudo eliminar el archivo/carpeta")
