import asyncio
import logging
import sys
from pyrogram import Client, filters

from config import API_ID, API_HASH, BOT_TOKEN
from telegram_handlers import (
    start_command, help_command, status_command,
    cd_command, list_command, delete_command, clear_command, rename_command,
    pack_command, yt_command, handle_file, setup_handlers
)

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.client = None
        self.is_running = False

    async def setup_handlers(self):
        """Configura todos los handlers del bot (sin callbacks)"""
        # Comandos básicos
        self.client.on_message(filters.command("start") & filters.private)(start_command)
        self.client.on_message(filters.command("help") & filters.private)(help_command)
        self.client.on_message(filters.command("status") & filters.private)(status_command)
        
        # Sistema de carpetas
        self.client.on_message(filters.command("cd") & filters.private)(cd_command)
        self.client.on_message(filters.command("list") & filters.private)(list_command)
        self.client.on_message(filters.command("delete") & filters.private)(delete_command)
        self.client.on_message(filters.command("clear") & filters.private)(clear_command)
        self.client.on_message(filters.command("rename") & filters.private)(rename_command)
        
        # Empaquetado
        self.client.on_message(filters.command("pack") & filters.private)(pack_command)
        
        # YouTube
        self.client.on_message(filters.command("yt") & filters.private)(yt_command)
        
        # Archivos (sin botones)
        self.client.on_message(
            (filters.document | filters.video | filters.audio | filters.photo) &
            filters.private
        )(handle_file)

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
