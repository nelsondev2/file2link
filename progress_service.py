import logging
import sys
from file_service import file_service

logger = logging.getLogger(__name__)

class ProgressService:
    def create_progress_bar(self, current, total, bar_length=15):
        """Crea una barra de progreso visual en una sola línea"""
        if total == 0:
            return "[░░░░░░░░░░░░░░░] 0.0%"
        
        percent = min(100.0, float(current) * 100 / float(total))
        filled_length = int(round(bar_length * current / float(total)))
        
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        return f"[{bar}] {percent:.1f}%"

    def create_progress_message(self, filename, current, total, speed=0, file_num=1, total_files=1, user_id=None, process_type="Descargando"):
        """Crea el mensaje de progreso con el formato profesional"""
        if len(filename) > 25:
            display_name = filename[:22] + "..."
        else:
            display_name = filename
        
        progress_bar = self.create_progress_bar(current, total)
        processed = file_service.format_bytes(current)
        total_size = file_service.format_bytes(total)
        speed_str = file_service.format_bytes(speed) + "/s" if speed > 0 else "0.0 B/s"

        message = f"**📁 {process_type}:** `{display_name}`\n"
        message += f"`{progress_bar}`\n"
        message += f"**📊 Progreso:** {processed} / {total_size}\n"
        message += f"**⚡ Velocidad:** {speed_str}\n"
        message += f"**🔢 Archivo:** {file_num}/{total_files}\n"
        if user_id:
            message += f"**👤 Usuario:** {user_id}"

        return message

progress_service = ProgressService()
