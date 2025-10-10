import os
import logging
import threading
import time
import asyncio
from flask import Flask, send_from_directory, jsonify
from waitress import serve
import sys
import urllib.parse
import hashlib
import concurrent.futures
import zipfile
import json
import shutil
import subprocess
import psutil
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

# ===== CONFIGURACIÓN OPTIMIZADA =====
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "tu_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_bot_token")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://nelson-file2link.onrender.com")
BASE_DIR = "static"
PORT = int(os.getenv("PORT", 8080))

# Configuración optimizada para CPU limitada
MAX_PART_SIZE_MB = 100
COMPRESSION_TIMEOUT = 600
MAX_CONCURRENT_PROCESSES = 1
CPU_USAGE_LIMIT = 80

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ===== SISTEMA DE GESTIÓN DE CARGA =====
class LoadManager:
    def __init__(self):
        self.active_processes = 0
        self.max_processes = MAX_CONCURRENT_PROCESSES
        self.lock = threading.Lock()
    
    def can_start_process(self):
        """Verifica si se puede iniciar un nuevo proceso pesado"""
        with self.lock:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
            except:
                cpu_percent = 0
            
            if cpu_percent > CPU_USAGE_LIMIT:
                return False, f"CPU sobrecargada ({cpu_percent:.1f}%). Espera un momento."
            
            if self.active_processes >= self.max_processes:
                return False, "Ya hay un proceso en ejecución. Espera a que termine."
            
            self.active_processes += 1
            return True, f"Proceso iniciado (CPU: {cpu_percent:.1f}%)"
    
    def finish_process(self):
        """Marca un proceso como terminado"""
        with self.lock:
            self.active_processes = max(0, self.active_processes - 1)
    
    def get_status(self):
        """Obtiene estado actual del sistema"""
        with self.lock:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
            except:
                cpu_percent = 0
                memory_percent = 0
            
            return {
                'active_processes': self.active_processes,
                'max_processes': self.max_processes,
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'can_accept_work': self.active_processes < self.max_processes and cpu_percent < CPU_USAGE_LIMIT
            }

# Instancia global del gestor de carga
load_manager = LoadManager()

# ===== FLASK APP =====
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nelson File2Link - Servidor de Archivos</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            
            .header {
                text-align: center;
                margin-bottom: 40px;
                padding: 40px 20px;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                backdrop-filter: blur(10px);
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                color: #2c3e50;
            }
            
            .header p {
                font-size: 1.2rem;
                color: #7f8c8d;
                margin-bottom: 20px;
            }
            
            .status-badge {
                display: inline-block;
                background: #27ae60;
                color: white;
                padding: 8px 20px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 0.9rem;
            }
            
            .btn {
                display: inline-block;
                background: #3498db;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 25px;
                margin: 10px;
                font-size: 1rem;
                transition: all 0.3s ease;
                border: none;
                cursor: pointer;
            }
            
            .btn:hover {
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }
            
            .btn-telegram {
                background: #0088cc;
            }
            
            .btn-telegram:hover {
                background: #0077b5;
            }
            
            .info-section {
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 15px;
                margin-bottom: 20px;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            }
            
            .info-section h3 {
                color: #2c3e50;
                margin-bottom: 15px;
                font-size: 1.4rem;
            }
            
            .info-section p {
                line-height: 1.6;
                margin-bottom: 10px;
                color: #5d6d7e;
            }
            
            .code {
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                margin: 10px 0;
                overflow-x: auto;
            }
            
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }
            
            .feature-card {
                background: rgba(255, 255, 255, 0.95);
                padding: 25px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
                transition: transform 0.3s ease;
            }
            
            .feature-card:hover {
                transform: translateY(-5px);
            }
            
            .feature-icon {
                font-size: 2.5rem;
                margin-bottom: 15px;
            }
            
            .feature-card h4 {
                color: #2c3e50;
                margin-bottom: 10px;
                font-size: 1.2rem;
            }
            
            @media (max-width: 768px) {
                .header h1 {
                    font-size: 2rem;
                }
                
                .features {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Nelson File2Link</h1>
                <div class="status-badge">✅ ACTIVO Y FUNCIONANDO</div>
                <p>Servidor profesional de archivos via Telegram</p>
                
                <a href="https://t.me/nelson_file2link_bot" class="btn btn-telegram">🚀 Usar el Bot en Telegram</a>
            </div>

            <div class="features">
                <div class="feature-card">
                    <div class="feature-icon">📁</div>
                    <h4>Almacenamiento Seguro</h4>
                    <p>Tus archivos almacenados de forma segura con enlaces permanentes</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">📦</div>
                    <h4>Empaquetado Simple</h4>
                    <p>Une todos tus archivos en un ZIP sin compresión</p>
                </div>
            </div>

            <div class="info-section">
                <h3>📁 ¿Cómo funciona?</h3>
                <p>1. Envía cualquier archivo al bot de Telegram</p>
                <p>2. El archivo se guarda en tu carpeta personal segura</p>
                <p>3. Obtienes un enlace web permanente para compartir</p>
                <p>4. Gestiona tus archivos fácilmente desde cualquier dispositivo</p>

                <h3>🔗 Ejemplo de enlace:</h3>
                <div class="code">https://nelson-file2link.onrender.com/static/123456/download/mi_archivo.pdf</div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "online",
        "service": "nelson-file2link",
        "bot_status": "running",
        "timestamp": time.time()
    })

@app.route('/system-status')
def system_status():
    """Endpoint para verificar el estado del sistema"""
    status = load_manager.get_status()
    return jsonify({
        "status": "online",
        "service": "nelson-file2link-optimized",
        "system_load": status,
        "timestamp": time.time(),
        "optimized_for": "low-cpu-environment",
        "max_concurrent_processes": MAX_CONCURRENT_PROCESSES
    })

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(BASE_DIR, path)

@app.route('/static/<user_id>/download/<filename>')
def serve_download(user_id, filename):
    """Sirve archivos de descarga con nombre original"""
    user_download_dir = os.path.join(BASE_DIR, user_id, "download")
    return send_from_directory(user_download_dir, filename)

@app.route('/static/<user_id>/packed/<filename>')
def serve_packed(user_id, filename):
    """Sirve archivos empaquetados"""
    user_packed_dir = os.path.join(BASE_DIR, user_id, "packed")
    return send_from_directory(user_packed_dir, filename)

# ===== UTILIDADES DE ARCHIVOS MEJORADAS =====
class FileService:
    def __init__(self):
        self.file_mappings = {}
        self.metadata_file = "file_metadata.json"
        self.load_metadata()
    
    def load_metadata(self):
        """Carga la metadata de archivos desde JSON"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}
        except Exception as e:
            logger.error(f"Error cargando metadata: {e}")
            self.metadata = {}
    
    def save_metadata(self):
        """Guarda la metadata de archivos en JSON"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
    
    def get_next_file_number(self, user_id, file_type="download"):
        """Obtiene el siguiente número de archivo para el usuario"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        next_num = self.metadata[user_key]["next_number"]
        self.metadata[user_key]["next_number"] += 1
        self.save_metadata()
        return next_num
    
    def sanitize_filename(self, filename):
        """Limpia el nombre de archivo para que sea URL-safe"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100-len(ext)] + ext
        return filename

    def format_bytes(self, size):
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def create_download_url(self, user_id, filename):
        """Crea una URL de descarga válida"""
        safe_filename = self.sanitize_filename(filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        return f"{RENDER_DOMAIN}/static/{user_id}/download/{encoded_filename}"

    def create_packed_url(self, user_id, filename):
        """Crea una URL para archivos empaquetados"""
        safe_filename = self.sanitize_filename(filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        return f"{RENDER_DOMAIN}/static/{user_id}/packed/{encoded_filename}"

    def get_user_directory(self, user_id):
        """Obtiene el directorio del usuario"""
        user_dir = os.path.join(BASE_DIR, str(user_id), "download")
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def get_user_storage_usage(self, user_id):
        """Calcula el uso de almacenamiento por usuario"""
        user_dir = self.get_user_directory(user_id)
        if not os.path.exists(user_dir):
            return 0
        
        total_size = 0
        for file in os.listdir(user_dir):
            file_path = os.path.join(user_dir, file)
            if os.path.isfile(file_path):
                total_size += os.path.getsize(file_path)
        
        return total_size

    def create_file_hash(self, user_id, filename):
        """Crea un hash único para el archivo"""
        data = f"{user_id}_{filename}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    def store_file_mapping(self, file_hash, user_id, filename):
        """Almacena el mapeo hash→archivo"""
        self.file_mappings[file_hash] = {
            'user_id': user_id,
            'filename': filename
        }

    def get_file_info(self, file_hash):
        """Obtiene información del archivo por hash"""
        return self.file_mappings.get(file_hash)

    def delete_file_mapping(self, file_hash):
        """Elimina un mapeo de archivo"""
        if file_hash in self.file_mappings:
            del self.file_mappings[file_hash]

    def list_user_files(self, user_id):
        """Lista archivos del usuario con numeración ACTUALIZADA"""
        user_dir = self.get_user_directory(user_id)
        if not os.path.exists(user_dir):
            return []
        
        files = []
        user_key = f"{user_id}_download"
        
        if user_key in self.metadata:
            # Obtener archivos existentes y ordenar por número
            existing_files = []
            for file_num, file_data in self.metadata[user_key]["files"].items():
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.exists(file_path):
                    existing_files.append((int(file_num), file_data))
            
            # Ordenar por número y reasignar números secuenciales
            existing_files.sort(key=lambda x: x[0])
            
            for new_number, (old_number, file_data) in enumerate(existing_files, 1):
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    download_url = self.create_download_url(user_id, file_data["stored_name"])
                    files.append({
                        'number': new_number,
                        'original_number': old_number,
                        'name': file_data["original_name"],
                        'stored_name': file_data["stored_name"],
                        'size': size,
                        'size_mb': size / (1024 * 1024),
                        'url': download_url
                    })
        
        return files

    def register_file(self, user_id, original_name, stored_name, file_type="download"):
        """Registra un archivo en la metadata"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        file_num = self.metadata[user_key]["next_number"] - 1
        self.metadata[user_key]["files"][str(file_num)] = {
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time()
        }
        self.save_metadata()
        return file_num

    def get_file_by_number(self, user_id, file_number, file_type="download"):
        """Obtiene información de archivo por número (usa números originales)"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return None
        
        file_data = None
        original_number = None
        
        files_list = self.list_user_files(user_id)
        for file_info in files_list:
            if file_info['number'] == file_number:
                original_number = file_info['original_number']
                file_data = self.metadata[user_key]["files"].get(str(original_number))
                break
        
        if not file_data:
            return None
        
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        file_path = os.path.join(user_dir, file_data["stored_name"])
        
        if not os.path.exists(file_path):
            return None
        
        download_url = self.create_download_url(user_id, file_data["stored_name"])
        
        return {
            'number': file_number,
            'original_number': original_number,
            'original_name': file_data["original_name"],
            'stored_name': file_data["stored_name"],
            'path': file_path,
            'url': download_url
        }

    def rename_file(self, user_id, file_number, new_name, file_type="download"):
        """Renombra un archivo"""
        try:
            user_key = f"{user_id}_{file_type}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado"
            
            file_info = self.get_file_by_number(user_id, file_number, file_type)
            if not file_info:
                return False, "Archivo no encontrado"
            
            original_number = file_info['original_number']
            file_data = self.metadata[user_key]["files"].get(str(original_number))
            if not file_data:
                return False, "Archivo no encontrado en metadata"
            
            new_name = self.sanitize_filename(new_name)
            
            user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
            old_path = os.path.join(user_dir, file_data["stored_name"])
            
            if not os.path.exists(old_path):
                return False, "Archivo físico no encontrado"
            
            _, ext = os.path.splitext(file_data["stored_name"])
            new_stored_name = new_name + ext
            
            counter = 1
            base_new_stored_name = new_stored_name
            while os.path.exists(os.path.join(user_dir, new_stored_name)):
                name_no_ext = os.path.splitext(base_new_stored_name)[0]
                ext = os.path.splitext(base_new_stored_name)[1]
                new_stored_name = f"{name_no_ext}_{counter}{ext}"
                counter += 1
            
            new_path = os.path.join(user_dir, new_stored_name)
            
            os.rename(old_path, new_path)
            
            file_data["original_name"] = new_name
            file_data["stored_name"] = new_stored_name
            self.save_metadata()
            
            new_url = self.create_download_url(user_id, new_stored_name)
            
            return True, f"Archivo renombrado a: {new_name}", new_url
            
        except Exception as e:
            logger.error(f"Error renombrando archivo: {e}")
            return False, f"Error al renombrar: {str(e)}", None

    def delete_file_by_number(self, user_id, file_number, file_type="download"):
        """Elimina un archivo por número (usa números mostrados)"""
        try:
            user_key = f"{user_id}_{file_type}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado"
            
            file_info = self.get_file_by_number(user_id, file_number, file_type)
            if not file_info:
                return False, "Archivo no encontrado"
            
            original_number = file_info['original_number']
            file_data = self.metadata[user_key]["files"].get(str(original_number))
            if not file_data:
                return False, "Archivo no encontrado en metadata"
            
            user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
            file_path = os.path.join(user_dir, file_data["stored_name"])
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            del self.metadata[user_key]["files"][str(original_number)]
            self.save_metadata()
            
            return True, f"Archivo #{file_number} eliminado"
            
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False, f"Error al eliminar archivo: {str(e)}"

    def delete_all_files(self, user_id, file_type="download"):
        """Elimina todos los archivos del usuario"""
        try:
            user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
            
            if not os.path.exists(user_dir):
                return False, "No hay archivos para eliminar"
            
            files = os.listdir(user_dir)
            if not files:
                return False, "No hay archivos para eliminar"
            
            deleted_count = 0
            for filename in files:
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            user_key = f"{user_id}_{file_type}"
            if user_key in self.metadata:
                self.metadata[user_key]["files"] = {}
                self.metadata[user_key]["next_number"] = 1
                self.save_metadata()
            
            return True, f"Se eliminaron {deleted_count} archivos"
            
        except Exception as e:
            logger.error(f"Error eliminando todos los archivos: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"

# Instancia global
file_service = FileService()

# ===== UTILIDADES DE PROGRESO =====
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

# Instancia global
progress_service = ProgressService()

# ===== EMPAQUETADO SIMPLE (SIN COMPRESIÓN) =====
class SimplePackingService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB
    
    def pack_folder(self, user_id, split_size_mb=None):
        """Empaqueta la carpeta del usuario SIN compresión"""
        try:
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message
            
            try:
                user_dir = file_service.get_user_directory(user_id)
                if not os.path.exists(user_dir):
                    return None, "No tienes archivos para empaquetar"
                
                files = os.listdir(user_dir)
                if not files:
                    return None, "No tienes archivos para empaquetar"
                
                packed_dir = os.path.join(BASE_DIR, str(user_id), "packed")
                os.makedirs(packed_dir, exist_ok=True)
                
                timestamp = int(time.time())
                base_filename = f"packed_files_{timestamp}"
                
                if split_size_mb:
                    result = self._pack_split_simple(user_id, user_dir, packed_dir, base_filename, split_size_mb)
                else:
                    result = self._pack_single_simple(user_id, user_dir, packed_dir, base_filename)
                
                return result
                
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"Error en empaquetado simple: {e}")
            return None, f"Error al empaquetar: {str(e)}"
    
    def _pack_single_simple(self, user_id, user_dir, packed_dir, base_filename):
        """Empaqueta en un solo archivo ZIP SIN compresión"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for file in os.listdir(user_dir):
                    file_path = os.path.join(user_dir, file)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, file)
            
            file_size = os.path.getsize(output_file)
            size_mb = file_size / (1024 * 1024)
            
            file_num = file_service.register_file(user_id, f"{base_filename}.zip", f"{base_filename}.zip", "packed")
            
            download_url = file_service.create_packed_url(user_id, f"{base_filename}.zip")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'size_mb': size_mb
            }], f"Empaquetado completado: {size_mb:.1f}MB"
            
        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            raise e
    
    def _pack_split_simple(self, user_id, user_dir, packed_dir, base_filename, split_size_mb):
        """Empaqueta y divide en partes SIN compresión"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            temp_file = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            
            with zipfile.ZipFile(temp_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for file in os.listdir(user_dir):
                    file_path = os.path.join(user_dir, file)
                    if os.path.isfile(file_path):
                        zipf.write(file_path, file)
            
            part_files = []
            part_num = 1
            
            with open(temp_file, 'rb') as f:
                while True:
                    chunk = f.read(split_size_bytes)
                    if not chunk:
                        break
                    
                    part_filename = f"{base_filename}.part{part_num:03d}.zip"
                    part_path = os.path.join(packed_dir, part_filename)
                    
                    with open(part_path, 'wb') as part_file:
                        part_file.write(chunk)
                    
                    part_size = os.path.getsize(part_path)
                    download_url = file_service.create_packed_url(user_id, part_filename)
                    
                    file_num = file_service.register_file(user_id, part_filename, part_filename, "packed")
                    
                    part_files.append({
                        'number': file_num,
                        'filename': part_filename,
                        'url': download_url,
                        'size_mb': part_size / (1024 * 1024)
                    })
                    
                    part_num += 1
            
            os.remove(temp_file)
            
            total_size = sum(part['size_mb'] for part in part_files)
            return part_files, f"Empaquetado completado: {len(part_files)} partes, {total_size:.1f}MB total"
            
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise e

    def clear_packed_folder(self, user_id):
        """Elimina todos los archivos empaquetados del usuario"""
        try:
            packed_dir = os.path.join(BASE_DIR, str(user_id), "packed")
            
            if not os.path.exists(packed_dir):
                return False, "No tienes archivos empaquetados para eliminar"
            
            files = os.listdir(packed_dir)
            if not files:
                return False, "No tienes archivos empaquetados para eliminar"
            
            deleted_count = 0
            for filename in files:
                file_path = os.path.join(packed_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            user_key = f"{user_id}_packed"
            if user_key in file_service.metadata:
                file_service.metadata[user_key]["files"] = {}
                file_service.save_metadata()
            
            return True, f"Se eliminaron {deleted_count} archivos empaquetados"
            
        except Exception as e:
            logger.error(f"Error limpiando carpeta empaquetada: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"

# Instancia global
packing_service = SimplePackingService()

# ===== MANEJADORES DE COMANDOS OPTIMIZADOS =====
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
`/rename N NUEVO_NOMBRE` - Renombrar archivo N

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
            response_text = f"""**Empaquetado Completado**

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
            response_text = f"""**Empaquetado Completado**

**Archivos Generados:** {len(files)} partes
**Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB

**Enlaces de Descarga:**\n"""
            
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

# ===== MANEJADOR DE ARCHIVOS MEJORADO =====
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

# ===== MANEJADORES DE CALLBACKS ACTUALIZADOS =====
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

# ===== BOT DE TELEGRAM =====
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

# ===== INICIALIZACIÓN =====
def start_telegram_bot():
    """Inicia el bot de Telegram en un hilo separado"""
    logger.info("Iniciando bot de Telegram...")
    bot = TelegramBot()
    bot.run_bot()

def start_web_server():
    """Inicia el servidor web Flask"""
    logger.info(f"Iniciando servidor web en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    logger.info("Directorio static creado/verificado")

    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()

    logger.info("Hilo del bot iniciado")

    time.sleep(10)

    logger.info("Iniciando servidor web principal...")

    start_web_server()
