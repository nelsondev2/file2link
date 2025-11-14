import os
import logging
import sys
import time
import asyncio
import concurrent.futures
from pyrogram import Client, filters
from pyrogram.types import Message

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import download_service
from config import DOWNLOAD_MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

# ===== SISTEMA DE SESIÓN POR USUARIO =====
user_sessions = {}  # {user_id: {'current_folder': 'downloads'}}
user_queues = {}    # {user_id: [message1, message2, ...]}
user_progress_msgs = {}  # {user_id: {message_id: progress_message}}
user_current_processing = {}  # {user_id: current_message_id}

def get_user_session(user_id):
    """Obtiene o crea la sesión del usuario"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'current_folder': 'downloads'}
    return user_sessions[user_id]

# ===== COMANDOS DE NAVEGACIÓN =====

async def start_command(client, message):
    """Maneja el comando /start"""
    try:
        user = message.from_user
        
        welcome_text = f"""👋 **Bienvenido/a {user.first_name}!**

🤖 File2Link Bot - Sistema de Gestión de Archivos por Carpetas

**📁 SISTEMA DE CARPETAS:**
`/cd downloads` - Acceder a archivos de descarga
`/cd packed` - Acceder a archivos empaquetados
`/cd` - Mostrar carpeta actual

**📄 COMANDOS EN CARPETA:**
`/list` - Listar archivos de la carpeta actual
`/rename <número> <nuevo_nombre>`
`/delete <número>`
`/clear` - Vaciar carpeta actual

**📦 EMPAQUETADO:**
`/pack` - Empaquetar downloads → packed
`/pack <MB>` - Empaquetar y dividir

**🌐 DESCARGAS WEB:**
`/dl <url>` - Descargar archivo desde enlace web

**🔄 GESTIÓN DE COLA:**
`/queue` - Ver archivos en cola de descarga
`/clearqueue` - Limpiar cola de descarga

**🔍 INFORMACIÓN:**
`/status` - Estado del sistema
`/help` - Ayuda completa

**¡Envía archivos o usa /cd para comenzar!**"""

        await message.reply_text(welcome_text)
        logger.info(f"/start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"Error en /start: {e}")

async def help_command(client, message):
    """Maneja el comando /help"""
    try:
        help_text = """📚 **Ayuda - Sistema de Carpetas**

**📁 NAVEGACIÓN:**
`/cd downloads` - Archivos de descarga
`/cd packed` - Archivos empaquetados  
`/cd` - Carpeta actual

**📄 GESTIÓN (en carpeta actual):**
`/list` - Ver archivos
`/rename N NUEVO_NOMBRE` - Renombrar
`/delete N` - Eliminar archivo
`/clear` - Vaciar carpeta

**📦 EMPAQUETADO:**
`/pack` - Crear ZIP de downloads
`/pack MB` - Dividir en partes

**🌐 DESCARGAS WEB:**
`/dl <url>` - Descargar archivo desde enlace

**🔄 GESTIÓN DE COLA:**
`/queue` - Ver archivos en cola de descarga
`/clearqueue` - Limpiar cola de descarga

**🔍 INFORMACIÓN:**
`/status` - Estado del sistema
`/help` - Esta ayuda

**📌 EJEMPLOS:**
`/cd downloads`
`/list`
`/delete 5`
`/rename 3 mi_documento`
`/pack 100`
`/dl https://ejemplo.com/archivo.pdf`
`/queue` - Ver qué archivos están en cola"""

        await message.reply_text(help_text)

    except Exception as e:
        logger.error(f"Error en /help: {e}")

async def cd_command(client, message):
    """Maneja el comando /cd - Cambiar carpeta actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        args = message.text.split()
        
        if len(args) == 1:
            # Mostrar carpeta actual
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
    """Maneja el comando /list - Listar archivos de la carpeta actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        files = file_service.list_user_files(user_id, current_folder)
        
        if not files:
            await message.reply_text(
                f"📂 **Carpeta {current_folder} vacía.**\n\n"
                f"**Para agregar archivos:**\n"
                f"• Envía archivos al bot (van a 'downloads')\n"
                f"• Usa `/pack` para crear archivos en 'packed'\n"
                f"• Usa `/dl` para descargar archivos desde enlaces web"
            )
            return
        
        folder_display = "📥 DESCARGAS" if current_folder == "downloads" else "📦 EMPAQUETADOS"
        files_text = f"**{folder_display}** ({len(files)} archivos)\n\n"
        
        for file_info in files:
            files_text += f"**#{file_info['number']}** - `{file_info['name']}`\n"
            files_text += f"📏 **Tamaño:** {file_info['size_mb']:.1f} MB\n"
            files_text += f"🔗 **Enlace:** [Descargar]({file_info['url']})\n\n"

        files_text += f"**Comandos disponibles en esta carpeta:**\n"
        files_text += f"• `/delete <número>` - Eliminar archivo\n"
        files_text += f"• `/rename <número> <nuevo_nombre>` - Renombrar\n"
        files_text += f"• `/clear` - Vaciar carpeta completa"

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
        
        # Eliminar archivo inmediatamente (sin confirmación)
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
        
        # Vaciar carpeta inmediatamente (sin confirmación)
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

# ===== COMANDOS GLOBALES =====

async def status_command(client, message):
    """Maneja el comando /status - Estado del sistema"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        
        # Archivos por carpeta
        downloads_count = len(file_service.list_user_files(user_id, "downloads"))
        packed_count = len(file_service.list_user_files(user_id, "packed"))
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        system_status = load_manager.get_status()
        
        status_text = f"""**📊 ESTADO DEL SISTEMA - {message.from_user.first_name}**

**👤 USUARIO:**
• **ID:** `{user_id}`
• **Carpeta actual:** `{session['current_folder']}`
• **Archivos downloads:** {downloads_count}
• **Archivos packed:** {packed_count}
• **Espacio usado:** {size_mb:.2f} MB

**🖥️ SERVIDOR:**
• **Procesos activos:** {system_status['active_processes']}/{system_status['max_processes']}
• **Uso de CPU:** {system_status['cpu_percent']:.1f}%
• **Uso de memoria:** {system_status['memory_percent']:.1f}%
• **Estado:** {"✅ ACEPTANDO TRABAJO" if system_status['can_accept_work'] else "⚠️ SOBRECARGADO"}"""
        
        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ Error al obtener estado.")

async def pack_command(client, message):
    """Maneja el comando /pack - Empaquetado"""
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
                if split_size > 200:
                    await message.reply_text("❌ El tamaño máximo por parte es 200 MB")
                    return
            except ValueError:
                await message.reply_text("❌ Formato incorrecto. Usa: `/pack` o `/pack 100`")
                return
        
        status_msg = await message.reply_text(
            "📦 **Iniciando empaquetado...**\n\n"
            "Uniendo todos tus archivos en un ZIP..."
        )
        
        def run_simple_packing():
            try:
                files, status_message = packing_service.pack_folder(user_id, split_size)
                return files, status_message
            except Exception as e:
                logger.error(f"Error en empaquetado: {e}")
                return None, f"Error al empaquetar: {str(e)}"
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_simple_packing)
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
                if 'total_files' in file_info:
                    total_files = file_info['total_files']
                    break
            
            total_files_info = f" ({total_files} archivos)" if total_files > 0 else ""
            
            response_text = f"""✅ **Empaquetado Completado{total_files_info}**

**Archivos Generados:** {len(files)} partes
**Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB

**Enlaces de Descarga:**"""
            
            for file_info in files:
                response_text += f"\n\n**Parte {file_info['number']}:** 🔗 [{file_info['filename']}]({file_info['url']})"
            
            response_text += "\n\n**Nota:** Usa `/cd packed` y `/list` para ver tus archivos empaquetados"
            
            if len(response_text) > 4000:
                await status_msg.edit_text("✅ **Empaquetado completado**\n\nLos enlaces se enviarán en varios mensajes...")
                
                for file_info in files:
                    part_text = f"**Parte {file_info['number']}:** 🔗 [{file_info['filename']}]({file_info['url']})"
                    await message.reply_text(part_text, disable_web_page_preview=True)
            else:
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True
                )
                
        logger.info(f"Empaquetado completado para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text("❌ El empaquetado tardó demasiado tiempo. Intenta con menos archivos.")
    except Exception as e:
        logger.error(f"Error en comando /pack: {e}")
        await message.reply_text("❌ Error en el proceso de empaquetado.")

# ===== NUEVO COMANDO DE DESCARGA WEB =====

async def download_command(client, message):
    """Maneja el comando /dl - Descargar archivo desde URL"""
    try:
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/dl <url_del_archivo>`\n"
                "**Ejemplo:** `/dl https://ejemplo.com/mi_archivo.pdf`\n\n"
                "**Formatos soportados:** Cualquier archivo descargable (PDF, ZIP, MP4, etc.)\n"
                f"**Tamaño máximo:** {DOWNLOAD_MAX_FILE_SIZE_MB}MB"
            )
            return

        url = args[1].strip()
        
        # Verificar carga del sistema
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado.**\n\n"
                f"CPU: {system_status['cpu_percent']:.1f}%\n"
                f"Procesos activos: {system_status['active_processes']}\n"
                f"Intenta nuevamente en unos minutos."
            )
            return

        # Mensaje de inicio
        status_msg = await message.reply_text(
            "🌐 **Iniciando descarga desde URL...**\n\n"
            "🔍 Verificando enlace y obteniendo información..."
        )

        # Realizar descarga
        success, result = await download_service.download_from_url(url, user_id)

        if not success:
            error_message = result
            
            # Mensajes de error más específicos
            if "no válida" in error_message.lower():
                error_message += "\n\n💡 **Sugerencia:** Verifica que la URL sea correcta y accesible."
            elif "demasiado grande" in error_message.lower():
                error_message += f"\n\n💡 **Sugerencia:** El tamaño máximo es {DOWNLOAD_MAX_FILE_SIZE_MB}MB."
            elif "timeout" in error_message.lower():
                error_message += "\n\n💡 **Sugerencia:** El servidor está respondiendo lentamente."
            
            await status_msg.edit_text(f"❌ **Error:** {error_message}")
            return

        # Éxito - mostrar información
        file_info = result

        success_text = f"""✅ **Archivo #{file_info['file_number']} Descargado!**

**Nombre:** `{file_info['filename']}`
**Tamaño:** {file_info['size_mb']:.2f} MB
**Tipo:** {file_info['content_type']}

**Enlace de Descarga:**
🔗 [{file_info['filename']}]({file_info['url']})

**Ubicación:** Carpeta `downloads`"""

        await status_msg.edit_text(success_text, disable_web_page_preview=True)
        
        logger.info(f"✅ Descarga web exitosa para {user_id}: {file_info['filename']}")

    except Exception as e:
        logger.error(f"❌ Error en comando /dl: {e}")
        try:
            await message.reply_text(
                "❌ **Error interno del sistema.**\n\n"
                "El servicio de descargas puede estar experimentando problemas temporales. "
                "Intenta nuevamente en unos minutos."
            )
        except:
            pass

# ===== GESTIÓN DE COLA =====

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
        
        # Limpiar también el procesamiento actual
        if user_id in user_current_processing:
            del user_current_processing[user_id]
        
        await message.reply_text(f"🗑️ **Cola limpiada**\n\nSe removieron {queue_size} archivos de la cola.")
        
    except Exception as e:
        logger.error(f"Error en /clearqueue: {e}")
        await message.reply_text("❌ Error al limpiar la cola.")

# ===== COMANDO CLEANUP =====

async def cleanup_command(client, message):
    """Limpia archivos temporales y optimiza el sistema"""
    try:
        status_msg = await message.reply_text("🧹 **Limpiando archivos temporales...**")
        
        # Limpiar temporales de descargas
        download_service.cleanup_temp_files()
        
        # Obtener estadísticas de espacio
        total_size = file_service.get_user_storage_usage(message.from_user.id)
        size_mb = total_size / (1024 * 1024)
        
        await status_msg.edit_text(
            f"✅ **Limpieza completada**\n\n"
            f"• Archivos temporales eliminados\n"
            f"• Espacio usado: {size_mb:.2f} MB\n"
            f"• Sistema optimizado"
        )
        
    except Exception as e:
        logger.error(f"Error en comando cleanup: {e}")
        await message.reply_text("❌ Error durante la limpieza.")

# ===== MANEJO DE ARCHIVOS CON COLA MEJORADO =====

async def handle_file(client, message):
    """Maneja la recepción de archivos con sistema de cola MEJORADO"""
    try:
        user = message.from_user
        user_id = user.id

        logger.info(f"📥 Archivo recibido de {user_id} - Agregando a cola")

        # Validar tamaño máximo del archivo (500MB)
        MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
        
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
                f"**Tamaño máximo permitido:** 500 MB\n"
                f"**Tu archivo:** {file_service.format_bytes(file_size)}\n\n"
                "Por favor, divide el archivo en partes más pequeñas."
            )
            return

        # Inicializar cola del usuario si no existe
        if user_id not in user_queues:
            user_queues[user_id] = []
        
        # Agregar mensaje a la cola
        user_queues[user_id].append(message)
        
        # Si es el primer archivo en la cola, procesar inmediatamente
        if len(user_queues[user_id]) == 1:
            await process_file_queue(client, user_id)
        else:
            # Notificar al usuario que el archivo está en cola
            queue_position = len(user_queues[user_id]) - 1
            await message.reply_text(
                f"📋 **Archivo agregado a la cola**\n\n"
                f"**Posición en cola:** #{queue_position + 1}\n"
                f"**Total en cola:** {len(user_queues[user_id])} archivos\n\n"
                f"⏳ Se procesará automáticamente cuando termine el archivo actual."
            )
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)
        try:
            await message.reply_text("❌ Error al procesar el archivo.")
        except:
            pass

async def process_file_queue(client, user_id):
    """Procesa la cola de archivos del usuario de manera secuencial - VERSIÓN MEJORADA"""
    try:
        while user_queues.get(user_id) and user_queues[user_id]:
            message = user_queues[user_id][0]
            logger.info(f"🔄 Procesando archivo en cola para usuario {user_id}, archivos restantes: {len(user_queues[user_id])}")
            
            await process_single_file(client, message, user_id)
            
            # Pequeña pausa entre archivos para evitar sobrecarga
            await asyncio.sleep(1)
                
    except Exception as e:
        logger.error(f"Error en process_file_queue: {e}", exc_info=True)
        # Limpiar cola en caso de error
        if user_id in user_queues:
            user_queues[user_id] = []

async def process_single_file(client, message, user_id, retry_count=0):
    """Procesa un solo archivo con progreso actualizado - VERSIÓN CON REINTENTOS"""
    max_retries = 2
    try:
        # Obtener información del archivo
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
            file_obj = message.photo[-1]  # Foto de mayor calidad
            file_type = "foto"
            original_filename = f"foto_{message.id}.jpg"
            file_size = file_obj.file_size or 0
        else:
            logger.warning(f"Mensaje no contiene archivo manejable: {message.media}")
            # Eliminar de la cola si no es un archivo válido
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            return

        if not file_obj:
            logger.error("No se pudo obtener el objeto de archivo")
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            await message.reply_text("❌ Error: No se pudo identificar el archivo.")
            return

        # Crear directorio de usuario
        user_dir = file_service.get_user_directory(user_id, "downloads")
        
        # Sanitizar y generar nombre único
        sanitized_name = file_service.sanitize_filename(original_filename)
        
        # Generar nombre único para evitar colisiones
        stored_filename = sanitized_name
        counter = 1
        base_name, ext = os.path.splitext(sanitized_name)
        file_path = os.path.join(user_dir, stored_filename)
        
        while os.path.exists(file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        # Registrar archivo ANTES de descargar
        file_number = file_service.register_file(user_id, original_filename, stored_filename, "downloads")
        logger.info(f"📝 Archivo registrado: #{file_number} - {original_filename} -> {stored_filename}")

        start_time = time.time()
        
        # Crear mensaje de progreso INDIVIDUAL para este archivo
        queue_info = ""
        if user_id in user_queues and len(user_queues[user_id]) > 1:
            queue_info = f"\n📋 **En cola:** {len(user_queues[user_id]) - 1} archivos restantes"
        
        initial_message = progress_service.create_progress_message(
            filename=original_filename,
            current=0,
            total=file_size,
            speed=0,
            file_num=1,
            total_files=1,
            user_id=user_id,
            process_type="Descargando"
        ) + queue_info
        
        progress_msg = await message.reply_text(initial_message)
        
        # Guardar el mensaje de progreso actual para este usuario
        user_current_processing[user_id] = progress_msg.id

        progress_data = {'last_update': 0}

        async def progress_callback(current, total):
            try:
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0

                current_time = time.time()
                last_update = progress_data.get('last_update', 0)

                if current_time - last_update >= 2 or current == total:
                    queue_info = ""
                    if user_id in user_queues and len(user_queues[user_id]) > 1:
                        queue_info = f"\n📋 **En cola:** {len(user_queues[user_id]) - 1} archivos restantes"
                    
                    progress_message = progress_service.create_progress_message(
                        filename=original_filename,
                        current=current,
                        total=total,
                        speed=speed,
                        file_num=1,
                        total_files=1,
                        user_id=user_id,
                        process_type="Descargando"
                    ) + queue_info

                    try:
                        await progress_msg.edit_text(progress_message)
                        progress_data['last_update'] = current_time
                    except Exception as edit_error:
                        logger.warning(f"No se pudo editar mensaje de progreso: {edit_error}")

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")

        # Descargar archivo
        try:
            logger.info(f"⬇️ Iniciando descarga: {original_filename}")
            downloaded_path = await message.download(
                file_path,
                progress=progress_callback
            )

            if not downloaded_path or not os.path.exists(file_path):
                if retry_count < max_retries:
                    logger.warning(f"Reintentando descarga (intento {retry_count + 1})")
                    await asyncio.sleep(2)
                    await process_single_file(client, message, user_id, retry_count + 1)
                    return
                else:
                    await progress_msg.edit_text("❌ Error: El archivo no se descargó correctamente después de varios intentos.")
                    # Revertir registro si falla la descarga
                    if user_id in user_queues and user_queues[user_id]:
                        user_queues[user_id].pop(0)
                    return

            # Verificar que el archivo se descargó completamente
            final_size = os.path.getsize(file_path)
            if file_size > 0 and final_size < file_size * 0.9:  # Permitir 10% de diferencia
                logger.warning(f"⚠️ Tamaño del archivo sospechoso: esperado {file_size}, obtenido {final_size}")

            size_mb = final_size / (1024 * 1024)

            # Generar URL de descarga
            download_url = file_service.create_download_url(user_id, stored_filename)
            logger.info(f"🔗 URL generada: {download_url}")

            # Obtener número real del archivo
            files_list = file_service.list_user_files(user_id, "downloads")
            current_file_number = None
            for file_info in files_list:
                if file_info['stored_name'] == stored_filename:
                    current_file_number = file_info['number']
                    break

            # Mensaje final de éxito
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

            # Mostrar mensaje final
            await progress_msg.edit_text(success_text, disable_web_page_preview=True)
            
            logger.info(f"✅ Archivo guardado exitosamente: {stored_filename} para usuario {user_id}")

        except Exception as download_error:
            logger.error(f"❌ Error en descarga: {download_error}", exc_info=True)
            if retry_count < max_retries:
                logger.info(f"Reintentando descarga (intento {retry_count + 1})")
                await asyncio.sleep(2)
                await process_single_file(client, message, user_id, retry_count + 1)
                return
            else:
                await progress_msg.edit_text(f"❌ Error al descargar el archivo después de {max_retries + 1} intentos: {str(download_error)}")
        
        # FINALMENTE: Remover este mensaje de la cola y procesar el siguiente
        if user_id in user_queues and user_queues[user_id]:
            # Remover el archivo actual de la cola
            user_queues[user_id].pop(0)
            
            # Limpiar mensaje de procesamiento actual
            if user_id in user_current_processing:
                del user_current_processing[user_id]
            
            # Si hay más archivos en la cola, procesar el siguiente
            if user_queues[user_id]:
                logger.info(f"🔄 Procesando siguiente archivo en cola para usuario {user_id}")
                await asyncio.sleep(1)  # Pequeña pausa
                await process_file_queue(client, user_id)

    except Exception as e:
        logger.error(f"❌ Error procesando archivo individual: {e}", exc_info=True)
        try:
            # Intentar notificar al usuario del error
            error_msg = await message.reply_text(f"❌ Error procesando archivo: {str(e)}")
        except:
            pass
        
        # Asegurarse de remover de la cola incluso en error
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        # Limpiar mensaje de procesamiento actual
        if user_id in user_current_processing:
            del user_current_processing[user_id]
            
        # Intentar continuar con la cola si hay más archivos
        if user_id in user_queues and user_queues[user_id]:
            await asyncio.sleep(1)
            await process_file_queue(client, user_id)

# ===== CONFIGURACIÓN DE HANDLERS =====

def setup_handlers(client):
    """Configura todos los handlers del bot"""
    # Comandos básicos
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    
    # Sistema de carpetas
    client.on_message(filters.command("cd") & filters.private)(cd_command)
    client.on_message(filters.command("list") & filters.private)(list_command)
    client.on_message(filters.command("delete") & filters.private)(delete_command)
    client.on_message(filters.command("clear") & filters.private)(clear_command)
    client.on_message(filters.command("rename") & filters.private)(rename_command)
    
    # Empaquetado
    client.on_message(filters.command("pack") & filters.private)(pack_command)
    
    # NUEVO: Descargas web
    client.on_message(filters.command("dl") & filters.private)(download_command)
    
    # Gestión de cola
    client.on_message(filters.command("queue") & filters.private)(queue_command)
    client.on_message(filters.command("clearqueue") & filters.private)(clear_queue_command)
    
    # Limpieza
    client.on_message(filters.command("cleanup") & filters.private)(cleanup_command)
    
    # Archivos (sin botones)
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) &
        filters.private
    )(handle_file)
