import os
import logging
import time
import asyncio
import concurrent.futures

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import fast_download_service
from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  ESTADO EN MEMORIA POR USUARIO
# ─────────────────────────────────────────────
user_sessions: dict = {}
user_queues: dict = {}
user_current_processing: dict = {}
user_batch_totals: dict = {}


def get_session(user_id: int) -> dict:
    if user_id not in user_sessions:
        user_sessions[user_id] = {"current_folder": "downloads"}
    return user_sessions[user_id]


# ─────────────────────────────────────────────
#  TECLADOS INLINE REUTILIZABLES
# ─────────────────────────────────────────────

def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Descargas", callback_data="cd:downloads"),
            InlineKeyboardButton("📦 Empaquetados", callback_data="cd:packed"),
        ],
        [
            InlineKeyboardButton("📋 Ver archivos", callback_data="list:1"),
            InlineKeyboardButton("📊 Estado", callback_data="status"),
        ],
        [InlineKeyboardButton("❓ Ayuda", callback_data="help")],
    ])


def kb_folder_actions(folder: str) -> InlineKeyboardMarkup:
    other = "packed" if folder == "downloads" else "downloads"
    other_label = "📦 Ir a Empaquetados" if folder == "downloads" else "📥 Ir a Descargas"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Ver archivos", callback_data="list:1"),
            InlineKeyboardButton(other_label, callback_data=f"cd:{other}"),
        ],
        [
            InlineKeyboardButton("🗑️ Vaciar carpeta", callback_data=f"clear_confirm:{folder}"),
            InlineKeyboardButton("📦 Empaquetar", callback_data="pack"),
        ],
        [InlineKeyboardButton("🏠 Menú principal", callback_data="main_menu")],
    ])


def kb_list_nav(page: int, total_pages: int) -> InlineKeyboardMarkup:
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"list:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"list:{page + 1}"))

    bottom = [
        InlineKeyboardButton("🔄 Actualizar", callback_data=f"list:{page}"),
        InlineKeyboardButton("🏠 Menú", callback_data="main_menu"),
    ]
    rows = []
    if nav_row:
        rows.append(nav_row)
    rows.append(bottom)
    return InlineKeyboardMarkup(rows)


def kb_confirm_clear(folder: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, vaciar", callback_data=f"clear_do:{folder}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"cd:{folder}"),
    ]])


def kb_confirm_delete(file_number: int, folder: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"delete_do:{file_number}:{folder}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="list:1"),
    ]])


def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Ver archivos", callback_data="list:1"),
        InlineKeyboardButton("🏠 Menú", callback_data="main_menu"),
    ]])


# ─────────────────────────────────────────────
#  TEXTOS
# ─────────────────────────────────────────────

WELCOME_TEXT = (
    "👋 **¡Hola, {name}!** Bienvenido a **File2Link Bot**.\n\n"
    "Guardo tus archivos y genero enlaces de descarga directa.\n\n"
    "📂 **Carpetas:**\n"
    "• `downloads` — archivos recibidos\n"
    "• `packed` — archivos comprimidos (ZIP)\n\n"
    "📏 **Límite por archivo:** `{limit} MB`\n\n"
    "Elige una opción 👇"
)

HELP_TEXT = (
    "📚 **Guía de uso — File2Link Bot**\n\n"
    "**COMANDOS:**\n"
    "`/start` — Menú principal\n"
    "`/cd downloads` | `/cd packed` — Cambiar carpeta\n"
    "`/list` — Ver archivos de la carpeta activa\n"
    "`/delete <n>` — Eliminar archivo por número\n"
    "`/rename <n> <nombre>` — Renombrar archivo\n"
    "`/clear` — Vaciar carpeta activa\n"
    "`/pack` — Comprimir descargas en ZIP\n"
    "`/pack <MB>` — ZIP dividido en partes\n"
    "`/queue` — Ver cola de descargas\n"
    "`/clearqueue` — Cancelar cola\n"
    "`/status` — Estado del sistema\n\n"
    "**FLUJO TÍPICO:**\n"
    "1️⃣ Envía archivos → se guardan en `downloads`\n"
    "2️⃣ `/list` → copia el enlace de descarga\n"
    "3️⃣ `/pack` → crea un ZIP descargable\n\n"
    f"📏 **Límite por archivo:** `{MAX_FILE_SIZE_MB} MB`"
)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _folder_label(folder: str) -> str:
    return "📥 Descargas" if folder == "downloads" else "📦 Empaquetados"


def _build_list(files: list, folder: str, page: int, total_pages: int) -> str:
    label = _folder_label(folder)
    header = (
        f"**{label}** — Página {page}/{total_pages}\n"
        f"**Total:** {len(files)} archivo(s)\n"
        "─────────────────────────\n\n"
    )
    per_page = 10
    page_files = files[(page - 1) * per_page: page * per_page]
    items = []
    for f in page_files:
        items.append(
            f"**#{f['number']}** `{f['name']}`\n"
            f"   📏 {f['size_mb']:.1f} MB · [⬇️ Descargar]({f['url']})"
        )
    footer = (
        "\n\n─────────────────────────\n"
        "`/delete <n>` · `/rename <n> <nombre>`"
    )
    return header + "\n\n".join(items) + footer


def _split_text(text: str, limit: int = 4096) -> list:
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


# ─────────────────────────────────────────────
#  COMANDOS — HANDLERS DE MENSAJE
# ─────────────────────────────────────────────

async def start_command(client: Client, message: Message):
    user = message.from_user
    await message.reply_text(
        WELCOME_TEXT.format(name=user.first_name, limit=MAX_FILE_SIZE_MB),
        reply_markup=kb_main_menu(),
    )
    logger.info(f"/start — {user.id} ({user.first_name})")


async def help_command(client: Client, message: Message):
    await message.reply_text(HELP_TEXT, reply_markup=kb_back())


async def cd_command(client: Client, message: Message):
    user_id = message.from_user.id
    session = get_session(user_id)
    args = message.text.split()

    if len(args) == 1:
        folder = session["current_folder"]
        await message.reply_text(
            f"📂 Estás en **`{folder}`**. ¿Qué deseas hacer?",
            reply_markup=kb_folder_actions(folder),
        )
        return

    folder = args[1].lower()
    if folder not in ("downloads", "packed"):
        await message.reply_text(
            "❌ **Carpeta inválida.**\n\n"
            "Opciones disponibles:\n"
            "• `downloads` — archivos recibidos\n"
            "• `packed` — archivos comprimidos\n\n"
            "**Ejemplo:** `/cd downloads`",
            reply_markup=kb_main_menu(),
        )
        return

    session["current_folder"] = folder
    count = len(file_service.list_user_files(user_id, folder))
    label = _folder_label(folder)
    await message.reply_text(
        f"📂 Ahora estás en **{label}**.\n"
        f"Tienes **{count}** archivo(s) aquí.",
        reply_markup=kb_folder_actions(folder),
    )


async def list_command(client: Client, message: Message):
    user_id = message.from_user.id
    session = get_session(user_id)
    folder = session["current_folder"]
    args = message.text.split()
    try:
        page = max(1, int(args[1])) if len(args) > 1 else 1
    except ValueError:
        page = 1

    files = file_service.list_user_files(user_id, folder)
    if not files:
        await message.reply_text(
            f"📭 **{_folder_label(folder)}** está vacía.\n\n"
            "Envía archivos al bot para guardarlos.",
            reply_markup=kb_main_menu(),
        )
        return

    per_page = 10
    total_pages = max(1, (len(files) + per_page - 1) // per_page)
    page = min(page, total_pages)
    text = _build_list(files, folder, page, total_pages)

    if len(text) > 4096:
        for i, chunk in enumerate(_split_text(text)):
            kb = kb_list_nav(page, total_pages) if i == len(_split_text(text)) - 1 else None
            await message.reply_text(chunk, reply_markup=kb, disable_web_page_preview=True)
    else:
        await message.reply_text(text, reply_markup=kb_list_nav(page, total_pages),
                                  disable_web_page_preview=True)


async def delete_command(client: Client, message: Message):
    user_id = message.from_user.id
    folder = get_session(user_id)["current_folder"]
    args = message.text.split()

    if len(args) < 2:
        await message.reply_text(
            "❌ **Faltan argumentos.**\n\n"
            "**Uso:** `/delete <número>`\n**Ejemplo:** `/delete 5`\n\n"
            "Usa `/list` para ver los números.",
            reply_markup=kb_back(),
        )
        return

    try:
        num = int(args[1])
    except ValueError:
        await message.reply_text("❌ El número debe ser un entero válido.")
        return

    files = file_service.list_user_files(user_id, folder)
    target = next((f for f in files if f["number"] == num), None)
    if not target:
        await message.reply_text(
            f"❌ No existe el archivo **#{num}** en `{folder}`.",
            reply_markup=kb_back(),
        )
        return

    await message.reply_text(
        f"⚠️ **¿Eliminar este archivo?**\n\n"
        f"**#{target['number']}** — `{target['name']}`\n"
        f"📏 {target['size_mb']:.1f} MB\n\n"
        "Esta acción **no se puede deshacer**.",
        reply_markup=kb_confirm_delete(num, folder),
    )


async def clear_command(client: Client, message: Message):
    user_id = message.from_user.id
    folder = get_session(user_id)["current_folder"]
    count = len(file_service.list_user_files(user_id, folder))

    if count == 0:
        await message.reply_text(
            f"📭 **{_folder_label(folder)}** ya está vacía.",
            reply_markup=kb_main_menu(),
        )
        return

    await message.reply_text(
        f"⚠️ **¿Vaciar {_folder_label(folder)}?**\n\n"
        f"Se eliminarán **{count}** archivo(s) permanentemente.\n"
        "Esta acción **no se puede deshacer**.",
        reply_markup=kb_confirm_clear(folder),
    )


async def rename_command(client: Client, message: Message):
    user_id = message.from_user.id
    folder = get_session(user_id)["current_folder"]
    args = message.text.split(maxsplit=2)

    if len(args) < 3:
        await message.reply_text(
            "❌ **Faltan argumentos.**\n\n"
            "**Uso:** `/rename <número> <nuevo_nombre>`\n"
            "**Ejemplo:** `/rename 3 informe_final`",
            reply_markup=kb_back(),
        )
        return

    try:
        num = int(args[1])
    except ValueError:
        await message.reply_text("❌ El número debe ser un entero válido.")
        return

    new_name = args[2].strip()
    if not new_name:
        await message.reply_text("❌ El nuevo nombre no puede estar vacío.")
        return

    success, msg, new_url = file_service.rename_file(user_id, num, new_name, folder)
    if success:
        await message.reply_text(
            f"✅ **Archivo renombrado.**\n\n"
            f"**Nombre:** `{new_name}`\n"
            f"🔗 [Nuevo enlace]({new_url})",
            reply_markup=kb_back(),
            disable_web_page_preview=True,
        )
    else:
        await message.reply_text(f"❌ {msg}", reply_markup=kb_back())


async def status_command(client: Client, message: Message):
    user_id = message.from_user.id
    session = get_session(user_id)
    text = _build_status_text(user_id, session)
    await message.reply_text(text, reply_markup=kb_main_menu())


async def pack_command(client: Client, message: Message):
    user_id = message.from_user.id
    parts = message.text.split()

    sys_st = load_manager.get_status()
    if not sys_st["can_accept_work"]:
        await message.reply_text(
            "⚠️ **El servidor está sobrecargado.**\n\n"
            f"CPU: `{sys_st['cpu_percent']:.1f}%`  |  "
            f"Procesos: `{sys_st['active_processes']}`\n\n"
            "Inténtalo de nuevo en unos minutos.",
            reply_markup=kb_main_menu(),
        )
        return

    split_size = None
    if len(parts) > 1:
        try:
            split_size = int(parts[1])
            if not (1 <= split_size <= 500):
                await message.reply_text(
                    "❌ El tamaño de cada parte debe estar entre **1 y 500 MB**.\n"
                    "**Ejemplo:** `/pack 100`"
                )
                return
        except ValueError:
            await message.reply_text(
                "❌ Valor no válido.\n**Uso:** `/pack` o `/pack <MB>`"
            )
            return

    status_msg = await message.reply_text(
        "⏳ **Empaquetando…**\n"
        f"{'Dividiendo en partes de ' + str(split_size) + ' MB…' if split_size else 'Creando archivo ZIP…'}"
    )

    def _do_pack():
        try:
            return packing_service.pack_folder(user_id, split_size)
        except Exception as e:
            return None, str(e)

    try:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            files, err_msg = ex.submit(_do_pack).result(timeout=300)
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text(
            "❌ **Tiempo de espera agotado.**\n\n"
            "El empaquetado tardó demasiado. Intenta con menos archivos."
        )
        return

    if not files:
        await status_msg.edit_text(f"❌ {err_msg}")
        return

    total_mb = sum(f["size_mb"] for f in files)
    orig_label = f" ({files[0]['total_files']} archivos originales)" \
        if files and files[0].get("total_files") else ""

    if len(files) == 1:
        f = files[0]
        await status_msg.edit_text(
            f"✅ **Empaquetado completado{orig_label}**\n\n"
            f"**Archivo:** `{f['filename']}`\n"
            f"**Tamaño:** {f['size_mb']:.1f} MB\n\n"
            f"🔗 [{f['filename']}]({f['url']})\n\n"
            "Usa `/cd packed` → `/list` para ver todos tus empaquetados.",
            disable_web_page_preview=True,
        )
    else:
        user_dir = file_service.get_user_directory(user_id, "packed")
        base = next((f["filename"].rsplit(".", 2)[0] for f in files if ".001" in f["filename"]), None)
        list_url = None
        if base:
            txt = f"{base}.txt"
            if os.path.exists(os.path.join(user_dir, txt)):
                list_url = file_service.create_packed_url(user_id, txt)

        header = (
            f"✅ **Empaquetado completado{orig_label}**\n\n"
            f"**Partes:** {len(files)}  |  **Total:** {total_mb:.1f} MB\n\n"
            "**🔗 Enlaces de descarga:**"
        )
        if list_url:
            header += f"\n📑 [Lista de partes]({list_url})"

        full = header + "".join(f"\n\n**{f['filename']}**\n{f['url']}" for f in files)
        full += "\n\nUsa `/cd packed` → `/list` para ver todos tus empaquetados."

        if len(full) > 4096:
            await status_msg.edit_text(
                f"✅ **{len(files)} partes generadas — {total_mb:.1f} MB total**"
                + (f"\n📑 [Lista de partes]({list_url})" if list_url else ""),
                disable_web_page_preview=True,
            )
            for i in range(0, len(files), 10):
                chunk = "\n\n".join(
                    f"**{f['filename']}**\n{f['url']}" for f in files[i:i + 10]
                )
                await message.reply_text(chunk, disable_web_page_preview=True)
            await message.reply_text(f"✅ **Total: {len(files)} partes generadas.**", reply_markup=kb_back())
        else:
            await status_msg.edit_text(full, disable_web_page_preview=True)

    logger.info(f"Pack completado para {user_id}: {len(files)} parte(s)")


async def queue_command(client: Client, message: Message):
    user_id = message.from_user.id
    queue = user_queues.get(user_id, [])

    if not queue:
        await message.reply_text("📭 **Cola vacía.** No hay archivos pendientes.", reply_markup=kb_main_menu())
        return

    lines = []
    for i, msg in enumerate(queue, 1):
        if msg.document:
            label = f"📄 {msg.document.file_name or 'documento'}"
        elif msg.video:
            label = f"🎥 {msg.video.file_name or 'video'}"
        elif msg.audio:
            label = f"🎵 {msg.audio.file_name or 'audio'}"
        elif msg.photo:
            label = "🖼️ Foto"
        else:
            label = "📎 Archivo"
        lines.append(f"**#{i}** — {label}")

    processing = user_id in user_current_processing
    await message.reply_text(
        f"📋 **Cola — {len(queue)} archivo(s)**\n\n"
        + "\n".join(lines)
        + f"\n\n{'⚙️ Procesando el primero ahora mismo…' if processing else '⏸️ En espera.'}",
        reply_markup=kb_main_menu(),
    )


async def clear_queue_command(client: Client, message: Message):
    user_id = message.from_user.id
    queue = user_queues.get(user_id, [])

    if not queue:
        await message.reply_text("📭 La cola ya está vacía.", reply_markup=kb_main_menu())
        return

    count = len(queue)
    user_queues[user_id] = []
    user_current_processing.pop(user_id, None)
    user_batch_totals.pop(user_id, None)
    await message.reply_text(
        f"🗑️ **Cola limpiada.** Se cancelaron **{count}** archivo(s).",
        reply_markup=kb_main_menu(),
    )


async def cleanup_command(client: Client, message: Message):
    status_msg = await message.reply_text("🧹 **Analizando almacenamiento…**")
    try:
        size_mb = file_service.get_user_storage_usage(message.from_user.id) / (1024 * 1024)
        await status_msg.edit_text(
            f"✅ **Análisis completado.**\n\n"
            f"• Espacio ocupado: **{size_mb:.2f} MB**\n"
            f"• Sistema: operativo"
        )
    except Exception as e:
        logger.error(f"Error en /cleanup: {e}")
        await status_msg.edit_text("❌ Error durante el análisis.")


# ─────────────────────────────────────────────
#  CALLBACKS DE BOTONES INLINE
# ─────────────────────────────────────────────

async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    session = get_session(user_id)

    try:
        if data == "main_menu":
            await query.message.edit_text(
                WELCOME_TEXT.format(name=query.from_user.first_name, limit=MAX_FILE_SIZE_MB),
                reply_markup=kb_main_menu(),
            )

        elif data == "help":
            await query.message.edit_text(HELP_TEXT, reply_markup=kb_back())

        elif data.startswith("cd:"):
            folder = data[3:]
            session["current_folder"] = folder
            count = len(file_service.list_user_files(user_id, folder))
            await query.message.edit_text(
                f"📂 Ahora estás en **{_folder_label(folder)}**.\n"
                f"Tienes **{count}** archivo(s) aquí.",
                reply_markup=kb_folder_actions(folder),
            )

        elif data.startswith("list:"):
            page = int(data[5:])
            folder = session["current_folder"]
            files = file_service.list_user_files(user_id, folder)

            if not files:
                await query.message.edit_text(
                    f"📭 **{_folder_label(folder)}** está vacía.",
                    reply_markup=kb_main_menu(),
                )
                await query.answer()
                return

            per_page = 10
            total_pages = max(1, (len(files) + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            text = _build_list(files, folder, page, total_pages)
            await query.message.edit_text(
                text,
                reply_markup=kb_list_nav(page, total_pages),
                disable_web_page_preview=True,
            )

        elif data == "status":
            await query.message.edit_text(
                _build_status_text(user_id, session),
                reply_markup=kb_main_menu(),
            )

        elif data.startswith("clear_confirm:"):
            folder = data[14:]
            count = len(file_service.list_user_files(user_id, folder))
            if count == 0:
                await query.message.edit_text(
                    f"📭 **{_folder_label(folder)}** ya está vacía.",
                    reply_markup=kb_main_menu(),
                )
            else:
                await query.message.edit_text(
                    f"⚠️ **¿Vaciar {_folder_label(folder)}?**\n\n"
                    f"Se eliminarán **{count}** archivo(s) de forma permanente.\n"
                    "Esta acción **no se puede deshacer**.",
                    reply_markup=kb_confirm_clear(folder),
                )

        elif data.startswith("clear_do:"):
            folder = data[9:]
            success, msg = file_service.delete_all_files(user_id, folder)
            icon = "✅" if success else "❌"
            await query.message.edit_text(
                f"{icon} {msg}",
                reply_markup=kb_folder_actions(folder),
            )

        elif data.startswith("delete_do:"):
            _, num_str, folder = data.split(":", 2)
            success, msg = file_service.delete_file_by_number(user_id, int(num_str), folder)
            icon = "✅" if success else "❌"
            await query.message.edit_text(f"{icon} {msg}", reply_markup=kb_back())

        elif data == "pack":
            sys_st = load_manager.get_status()
            if not sys_st["can_accept_work"]:
                await query.answer("⚠️ Servidor sobrecargado. Intenta más tarde.", show_alert=True)
                return
            await query.answer("⏳ Iniciando empaquetado…")
            await query.message.reply_text("⏳ **Empaquetando…** Creando archivo ZIP…")
            asyncio.create_task(_pack_task(query.message, user_id))
            return

        else:
            await query.answer("Acción no reconocida.", show_alert=True)
            return

        await query.answer()

    except Exception as e:
        logger.error(f"Error callback '{data}': {e}", exc_info=True)
        try:
            await query.answer("❌ Ocurrió un error. Intenta de nuevo.", show_alert=True)
        except Exception:
            pass


async def _pack_task(reply_to: Message, user_id: int):
    def _do():
        try:
            return packing_service.pack_folder(user_id, None)
        except Exception as e:
            return None, str(e)

    with concurrent.futures.ThreadPoolExecutor() as ex:
        files, err = ex.submit(_do).result(timeout=300)

    if not files:
        await reply_to.reply_text(f"❌ {err}")
        return

    if len(files) == 1:
        f = files[0]
        await reply_to.reply_text(
            f"✅ **Empaquetado completado.**\n\n"
            f"**Archivo:** `{f['filename']}`\n"
            f"**Tamaño:** {f['size_mb']:.1f} MB\n\n"
            f"🔗 [{f['filename']}]({f['url']})",
            disable_web_page_preview=True,
        )
    else:
        total_mb = sum(f["size_mb"] for f in files)
        lines = "\n".join(f"🔗 [{f['filename']}]({f['url']})" for f in files)
        await reply_to.reply_text(
            f"✅ **{len(files)} partes — {total_mb:.1f} MB total**\n\n{lines}",
            disable_web_page_preview=True,
        )


def _build_status_text(user_id: int, session: dict) -> str:
    dl = len(file_service.list_user_files(user_id, "downloads"))
    pk = len(file_service.list_user_files(user_id, "packed"))
    mb = file_service.get_user_storage_usage(user_id) / (1024 * 1024)
    s = load_manager.get_status()
    icon = "🟢" if s["can_accept_work"] else "🔴"
    return (
        f"📊 **Estado del sistema**\n\n"
        f"**👤 Tu cuenta:**\n"
        f"  • ID: `{user_id}`\n"
        f"  • Carpeta activa: `{session['current_folder']}`\n"
        f"  • Archivos downloads: **{dl}**\n"
        f"  • Archivos packed: **{pk}**\n"
        f"  • Espacio usado: **{mb:.2f} MB**\n\n"
        f"**🖥️ Servidor:**\n"
        f"  • CPU: **{s['cpu_percent']:.1f}%**\n"
        f"  • Memoria: **{s['memory_percent']:.1f}%**\n"
        f"  • Procesos: **{s['active_processes']}/{s['max_processes']}**\n"
        f"  • Estado: {icon} {'Operativo' if s['can_accept_work'] else 'Sobrecargado'}"
    )


# ─────────────────────────────────────────────
#  RECEPCIÓN DE ARCHIVOS
# ─────────────────────────────────────────────

async def handle_file(client: Client, message: Message):
    user_id = message.from_user.id

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
            f"❌ **Archivo demasiado grande.**\n\n"
            f"• Tu archivo: **{file_service.format_bytes(file_size)}**\n"
            f"• Límite permitido: **{MAX_FILE_SIZE_MB} MB**\n\n"
            "Divide el archivo en partes más pequeñas e inténtalo de nuevo."
        )
        return

    if user_id not in user_queues:
        user_queues[user_id] = []

    user_queues[user_id].append(message)
    pos = len(user_queues[user_id])

    if pos == 1:
        await process_file_queue(client, user_id)
    else:
        await message.reply_text(
            f"📬 **Añadido a la cola.**\n"
            f"Posición: **#{pos}** — espera tu turno…"
        )


async def process_file_queue(client: Client, user_id: int):
    total = len(user_queues[user_id])
    user_batch_totals[user_id] = total
    pos = 0
    try:
        while user_queues.get(user_id):
            msg = user_queues[user_id][0]
            pos += 1
            await process_single_file(client, msg, user_id, pos, total)
            await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Error cola {user_id}: {e}", exc_info=True)
        user_queues[user_id] = []
    finally:
        user_batch_totals.pop(user_id, None)


async def process_single_file(client, message, user_id, position, total):
    start = time.time()
    try:
        if message.document:
            file_obj = message.document
            file_type, orig_name = "Documento", message.document.file_name or "archivo"
            file_size = file_obj.file_size or 0
        elif message.video:
            file_obj = message.video
            file_type, orig_name = "Video", message.video.file_name or "video.mp4"
            file_size = file_obj.file_size or 0
        elif message.audio:
            file_obj = message.audio
            file_type, orig_name = "Audio", message.audio.file_name or "audio.mp3"
            file_size = file_obj.file_size or 0
        elif message.photo:
            file_obj = message.photo[-1]
            file_type, orig_name = "Foto", f"foto_{message.id}.jpg"
            file_size = file_obj.file_size or 0
        else:
            user_queues[user_id].pop(0)
            return

        user_dir = file_service.get_user_directory(user_id, "downloads")
        sanitized = file_service.sanitize_filename(orig_name)
        stored = sanitized
        path = os.path.join(user_dir, stored)
        base, ext = os.path.splitext(sanitized)
        c = 1
        while os.path.exists(path):
            stored = f"{base}_{c}{ext}"
            path = os.path.join(user_dir, stored)
            c += 1

        file_number = file_service.register_file(user_id, orig_name, stored, "downloads")

        prog_msg = await message.reply_text(
            progress_service.create_progress_message(
                filename=orig_name, current=0, total=file_size, speed=0,
                user_first_name=message.from_user.first_name,
                process_type="Descargando", current_file=position, total_files=total,
            )
        )
        user_current_processing[user_id] = prog_msg.id

        pdata = {"last_update": 0.0, "last_speed": 0.0}

        async def on_progress(current, total_bytes):
            try:
                elapsed = time.time() - start
                speed = current / elapsed if elapsed > 0 else 0
                pdata["last_speed"] = 0.7 * pdata["last_speed"] + 0.3 * speed
                now = time.time()
                if now - pdata["last_update"] >= 0.6 or current == total_bytes:
                    txt = progress_service.create_progress_message(
                        filename=orig_name, current=current, total=total_bytes,
                        speed=pdata["last_speed"], user_first_name=message.from_user.first_name,
                        process_type="Descargando", current_file=position, total_files=total,
                    )
                    try:
                        await prog_msg.edit_text(txt)
                        pdata["last_update"] = now
                    except Exception:
                        pass
            except Exception:
                pass

        success, _ = await fast_download_service.download_with_retry(
            client=client, message=message, file_path=path, progress_callback=on_progress,
        )

        if not success or not os.path.exists(path):
            await prog_msg.edit_text(
                "❌ **Error al descargar el archivo.**\n\n"
                "El archivo no se guardó. Inténtalo de nuevo."
            )
            user_queues[user_id].pop(0)
            return

        final_size = os.path.getsize(path)
        if file_size > 0 and final_size < file_size * 0.95:
            logger.warning(f"Descarga posiblemente incompleta: {file_size}B → {final_size}B")

        size_mb = final_size / (1024 * 1024)
        url = file_service.create_download_url(user_id, stored)
        files_list = file_service.list_user_files(user_id, "downloads")
        final_num = next(
            (f["number"] for f in files_list if f["stored_name"] == stored), file_number
        )

        remaining = len(user_queues[user_id]) - 1
        queue_note = f"\n\n⏭️ Procesando siguiente… ({remaining} en cola)" if remaining > 0 else ""

        await prog_msg.edit_text(
            f"✅ **Archivo guardado — #{final_num}**\n\n"
            f"**Nombre:** `{orig_name}`\n"
            f"**Tipo:** {file_type}  ·  **Tamaño:** {size_mb:.2f} MB\n\n"
            f"🔗 [{orig_name}]({url})\n"
            f"📂 Carpeta: `downloads`{queue_note}",
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Error procesando archivo de {user_id}: {e}", exc_info=True)
        try:
            await message.reply_text(
                "❌ **Error inesperado al procesar el archivo.**\n\n"
                "Si el problema persiste, contacta al administrador."
            )
        except Exception:
            pass
    finally:
        if user_queues.get(user_id):
            user_queues[user_id].pop(0)
        user_current_processing.pop(user_id, None)


# ─────────────────────────────────────────────
#  REGISTRO DE HANDLERS
# ─────────────────────────────────────────────

def setup_handlers(client: Client):
    client.on_message(filters.command("start")      & filters.private)(start_command)
    client.on_message(filters.command("help")       & filters.private)(help_command)
    client.on_message(filters.command("status")     & filters.private)(status_command)
    client.on_message(filters.command("cd")         & filters.private)(cd_command)
    client.on_message(filters.command("list")       & filters.private)(list_command)
    client.on_message(filters.command("delete")     & filters.private)(delete_command)
    client.on_message(filters.command("clear")      & filters.private)(clear_command)
    client.on_message(filters.command("rename")     & filters.private)(rename_command)
    client.on_message(filters.command("pack")       & filters.private)(pack_command)
    client.on_message(filters.command("queue")      & filters.private)(queue_command)
    client.on_message(filters.command("clearqueue") & filters.private)(clear_queue_command)
    client.on_message(filters.command("cleanup")    & filters.private)(cleanup_command)

    client.on_callback_query()(callback_handler)

    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) & filters.private
    )(handle_file)
