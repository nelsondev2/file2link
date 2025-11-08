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
        processed = self.format_bytes(current)
        total_size = self.format_bytes(total)
        speed_str = self.format_bytes(speed) + "/s" if speed > 0 else "0.0 B/s"

        message = f"**📁 {process_type}:** `{display_name}`\n"
        message += f"`{progress_bar}`\n"
        message += f"**📊 Progreso:** {processed} / {total_size}\n"
        message += f"**⚡ Velocidad:** {speed_str}\n"
        message += f"**🔢 Archivo:** {file_num}/{total_files}\n"
        if user_id:
            message += f"**👤 Usuario:** {user_id}"

        return message

    def create_unified_progress_message(self, filename, current, total, speed=0, file_num=1, total_files=1, user_id=None, process_type="Descargando"):
        """Crea mensaje de progreso unificado estilo File2Link MEJORADO"""
        
        # Barra de progreso (20 caracteres) - EN UNA SOLA LÍNEA
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
        if len(filename) > 25:
            display_filename = filename[:22] + "..."
        else:
            display_filename = filename
        
        # Mensaje con tema File2Link mejorado - BARRA EN UNA LÍNEA
        message = f"🔗 **FILE2LINK - {process_type.upper()}**\n\n"
        message += f"`📁 {bar} {percent:.1f}%`\n"  # BARRA Y PORCENTAJE EN MISMA LÍNEA
        message += f"`📊 Progreso: {self.format_bytes(current)} / {self.format_bytes(total)}`\n"
        message += f"`📦 Archivos: {file_num}/{total_files}`\n"
        message += f"`⚡ Velocidad: {self.format_bytes(speed)}/s`\n"
        message += f"`⏰ Tiempo estimado: ~{eta_text}`\n"
        message += f"`📄 Actual: {display_filename}`"
        
        return message

    def create_individual_progress_message(self, filename, current, total, speed=0, file_num=1, total_files=1, eta_text="calculando..."):
        """Crea mensaje de progreso individual para un archivo específico"""
        
        # Barra de progreso (20 caracteres)
        bar_length = 20
        if total > 0:
            filled_length = int(bar_length * current / total)
            bar = '▰' * filled_length + '▱' * (bar_length - filled_length)
            percent = min(100.0, float(current) * 100 / float(total))
        else:
            bar = '▱' * bar_length
            percent = 0
        
        # Acortar nombre de archivo si es muy largo
        if len(filename) > 25:
            display_filename = filename[:22] + "..."
        else:
            display_filename = filename
        
        # Mensaje de progreso individual
        message = f"🔗 **FILE2LINK - DESCARGANDO**\n\n"
        message += f"`📁 {bar} {percent:.1f}%`\n"
        message += f"`📊 Progreso: {self.format_bytes(current)} / {self.format_bytes(total)}`\n"
        message += f"`📦 Archivo: {file_num}/{total_files}`\n"
        message += f"`⚡ Velocidad: {self.format_bytes(speed)}/s`\n"
        message += f"`⏰ Tiempo estimado: ~{eta_text}`\n"
        message += f"`📄 Archivo: {display_filename}`"
        
        return message

    def create_success_message(self, filename, file_number, size_mb, download_url, file_num=1, total_files=1):
        """Crea mensaje de éxito para un archivo completado"""
        
        message = f"**✅ Archivo {file_num}/{total_files} Completado**\n\n"
        message += f"**Archivo #{file_number}:** `{filename}`\n"
        message += f"**Tamaño:** {size_mb:.2f} MB\n"
        message += f"**Enlace:** 📎 [{filename}]({download_url})"
        
        if file_num < total_files:
            message += f"\n\n**⏳ Preparando siguiente archivo...**"
        
        return message

    def create_batch_complete_message(self, total_files_processed, last_filename, last_file_number, last_size_mb, last_download_url):
        """Crea mensaje de finalización de lote de archivos"""
        
        message = f"**🎉 Subida Completa - {total_files_processed} Archivos**\n\n"
        message += f"**Último archivo procesado:**\n"
        message += f"`#{last_file_number}` - `{last_filename}`\n"
        message += f"**Tamaño:** {last_size_mb:.2f} MB\n"
        message += f"**Enlace:** 📎 [{last_filename}]({last_download_url})\n\n"
        message += f"**Usa `/list` para ver todos tus archivos.**"
        
        return message

    def format_bytes(self, size):
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def format_time(self, seconds):
        """Formatea segundos a texto legible"""
        if seconds < 60:
            return f"{int(seconds)} segundos"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes} minutos {secs} segundos"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours} horas {minutes} minutos"

    def calculate_eta(self, current, total, speed):
        """Calcula el tiempo estimado de finalización"""
        if current <= 0 or speed <= 0 or total <= current:
            return "calculando..."
        
        remaining_bytes = total - current
        eta_seconds = remaining_bytes / speed
        
        if eta_seconds < 60:
            return f"{int(eta_seconds)}s"
        elif eta_seconds < 3600:
            minutes = int(eta_seconds / 60)
            seconds = int(eta_seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(eta_seconds / 3600)
            minutes = int((eta_seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def create_upload_progress_message(self, filename, current, total, speed=0, file_num=1, total_files=1):
        """Crea mensaje de progreso para subida de archivos"""
        
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
        eta_text = self.calculate_eta(current, total, speed)
        
        # Acortar nombre de archivo si es muy largo
        if len(filename) > 25:
            display_filename = filename[:22] + "..."
        else:
            display_filename = filename
        
        # Mensaje de progreso para subida
        message = f"🔗 **FILE2LINK - SUBIENDO**\n\n"
        message += f"`📁 {bar} {percent:.1f}%`\n"
        message += f"`📊 Progreso: {self.format_bytes(current)} / {self.format_bytes(total)}`\n"
        message += f"`📦 Archivo: {file_num}/{total_files}`\n"
        message += f"`⚡ Velocidad: {self.format_bytes(speed)}/s`\n"
        message += f"`⏰ Tiempo estimado: ~{eta_text}`\n"
        message += f"`📄 Archivo: {display_filename}`"
        
        return message

    def create_packing_progress_message(self, current_files, total_files, current_size, total_size, speed=0):
        """Crea mensaje de progreso para empaquetado"""
        
        # Barra de progreso (15 caracteres para empaquetado)
        bar_length = 15
        if total_files > 0:
            filled_length = int(bar_length * current_files / total_files)
            bar = '▰' * filled_length + '▱' * (bar_length - filled_length)
            percent = min(100.0, float(current_files) * 100 / float(total_files))
        else:
            bar = '▱' * bar_length
            percent = 0
        
        # Tiempo estimado
        if current_files > 0 and speed > 0 and total_files > current_files:
            remaining_files = total_files - current_files
            # Estimación simple basada en archivos por segundo
            eta_seconds = remaining_files / (current_files / (time.time() - getattr(self, 'pack_start_time', time.time())))
            if eta_seconds < 60:
                eta_text = f"{int(eta_seconds)}s"
            else:
                eta_text = f"{int(eta_seconds/60)}m {int(eta_seconds%60)}s"
        else:
            eta_text = "calculando..."
        
        message = f"📦 **FILE2LINK - EMPAQUETANDO**\n\n"
        message += f"`📊 {bar} {percent:.1f}%`\n"
        message += f"`📁 Archivos: {current_files}/{total_files} procesados`\n"
        message += f"`💾 Tamaño: {self.format_bytes(current_size)} / {self.format_bytes(total_size)}`\n"
        if speed > 0:
            message += f"`⚡ Velocidad: {self.format_bytes(speed)}/s`\n"
        message += f"`⏰ Tiempo estimado: ~{eta_text}`"
        
        return message

progress_service = ProgressService()
