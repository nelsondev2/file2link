import asyncio
import logging
import sys
from pyrogram import Client, filters

from config import API_ID, API_HASH, BOT_TOKEN
from telegram_handlers import (
    start_command, help_command, files_command, status_command,
    pack_command, rename_command, handle_file, delete_file_callback,
    clear_packed_callback, confirm_clear_packed_callback, cancel_clear_callback
)

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.client = None
        self.is_running = False

    async def setup_handlers(self):
        """Configura todos los handlers del bot"""
        # Comandos
        self.client.on_message(filters.command("start") & filters.private)(start_command)
        self.client.on_message(filters.command("help") & filters.private)(help_command)
        self.client.on_message(filters.command("files") & filters.private)(files_command)
        self.client.on_message(filters.command("status") & filters.private)(status_command)
        self.client.on_message(filters.command("pack") & filters.private)(pack_command)
        self.client.on_message(filters.command("rename") & filters.private)(rename_command)
        
        # Archivos
        self.client.on_message(
            (filters.document | filters.video | filters.audio | filters.photo) &
            filters.private
        )(handle_file)
        
        # Callbacks
        self.client.on_callback_query(filters.regex(r"^del_"))(delete_file_callback)
        self.client.on_callback_query(filters.regex(r"^delete_"))(delete_file_callback)
        self.client.on_callback_query(filters.regex(r"^confirm_delete_"))(delete_file_callback)
        self.client.on_callback_query(filters.regex("cancel_delete"))(delete_file_callback)
        self.client.on_callback_query(filters.regex("clear_packed"))(clear_packed_callback)
        self.client.on_callback_query(filters.regex(r"^confirm_clear_packed_"))(confirm_clear_packed_callback)
        self.client.on_callback_query(filters.regex("cancel_clear"))(cancel_clear_callback)

    async def start_bot(self):
        """Inicia el bot de Telegram"""
        try:
            self.client = Client(
                "file_to_link_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN
            )

            await self.setup_handlers()
            
            logger.info("Iniciando cliente de Telegram...")
            await self.client.start()

            bot_info = await self.client.get_me()
            logger.info(f"Bot iniciado: @{bot_info.username}")
            
            logger.info("El bot está listo y respondiendo a comandos")

            self.is_running = True
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"Error crítico en el bot: {e}")
            self.is_running = False

    def run_bot(self):
        """Ejecuta el bot en un loop asyncio"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start_bot())
        except Exception as e:
            logger.error(f"Error en el loop del bot: {e}")
