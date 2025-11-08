import os
import logging
import sys
import time
import concurrent.futures
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service

logger = logging.getLogger(__name__)

# Variable global para almacenar la carpeta actual por usuario
user_current_dirs = {}

# Variable global para almacenar mensajes de progreso activos
active_progress_messages = {}

async def start_command(client, message):
    """Maneja el comando /start"""
    try:
        user = message.from_user
        
        welcome_text = f"""👋 **Bienvenido/a {user.first_name}!

🤖 File2Link Bot - Gestión de Archivos**

**Comandos Disponibles:**
`/start` - Mensaje de bienvenida
`/help` - Ayuda y comandos disponibles
`/cd` - Cambiar a carpeta (download o packed)
`/dir` - Ver ruta actual
`/list` - Listar archivos en carpeta actual
`/pack` - Empaquetar archivos en download
`/rename` - Renombrar archivo
`/delete` - Eliminar archivo o todos

**¿Cómo Funciona?**
1. Envíame cualquier archivo
2. Lo almaceno en tu carpeta personal
3. Obtienes un enlace web permanente
4. Gestiona tus archivos fácilmente

**¡Envía un archivo para comenzar!**"""

        await message.reply_text(welcome_text)
        logger.info(f"/start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"Error en /start: {e}")

async def help_command(client, message):
    """Maneja el comando /help"""
    try:
        help_text = """📚 **Ayuda - Comandos Disponibles**

**Navegación:**
`/cd download` - Ir a carpeta de descargas
`/cd packed` - Ir a carpeta empaquetados
`/dir` - Ver ruta actual
`/list` - Listar archivos en carpeta actual

**Gestión de Archivos:**
`/delete` - Eliminar TODOS los archivos
`/delete número` - Eliminar archivo específico
`/rename número nuevo_nombre` - Renombrar archivo

**Empaquetado:**
`/pack` - Crear ZIP de todos los archivos en download
`/pack MB` - Dividir en partes de MB especificados

**Información:**
`/start` - Información inicial
`/help` - Esta ayuda

**Uso Básico:**
1. Envía archivos al bot
2. Usa `/cd download` para ir a descargas
3. Usa `/list` para ver archivos
4. Usa números para gestionar archivos"""

        await message.reply_text(help_text)

    except Exception as e:
        logger.error(f"Error en /help: {e}")

async def cd_command(client, message):
    """Maneja el comando /cd para cambiar de carpeta"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        if len(command_parts) < 2:
            await message.reply_text(
                "**Uso:** `/cd carpeta`\n\n"
                "**Carpetas disponibles:**\n"
                "• `download` - Archivos descargados\n"
                "• `packed` - Archivos empaquetados"
            )
            return
        
        folder = command_parts[1].lower()
        
        if folder not in ['download', 'packed']:
            await message.reply_text(
                "**Carpeta no válida.**\n\n"
                "**Carpetas disponibles:**\n"
                "• `download` - Archivos descargados\n"
                "• `packed` - Archivos empaquetados"
            )
            return
        
        # Actualizar carpeta actual del usuario
        user_current_dirs[user_id] = folder
        
        await message.reply_text(f"✅ **Cambiado a carpeta:** `{folder}`")
        
    except Exception as e:
        logger.error(f"Error en /cd: {e}")
        await message.reply_text("Error al cambiar de carpeta.")

async def dir_command(client, message):
    """Maneja el comando /dir para ver la ruta actual"""
    try:
        user_id = message.from_user.id
        
        # Obtener carpeta actual o usar 'download' por defecto
        current_dir = user_current_dirs.get(user_id, 'download')
        
        await message.reply_text(f"📁 **Ruta actual:** `/static/{user_id}/{current_dir}/`")
        
    except Exception as e:
        logger.error(f"Error en /dir: {e}")
        await message.reply_text("Error al obtener ruta actual.")

async def list_command(client, message):
    """Maneja el comando /list para listar archivos"""
    try:
        user_id = message.from_user.id
        
        # Obtener carpeta actual o usar 'download' por defecto
        current_dir = user_current_dirs.get(user_id, 'download')
        
        if current_dir == 'download':
            files = file_service.list_user_files(user_id)
        else:
            files = file_service.list_packed_files(user_id)
        
        if not files:
            await message.reply_text(
                f"**No hay archivos en la carpeta `{current_dir}`.**\n\n"
                "Usa `/cd download` o `/cd packed` para cambiar de carpeta."
            )
            return
        
        files_text = f"**📁 Archivos en `{current_dir}` ({len(files)}):**\n\n"
        
        for file_info in files:
            files_text += f"**{file_info['number']}.** `{file_info['name']}` ({file_info['size_mb']:.1f} MB)\n"
            files_text += f"🔗 [Descargar]({file_info['url']})\n\n"

        files_text += f"**Usa los números para gestionar archivos:**\n"
        files_text += f"• Eliminar: `/delete número`\n"
        if current_dir == 'download':
            files_text += f"• Renombrar: `/rename número nuevo_nombre`\n"

        await message.reply_text(files_text, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error en /list: {e}")
        await message.reply_text("Error al listar archivos.")

async def files_command(client, message):
    """Maneja el comando /files (compatibilidad)"""
    try:
        user_id = message.from_user.id
        files = file_service.list_user_files(user_id)
        
        if not files:
            await message.reply_text(
                "No tienes archivos almacenados.\n\n"
                "¡Envía tu primer archivo para comenzar!"
            )
            return
        
        files_text = f"**Tus Archivos ({len(files)}):**\n\n"
        
        for file_info in files:
            files_text += f"**{file_info['number']}.** `{file_info['name']}` ({file_info['size_mb']:.1f} MB)\n"
            files_text += f"🔗 [Descargar]({file_info['url']})\n\n"

        files_text += f"**Usa los números para gestionar archivos:**\n"
        files_text += f"• Renombrar: `/rename número nuevo_nombre`\n"
        files_text += f"• Eliminar: `/delete número`\n"
        files_text += f"• Ver todos: `/list`"

        await message.reply_text(files_text, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error en /files: {e}")
        await message.reply_text("Error al listar archivos.")

async def status_command(client, message):
    """Maneja el comando /status"""
    try:
        user_id = message.from_user.id
        files = file_service.list_user_files(user_id)
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        system_status = load_manager.get_status()
        
        status_text = f"""**Estado del Sistema - {message.from_user.first_name}**

**Usuario:** {user_id}
**Archivos:** {len(files)}
**Espacio Usado:** {size_mb:.2f} MB

**Estado del Servidor:**
• **Procesos Activos:** {system_status['active_processes']}/{system_status['max_processes']}
• **Uso de CPU:** {system_status['cpu_percent']:.1f}%
• **Uso de Memoria:** {system_status['memory_percent']:.1f}%
• **Estado:** {"✅ ACEPTANDO TRABAJO" if system_status['can_accept_work'] else "⚠️ SOBRECARGADO"}"""
        
        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("Error al obtener estado.")

async def pack_command(client, message):
    """Maneja el comando /pack"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"""**Sistema sobrecargado.**\n\n"""
                f"""CPU: {system_status['cpu_percent']:.1f}%\n"""
                f"""Procesos activos: {system_status['active_processes']}\n"""
                f"""Intenta nuevamente en unos minutos."""
            )
            return
        
        split_size = None
        if len(command_parts) > 1:
            try:
                split_size = int(command_parts[1])
                if split_size <= 0:
                    await message.reply_text("El tamaño de división debe ser mayor a 0 MB")
                    return
                if split_size > 200:
                    await message.reply_text("El tamaño máximo por parte es 200 MB")
                    return
            except ValueError:
                await message.reply_text("Formato incorrecto. Usa: `/pack` o `/pack 100`")
                return
        
        status_msg = await message.reply_text(
            "**Iniciando empaquetado...**\n\n"
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
            await status_msg.edit_text(status_message)
            return
        
        if len(files) == 1:
            file_info = files[0]
            total_files_info = f" ({file_info['total_files']} archivos)" if 'total_files' in file_info else ""
            
            response_text = f"""**Empaquetado Completado{total_files_info}**

**Archivo #{file_info['number']}:** `{file_info['filename']}`
**Tamaño:** {file_info['size_mb']:.1f} MB

**Enlace de Descarga:**
📎 [{file_info['filename']}]({file_info['url']})

**Al descargar:** Descomprime el ZIP para obtener todos tus archivos"""
            
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
            
            response_text = f"""**Empaquetado Completado{total_files_info}**

**Archivos Generados:** {len(files)} partes
**Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB

**Enlaces de Descarga:**
"""
            
            for file_info in files:
                response_text += f"\n**Parte {file_info['number']}:** 📎 [{file_info['filename']}]({file_info['url']})"
            
            response_text += "\n\n**Al descargar:** Descarga todas las partes y descomprime el ZIP"
            
            if len(response_text) > 4000:
                await status_msg.edit_text("**Empaquetado completado**\n\nLos enlaces se enviarán en varios mensajes...")
                
                for file_info in files:
                    part_text = f"**Parte {file_info['number']}:** 📎 [{file_info['filename']}]({file_info['url']})"
                    await message.reply_text(part_text, disable_web_page_preview=True)
            else:
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True
                )
                
        logger.info(f"Empaquetado completado para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text("El empaquetado tardó demasiado tiempo. Intenta con menos archivos.")
    except Exception as e:
        logger.error(f"Error en comando /pack: {e}")
        await message.reply_text("Error en el proceso de empaquetado.")

async def rename_command(client, message):
    """Maneja el comando /rename"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split(maxsplit=2)
        
        if len(command_parts) < 3:
            await message.reply_text("Formato incorrecto. Usa: `/rename número nuevo_nombre`")
            return
        
        try:
            file_number = int(command_parts[1])
        except ValueError:
            await message.reply_text("El número debe ser un valor numérico válido.")
            return
        
        new_name = command_parts[2].strip()
        
        if not new_name:
            await message.reply_text("El nuevo nombre no puede estar vacío.")
            return
        
        # Obtener carpeta actual para determinar tipo de archivo
        current_dir = user_current_dirs.get(user_id, 'download')
        file_type = current_dir
        
        success, result_message, new_url = file_service.rename_file(user_id, file_number, new_name, file_type)
        
        if success:
            response_text = f"**{result_message}**\n\n"
            response_text += f"**Nuevo enlace:**\n"
            response_text += f"📎 [{new_name}]({new_url})"
            
            await message.reply_text(
                response_text,
                disable_web_page_preview=True
            )
        else:
            await message.reply_text(f"**{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en comando /rename: {e}")
        await message.reply_text("Error al renombrar archivo.")

async def delete_command(client, message):
    """Maneja el comando /delete"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        if len(command_parts) == 1:
            # Eliminar todos los archivos (confirmación)
            confirm_text = """**¿Eliminar TODOS los archivos?**

**Esta acción:**
• Eliminará todos tus archivos
• No se puede deshacer
• Los enlaces dejarán de funcionar

**Para confirmar:** `/delete confirm`"""
            
            await message.reply_text(confirm_text)
            return
        
        if command_parts[1] == "confirm":
            # Eliminar todos los archivos
            success, result_message = file_service.delete_all_files(user_id)
            await message.reply_text(f"**{result_message}**")
            return
        
        # Eliminar archivo específico
        try:
            file_number = int(command_parts[1])
        except ValueError:
            await message.reply_text("Formato incorrecto. Usa: `/delete número` o `/delete` para eliminar todo")
            return
        
        # Obtener carpeta actual para determinar tipo de archivo
        current_dir = user_current_dirs.get(user_id, 'download')
        file_type = current_dir
        
        success, result_message = file_service.delete_file_by_number(user_id, file_number, file_type)
        await message.reply_text(f"**{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en comando /delete: {e}")
        await message.reply_text("Error al eliminar archivo.")

async def handle_file(client, message):
    """Maneja la recepción de archivos con progreso unificado CORREGIDO"""
    try:
        user = message.from_user
        user_id = user.id

        logger.info(f"Archivo recibido de {user_id}. Tipo de mensaje: {message.media}")

        user_dir = file_service.get_user_directory(user_id)

        file_obj = None
        file_type = None
        original_filename = None
        file_size = 0

        if message.document:
            file_obj = message.document
            file_type = "documento"
            original_filename = message.document.file_name or "archivo"
            file_size = file_obj.file_size
            logger.info(f"Detectado documento: {original_filename}, tamaño: {file_size}")
        elif message.video:
            file_obj = message.video
            file_type = "video"
            original_filename = message.video.file_name or "video.mp4"
            file_size = file_obj.file_size
            logger.info(f"Detectado video: {original_filename}, tamaño: {file_size}")
        elif message.audio:
            file_obj = message.audio
            file_type = "audio"
            original_filename = message.audio.file_name or "audio.mp3"
            file_size = file_obj.file_size
            logger.info(f"Detectado audio: {original_filename}, tamaño: {file_size}")
        elif message.photo:
            file_obj = message.photo[-1] # Obtener la foto de mayor resolución
            file_type = "foto"
            original_filename = f"foto_{file_obj.file_id}.jpg"
            file_size = file_obj.file_size
            logger.info(f"Detectada foto: {original_filename}, tamaño: {file_size}")
        else:
            logger.warning(f"Mensaje no contiene un tipo de archivo manejable: {message}")
            return

        if not file_obj:
            logger.error(f"No se pudo obtener el objeto de archivo para el mensaje: {message}")
            await message.reply_text("Error: No se pudo identificar el archivo en el mensaje.")
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

        # Registrar el archivo ANTES de iniciar la descarga
        registered_file_num = file_service.register_file(user_id, original_filename, stored_filename)

        start_time = time.time()
        
        # Inicializar o actualizar progreso unificado
        if user_id not in active_progress_messages:
            # Crear mensaje inicial de progreso unificado
            initial_message = progress_service.create_unified_progress_message(
                filename=original_filename,
                current=0,
                total=file_size,
                speed=0,
                file_num=1,
                total_files=1,  # Empezamos con 1 archivo
                user_id=user_id,
                process_type="Descargando"
            )
            progress_msg = await message.reply_text(initial_message)
            active_progress_messages[user_id] = {
                'message': progress_msg,
                'start_time': start_time,
                'files': {original_filename: {'current': 0, 'total': file_size, 'completed': False}},
                'total_files': 1,  # Total de archivos en este lote
                'completed_files': 0,
                'last_update': 0
            }
            logger.info(f"Nuevo progreso unificado creado para usuario {user_id}")
        else:
            # Agregar nuevo archivo al progreso existente
            active_progress_messages[user_id]['files'][original_filename] = {
                'current': 0, 
                'total': file_size, 
                'completed': False
            }
            active_progress_messages[user_id]['total_files'] = len(active_progress_messages[user_id]['files'])
            logger.info(f"Archivo agregado a progreso existente. Total: {active_progress_messages[user_id]['total_files']}")

        progress_data = active_progress_messages[user_id]

        async def progress_callback(current, total, filename, user_id):
            try:
                current_time = time.time()
                last_update = progress_data.get('last_update', 0)
                
                # Actualizar progreso del archivo actual
                if filename in progress_data['files']:
                    progress_data['files'][filename]['current'] = current
                    progress_data['files'][filename]['total'] = total
                
                # Actualizar cada 1.5 segundos o cuando se complete (más frecuente)
                if current_time - last_update >= 1.5 or current == total:
                    # Calcular progreso total
                    total_current = sum(f['current'] for f in progress_data['files'].values())
                    total_size = sum(f['total'] for f in progress_data['files'].values())
                    elapsed_time = current_time - progress_data['start_time']
                    speed = total_current / elapsed_time if elapsed_time > 0 else 0
                    
                    # Contar archivos completados
                    completed_files = sum(1 for f in progress_data['files'].values() if f.get('completed', False))
                    
                    # Encontrar archivo actualmente en progreso (el que no está completado)
                    current_file = filename
                    for file_name, file_data in progress_data['files'].items():
                        if not file_data.get('completed', False) and file_data['current'] < file_data['total']:
                            current_file = file_name
                            break
                    
                    progress_message = progress_service.create_unified_progress_message(
                        filename=current_file,
                        current=total_current,
                        total=total_size,
                        speed=speed,
                        file_num=completed_files + 1,  # +1 porque estamos en el siguiente
                        total_files=progress_data['total_files'],
                        user_id=user_id,
                        process_type="Descargando"
                    )

                    try:
                        await progress_data['message'].edit_text(progress_message)
                        progress_data['last_update'] = current_time
                    except Exception as edit_error:
                        logger.error(f"Error editando mensaje de progreso: {edit_error}")
                    
                    # Marcar como completado si es el caso
                    if current == total and filename in progress_data['files']:
                        progress_data['files'][filename]['completed'] = True
                        progress_data['completed_files'] = completed_files + 1

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")

        async def update_progress(current, total):
            await progress_callback(current, total, original_filename, user_id)

        # Descargar el archivo
        downloaded_path = await message.download(
            file_path,
            progress=update_progress
        )

        if not downloaded_path:
            logger.error(f"Error al descargar archivo {original_filename}")
            # Marcar como error pero mantener el progreso para otros archivos
            if user_id in active_progress_messages and original_filename in active_progress_messages[user_id]['files']:
                active_progress_messages[user_id]['files'][original_filename]['completed'] = True
                active_progress_messages[user_id]['completed_files'] += 1
            return

        final_size = os.path.getsize(file_path)
        size_mb = final_size / (1024 * 1024)

        download_url = file_service.create_download_url(user_id, stored_filename)

        # Obtener el número de archivo que ve el usuario
        files_list = file_service.list_user_files(user_id)
        current_file_number = None
        for file_info in files_list:
            if file_info['stored_name'] == stored_filename:
                current_file_number = file_info['number']
                break

        logger.info(f"Archivo {original_filename} descargado exitosamente. Número: {current_file_number}")

        # Verificar si todos los archivos están completos
        if user_id in active_progress_messages:
            all_completed = all(f.get('completed', False) for f in active_progress_messages[user_id]['files'].values())
            
            if all_completed:
                total_files_processed = active_progress_messages[user_id]['total_files']
                success_text = f"""**✅ Subida Completa - {total_files_processed} Archivos**

**Último archivo procesado:**
`#{current_file_number}` - `{original_filename}`
**Tamaño:** {size_mb:.2f} MB
**Enlace:** 📎 [{original_filename}]({download_url})

**Usa `/list` para ver todos tus archivos.**"""

                try:
                    await active_progress_messages[user_id]['message'].edit_text(success_text, disable_web_page_preview=True)
                except Exception as e:
                    logger.error(f"Error editando mensaje final: {e}")
                    await message.reply_text(success_text, disable_web_page_preview=True)
                
                # Limpiar progreso completado
                del active_progress_messages[user_id]
                logger.info(f"Progreso unificado completado y limpiado para usuario {user_id}")
            else:
                # Solo log, no hacer nada - el callback se encargará de las actualizaciones
                logger.info(f"Archivo {original_filename} completado, esperando otros archivos...")

        logger.info(f"Archivo guardado: {stored_filename} para usuario {user_id}")

    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)
        # Limpiar progreso en caso de error general
        if user_id in active_progress_messages:
            try:
                await active_progress_messages[user_id]['message'].edit_text("❌ Error durante la subida de archivos.")
                del active_progress_messages[user_id]
            except:
                pass
        try:
            await message.reply_text("Error al procesar el archivo.")
        except:
            pass
