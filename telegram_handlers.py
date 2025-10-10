import logging
import sys
import concurrent.futures
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service

logger = logging.getLogger(__name__)

async def start_command(client, message):
    """Maneja el comando /start"""
    try:
        user = message.from_user
        
        welcome_text = f"""👋 **Bienvenido/a {user.first_name}!

🤖 File2Link Bot - Gestión de Archivos**

**Comandos Disponibles:**
`/start` - Mensaje de bienvenida
`/help` - Ayuda y comandos disponibles
`/files` - Ver tus archivos numerados
`/status` - Ver tu estado y uso
`/pack` - Empaquetar todos tus archivos
`/pack [MB]` - Empaquetar y dividir (ej: `/pack 100`)
`/rename [número] [nuevo_nombre]` - Renombrar archivo

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

**Gestión de Archivos:**
`/files` - Ver todos tus archivos con números
`/status` - Ver tu uso de almacenamiento
`/rename N NUEVO_NOMBRE` - Renombrar archivo

**Empaquetado:**
`/pack` - Crear ZIP de todos los archivos
`/pack MB` - Dividir en partes de MB especificados

**Información:**
`/start` - Información inicial
`/help` - Esta ayuda

**Uso Básico:**
1. Envía archivos al bot
2. Usa `/files` para ver la lista
3. Usa los números para gestionar archivos
4. Usa `/pack` para empaquetar todo"""

        await message.reply_text(help_text)

    except Exception as e:
        logger.error(f"Error en /help: {e}")

async def files_command(client, message):
    """Maneja el comando /files"""
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
        files_text += f"• Eliminar: Usa los botones debajo\n"

        keyboard_buttons = []
        for i in range(0, len(files), 2):
            row = []
            for file_info in files[i:i+2]:
                row.append(InlineKeyboardButton(
                    f"🗑️ {file_info['number']}",
                    callback_data=f"delete_{file_info['number']}"
                ))
            keyboard_buttons.append(row)
        
        keyboard_buttons.append([InlineKeyboardButton("🗑️ ELIMINAR TODOS", callback_data="delete_all")])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)

        await message.reply_text(files_text, reply_markup=keyboard, disable_web_page_preview=True)

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
                f"**Sistema sobrecargado.**\n\n"
                f"CPU: {system_status['cpu_percent']:.1f}%
"
                f"Procesos activos: {system_status['active_processes']}
"
                f"Intenta nuevamente en unos minutos."
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
            
            clear_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Vaciar Empaquetados", callback_data="clear_packed")]
            ])
            
            await status_msg.edit_text(
                response_text, 
                disable_web_page_preview=True,
                reply_markup=clear_keyboard
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
                
                clear_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑️ Vaciar Empaquetados", callback_data="clear_packed")]
                ])
                await message.reply_text(
                    "¿Quieres liberar espacio?",
                    reply_markup=clear_keyboard
                )
            else:
                clear_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑️ Vaciar Empaquetados", callback_data="clear_packed")]
                ])
                
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True,
                    reply_markup=clear_keyboard
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
        
        success, result_message, new_url = file_service.rename_file(user_id, file_number, new_name)
        
        if success:
            response_text = f"**{result_message}**\n\n"
            response_text += f"**Nuevo enlace:**\n"
            response_text += f"📎 [{new_name}]({new_url})"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Abrir Enlace", url=new_url)]
            ])
            
            await message.reply_text(
                response_text,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
        else:
            await message.reply_text(f"**{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en comando /rename: {e}")
        await message.reply_text("Error al renombrar archivo.")

async def handle_file(client, message):
    """Maneja la recepción de archivos"""
    try:
        user = message.from_user
        user_id = user.id

        logger.info(f"Archivo recibido de {user_id}")

        user_dir = file_service.get_user_directory(user_id)

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
            file_obj = message.photo
            file_type = "foto"
            original_filename = f"foto_{message.id}.jpg"
            file_size = file_obj.file_size
        else:
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
        initial_message = progress_service.create_progress_message(
            filename=original_filename,
            current=0,
            total=file_size,
            speed=0,
            file_num=1,
            total_files=1,
            user_id=user_id,
            process_type="Descargando"
        )

        progress_msg = await message.reply_text(initial_message)

        progress_data = {'last_update': 0}

        async def progress_callback(current, total, message, filename, user_id, start_time):
            try:
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0

                current_time = time.time()
                last_update = progress_data.get('last_update', 0)

                if current_time - last_update >= 2 or current == total:
                    progress_message = progress_service.create_progress_message(
                        filename=filename,
                        current=current,
                        total=total,
                        speed=speed,
                        file_num=1,
                        total_files=1,
                        user_id=user_id,
                        process_type="Descargando"
                    )

                    await message.edit_text(progress_message)
                    progress_data['last_update'] = current_time

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")

        async def update_progress(current, total):
            await progress_callback(current, total, progress_msg, original_filename, user_id, start_time)

        downloaded_path = await message.download(
            file_path,
            progress=update_progress
        )

        if not downloaded_path:
            await progress_msg.edit_text("Error al descargar el archivo.")
            return

        final_size = os.path.getsize(file_path)
        size_mb = final_size / (1024 * 1024)

        download_url = file_service.create_download_url(user_id, stored_filename)

        files_list = file_service.list_user_files(user_id)
        current_file_number = None
        for file_info in files_list:
            if file_info['stored_name'] == stored_filename:
                current_file_number = file_info['number']
                break

        success_text = f"""**¡Archivo #{current_file_number} Almacenado!**

**Nombre:** `{original_filename}`
**Tipo:** {file_type}
**Tamaño:** {size_mb:.2f} MB

**Enlace de Descarga:**
📎 [{original_filename}]({download_url})"""

        try:
            file_hash = file_service.create_file_hash(user_id, stored_filename)
            file_service.store_file_mapping(file_hash, user_id, stored_filename)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Abrir Enlace", url=download_url)],
                [InlineKeyboardButton("🗑️ Eliminar", callback_data=f"del_{file_hash}")]
            ])

            await progress_msg.edit_text(success_text, reply_markup=keyboard)

        except Exception as button_error:
            logger.error(f"Error con botones: {button_error}")
            await progress_msg.edit_text(success_text)

        logger.info(f"Archivo guardado: {stored_filename} para usuario {user_id}")

    except Exception as e:
        logger.error(f"Error procesando archivo: {e}")
        try:
            await message.reply_text("Error al procesar el archivo.")
        except:
            pass

async def delete_file_callback(client, callback_query):
    """Maneja el callback de eliminar archivos individuales"""
    try:
        data = callback_query.data
        
        if data.startswith("delete_"):
            file_number_str = data.replace("delete_", "")
            
            if file_number_str == "all":
                success, message = file_service.delete_all_files(callback_query.from_user.id)
                if success:
                    await callback_query.message.edit_text(f"**{message}**")
                else:
                    await callback_query.message.edit_text(f"**{message}**")
                await callback_query.answer()
                return
            
            try:
                file_number = int(file_number_str)
            except ValueError:
                await callback_query.answer("Número de archivo inválido", show_alert=True)
                return
            
            user_id = callback_query.from_user.id
            
            file_info = file_service.get_file_by_number(user_id, file_number)
            if not file_info:
                await callback_query.answer("Archivo no encontrado", show_alert=True)
                return
            
            confirm_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"confirm_delete_{file_number}"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel_delete")
                ]
            ])
            
            await callback_query.message.edit_text(
                f"**¿Eliminar archivo #{file_number}?**\n\n"
                f"**Archivo:** `{file_info['original_name']}`\n\n"
                f"Esta acción no se puede deshacer.",
                reply_markup=confirm_keyboard
            )
            
        elif data.startswith("confirm_delete_"):
            file_number = int(data.replace("confirm_delete_", ""))
            user_id = callback_query.from_user.id
            
            success, message = file_service.delete_file_by_number(user_id, file_number)
            if success:
                await callback_query.message.edit_text(f"**{message}**")
            else:
                await callback_query.message.edit_text(f"**{message}**")
            
        elif data == "cancel_delete":
            await callback_query.message.edit_text("**Eliminación cancelada.**")
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error eliminando archivo: {e}")
        await callback_query.answer("Error eliminando archivo", show_alert=True)

async def clear_packed_callback(client, callback_query):
    """Maneja el callback para vaciar la carpeta empaquetada"""
    try:
        user_id = callback_query.from_user.id
        
        confirm_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Sí, eliminar todo", callback_data=f"confirm_clear_packed_{user_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_clear")
            ]
        ])
        
        await callback_query.message.edit_text(
            "**¿Eliminar TODOS los archivos empaquetados?**\n\n"
            "Esta acción no se puede deshacer.",
            reply_markup=confirm_keyboard
        )
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error en clear_packed_callback: {e}")
        await callback_query.answer("Error", show_alert=True)

async def confirm_clear_packed_callback(client, callback_query):
    """Maneja la confirmación para vaciar la carpeta empaquetada"""
    try:
        data = callback_query.data.replace("confirm_clear_packed_", "")
        user_id = int(data)
        
        if callback_query.from_user.id != user_id:
            await callback_query.answer("No puedes realizar esta acción", show_alert=True)
            return
        
        success, message = packing_service.clear_packed_folder(user_id)
        
        if success:
            await callback_query.message.edit_text(f"**{message}**")
        else:
            await callback_query.message.edit_text(f"**{message}**")
            
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error en confirm_clear_packed_callback: {e}")
        await callback_query.answer("Error al eliminar archivos", show_alert=True)

async def cancel_clear_callback(client, callback_query):
    """Maneja la cancelación de limpieza"""
    try:
        await callback_query.message.edit_text("**Operación cancelada.**")
        await callback_query.answer("Operación cancelada")
    except Exception as e:
        logger.error(f"Error en cancel_clear_callback: {e}")
