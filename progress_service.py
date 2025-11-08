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

    def create_unified_progress_message(self, filename, current, total, speed=0, file_num=1, total_files=1, user_id=None, process_type="Descargando"):
        """Crea mensaje de progreso unificado estilo File2Link"""
        
        # Barra de progreso (20 caracteres)
        bar_length = 20
        if total > 0:
            filled_length = int(bar_length * current / total)
            bar = '▰' * filled_length + '▱' * (bar_length - filled_length)
            percent = min(100.0, float(current) * 100 / float(total))
        else:
            bar = '▱' * bar_length
            percent = 0
        
        # Tiempo estimado
        if current > 0 and speed > 0 and total > current:
            remaining_bytes = total - current
            eta_seconds = remaining_bytes / speed
            if eta_seconds < 60:
                eta_text = f"{int(eta_seconds)}s"
            elif eta_seconds < 3600:
                eta_text = f"{int(eta_seconds/60)}m {int(eta_seconds%60)}s"
            else:
                eta_text = f"{int(eta_seconds/3600)}h {int((eta_seconds%3600)/60)}m"
        else:
            eta_text = "calculando..."
        
        # Acortar nombre de archivo si es muy largo
        if len(filename) > 30:
            display_filename = filename[:27] + "..."
        else:
            display_filename = filename
        
        # Mensaje con tema File2Link mejorado
        message = f"🔗 **FILE2LINK - {process_type.upper()}**\n\n"
        message += f"`📁 [{bar}] {percent:.1f}%`\n"
        message += f"`📊 Progreso: {file_service.format_bytes(current)} / {file_service.format_bytes(total)}`\n"
        message += f"`📦 Archivos: {file_num}/{total_files} procesados`\n"
        message += f"`⚡ Velocidad: {file_service.format_bytes(speed)}/s`\n"
        message += f"`⏰ Tiempo estimado: ~{eta_text}`\n"
        message += f"`📄 Actual: {display_filename}`"
        
        return message

    def format_time(self, seconds):
        """Formatea segundos a texto legible"""
        if seconds < 60:
            return f"{int(seconds)} segundos"
        elif seconds < 3600:
            return f"{int(seconds/60)} minutos {int(seconds%60)} segundos"
        else:
            hours = int(seconds/3600)
            minutes = int((seconds%3600)/60)
            return f"{hours} horas {minutes} minutos"

progress_service = ProgressService()
