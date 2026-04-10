import os
import logging
import sys
import time
import asyncio
import concurrent.futures
from typing import Dict, List, Optional, Any
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import fast_download_service
from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB, VERSION

logger = logging.getLogger(__name__)

# ===== CONSTANTES DE CONFIGURACIÓN =====
ITEMS_PER_PAGE = 10
PROGRESS_UPDATE_INTERVAL = 0.5  # segundos
MAX_PROGRESS_MESSAGE_LENGTH = 4000
QUEUE_CHECK_INTERVAL = 1  # segundos entre archivos en cola

# ===== SISTEMA DE SESIÓN POR USUARIO =====
user_sessions: Dict[int, Dict[str, Any]] = {}
user_queues: Dict[int, List[Message]] = {}
user_progress_msgs: Dict[int, Message] = {}
user_current_processing: Dict[int, int] = {}
user_batch_totals: Dict[int, int] = {}
user_last_activity: Dict[int, float] = {}  # Para limpieza automática


def get_user_session(user_id: int) -> Dict[str, Any]:
    """Obtiene o crea la sesión del usuario con inicialización segura"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'current_folder': 'downloads',
            'last_command': None,
            'preferences': {
                'show_progress': True,
                'compact_mode': False
            }
        }
        user_last_activity[user_id] = time.time()
    return user_sessions[user_id]


def update_user_activity(user_id: int):
    """Actualiza el timestamp de última actividad del usuario"""
    user_last_activity[user_id] = time.time()


def create_navigation_keyboard(page: int, total_pages: int, user_id: int) -> InlineKeyboardMarkup:
    """Crea un teclado inline para navegación de páginas"""
    keyboard = []
    row = []
    
    if total_pages > 1:
        if page > 1:
            row.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"nav_prev_{user_id}_{page-1}"))
        
        row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="nav_info"))
        
        if page < total_pages:
            row.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"nav_next_{user_id}_{page+1}"))
        
        keyboard.append(row)
    
    # Botones de acción rápida
    keyboard.append([
        InlineKeyboardButton("🗑️ Eliminar", callback_data=f"action_delete_{user_id}"),
        InlineKeyboardButton("✏️ Renombrar", callback_data=f"action_rename_{user_id}")
    ])
    
    return InlineKeyboardMarkup(keyboard)

# ===== COMANDOS DE NAVEGACIÓN =====

async def start_command(client, message):
    """Maneja el comando /start con mensaje de bienvenida profesional"""
    try:
        user = message.from_user
        update_user_activity(user.id)
        
        welcome_text = f"""👋 **¡Hola {user.first_name}!**

🤖 **File2Link Bot** - Tu gestor de archivos en la nube

━━━━━━━━━━━━━━━━━━━━━━
📁 **GESTIÓN POR CARPETAS**

`/cd downloads` → Archivos de descarga
`/cd packed` → Archivos empaquetados
`/cd` → Ver carpeta actual

📄 **COMANDOS EN CARPETA**
`/list` → Listar archivos
`/rename <nº> <nombre>` → Renombrar
`/delete <nº>` → Eliminar archivo
`/clear` → Vaciar carpeta

📦 **EMPAQUETADO**
`/pack` → Empaquetar downloads → packed
`/pack <MB>` → Dividir en partes

🔄 **COLA DE DESCARGA**
`/queue` → Ver archivos en cola
`/clearqueue` → Limpiar cola

🔍 **INFORMACIÓN**
`/status` → Estado del sistema
`/help` → Ayuda completa

━━━━━━━━━━━━━━━━━━━━━━
📏 **LÍMITES**
• Tamaño máximo: **{MAX_FILE_SIZE_MB} MB** por archivo
• Carpetas ilimitadas
• Descargas ilimitadas

💡 **Consejo:** Envía archivos directamente al bot para comenzar.
━━━━━━━━━━━━━━━━━━━━━━"""

        await message.reply_text(welcome_text)
        logger.info(f"✅ /start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"❌ Error en /start: {e}")


async def help_command(client, message):
    """Maneja el comando /help con guía detallada"""
    try:
        update_user_activity(message.from_user.id)
        
        help_text = f"""📚 **Guía Completa - File2Link Bot**

━━━━━━━━━━━━━━━━━━━━━━
📁 **NAVEGACIÓN ENTRE CARPETAS**
━━━━━━━━━━━━━━━━━━━━━━
`/cd downloads` - Acceder a archivos de descarga
`/cd packed` - Acceder a archivos empaquetados  
`/cd` - Mostrar carpeta actual

📄 **GESTIÓN DE ARCHIVOS** (en carpeta actual)
━━━━━━━━━━━━━━━━━━━━━━
`/list` - Ver todos los archivos
`/list <página>` - Paginación de resultados
`/rename N NUEVO_NOMBRE` - Renombrar archivo #N
`/delete N` - Eliminar archivo #N
`/clear` - Vaciar carpeta completa

📦 **EMPAQUETADO Y COMPRESIÓN**
━━━━━━━━━━━━━━━━━━━━━━
`/pack` - Crear ZIP con todos los downloads
`/pack 100` - Dividir en partes de 100 MB
`/pack 500` - Dividir en partes de 500 MB

🔄 **GESTIÓN DE COLA**
━━━━━━━━━━━━━━━━━━━━━━
`/queue` - Ver archivos en espera
`/clearqueue` - Cancelar descargas pendientes

🔍 **INFORMACIÓN DEL SISTEMA**
━━━━━━━━━━━━━━━━━━━━━━
`/status` - Estado completo del sistema
`/help` - Esta guía de ayuda

📏 **LÍMITES DE USO**
━━━━━━━━━━━━━━━━━━━━../../telegram_handlers.py
Tamaño máximo por archivo: **{MAX_FILE_SIZE_MB} MB**

💡 **EJEMPLOS PRÁCTICOS**
━━━━━━━━━━━━━━━━━━━━━━
1️⃣ Enviar un archivo → Se guarda en `downloads`
2️⃣ `/list` → Ver archivos disponibles
3️⃣ `/pack 100` → Comprimir en partes de 100MB
4️⃣ `/cd packed` → Ir a carpeta empaquetados
5️⃣ `/list` → Ver archivos comprimidos

🎯 **COMANDOS RÁPIDOS**
━━━━━━━━━━━━━━━━━━━━━━
• Los números de archivo son persistentes
• Usa `/list` para ver los números actuales
• Los enlaces de descarga son permanentes"""

        await message.reply_text(help_text)
        logger.info(f"✅ /help enviado a {message.from_user.id}")

    except Exception as e:
        logger.error(f"❌ Error en /help: {e}")

async def cd_command(client, message):
    """Maneja el comando /cd - Cambiar carpeta actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        args = message.text.split()
        
        if len(args) == 1:
            current = session['current_folder']
            await message.reply_text(f"📂 **Carpeta actual:** `{current}`")
        else:
            folder = args[1].lower()
            if folder in ['downloads', 'packed']:
                session['current_folder'] = folder
                await message.reply_text(f"📂 **Cambiado a carpeta:** `{folder}`")
            else:
                await message.reply_text(
                    "❌ **Carpeta no válida.**\n\n"
                    "**Carpetas disponibles:**\n"
                    "• `downloads` - Tus archivos de descarga\n"  
                    "• `packed` - Archivos empaquetados\n\n"
                    "**Uso:** `/cd downloads` o `/cd packed`"
                )

    except Exception as e:
        logger.error(f"Error en /cd: {e}")
        await message.reply_text("❌ Error al cambiar carpeta.")

async def list_command(client, message):
    """Maneja el comando /list - Listar archivos de la carpeta actual CON PAGINACIÓN"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        args = message.text.split()
        page = 1
        if len(args) > 1:
            try:
                page = int(args[1])
            except ValueError:
                page = 1
        
        files = file_service.list_user_files(user_id, current_folder)
        
        if not files:
            await message.reply_text(
                f"📂 **Carpeta {current_folder} vacía.**\n\n"
                f"**Para agregar archivos:**\n"
                f"• Envía archivos al bot (van a 'downloads')\n"
                f"• Usa `/pack` para crear archivos en 'packed'\n"
            )
            return
        
        items_per_page = 10
        total_pages = (len(files) + items_per_page - 1) // items_per_page
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_files = files[start_idx:end_idx]
        
        folder_display = "📥 DESCARGAS" if current_folder == "downloads" else "📦 EMPAQUETADOS"
        files_text = f"**{folder_display}** - Página {page}/{total_pages}\n"
        files_text += f"**Total de archivos:** {len(files)}\n\n"
        
        for file_info in page_files:
            files_text += f"**#{file_info['number']}** - `{file_info['name']}`\n"
            files_text += f"📏 **Tamaño:** {file_info['size_mb']:.1f} MB\n"
            files_text += f"🔗 **Enlace:** [Descargar]({file_info['url']})\n\n"

        if total_pages > 1:
            files_text += f"**Navegación:**\n"
            if page > 1:
                files_text += f"• `/list {page-1}` - Página anterior\n"
            if page < total_pages:
                files_text += f"• `/list {page+1}` - Página siguiente\n"
            files_text += f"• `/list <número>` - Ir a página específica\n"

        files_text += f"\n**Comandos disponibles:**\n"
        files_text += f"• `/delete <número>` - Eliminar archivo\n"
        files_text += f"• `/rename <número> <nuevo_nombre>` - Renombrar\n"
        files_text += f"• `/clear` - Vaciar carpeta completa"

        if len(files_text) > 4000:
            parts = []
            current_part = ""
            
            for line in files_text.split('\n'):
                if len(current_part + line + '\n') > 4000:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part)
            
            await message.reply_text(parts[0], disable_web_page_preview=True)
            
            for part in parts[1:]:
                await message.reply_text(part, disable_web_page_preview=True)
        else:
            await message.reply_text(files_text, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error en /list: {e}")
        await message.reply_text("❌ Error al listar archivos.")

async def delete_command(client, message):
    """Maneja el comando /delete - Eliminar archivo actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        args = message.text.split()
        
        if len(args) < 2:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/delete <número>`\n"
                "**Ejemplo:** `/delete 5`\n\n"
                "Usa `/list` para ver los números de archivo."
            )
            return
        
        try:
            file_number = int(args[1])
        except ValueError:
            await message.reply_text("❌ El número debe ser un valor numérico válido.")
            return
        
        success, result_message = file_service.delete_file_by_number(user_id, file_number, current_folder)
        
        if success:
            await message.reply_text(f"✅ **{result_message}**")
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en /delete: {e}")
        await message.reply_text("❌ Error al eliminar archivo.")

async def clear_command(client, message):
    """Maneja el comando /clear - Vaciar carpeta actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        success, result_message = file_service.delete_all_files(user_id, current_folder)
        
        if success:
            await message.reply_text(f"✅ **{result_message}**")
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en /clear: {e}")
        await message.reply_text("❌ Error al vaciar carpeta.")

async def rename_command(client, message):
    """Maneja el comando /rename - Renombrar archivo actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        args = message.text.split(maxsplit=2)
        
        if len(args) < 3:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/rename <número> <nuevo_nombre>`\n"
                "**Ejemplo:** `/rename 3 mi_documento_importante`\n\n"
                "Usa `/list` para ver los números de archivo."
            )
            return
        
        try:
            file_number = int(args[1])
        except ValueError:
            await message.reply_text("❌ El número debe ser un valor numérico válido.")
            return
        
        new_name = args[2].strip()
        
        if not new_name:
            await message.reply_text("❌ El nuevo nombre no puede estar vacío.")
            return
        
        success, result_message, new_url = file_service.rename_file(user_id, file_number, new_name, current_folder)
        
        if success:
            response_text = f"✅ **{result_message}**\n\n"
            response_text += f"**Nuevo enlace:**\n"
            response_text += f"🔗 [{new_name}]({new_url})"
            
            await message.reply_text(
                response_text,
                disable_web_page_preview=True
            )
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en comando /rename: {e}")
        await message.reply_text("❌ Error al renombrar archivo.")

async def status_command(client, message):
    """Maneja el comando /status - Estado profesional del sistema"""
    try:
        user_id = message.from_user.id
        update_user_activity(user_id)
        session = get_user_session(user_id)
        
        downloads_count = len(file_service.list_user_files(user_id, "downloads"))
        packed_count = len(file_service.list_user_files(user_id, "packed"))
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        system_status = load_manager.get_status()
        server_state = "✅ Óptimo" if system_status['can_accept_work'] else "⚠️ Ocupado"
        
        status_text = f"""📊 **Estado del Sistema**

━━━━━━━━━━━━━━━━━━━━━━
👤 **TU CUENTA**
━━━━━━━━━━━━━━━━━━━━━━
• ID: `{user_id}`
• Carpeta actual: `{session['current_folder']}`
• Archivos en downloads: **{downloads_count}**
• Archivos empaquetados: **{packed_count}**
• Espacio usado: **{size_mb:.2f} MB**

━━━━━━━━━━━━━━━━━━━━━━
📏 **CONFIGURACIÓN**
━━━━━━━━━━━━━━━━━━━━━━
• Límite por archivo: **{MAX_FILE_SIZE_MB} MB**
• Compresión: **ZIP con división**

━━━━━━━━━━━━━━━━━━━━━━
🖥️ **SERVIDOR**
━━━━━━━━━━━━━━━━━━━━━━
• Procesos: {system_status['active_processes']}/{system_status['max_processes']}
• CPU: {system_status['cpu_percent']:.1f}%
• Memoria: {system_status['memory_percent']:.1f}%
• Estado: **{server_state}**

━━━━━━━━━━━━━━━━━━━━━━
💡 **Consejo:** Usa `/pack` para comprimir tus archivos."""
        
        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"❌ Error en /status: {e}")
        await message.reply_text("❌ Error al obtener estado.")

async def pack_command(client, message):
    """Maneja el comando /pack - Empaquetado COMPLETO como el original"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado.**\n\n"
                f"CPU: {system_status['cpu_percent']:.1f}%\n"
                f"Procesos activos: {system_status['active_processes']}\n"
                f"Intenta nuevamente en unos minutos."
            )
            return
        
        split_size = None
        if len(command_parts) > 1:
            try:
                split_size = int(command_parts[1])
                if split_size <= 0:
                    await message.reply_text("❌ El tamaño de división debe ser mayor a 0 MB")
                    return
                if split_size > 501:
                    await message.reply_text("❌ El tamaño máximo por parte es 500 MB")
                    return
            except ValueError:
                await message.reply_text("❌ Formato incorrecto. Usa: `/pack` o `/pack 100`")
                return
        
        status_msg = await message.reply_text(
            "📦 **Iniciando empaquetado...**\n\n"
            f"{'Dividiendo en partes...' if split_size else 'Creando archivo ZIP...'}"
        )
        
        def run_advanced_packing():
            try:
                files, status_message = packing_service.pack_folder(user_id, split_size)
                return files, status_message
            except Exception as e:
                logger.error(f"Error en empaquetado optimizado: {e}")
                return None, f"Error al empaquetar: {str(e)}"
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_advanced_packing)
            files, status_message = future.result(timeout=300)
        
        if not files:
            await status_msg.edit_text(f"❌ {status_message}")
            return
        
        if len(files) == 1:
            file_info = files[0]
            total_files_info = f" ({file_info['total_files']} archivos)" if 'total_files' in file_info else ""
            
            response_text = f"""✅ **Empaquetado Completado{total_files_info}**

**Archivo:** `{file_info['filename']}`
**Tamaño:** {file_info['size_mb']:.1f} MB

**Enlace de Descarga:**
🔗 [{file_info['filename']}]({file_info['url']})

**Nota:** Usa `/cd packed` y `/list` para ver tus archivos empaquetados"""
            
            await status_msg.edit_text(
                response_text, 
                disable_web_page_preview=True
            )
            
        else:
            total_files = 0
            for file_info in files:
                if 'total_files' in file_info and file_info['total_files'] > 0:
                    total_files = file_info['total_files']
                    break
            
            total_files_info = f" ({total_files} archivos)" if total_files > 0 else ""
            
            # Buscar archivo de lista de partes (.txt)
            user_dir = file_service.get_user_directory(user_id, "packed")
            base_name = None
            for file_info in files:
                if '.001' in file_info['filename']:
                    base_name = file_info['filename'].rsplit('.', 2)[0]
                    break
            
            list_filename = f"{base_name}.txt" if base_name else None
            list_url = None
            
            if list_filename and os.path.exists(os.path.join(user_dir, list_filename)):
                list_url = file_service.create_packed_url(user_id, list_filename)
            
            # CONSTRUIR MENSAJE COMPLETO CON TODOS LOS ENLACES (COMO EL ORIGINAL)
            response_text = f"""✅ **Empaquetado Completado{total_files_info}**

**Archivos Generados:** {len(files)} partes
**Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB

**Enlaces de Descarga:**"""
            
            # Agregar TODOS los enlaces en el mensaje (como el original)
            for file_info in files:
                response_text += f"\n\n**{file_info['filename']}**\n"
                response_text += f"🔗 {file_info['url']}"
            
            # Agregar enlace al archivo .txt si existe
            if list_url:
                response_text += f"\n\n**📑 Lista completa en archivo:**"
                response_text += f"\n🔗 [{list_filename}]({list_url})"
            
            response_text += "\n\n**Nota:** Usa `/cd packed` y `/list` para ver tus archivos empaquetados"
            
            # Manejar mensajes largos (dividir si es necesario)
            if len(response_text) > 4000:
                await status_msg.edit_text("✅ **Empaquetado completado**\n\nLos enlaces se enviarán en varios mensajes...")
                
                # Enviar primero el mensaje con estadísticas
                stats_msg = f"""✅ **Empaquetado Completado{total_files_info}**

**Archivos Generados:** {len(files)} partes
**Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB"""
                
                if list_url:
                    stats_msg += f"\n\n**📑 Lista completa en archivo:**"
                    stats_msg += f"\n🔗 [{list_filename}]({list_url})"
                
                await message.reply_text(stats_msg, disable_web_page_preview=True)
                
                # Enviar enlaces en grupos de 10
                for i in range(0, len(files), 10):
                    group = files[i:i+10]
                    group_text = ""
                    for file_info in group:
                        group_text += f"\n\n**{file_info['filename']}**\n"
                        group_text += f"🔗 {file_info['url']}"
                    
                    await message.reply_text(group_text, disable_web_page_preview=True)
                    
                await message.reply_text(f"✅ **Total: {len(files)} partes generadas**")
            else:
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True
                )
                
        logger.info(f"Empaquetado optimizado completado para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text("❌ El empaquetado tardó demasiado tiempo. Intenta con menos archivos.")
    except Exception as e:
        logger.error(f"Error en comando /pack optimizado: {e}")
        await message.reply_text("❌ Error en el proceso de empaquetado.")

async def queue_command(client, message):
    """Maneja el comando /queue - Ver estado de la cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola vacía**\n\nNo hay archivos en cola de descarga.")
            return
        
        queue_size = len(user_queues[user_id])
        current_processing = "Sí" if user_id in user_current_processing else "No"
        
        queue_text = f"📋 **Estado de la Cola - {queue_size} archivo(s)**\n\n"
        
        for i, msg in enumerate(user_queues[user_id]):
            file_info = "Desconocido"
            if msg.document:
                file_info = f"📄 {msg.document.file_name or 'Documento sin nombre'}"
            elif msg.video:
                file_info = f"🎥 {msg.video.file_name or 'Video sin nombre'}"
            elif msg.audio:
                file_info = f"🎵 {msg.audio.file_name or 'Audio sin nombre'}"
            elif msg.photo:
                file_info = f"🖼️ Foto"
            
            queue_text += f"**#{i+1}** - {file_info}\n"
        
        queue_text += f"\n**Procesando actualmente:** {current_processing}"
        
        await message.reply_text(queue_text)
        
    except Exception as e:
        logger.error(f"Error en /queue: {e}")
        await message.reply_text("❌ Error al obtener estado de la cola.")

async def clear_queue_command(client, message):
    """Maneja el comando /clearqueue - Limpiar cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola ya está vacía**")
            return
        
        queue_size = len(user_queues[user_id])
        user_queues[user_id] = []
        
        if user_id in user_current_processing:
            del user_current_processing[user_id]
        
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
        
        await message.reply_text(f"🗑️ **Cola limpiada**\n\nSe removieron {queue_size} archivos de la cola.")
        
    except Exception as e:
        logger.error(f"Error en /clearqueue: {e}")
        await message.reply_text("❌ Error al limpiar la cola.")

async def cleanup_command(client, message):
    """Limpia archivos temporales y optimiza el sistema"""
    try:
        status_msg = await message.reply_text("🧹 **Limpiando archivos temporales...**")
        
        total_size = file_service.get_user_storage_usage(message.from_user.id)
        size_mb = total_size / (1024 * 1024)
        
        await status_msg.edit_text(
            f"✅ **Limpieza completada**\n\n"
            f"• Espacio usado: {size_mb:.2f} MB\n"
            f"• Sistema optimizado"
        )
        
    except Exception as e:
        logger.error(f"Error en comando cleanup: {e}")
        await message.reply_text("❌ Error durante la limpieza.")

async def handle_file(client, message):
    """Maneja la recepción de archivos con sistema de cola MEJORADO"""
    try:
        user = message.from_user
        user_id = user.id

        logger.info(f"📥 Archivo recibido de {user_id} - Agregando a cola")

        file_size = 0
        if message.document:
            file_size = message.document.file_size or 0
        elif message.video:
            file_size = message.video.file_size or 0
        elif message.audio:
            file_size = message.audio.file_size or 0
        elif message.photo:
            file_size = message.photo[-1].file_size or 0

        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                "❌ **Archivo demasiado grande**\n\n"
                f"**Tamaño máximo permitido:** {MAX_FILE_SIZE_MB} MB\n"
                f"**Tu archivo:** {file_service.format_bytes(file_size)}\n\n"
                "Por favor, divide el archivo en partes más pequeñas."
            )
            return

        if user_id not in user_queues:
            user_queues[user_id] = []
        
        user_queues[user_id].append(message)
        
        if len(user_queues[user_id]) == 1:
            await process_file_queue(client, user_id)
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)
        try:
            await message.reply_text("❌ Error al procesar el archivo.")
        except:
            pass

async def process_file_queue(client, user_id):
    """Procesa la cola de archivos del usuario de manera secuencial - VERSIÓN CORREGIDA"""
    try:
        total_files_in_batch = len(user_queues[user_id])
        user_batch_totals[user_id] = total_files_in_batch
        
        current_position = 0
        
        while user_queues.get(user_id) and user_queues[user_id]:
            message = user_queues[user_id][0]
            current_position += 1
            
            logger.info(f"🔄 Procesando archivo {current_position}/{total_files_in_batch} para usuario {user_id}")
            
            await process_single_file(client, message, user_id, current_position, total_files_in_batch)
            
            await asyncio.sleep(1)
        
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
                
    except Exception as e:
        logger.error(f"Error en process_file_queue: {e}", exc_info=True)
        if user_id in user_queues:
            user_queues[user_id] = []
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]

async def process_single_file(client, message, user_id, current_position, total_files):
    """Procesa un solo archivo con progreso MEJORADO y descarga rápida"""
    max_retries = 3
    start_time = time.time()
    
    try:
        file_obj = None
        file_type = None
        original_filename = None
        file_size = 0

        if message.document:
            file_obj = message.document
            file_type = "documento"
            original_filename = message.document.file_name or "archivo_sin_nombre"
            file_size = file_obj.file_size or 0
        elif message.video:
            file_obj = message.video
            file_type = "video"
            original_filename = message.video.file_name or "video_sin_nombre.mp4"
            file_size = file_obj.file_size or 0
        elif message.audio:
            file_obj = message.audio
            file_type = "audio"
            original_filename = message.audio.file_name or "audio_sin_nombre.mp3"
            file_size = file_obj.file_size or 0
        elif message.photo:
            file_obj = message.photo[-1]
            file_type = "foto"
            original_filename = f"foto_{message.id}.jpg"
            file_size = file_obj.file_size or 0
        else:
            logger.warning(f"Mensaje no contiene archivo manejable: {message.media}")
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            return

        if not file_obj:
            logger.error("No se pudo obtener el objeto de archivo")
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            await message.reply_text("❌ Error: No se pudo identificar el archivo.")
            return

        user_dir = file_service.get_user_directory(user_id, "downloads")
        
        sanitized_name = file_service.sanitize_filename(original_filename)
        
        stored_filename = sanitized_name
        counter = 1
        base_name, ext = os.path.splitext(sanitized_name)
        file_path = os.path.join(user_dir, stored_filename)
        
        while os.path.exists(file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        file_number = file_service.register_file(user_id, original_filename, stored_filename, "downloads")
        logger.info(f"📝 Archivo registrado: #{file_number} - {original_filename} -> {stored_filename}")

        initial_message = progress_service.create_progress_message(
            filename=original_filename,
            current=0,
            total=file_size,
            speed=0,
            user_first_name=message.from_user.first_name,
            process_type="Subiendo",
            current_file=current_position,
            total_files=total_files
        )
        
        progress_msg = await message.reply_text(initial_message)
        
        user_current_processing[user_id] = progress_msg.id

        progress_data = {'last_update': 0, 'last_speed': 0}

        async def progress_callback(current, total):
            try:
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0
                
                progress_data['last_speed'] = (
                    0.7 * progress_data.get('last_speed', 0) + 0.3 * speed
                )
                smoothed_speed = progress_data['last_speed']

                current_time = time.time()
                last_update = progress_data.get('last_update', 0)

                if current_time - last_update >= 0.5 or current == total:
                    progress_message = progress_service.create_progress_message(
                        filename=original_filename,
                        current=current,
                        total=total,
                        speed=smoothed_speed,
                        user_first_name=message.from_user.first_name,
                        process_type="Subiendo",
                        current_file=current_position,
                        total_files=total_files
                    )

                    try:
                        await progress_msg.edit_text(progress_message)
                        progress_data['last_update'] = current_time
                    except Exception as edit_error:
                        logger.warning(f"No se pudo editar mensaje de progreso: {edit_error}")

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")

        try:
            logger.info(f"⚡ Iniciando descarga rápida: {original_filename}")
            
            success, downloaded = await fast_download_service.download_with_retry(
                client=client,
                message=message,
                file_path=file_path,
                progress_callback=progress_callback
            )

            if not success or not os.path.exists(file_path):
                await progress_msg.edit_text("❌ Error: El archivo no se descargó correctamente.")
                if user_id in user_queues and user_queues[user_id]:
                    user_queues[user_id].pop(0)
                return

            final_size = os.path.getsize(file_path)
            if file_size > 0 and final_size < file_size * 0.95:
                logger.warning(f"⚠️ Posible descarga incompleta: esperado {file_size}, obtenido {final_size}")
                await progress_msg.edit_text("⚠️ Advertencia: El archivo podría estar incompleto.")
            
            size_mb = final_size / (1024 * 1024)

            download_url = file_service.create_download_url(user_id, stored_filename)
            logger.info(f"🔗 URL generada: {download_url}")

            files_list = file_service.list_user_files(user_id, "downloads")
            current_file_number = None
            for file_info in files_list:
                if file_info['stored_name'] == stored_filename:
                    current_file_number = file_info['number']
                    break

            queue_info = ""
            next_files_count = len(user_queues[user_id]) - 1 if user_id in user_queues and user_queues[user_id] else 0
            
            if next_files_count > 0:
                queue_info = f"\n\n⏭️ **Siguiente archivo en cola...** ({next_files_count} restantes)"

            success_text = f"""✅ **Archivo #{current_file_number or file_number} Almacenado!**

**Nombre:** `{original_filename}`
**Tipo:** {file_type}
**Tamaño:** {size_mb:.2f} MB

**Enlace de Descarga:**
🔗 [{original_filename}]({download_url})

**Ubicación:** Carpeta `downloads`{queue_info}"""

            await progress_msg.edit_text(success_text, disable_web_page_preview=True)
            
            logger.info(f"✅ Archivo guardado exitosamente: {stored_filename} para usuario {user_id}")

        except Exception as download_error:
            logger.error(f"❌ Error en descarga: {download_error}", exc_info=True)
            await progress_msg.edit_text(f"❌ Error al descargar el archivo: {str(download_error)}")
        
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

    except Exception as e:
        logger.error(f"❌ Error procesando archivo individual: {e}", exc_info=True)
        try:
            await message.reply_text(f"❌ Error procesando archivo: {str(e)}")
        except:
            pass
        
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

def setup_handlers(client):
    """Configura todos los handlers del bot de forma profesional"""
    
    # Comandos principales
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    
    # Navegación y gestión de carpetas
    client.on_message(filters.command("cd") & filters.private)(cd_command)
    client.on_message(filters.command("list") & filters.private)(list_command)
    
    # Gestión de archivos
    client.on_message(filters.command("delete") & filters.private)(delete_command)
    client.on_message(filters.command("clear") & filters.private)(clear_command)
    client.on_message(filters.command("rename") & filters.private)(rename_command)
    
    # Empaquetado
    client.on_message(filters.command("pack") & filters.private)(pack_command)
    
    # Gestión de cola
    client.on_message(filters.command("queue") & filters.private)(queue_command)
    client.on_message(filters.command("clearqueue") & filters.private)(clear_queue_command)
    
    # Limpieza
    client.on_message(filters.command("cleanup") & filters.private)(cleanup_command)
    
    # Manejo de archivos multimedia
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) &
        filters.private
    )(handle_file)
    
    logger.info("✅ Handlers configurados correctamente")
