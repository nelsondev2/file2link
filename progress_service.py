import logging
import sys
import time
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

    def calculate_eta(self, current, total, speed, elapsed_time):
        """Calcula el tiempo estimado de finalización"""
        if speed <= 0 or current <= 0:
            return "Calculando..."
        
        remaining_bytes = total - current
        eta_seconds = remaining_bytes / speed
        
        if eta_seconds < 60:
            return f"{int(eta_seconds)}s"
        elif eta_seconds < 3600:
            return f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
        else:
            hours = int(eta_seconds // 3600)
            minutes = int((eta_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def format_elapsed_time(self, seconds):
        """Formatea el tiempo transcurrido"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def create_progress_message(self, filename, current, total, speed=0, elapsed_time=0, user_first_name=None, process_type="Descargando"):
        """Crea el mensaje de progreso con ETA y nombre de usuario"""
        if len(filename) > 25:
            display_name = filename[:22] + "..."
        else:
            display_name = filename
        
        progress_bar = self.create_progress_bar(current, total)
        processed = file_service.format_bytes(current)
        total_size = file_service.format_bytes(total)
        speed_str = file_service.format_bytes(speed) + "/s" if speed > 0 else "0.0 B/s"
        
        # Calcular ETA
        eta = self.calculate_eta(current, total, speed, elapsed_time)
        elapsed_str = self.format_elapsed_time(elapsed_time)

        message = f"**📁 {process_type}:** `{display_name}`\n"
        message += f"`{progress_bar}`\n"
        message += f"**📊 Progreso:** {processed} / {total_size}\n"
        message += f"**⚡ Velocidad:** {speed_str}\n"
        message += f"**⏱️ Tiempo Transcurrido:** {elapsed_str}\n"
        message += f"**🕐 ETA:** {eta}\n"
        if user_first_name:
            message += f"**👤 Usuario:** {user_first_name}"

        return message

progress_service = ProgressService()
