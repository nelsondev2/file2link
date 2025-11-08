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
from youtube_service import youtube_service

logger = logging.getLogger(__name__)

# ===== SISTEMA DE SESIÓN POR USUARIO =====
user_sessions = {}  # {user_id: {'current_folder': 'downloads'}}
user_queues = {}    # {user_id: [message1, message2, ...]}
user_progress_msgs = {}  # {user_id: progress_message}

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

**🎬 YOUTUBE:**
`/yt <url>` - Descargar video (360p MP4)

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

**🎬 YOUTUBE:**
`/yt <url>` - Descargar video de YouTube (360p MP4)

**🔍 INFORMACIÓN:**
`/status` - Estado del sistema
`/help` - Esta ayuda

**📌 EJEMPLOS:**
`/cd downloads`
`/list`
`/delete 5`
`/rename 3 mi_documento`
`/pack 100`
`/yt https://youtube.com/watch?v=...`"""

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
                f"• Usa `/yt` para descargar videos de YouTube"
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

async def yt_command(client, message):
    """Maneja el comando /yt - Descargar video de YouTube"""
    try:
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/yt <url_de_youtube>`\n"
                "**Ejemplo:** `/yt https://www.youtube.com/watch?v=ABCD1234`\n\n"
                "**Características:**\n"
                "• Descarga en calidad 360p MP4\n"
                "• Máximo 200MB por video\n"
                "• Tiempo máximo: 5 minutos"
            )
            return

        url = args[1].strip()
        
        # Verificar que el sistema puede aceptar trabajo
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado.**\n\n"
                f"CPU: {system_status['cpu_percent']:.1f}%\n"
                f"Procesos activos: {system_status['active_processes']}\n"
                f"Intenta nuevamente en unos minutos."
            )
            return

        # Enviar mensaje de inicio
        status_msg = await message.reply_text(
            "📥 **Iniciando descarga de YouTube...**\n\n"
            "🔍 Obteniendo información del video..."
        )

        # Realizar la descarga
        success, result = await youtube_service.download_youtube_video(url, user_id)

        if not success:
            await status_msg.edit_text(f"❌ **Error en descarga:** {result}")
            return

        # Éxito - mostrar información del archivo
        video_info = result
        duration_str = ""
        if video_info['duration'] > 0:
            minutes = video_info['duration'] // 60
            seconds = video_info['duration'] % 60
            duration_str = f"**Duración:** {minutes}:{seconds:02d}\n"

        success_text = f"""✅ **Video #{video_info['file_number']} Descargado!**

**Título:** `{video_info['title']}`
**Tamaño:** {video_info['size_mb']:.2f} MB
{duration_str}**Calidad:** 360p MP4

**Enlace de Descarga:**
🔗 [{video_info['filename']}]({video_info['url']})

**Ubicación:** Carpeta `downloads`"""

        await status_msg.edit_text(success_text, disable_web_page_preview=True)
        
        logger.info(f"Descarga de YouTube completada para usuario {user_id}: {video_info['filename']}")

    except Exception as e:
        logger.error(f"Error en comando /yt: {e}")
        try:
            await message.reply_text("❌ Error al procesar la descarga de YouTube.")
        except:
            pass

# ===== MANEJO DE ARCHIVOS CON COLA =====

async def handle_file(client, message):
    """Maneja la recepción de archivos con sistema de cola"""
    try:
        user = message.from_user
        user_id = user.id

        logger.info(f"Archivo recibido de {user_id}")

        # Inicializar cola del usuario si no existe
        if user_id not in user_queues:
            user_queues[user_id] = []
        
        # Agregar mensaje a la cola
        user_queues[user_id].append(message)
        
        # Si es el primer archivo en la cola, procesar inmediatamente
        if len(user_queues[user_id]) == 1:
            await process_file_queue(client, user_id)
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)
        try:
            await message.reply_text("❌ Error al procesar el archivo.")
        except:
            pass

async def process_file_queue(client, user_id):
    """Procesa la cola de archivos del usuario de manera secuencial"""
    try:
        while user_queues.get(user_id):
            message = user_queues[user_id][0]
            await process_single_file(client, message, user_id)
            
            # Remover el archivo procesado de la cola
            user_queues[user_id].pop(0)
            
            # Si hay más archivos, continuar procesando
            if user_queues[user_id]:
                # Pequeña pausa entre archivos
                await asyncio.sleep(1)
            else:
                # No hay más archivos, limpiar mensaje de progreso
                if user_id in user_progress_msgs:
                    try:
                        await user_progress_msgs[user_id].delete()
                        del user_progress_msgs[user_id]
                    except:
                        pass
                
    except Exception as e:
        logger.error(f"Error en process_file_queue: {e}")
        # Limpiar cola en caso de error
        if user_id in user_queues:
            user_queues[user_id] = []

async def process_single_file(client, message, user_id):
    """Procesa un solo archivo con progreso actualizado"""
    try:
        user_dir = file_service.get_user_directory(user_id, "downloads")

        file_obj = None
        file_type = None
        original_filename = None
        file_size = 0

        if message.document:
            file_obj = message.document
            file_type = "documento"
            original_filename = message.document.file_name or "archivo"
            file_size = file_obj.file_size
        elif message.video:
            file_obj = message.video
            file_type = "video"
            original_filename = message.video.file_name or "video.mp4"
            file_size = file_obj.file_size
        elif message.audio:
            file_obj = message.audio
            file_type = "audio"
            original_filename = message.audio.file_name or "audio.mp3"
            file_size = file_obj.file_size
        elif message.photo:
            file_obj = message.photo[-1]
            file_type = "foto"
            original_filename = f"foto_{file_obj.file_id}.jpg"
            file_size = file_obj.file_size
        else:
            logger.warning(f"Mensaje no contiene un tipo de archivo manejable: {message}")
            return

        if not file_obj:
            logger.error(f"No se pudo obtener el objeto de archivo")
            await message.reply_text("❌ Error: No se pudo identificar el archivo.")
            return

        sanitized_name = file_service.sanitize_filename(original_filename)
        file_number = file_service.get_next_file_number(user_id)
        
        stored_filename = sanitized_name
        
        counter = 1
        base_stored_filename = stored_filename
        file_path = os.path.join(user_dir, stored_filename)
        while os.path.exists(file_path):
            name_no_ext = os.path.splitext(base_stored_filename)[0]
            ext = os.path.splitext(base_stored_filename)[1]
            stored_filename = f"{name_no_ext}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        file_service.register_file(user_id, original_filename, stored_filename)

        start_time = time.time()
        
        # Crear o actualizar mensaje de progreso
        if user_id not in user_progress_msgs:
            initial_message = progress_service.create_progress_message(
                filename=original_filename,
                current=0,
                total=file_size,
                speed=0,
                file_num=len(user_queues[user_id]),
                total_files=len(user_queues[user_id]),
                user_id=user_id,
                process_type="Descargando"
            )
            progress_msg = await message.reply_text(initial_message)
            user_progress_msgs[user_id] = progress_msg
        else:
            progress_msg = user_progress_msgs[user_id]

        progress_data = {'last_update': 0}

        async def progress_callback(current, total):
            try:
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0

                current_time = time.time()
                last_update = progress_data.get('last_update', 0)

                if current_time - last_update >= 2 or current == total:
                    queue_position = user_queues[user_id].index(message) + 1 if user_id in user_queues else 1
                    queue_total = len(user_queues[user_id]) if user_id in user_queues else 1
                    
                    progress_message = progress_service.create_progress_message(
                        filename=original_filename,
                        current=current,
                        total=total,
                        speed=speed,
                        file_num=queue_position,
                        total_files=queue_total,
                        user_id=user_id,
                        process_type="Descargando"
                    )

                    await progress_msg.edit_text(progress_message)
                    progress_data['last_update'] = current_time

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")

        # Descargar archivo
        downloaded_path = await message.download(
            file_path,
            progress=progress_callback
        )

        if not downloaded_path:
            await progress_msg.edit_text("❌ Error al descargar el archivo.")
            return

        final_size = os.path.getsize(file_path)
        size_mb = final_size / (1024 * 1024)

        download_url = file_service.create_download_url(user_id, stored_filename)

        # Mensaje final para el archivo actual
        files_list = file_service.list_user_files(user_id, "downloads")
        current_file_number = None
        for file_info in files_list:
            if file_info['stored_name'] == stored_filename:
                current_file_number = file_info['number']
                break

        success_text = f"""✅ **Archivo #{current_file_number} Almacenado!**

**Nombre:** `{original_filename}`
**Tipo:** {file_type}
**Tamaño:** {size_mb:.2f} MB

**Enlace de Descarga:**
🔗 [{original_filename}]({download_url})

**Ubicación:** Carpeta `downloads`"""

        # Si es el último archivo en la cola, mostrar mensaje final
        if user_id in user_queues and len(user_queues[user_id]) <= 1:
            await progress_msg.edit_text(success_text, disable_web_page_preview=True)
        else:
            # Solo actualizar el progreso, el mensaje final vendrá después
            pass

        logger.info(f"Archivo guardado: {stored_filename} para usuario {user_id}")

    except Exception as e:
        logger.error(f"Error procesando archivo individual: {e}", exc_info=True)
        if user_id in user_progress_msgs:
            try:
                await user_progress_msgs[user_id].edit_text(f"❌ Error procesando archivo: {str(e)}")
            except:
                pass

# ===== CONFIGURACIÓN DE HANDLERS =====

def setup_handlers(client):
    """Configura todos los handlers del bot (sin callbacks)"""
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
    
    # YouTube
    client.on_message(filters.command("yt") & filters.private)(yt_command)
    
    # Archivos (sin botones)
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) &
        filters.private
    )(handle_file)
