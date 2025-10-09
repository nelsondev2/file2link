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
import py7zr
import json
import shutil
import subprocess
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
MAX_PART_SIZE_MB = 50  # Reducido para menos carga
COMPRESSION_TIMEOUT = 600  # 10 minutos máximo
MAX_CONCURRENT_PROCESSES = 1  # Solo 1 proceso pesado a la vez
CPU_USAGE_LIMIT = 80  # Límite de uso de CPU

# ===== SISTEMA DE GESTIÓN DE CARGA =====
class LoadManager:
    def __init__(self):
        self.active_processes = 0
        self.max_processes = MAX_CONCURRENT_PROCESSES
        self.lock = threading.Lock()
    
    def can_start_process(self):
        """Verifica si se puede iniciar un nuevo proceso pesado"""
        with self.lock:
            # Verificar uso actual de CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > CPU_USAGE_LIMIT:
                return False, f"❌ CPU sobrecargada ({cpu_percent:.1f}%). Espera un momento."
            
            if self.active_processes >= self.max_processes:
                return False, "❌ Ya hay un proceso en ejecución. Espera a que termine."
            
            self.active_processes += 1
            return True, f"✅ Proceso iniciado (CPU: {cpu_percent:.1f}%)"
    
    def finish_process(self):
        """Marca un proceso como terminado"""
        with self.lock:
            self.active_processes = max(0, self.active_processes - 1)
    
    def get_status(self):
        """Obtiene estado actual del sistema"""
        with self.lock:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            return {
                'active_processes': self.active_processes,
                'max_processes': self.max_processes,
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'can_accept_work': self.active_processes < self.max_processes and cpu_percent < CPU_USAGE_LIMIT
            }

# Instancia global del gestor de carga
load_manager = LoadManager()

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

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
                    <div class="feature-icon">🎬</div>
                    <h4>Conversión de Video</h4>
                    <p>Conversión automática a 320x240 con compresión optimizada</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🔗</div>
                    <h4>Enlaces Permanentes</h4>
                    <p>Enlaces web permanentes para todos tus archivos</p>
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

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(BASE_DIR, path)

@app.route('/static/<user_id>/compressed/<filename>')
def serve_compressed(user_id, filename):
    """Sirve archivos comprimidos"""
    user_compress_dir = os.path.join(BASE_DIR, user_id, "compressed")
    return send_from_directory(user_compress_dir, filename)

@app.route('/files/<user_id>')
def file_explorer(user_id):
    """Explorador web moderno de archivos para el usuario"""
    try:
        user_dir = os.path.join(BASE_DIR, user_id, "download")
        compressed_dir = os.path.join(BASE_DIR, user_id, "compressed")
        
        # Obtener archivos normales
        normal_files = []
        total_normal_size = 0
        if os.path.exists(user_dir):
            for filename in sorted(os.listdir(user_dir)):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    total_normal_size += size
                    normal_files.append({
                        'name': filename,
                        'size': size,
                        'size_mb': size / (1024 * 1024),
                        'url': f"{RENDER_DOMAIN}/static/{user_id}/download/{urllib.parse.quote(filename)}",
                        'type': 'normal'
                    })
        
        # Obtener archivos comprimidos
        compressed_files = []
        total_compressed_size = 0
        if os.path.exists(compressed_dir):
            for filename in sorted(os.listdir(compressed_dir)):
                file_path = os.path.join(compressed_dir, filename)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    total_compressed_size += size
                    compressed_files.append({
                        'name': filename,
                        'size': size,
                        'size_mb': size / (1024 * 1024),
                        'url': f"{RENDER_DOMAIN}/static/{user_id}/compressed/{urllib.parse.quote(filename)}",
                        'type': 'compressed'
                    })
        
        # Combinar todos los archivos
        all_files = normal_files + compressed_files
        total_files = len(all_files)
        total_size_mb = (total_normal_size + total_compressed_size) / (1024 * 1024)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Archivos del Usuario {user_id} - Nelson File2Link</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    color: #333;
                }}
                
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                
                .header {{
                    background: rgba(255, 255, 255, 0.95);
                    padding: 30px;
                    border-radius: 15px;
                    margin-bottom: 20px;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                    text-align: center;
                }}
                
                .header h1 {{
                    color: #2c3e50;
                    margin-bottom: 10px;
                    font-size: 2rem;
                }}
                
                .header p {{
                    color: #7f8c8d;
                    font-size: 1.1rem;
                }}
                
                .stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin: 25px 0;
                }}
                
                .stat-card {{
                    background: linear-gradient(135deg, #3498db, #2980b9);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
                }}
                
                .stat-card h3 {{
                    font-size: 2rem;
                    margin-bottom: 5px;
                }}
                
                .stat-card p {{
                    opacity: 0.9;
                    font-size: 0.9rem;
                }}
                
                .file-browser {{
                    background: rgba(255, 255, 255, 0.95);
                    border-radius: 15px;
                    padding: 0;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                }}
                
                .file-table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                
                .file-table th {{
                    background: #34495e;
                    color: white;
                    padding: 15px;
                    text-align: left;
                    font-weight: 600;
                }}
                
                .file-table tr:nth-child(even) {{
                    background: #f8f9fa;
                }}
                
                .file-table tr:hover {{
                    background: #e3f2fd;
                }}
                
                .file-table td {{
                    padding: 15px;
                    border-bottom: 1px solid #ecf0f1;
                }}
                
                .file-name {{
                    font-weight: 500;
                    color: #2c3e50;
                }}
                
                .file-link {{
                    color: #3498db;
                    text-decoration: none;
                    font-weight: 500;
                    transition: color 0.3s ease;
                }}
                
                .file-link:hover {{
                    color: #2980b9;
                    text-decoration: underline;
                }}
                
                .file-type {{
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 0.8rem;
                    font-weight: 600;
                    text-transform: uppercase;
                }}
                
                .type-normal {{
                    background: #d4edda;
                    color: #155724;
                }}
                
                .type-compressed {{
                    background: #fff3cd;
                    color: #856404;
                }}
                
                .file-size {{
                    color: #7f8c8d;
                    font-family: 'Courier New', monospace;
                    font-weight: 500;
                }}
                
                .empty-state {{
                    text-align: center;
                    padding: 60px 20px;
                    color: #7f8c8d;
                }}
                
                .empty-state .icon {{
                    font-size: 4rem;
                    margin-bottom: 20px;
                    opacity: 0.5;
                }}
                
                .section-title {{
                    background: #2c3e50;
                    color: white;
                    padding: 15px 25px;
                    margin: 0;
                    font-size: 1.1rem;
                }}
                
                @media (max-width: 768px) {{
                    .file-table {{
                        display: block;
                        overflow-x: auto;
                    }}
                    
                    .file-table th,
                    .file-table td {{
                        padding: 10px;
                        font-size: 0.9rem;
                    }}
                    
                    .stats {{
                        grid-template-columns: 1fr;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📁 Explorador de Archivos</h1>
                    <p>Usuario ID: {user_id}</p>
                    
                    <div class="stats">
                        <div class="stat-card">
                            <h3>{total_files}</h3>
                            <p>Archivos Totales</p>
                        </div>
                        <div class="stat-card">
                            <h3>{len(normal_files)}</h3>
                            <p>Archivos Normales</p>
                        </div>
                        <div class="stat-card">
                            <h3>{len(compressed_files)}</h3>
                            <p>Archivos Comprimidos</p>
                        </div>
                        <div class="stat-card">
                            <h3>{total_size_mb:.1f}</h3>
                            <p>MB Usados</p>
                        </div>
                    </div>
                </div>
                
                <div class="file-browser">
                    <h3 class="section-title">🗂️ Todos los Archivos ({total_files})</h3>
                    
                    {"".join([f"""
                    <div style="padding: 20px; border-bottom: 1px solid #ecf0f1;">
                        <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 10px;">
                            <div>
                                <a href="{file['url']}" class="file-link" style="font-size: 1.1rem; font-weight: 600;">
                                    {file['name']}
                                </a>
                                <span class="file-type type-{file['type']}" style="margin-left: 10px;">
                                    {file['type']}
                                </span>
                            </div>
                            <div class="file-size" style="font-weight: 600;">
                                {file['size_mb']:.2f} MB
                            </div>
                        </div>
                        <div style="color: #7f8c8d; font-size: 0.9rem;">
                            <strong>Enlace:</strong> 
                            <a href="{file['url']}" style="color: #3498db; text-decoration: none; word-break: break-all;">
                                {file['url']}
                            </a>
                        </div>
                    </div>
                    """ for file in all_files]) if all_files else '''
                    <div class="empty-state">
                        <div class="icon">📂</div>
                        <h3>No hay archivos</h3>
                        <p>Este usuario aún no ha subido ningún archivo.</p>
                    </div>
                    '''}
                </div>
                
                {"".join([f'''
                <div class="file-browser" style="margin-top: 20px;">
                    <h3 class="section-title">📄 Archivos Normales ({len(normal_files)})</h3>
                    <table class="file-table">
                        <thead>
                            <tr>
                                <th>Nombre del Archivo</th>
                                <th>Tamaño</th>
                                <th>Tipo</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join([f"""
                            <tr>
                                <td>
                                    <a href="{file['url']}" class="file-link">{file['name']}</a>
                                </td>
                                <td class="file-size">{file['size_mb']:.2f} MB</td>
                                <td><span class="file-type type-normal">Normal</span></td>
                            </tr>
                            """ for file in normal_files])}
                        </tbody>
                    </table>
                </div>
                ''' for _ in [1] if normal_files])}
                
                {"".join([f'''
                <div class="file-browser" style="margin-top: 20px;">
                    <h3 class="section-title">🗜️ Archivos Comprimidos ({len(compressed_files)})</h3>
                    <table class="file-table">
                        <thead>
                            <tr>
                                <th>Nombre del Archivo</th>
                                <th>Tamaño</th>
                                <th>Tipo</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join([f"""
                            <tr>
                                <td>
                                    <a href="{file['url']}" class="file-link">{file['name']}</a>
                                </td>
                                <td class="file-size">{file['size_mb']:.2f} MB</td>
                                <td><span class="file-type type-compressed">Comprimido</span></td>
                            </tr>
                            """ for file in compressed_files])}
                        </tbody>
                    </table>
                </div>
                ''' for _ in [1] if compressed_files])}
            </div>
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - Nelson File2Link</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    color: white;
                    text-align: center;
                }}
                .error-container {{
                    background: rgba(255,255,255,0.1);
                    padding: 40px;
                    border-radius: 15px;
                    backdrop-filter: blur(10px);
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>❌ Error</h1>
                <p>No se pudieron cargar los archivos: {str(e)}</p>
            </div>
        </body>
        </html>
        """
# ===== RUTA DE ESTADO DEL SISTEMA =====
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
        "max_file_size_mb": 100,
        "max_concurrent_processes": MAX_CONCURRENT_PROCESSES
    })
# ===== UTILIDADES DE ARCHIVOS =====
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
        """Lista archivos del usuario con numeración"""
        user_dir = self.get_user_directory(user_id)
        if not os.path.exists(user_dir):
            return []
        
        files = []
        user_key = f"{user_id}_download"
        
        if user_key in self.metadata:
            # Ordenar por número
            numbered_files = []
            for file_num, file_data in self.metadata[user_key]["files"].items():
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.exists(file_path):
                    numbered_files.append((int(file_num), file_data))
            
            numbered_files.sort(key=lambda x: x[0])
            
            for file_num, file_data in numbered_files:
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    download_url = self.create_download_url(user_id, file_data["stored_name"])
                    files.append({
                        'number': file_num,
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
        
        file_num = self.metadata[user_key]["next_number"] - 1  # El número actual
        self.metadata[user_key]["files"][str(file_num)] = {
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time()
        }
        self.save_metadata()
        return file_num

    def get_file_by_number(self, user_id, file_number, file_type="download"):
        """Obtiene información de archivo por número"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return None
        
        file_data = self.metadata[user_key]["files"].get(str(file_number))
        if not file_data:
            return None
        
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        file_path = os.path.join(user_dir, file_data["stored_name"])
        
        if not os.path.exists(file_path):
            return None
        
        download_url = self.create_download_url(user_id, file_data["stored_name"])
        
        return {
            'number': file_number,
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
            
            file_data = self.metadata[user_key]["files"].get(str(file_number))
            if not file_data:
                return False, "Archivo no encontrado"
            
            # Sanitizar nuevo nombre
            new_name = self.sanitize_filename(new_name)
            
            user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
            old_path = os.path.join(user_dir, file_data["stored_name"])
            
            if not os.path.exists(old_path):
                return False, "Archivo físico no encontrado"
            
            # Generar nuevo nombre almacenado
            _, ext = os.path.splitext(file_data["stored_name"])
            new_stored_name = f"{file_number:03d}_{new_name}{ext}"
            new_path = os.path.join(user_dir, new_stored_name)
            
            # Renombrar archivo físico
            os.rename(old_path, new_path)
            
            # Actualizar metadata
            file_data["original_name"] = new_name
            file_data["stored_name"] = new_stored_name
            self.save_metadata()
            
            # Generar nueva URL
            new_url = self.create_download_url(user_id, new_stored_name)
            
            return True, f"Archivo renombrado a: {new_name}", new_url
            
        except Exception as e:
            logger.error(f"Error renombrando archivo: {e}")
            return False, f"Error al renombrar: {str(e)}", None

    def delete_file_by_number(self, user_id, file_number, file_type="download"):
        """Elimina un archivo por número"""
        try:
            user_key = f"{user_id}_{file_type}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado"
            
            file_data = self.metadata[user_key]["files"].get(str(file_number))
            if not file_data:
                return False, "Archivo no encontrado"
            
            user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
            file_path = os.path.join(user_dir, file_data["stored_name"])
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Eliminar de metadata
            del self.metadata[user_key]["files"][str(file_number)]
            self.save_metadata()
            
            return True, f"Archivo #{file_number} eliminado exitosamente"
            
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
            
            # Limpiar metadata
            user_key = f"{user_id}_{file_type}"
            if user_key in self.metadata:
                self.metadata[user_key]["files"] = {}
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
        # Acortar nombres de archivo largos para mejor visualización
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

    def create_conversion_progress(self, filename, current_part, total_parts, current_step, total_steps, process_type="Conversión"):
        """Crea mensaje de progreso para conversión de videos"""
        if len(filename) > 25:
            display_name = filename[:22] + "..."
        else:
            display_name = filename
        
        step_progress = self.create_progress_bar(current_step, total_steps)
        part_progress = self.create_progress_bar(current_part, total_parts)
        
        message = f"**🎬 {process_type}:** `{display_name}`\n"
        message += f"**🔄 Proceso:** {current_step}/{total_steps} - `{step_progress}`\n"
        message += f"**📦 Parte:** {current_part}/{total_parts} - `{part_progress}`\n"
        message += f"**⏰ Estado:** Procesando..."
        
        return message

# Instancia global
progress_service = ProgressService()

# ===== SERVICIO DE COMPRESIÓN (SIN LÍMITE DE PARTES) =====
# ===== COMPRESIÓN OPTIMIZADA =====
class OptimizedCompressionService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB
        self.compression_level = 1  # Nivel bajo para menos CPU (1-9, donde 1 es más rápido)
    
    def compress_folder(self, user_id, split_size_mb=None):
        """Comprime la carpeta del usuario de forma optimizada"""
        try:
            # Verificar carga del sistema
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message
            
            try:
                user_dir = file_service.get_user_directory(user_id)
                if not os.path.exists(user_dir):
                    return None, "❌ No tienes archivos para comprimir"
                
                files = os.listdir(user_dir)
                if not files:
                    return None, "❌ No tienes archivos para comprimir"
                
                compress_dir = os.path.join(BASE_DIR, str(user_id), "compressed")
                os.makedirs(compress_dir, exist_ok=True)
                
                timestamp = int(time.time())
                base_filename = f"backup_{timestamp}"
                
                if split_size_mb:
                    result = self._compress_split_optimized(user_id, user_dir, compress_dir, base_filename, split_size_mb)
                else:
                    result = self._compress_single_optimized(user_id, user_dir, compress_dir, base_filename)
                
                return result
                
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"❌ Error en compresión optimizada: {e}")
            return None, f"❌ Error al comprimir: {str(e)}"
    
    def _compress_single_optimized(self, user_id, user_dir, compress_dir, base_filename):
        """Compresión simple optimizada"""
        output_file = os.path.join(compress_dir, f"{base_filename}.7z")
        
        try:
            # Usar nivel de compresión bajo para menos CPU
            with py7zr.SevenZipFile(output_file, 'w', compression_level=self.compression_level) as archive:
                for file in os.listdir(user_dir):
                    file_path = os.path.join(user_dir, file)
                    if os.path.isfile(file_path):
                        archive.write(file_path, file)
            
            file_size = os.path.getsize(output_file)
            size_mb = file_size / (1024 * 1024)
            
            # Registrar archivo comprimido
            file_num = file_service.register_file(user_id, f"{base_filename}.7z", f"{base_filename}.7z", "compressed")
            
            download_url = f"{RENDER_DOMAIN}/static/{user_id}/compressed/{base_filename}.7z"
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.7z",
                'url': download_url,
                'size_mb': size_mb
            }], f"✅ Compresión completada: {size_mb:.1f}MB"
            
        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            raise e
    
    def _compress_split_optimized(self, user_id, user_dir, compress_dir, base_filename, split_size_mb):
        """Compresión dividida optimizada"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            # Primero comprimir con nivel bajo
            temp_file = os.path.join(compress_dir, f"temp_{base_filename}.7z")
            
            with py7zr.SevenZipFile(temp_file, 'w', compression_level=self.compression_level) as archive:
                for file in os.listdir(user_dir):
                    file_path = os.path.join(user_dir, file)
                    if os.path.isfile(file_path):
                        archive.write(file_path, file)
            
            # Dividir el archivo comprimido
            part_files = []
            part_num = 1
            
            with open(temp_file, 'rb') as f:
                while True:
                    chunk = f.read(split_size_bytes)
                    if not chunk:
                        break
                    
                    part_filename = f"{base_filename}.part{part_num:03d}.7z"
                    part_path = os.path.join(compress_dir, part_filename)
                    
                    with open(part_path, 'wb') as part_file:
                        part_file.write(chunk)
                    
                    part_size = os.path.getsize(part_path)
                    download_url = f"{RENDER_DOMAIN}/static/{user_id}/compressed/{part_filename}"
                    
                    # Registrar cada parte
                    file_num = file_service.register_file(user_id, part_filename, part_filename, "compressed")
                    
                    part_files.append({
                        'number': file_num,
                        'filename': part_filename,
                        'url': download_url,
                        'size_mb': part_size / (1024 * 1024)
                    })
                    
                    part_num += 1
            
            os.remove(temp_file)
            
            total_size = sum(part['size_mb'] for part in part_files)
            return part_files, f"✅ Compresión completada: {len(part_files)} partes, {total_size:.1f}MB total"
            
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise e

    def clear_compressed_folder(self, user_id):
        """Elimina todos los archivos comprimidos del usuario"""
        try:
            compress_dir = os.path.join(BASE_DIR, str(user_id), "compressed")
            
            if not os.path.exists(compress_dir):
                return False, "❌ No tienes archivos comprimidos para eliminar"
            
            files = os.listdir(compress_dir)
            if not files:
                return False, "❌ No tienes archivos comprimidos para eliminar"
            
            deleted_count = 0
            for filename in files:
                file_path = os.path.join(compress_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            # Limpiar metadata de comprimidos
            user_key = f"{user_id}_compressed"
            if user_key in file_service.metadata:
                file_service.metadata[user_key]["files"] = {}
                file_service.save_metadata()
            
            return True, f"✅ Se eliminaron {deleted_count} archivos comprimidos"
            
        except Exception as e:
            logger.error(f"❌ Error limpiando carpeta comprimida: {e}")
            return False, f"❌ Error al eliminar archivos: {str(e)}"

# Reemplazar la instancia global
compression_service = OptimizedCompressionService()

# Instancia global
compression_service = CompressionService()

# ===== GESTIÓN DE CONVERSIONES ACTIVAS =====
class ConversionManager:
    def __init__(self):
        self.active_conversions = {}
        self.conversion_lock = threading.Lock()
    
    def start_conversion(self, user_id, file_number, message_id):
        """Registra una conversión activa"""
        with self.conversion_lock:
            key = f"{user_id}_{file_number}"
            self.active_conversions[key] = {
                'message_id': message_id,
                'start_time': time.time(),
                'stopped': False
            }
        return key
    
    def stop_conversion(self, user_id, file_number):
        """Detiene una conversión activa"""
        with self.conversion_lock:
            key = f"{user_id}_{file_number}"
            if key in self.active_conversions:
                self.active_conversions[key]['stopped'] = True
                return True
            return False
    
    def is_conversion_stopped(self, user_id, file_number):
        """Verifica si una conversión fue detenida"""
        with self.conversion_lock:
            key = f"{user_id}_{file_number}"
            if key in self.active_conversions:
                return self.active_conversions[key]['stopped']
            return True  # Si no existe, considerar detenida
    
    def remove_conversion(self, user_id, file_number):
        """Elimina una conversión del registro"""
        with self.conversion_lock:
            key = f"{user_id}_{file_number}"
            if key in self.active_conversions:
                del self.active_conversions[key]

# Instancia global
conversion_manager = ConversionManager()

# ===== CONVERSIÓN DE VIDEO OPTIMIZADA =====
class OptimizedVideoConversionService:
    def __init__(self):
        self.max_video_size_mb = 25  # Reducido para menos procesamiento
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)  # Solo 1 conversión a la vez
        self.ffmpeg_preset = 'ultrafast'  # Más rápido, menos compresión
        self.ffmpeg_crf = '32'  # Calidad más baja para archivos más pequeños
    
    def convert_video(self, user_id, file_number, progress_callback=None):
        """Convierte videos de forma optimizada para CPU limitada"""
        try:
            # Verificar carga del sistema
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message
            
            try:
                # Verificar si la conversión fue detenida
                if conversion_manager.is_conversion_stopped(user_id, file_number):
                    return None, "❌ Conversión cancelada por el usuario"
                    
                file_info = file_service.get_file_by_number(user_id, file_number)
                if not file_info:
                    return None, "❌ Archivo no encontrado"
                
                # Verificar si es video
                video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp'}
                file_ext = os.path.splitext(file_info['original_name'].lower())[1]
                if file_ext not in video_extensions:
                    return None, "❌ El archivo no es un video compatible"
                
                original_path = file_info['path']
                original_size = os.path.getsize(original_path)
                original_size_mb = original_size / (1024 * 1024)
                
                # Verificar si FFmpeg está disponible
                if not self._check_ffmpeg():
                    return None, "❌ FFmpeg no está instalado. No se puede convertir videos."
                
                logger.info(f"🎬 Iniciando conversión OPTIMIZADA: {file_info['original_name']} ({original_size_mb:.1f} MB)")
                
                # Para CPU limitada, solo convertir videos pequeños
                if original_size_mb > 100:  # Límite de 100 MB
                    return None, "❌ Video demasiado grande para conversión optimizada. Límite: 100MB"
                
                # Usar método optimizado para videos pequeños
                return self._convert_fast_single(user_id, file_info, original_path, original_size, progress_callback)
                    
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"❌ Error en conversión optimizada: {e}")
            return None, f"❌ Error al convertir video: {str(e)}"
        finally:
            # Limpiar registro de conversión
            conversion_manager.remove_conversion(user_id, file_number)
    
    def _convert_fast_single(self, user_id, file_info, original_path, original_size, progress_callback=None):
        """Conversión rápida y optimizada para CPU limitada"""
        try:
            if progress_callback:
                progress_callback(1, 3, "Iniciando conversión rápida...")
            
            # Verificar si la conversión fue detenida
            if conversion_manager.is_conversion_stopped(user_id, file_info['number']):
                return None, "❌ Conversión cancelada por el usuario"
            
            # Generar nombre para el archivo convertido
            original_name_no_ext = os.path.splitext(file_info['original_name'])[0]
            converted_name = f"{original_name_no_ext}_converted.mp4"
            converted_stored_name = f"{file_info['number']:03d}_{converted_name}"
            converted_path = os.path.join(os.path.dirname(original_path), converted_stored_name)
            
            if progress_callback:
                progress_callback(2, 3, "Ejecutando FFmpeg optimizado...")
            
            # CONVERSIÓN OPTIMIZADA - Configuración para velocidad
            success, error_message = self._convert_fast_ffmpeg(original_path, converted_path, user_id, file_info['number'])
            
            if not success:
                return None, f"❌ Error en conversión FFmpeg: {error_message}"
            
            if progress_callback:
                progress_callback(3, 3, "Finalizando...")
            
            # Verificar si la conversión fue detenida
            if conversion_manager.is_conversion_stopped(user_id, file_info['number']):
                if os.path.exists(converted_path):
                    os.remove(converted_path)
                return None, "❌ Conversión cancelada por el usuario"
            
            # Verificar que el archivo convertido existe
            if not os.path.exists(converted_path):
                return None, "❌ Error: Archivo convertido no se creó"
            
            converted_size = os.path.getsize(converted_path)
            
            # Calcular reducción
            size_reduction = ((original_size - converted_size) / original_size) * 100
            
            # Eliminar archivo original
            try:
                os.remove(original_path)
            except Exception as e:
                logger.error(f"Error eliminando original: {e}")
            
            # Actualizar metadata
            file_service.metadata[f"{user_id}_download"]["files"][str(file_info['number'])] = {
                "original_name": converted_name,
                "stored_name": converted_stored_name,
                "registered_at": time.time(),
                "converted_from": file_info['original_name'],
                "original_size": original_size,
                "converted_size": converted_size,
                "reduction_percent": size_reduction
            }
            file_service.save_metadata()
            
            download_url = file_service.create_download_url(user_id, converted_stored_name)
            
            return {
                'original_name': file_info['original_name'],
                'converted_name': converted_name,
                'original_size': original_size,
                'converted_size': converted_size,
                'reduction_percent': size_reduction,
                'download_url': download_url,
                'parts': 1
            }, "✅ Conversión RÁPIDA completada"
            
        except Exception as e:
            logger.error(f"❌ Error en conversión rápida: {e}")
            return None, f"❌ Error al convertir video: {str(e)}"
    
    def _convert_fast_ffmpeg(self, input_path, output_path, user_id=None, file_number=None):
        """Conversión FFmpeg optimizada para velocidad"""
        try:
            # Verificar si la conversión fue detenida
            if user_id and file_number and conversion_manager.is_conversion_stopped(user_id, file_number):
                return False, "Conversión cancelada por el usuario"
                
            # Comando FFmpeg OPTIMIZADO para velocidad (menos calidad pero más rápido)
            cmd = [
                'ffmpeg',
                '-i', input_path,           # Archivo de entrada
                '-vf', 'scale=320:240',     # Redimensionar a 320x240
                '-c:v', 'libx264',          # Codec video H.264
                '-crf', self.ffmpeg_crf,    # Calidad más baja para archivos más pequeños
                '-preset', self.ffmpeg_preset,  # Velocidad máxima de compresión
                '-c:a', 'aac',              # Codec audio AAC
                '-b:a', '32k',              # Bitrate audio más bajo
                '-movflags', '+faststart',  # Optimizar para web
                '-y',                       # Sobrescribir si existe
                output_path                 # Archivo de salida
            ]
            
            logger.info(f"🔧 Ejecutando FFmpeg OPTIMIZADO: {' '.join(cmd)}")
            
            # Ejecutar conversión con timeout reducido
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minutos timeout (reducido)
            )
            
            # Verificar si la conversión fue detenida durante la ejecución
            if user_id and file_number and conversion_manager.is_conversion_stopped(user_id, file_number):
                if os.path.exists(output_path):
                    os.remove(output_path)
                return False, "Conversión cancelada por el usuario"
            
            if result.returncode != 0:
                error_msg = result.stderr[:500] if result.stderr else "Error desconocido"
                logger.error(f"❌ FFmpeg error: {error_msg}")
                return False, error_msg
            
            logger.info("✅ Conversión FFmpeg OPTIMIZADA completada exitosamente")
            return True, None
            
        except subprocess.TimeoutExpired:
            logger.error("❌ FFmpeg timeout (5 minutos)")
            return False, "La conversión tardó demasiado tiempo (más de 5 minutos)"
        except Exception as e:
            logger.error(f"❌ Error ejecutando FFmpeg: {e}")
            return False, str(e)
    
    def _check_ffmpeg(self):
        """Verifica si FFmpeg está disponible en el sistema"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

# Reemplazar la instancia global
video_service = OptimizedVideoConversionService()

# Instancia global
video_service = VideoConversionService()

# ===== MANEJADORES DE COMANDOS =====
async def start_command(client, message):
    """Maneja el comando /start"""
    try:
        user = message.from_user
        
        # Verificar si FFmpeg está disponible
        ffmpeg_status = "✅ FFmpeg disponible" if video_service._check_ffmpeg() else "❌ FFmpeg no disponible"
        
        welcome_text = f"""👋 **Bienvenido/a {user.first_name}!

🤖 File2Link Bot - Servicio Profesional de Gestión de Archivos**

📁 **Comandos Disponibles:**
`/start` - Mensaje de bienvenida
`/files` - Ver tus archivos numerados
`/status` - Ver tu estado y uso de almacenamiento
`/compress` - Comprimir todos tus archivos
`/compress [MB]` - Comprimir y dividir (ej: `/compress 10`)
`/rename [número] [nuevo_nombre]` - Renombrar archivo
`/convert [número]` - Convertir video a 320x240 MP4 (REAL)

🎬 **Conversión de Video:**
{ffmpeg_status}
• Conversión REAL a 320x240
• Límite automático: 50 MB por parte
• División y unión automática para videos grandes
• Reducción real de tamaño
• **Puedes cancelar en cualquier momento**

📁 **¿Cómo Funciona?**
1. Envíame cualquier archivo
2. Lo almaceno en tu carpeta personal segura
3. Obtienes un enlace web permanente
4. Gestiona tus archivos fácilmente

🌐 **Tu Explorador Web:** {RENDER_DOMAIN}/files/{user.id}

🚀 **¡Envía un archivo para comenzar!**"""

        await message.reply_text(welcome_text)
        logger.info(f"✅ /start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"❌ Error en /start: {e}")

async def files_command(client, message):
    """Maneja el comando /files - AHORA CON ENLACES"""
    try:
        user_id = message.from_user.id
        files = file_service.list_user_files(user_id)
        
        if not files:
            await message.reply_text(
                "📂 **No tienes archivos almacenados.**\n\n"
                "¡Envía tu primer archivo para comenzar!\n\n"
                f"🌐 **Tu explorador web:** {RENDER_DOMAIN}/files/{user_id}"
            )
            return
        
        files_text = f"📁 **Tus Archivos ({len(files)}):**\n\n"
        
        for file_info in files:
            files_text += f"**{file_info['number']}.** `{file_info['name']}` ({file_info['size_mb']:.1f} MB)\n"
            files_text += f"   🔗 [Descargar]({file_info['url']})\n\n"

        files_text += f"💡 **Usa los números para gestionar archivos:**\n"
        files_text += f"• Renombrar: `/rename número nuevo_nombre`\n"
        files_text += f"• Convertir video: `/convert número`\n"
        files_text += f"• Eliminar: Usa los botones debajo\n"
        files_text += f"\n🌐 **Explorador Web Completo:** {RENDER_DOMAIN}/files/{user_id}"

        # Crear teclado con botones de eliminación
        keyboard_buttons = []
        for i in range(0, len(files), 2):
            row = []
            for file_info in files[i:i+2]:
                row.append(InlineKeyboardButton(
                    f"🗑️ {file_info['number']}",
                    callback_data=f"delete_{file_info['number']}"
                ))
            keyboard_buttons.append(row)
        
        # Agregar botón para eliminar todos
        keyboard_buttons.append([InlineKeyboardButton("🗑️ ELIMINAR TODOS LOS ARCHIVOS", callback_data="delete_all")])
        
        # Agregar botón para abrir explorador web
        keyboard_buttons.append([InlineKeyboardButton("🌐 Abrir Explorador Web", url=f"{RENDER_DOMAIN}/files/{user_id}")])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)

        await message.reply_text(files_text, reply_markup=keyboard, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"❌ Error en /files: {e}")
        await message.reply_text("❌ **Error al listar archivos.** Por favor, intenta nuevamente.")

async def status_command(client, message):
    """Maneja el comando /status - AHORA CON INFO DE CARGA"""
    try:
        user_id = message.from_user.id
        files = file_service.list_user_files(user_id)
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        # Obtener estado del sistema
        system_status = load_manager.get_status()
        ffmpeg_status = "✅ Disponible" if video_service._check_ffmpeg() else "❌ No disponible"
        
        status_text = f"""📊 **Estado del Sistema - {message.from_user.first_name}**

👤 **Usuario:** {user_id}
📁 **Archivos Almacenados:** {len(files)}
💾 **Espacio Utilizado:** {size_mb:.2f} MB

⚙️ **Estado del Servidor:**
• 🎬 **Conversión de Video:** {ffmpeg_status}
• 🔄 **Procesos Activos:** {system_status['active_processes']}/{system_status['max_processes']}
• 💻 **Uso de CPU:** {system_status['cpu_percent']:.1f}%
• 🧠 **Uso de Memoria:** {system_status['memory_percent']:.1f}%
• 🚦 **Estado:** {"✅ ACEPTANDO TRABAJO" if system_status['can_accept_work'] else "⚠️ SOBRECARGADO"}

🔗 **Tu URL Personal:** {RENDER_DOMAIN}/static/{user_id}/download/
🌐 **Explorador Web:** {RENDER_DOMAIN}/files/{user_id}"""
        
        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ **Error al obtener estado del sistema.**")

async def compress_command(client, message):
    """Maneja el comando /compress - AHORA CON VERIFICACIÓN DE CARGA"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        # Verificar estado del sistema primero
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado en este momento.**\n\n"
                f"• CPU: {system_status['cpu_percent']:.1f}%\n"
                f"• Procesos activos: {system_status['active_processes']}\n"
                f"• Intenta nuevamente en unos minutos."
            )
            return
        
        split_size = None
        if len(command_parts) > 1:
            try:
                split_size = int(command_parts[1])
                if split_size <= 0:
                    await message.reply_text("❌ **El tamaño de división debe ser mayor a 0 MB**")
                    return
                if split_size > 50:  # Reducido el límite máximo
                    await message.reply_text("❌ **El tamaño máximo por parte es 50 MB**")
                    return
            except ValueError:
                await message.reply_text("❌ **Formato incorrecto.** Usa: `/compress` o `/compress 10`")
                return
        
        # Mensaje de inicio
        status_msg = await message.reply_text(
            "🔄 **Iniciando proceso de compresión OPTIMIZADA...**\n\n"
            "⏳ Esto puede tomar varios minutos...\n"
            "💡 **Modo optimizado para CPU limitada**"
        )
        
        # Ejecutar compresión optimizada
        def run_optimized_compression():
            try:
                files, status_message = compression_service.compress_folder(user_id, split_size)
                return files, status_message
            except Exception as e:
                logger.error(f"Error en compresión optimizada: {e}")
                return None, f"❌ **Error en compresión:** {str(e)}"
        
        # Ejecutar en thread
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_optimized_compression)
            files, status_message = future.result(timeout=300)  # 5 minutos timeout
        
        if not files:
            await status_msg.edit_text(status_message)
            return
        
        # Crear mensaje con los enlaces
        if len(files) == 1:
            # Un solo archivo
            file_info = files[0]
            response_text = f"""✅ **Compresión Completada Exitosamente**

📦 **Archivo #{file_info['number']}:** `{file_info['filename']}`
💾 **Tamaño Comprimido:** {file_info['size_mb']:.1f} MB

🔗 **Enlace de Descarga:**
📎 [{file_info['filename']}]({file_info['url']})"""
            
            # Agregar botón para limpiar
            clear_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Vaciar Archivos Comprimidos", callback_data="clear_compressed")]
            ])
            
            await status_msg.edit_text(
                response_text, 
                disable_web_page_preview=True,
                reply_markup=clear_keyboard
            )
            
        else:
            # Múltiples partes
            response_text = f"""✅ **Compresión Completada Exitosamente**

📦 **Archivos Generados:** {len(files)} partes
💾 **Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB

🔗 **Enlaces de Descarga:**\n"""
            
            for file_info in files:
                response_text += f"\n**Parte {file_info['number']}:** 📎 [{file_info['filename']}]({file_info['url']})"
            
            # Telegram limita a 4096 caracteres por mensaje
            if len(response_text) > 4000:
                # Enviar mensajes divididos
                await status_msg.edit_text("✅ **Compresión completada exitosamente**\n\n📦 **Los enlaces se enviarán en varios mensajes...**")
                
                for file_info in files:
                    part_text = f"**Parte {file_info['number']}:** 📎 [{file_info['filename']}]({file_info['url']})"
                    await message.reply_text(part_text, disable_web_page_preview=True)
                
                # Agregar botón para limpiar en un mensaje separado
                clear_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑️ Vaciar Archivos Comprimidos", callback_data="clear_compressed")]
                ])
                await message.reply_text(
                    "💡 **¿Quieres liberar espacio?**",
                    reply_markup=clear_keyboard
                )
            else:
                # Agregar botón para limpiar
                clear_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑️ Vaciar Archivos Comprimidos", callback_data="clear_compressed")]
                ])
                
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True,
                    reply_markup=clear_keyboard
                )
                
        logger.info(f"✅ Compresión completada para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text("❌ **La compresión tardó demasiado tiempo.** Intenta con menos archivos o tamaños más pequeños.")
    except Exception as e:
        logger.error(f"❌ Error en comando /compress: {e}")
        await message.reply_text("❌ **Error en el proceso de compresión.** Por favor, intenta nuevamente.")

async def convert_command(client, message):
    """Maneja el comando /convert - AHORA CON VERIFICACIÓN DE CARGA"""
    try:
        user_id = message.from_user.id
        
        # Verificar estado del sistema primero
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado en este momento.**\n\n"
                f"• CPU: {system_status['cpu_percent']:.1f}%\n"
                f"• Procesos activos: {system_status['active_processes']}\n"
                f"• Intenta nuevamente en unos minutos."
            )
            return
        
        command_parts = message.text.split()
        
        if len(command_parts) < 2:
            await message.reply_text("❌ **Formato incorrecto.** Usa: `/convert número`")
            return
        
        try:
            file_number = int(command_parts[1])
        except ValueError:
            await message.reply_text("❌ **El número debe ser un valor numérico válido.**")
            return
        
        # Verificar si FFmpeg está disponible
        if not video_service._check_ffmpeg():
            await message.reply_text(
                "❌ **FFmpeg no está disponible en este servidor.**\n\n"
                "La conversión REAL de videos no puede realizarse en este momento."
            )
            return
        
        # Verificar tamaño del archivo
        file_info = file_service.get_file_by_number(user_id, file_number)
        if file_info:
            file_size = os.path.getsize(file_info['path'])
            file_size_mb = file_size / (1024 * 1024)
            if file_size_mb > 100:  # Límite de 100 MB
                await message.reply_text(
                    f"❌ **Video demasiado grande para conversión optimizada.**\n\n"
                    f"• Tamaño actual: {file_size_mb:.1f} MB\n"
                    f"• Límite máximo: 100 MB\n"
                    f"• **Sugerencia:** Comprime el video primero o divide en partes más pequeñas."
                )
                return
        
        # Registrar conversión activa
        conversion_key = conversion_manager.start_conversion(user_id, file_number, message.id)
        
        # Mensaje de inicio con información de modo optimizado
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹️ Cancelar Conversión", callback_data=f"stop_convert_{user_id}_{file_number}")]
        ])
        
        status_msg = await message.reply_text(
            "🔄 **Iniciando conversión RÁPIDA optimizada...**\n\n"
            "⏳ **Procesando en modo velocidad (calidad reducida)**\n"
            "📊 **Progreso:** `[░░░░░░░░░░░░░░░] 0.0%`\n\n"
            "💡 **Conversión optimizada para CPU limitada**",
            reply_markup=cancel_keyboard
        )
        
        # Función para ejecutar la conversión en un hilo separado
        async def run_conversion_async():
            try:
                # Variables para progreso
                current_progress = {"step": 0, "total_steps": 3, "part": 0, "total_parts": 1}
                
                def progress_callback(current, total, message_text=""):
                    """Callback para actualizar progreso (se ejecuta en el hilo de conversión)"""
                    current_progress["step"] = current
                    current_progress["total_steps"] = total
                    
                    # Usar asyncio para actualizar el mensaje de Telegram
                    asyncio.run_coroutine_threadsafe(
                        update_progress_message(current, total, current_progress),
                        client.loop
                    )
                
                # Ejecutar conversión en el ThreadPoolExecutor
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = loop.run_in_executor(
                        executor, 
                        lambda: video_service.convert_video(user_id, file_number, progress_callback)
                    )
                    result, status_message = await asyncio.wait_for(future, timeout=1800)  # 30 minutos timeout
                
                return result, status_message
                
            except asyncio.TimeoutError:
                return None, "❌ **La conversión tardó demasiado tiempo (más de 30 minutos).**"
            except Exception as e:
                logger.error(f"Error en conversión async: {e}")
                return None, f"❌ **Error en conversión:** {str(e)}"
        
        async def update_progress_message(current, total, progress_data):
            """Actualiza el mensaje de progreso en Telegram"""
            try:
                # Verificar si la conversión fue cancelada
                if conversion_manager.is_conversion_stopped(user_id, file_number):
                    return
                    
                progress_text = progress_service.create_conversion_progress(
                    filename="Procesando video...",
                    current_part=progress_data["part"],
                    total_parts=progress_data["total_parts"],
                    current_step=current,
                    total_steps=total,
                    process_type="Conversión de Video"
                )
                
                # Mantener el botón de cancelar
                updated_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏹️ Cancelar Conversión", callback_data=f"stop_convert_{user_id}_{file_number}")]
                ])
                
                await status_msg.edit_text(
                    f"{progress_text}\n\n💡 **Conversión optimizada para CPU limitada**",
                    reply_markup=updated_keyboard
                )
            except Exception as e:
                logger.error(f"Error actualizando progreso: {e}")
        
        # Ejecutar la conversión en segundo plano sin bloquear
        asyncio.create_task(execute_conversion(user_id, file_number, status_msg, run_conversion_async))
        
        logger.info(f"🎬 Conversión optimizada iniciada para usuario {user_id}, archivo {file_number}")
        
    except Exception as e:
        conversion_manager.remove_conversion(user_id, file_number)
        logger.error(f"❌ Error en comando /convert: {e}")
        await message.reply_text("❌ **Error al iniciar la conversión.** Por favor, intenta nuevamente.")

async def compress_command(client, message):
    """Maneja el comando /compress"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        split_size = None
        if len(command_parts) > 1:
            try:
                split_size = int(command_parts[1])
                if split_size <= 0:
                    await message.reply_text("❌ **El tamaño de división debe ser mayor a 0 MB**")
                    return
                if split_size > 100:
                    await message.reply_text("❌ **El tamaño máximo por parte es 100 MB**")
                    return
            except ValueError:
                await message.reply_text("❌ **Formato incorrecto.** Usa: `/compress` o `/compress 10`")
                return
        
        # Mensaje de inicio
        status_msg = await message.reply_text("🔄 **Iniciando proceso de compresión...**\n\n⏳ Esto puede tomar varios minutos dependiendo del tamaño y cantidad de archivos...")
        
        # Ejecutar compresión en un hilo separado para no bloquear
        def run_compression():
            try:
                files, status_message = compression_service.compress_folder(user_id, split_size)
                return files, status_message
            except Exception as e:
                logger.error(f"Error en compresión: {e}")
                return None, f"❌ **Error en compresión:** {str(e)}"
        
        # Ejecutar en thread para no bloquear
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_compression)
            files, status_message = future.result(timeout=300)  # 5 minutos timeout
        
        if not files:
            await status_msg.edit_text(status_message)
            return
        
        # Crear mensaje con los enlaces
        if len(files) == 1:
            # Un solo archivo
            file_info = files[0]
            response_text = f"""✅ **Compresión Completada Exitosamente**

📦 **Archivo #{file_info['number']}:** `{file_info['filename']}`
💾 **Tamaño Comprimido:** {file_info['size_mb']:.1f} MB

🔗 **Enlace de Descarga:**
📎 [{file_info['filename']}]({file_info['url']})"""
            
            # Agregar botón para limpiar
            clear_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Vaciar Archivos Comprimidos", callback_data="clear_compressed")]
            ])
            
            await status_msg.edit_text(
                response_text, 
                disable_web_page_preview=True,
                reply_markup=clear_keyboard
            )
            
        else:
            # Múltiples partes
            response_text = f"""✅ **Compresión Completada Exitosamente**

📦 **Archivos Generados:** {len(files)} partes
💾 **Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB

🔗 **Enlaces de Descarga:**\n"""
            
            for file_info in files:
                response_text += f"\n**Parte {file_info['number']}:** 📎 [{file_info['filename']}]({file_info['url']})"
            
            # Telegram limita a 4096 caracteres por mensaje
            if len(response_text) > 4000:
                # Enviar mensajes divididos
                await status_msg.edit_text("✅ **Compresión completada exitosamente**\n\n📦 **Los enlaces se enviarán en varios mensajes...**")
                
                for file_info in files:
                    part_text = f"**Parte {file_info['number']}:** 📎 [{file_info['filename']}]({file_info['url']})"
                    await message.reply_text(part_text, disable_web_page_preview=True)
                
                # Agregar botón para limpiar en un mensaje separado
                clear_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑️ Vaciar Archivos Comprimidos", callback_data="clear_compressed")]
                ])
                await message.reply_text(
                    "💡 **¿Quieres liberar espacio?**",
                    reply_markup=clear_keyboard
                )
            else:
                # Agregar botón para limpiar
                clear_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑️ Vaciar Archivos Comprimidos", callback_data="clear_compressed")]
                ])
                
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True,
                    reply_markup=clear_keyboard
                )
                
        logger.info(f"✅ Compresión completada para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text("❌ **La compresión tardó demasiado tiempo.** Intenta con menos archivos o tamaños más pequeños.")
    except Exception as e:
        logger.error(f"❌ Error en comando /compress: {e}")
        await message.reply_text("❌ **Error en el proceso de compresión.** Por favor, intenta nuevamente.")

async def rename_command(client, message):
    """Maneja el comando /rename - AHORA CON NUEVO ENLACE"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split(maxsplit=2)
        
        if len(command_parts) < 3:
            await message.reply_text("❌ **Formato incorrecto.** Usa: `/rename número nuevo_nombre`")
            return
        
        try:
            file_number = int(command_parts[1])
        except ValueError:
            await message.reply_text("❌ **El número debe ser un valor numérico válido.**")
            return
        
        new_name = command_parts[2].strip()
        
        if not new_name:
            await message.reply_text("❌ **El nuevo nombre no puede estar vacío.**")
            return
        
        # Renombrar archivo
        success, result_message, new_url = file_service.rename_file(user_id, file_number, new_name)
        
        if success:
            response_text = f"✅ **{result_message}**\n\n"
            response_text += f"🔗 **Nuevo enlace de descarga:**\n"
            response_text += f"📎 [{new_name}]({new_url})"
            
            # Crear teclado con el nuevo enlace
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Abrir Nuevo Enlace", url=new_url)],
                [InlineKeyboardButton("📂 Ver Todos los Archivos", callback_data="files_list")]
            ])
            
            await message.reply_text(
                response_text,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"❌ Error en comando /rename: {e}")
        await message.reply_text("❌ **Error al renombrar archivo.** Por favor, intenta nuevamente.")

async def convert_command(client, message):
    """Maneja el comando /convert - VERSIÓN CORREGIDA SIN BLOQUEO"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        if len(command_parts) < 2:
            await message.reply_text("❌ **Formato incorrecto.** Usa: `/convert número`")
            return
        
        try:
            file_number = int(command_parts[1])
        except ValueError:
            await message.reply_text("❌ **El número debe ser un valor numérico válido.**")
            return
        
        # Verificar si FFmpeg está disponible
        if not video_service._check_ffmpeg():
            await message.reply_text(
                "❌ **FFmpeg no está disponible en este servidor.**\n\n"
                "La conversión REAL de videos no puede realizarse en este momento. "
                "Contacta al administrador del sistema para instalar FFmpeg."
            )
            return
        
        # Registrar conversión activa
        conversion_key = conversion_manager.start_conversion(user_id, file_number, message.id)
        
        # Mensaje de inicio con botón de cancelar
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹️ Cancelar Conversión", callback_data=f"stop_convert_{user_id}_{file_number}")]
        ])
        
        status_msg = await message.reply_text(
            "🔄 **Iniciando conversión REAL con FFmpeg...**\n\n"
            "⏳ **Este proceso puede tomar varios minutos...**\n"
            "📊 **Progreso:** `[░░░░░░░░░░░░░░░] 0.0%`\n\n"
            "💡 **Puedes cancelar en cualquier momento**",
            reply_markup=cancel_keyboard
        )
        
        # Función para ejecutar la conversión en un hilo separado
        async def run_conversion_async():
            try:
                # Variables para progreso
                current_progress = {"step": 0, "total_steps": 3, "part": 0, "total_parts": 1}
                
                def progress_callback(current, total, message_text=""):
                    """Callback para actualizar progreso (se ejecuta en el hilo de conversión)"""
                    current_progress["step"] = current
                    current_progress["total_steps"] = total
                    
                    # Usar asyncio para actualizar el mensaje de Telegram
                    asyncio.run_coroutine_threadsafe(
                        update_progress_message(current, total, current_progress),
                        client.loop
                    )
                
                # Ejecutar conversión en el ThreadPoolExecutor
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = loop.run_in_executor(
                        executor, 
                        lambda: video_service.convert_video(user_id, file_number, progress_callback)
                    )
                    result, status_message = await asyncio.wait_for(future, timeout=1800)  # 30 minutos timeout
                
                return result, status_message
                
            except asyncio.TimeoutError:
                return None, "❌ **La conversión tardó demasiado tiempo (más de 30 minutos).**"
            except Exception as e:
                logger.error(f"Error en conversión async: {e}")
                return None, f"❌ **Error en conversión:** {str(e)}"
        
        async def update_progress_message(current, total, progress_data):
            """Actualiza el mensaje de progreso en Telegram"""
            try:
                # Verificar si la conversión fue cancelada
                if conversion_manager.is_conversion_stopped(user_id, file_number):
                    return
                    
                progress_text = progress_service.create_conversion_progress(
                    filename="Procesando video...",
                    current_part=progress_data["part"],
                    total_parts=progress_data["total_parts"],
                    current_step=current,
                    total_steps=total,
                    process_type="Conversión de Video"
                )
                
                # Mantener el botón de cancelar
                updated_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏹️ Cancelar Conversión", callback_data=f"stop_convert_{user_id}_{file_number}")]
                ])
                
                await status_msg.edit_text(
                    f"{progress_text}\n\n💡 **Puedes cancelar en cualquier momento**",
                    reply_markup=updated_keyboard
                )
            except Exception as e:
                logger.error(f"Error actualizando progreso: {e}")
        
        # Ejecutar la conversión en segundo plano sin bloquear
        asyncio.create_task(execute_conversion(user_id, file_number, status_msg, run_conversion_async))
        
        logger.info(f"🎬 Conversión iniciada para usuario {user_id}, archivo {file_number}")
        
    except Exception as e:
        conversion_manager.remove_conversion(user_id, file_number)
        logger.error(f"❌ Error en comando /convert: {e}")
        await message.reply_text("❌ **Error al iniciar la conversión.** Por favor, intenta nuevamente.")

async def execute_conversion(user_id, file_number, status_msg, conversion_task):
    """Ejecuta la conversión y maneja el resultado"""
    try:
        # Ejecutar la tarea de conversión
        result, status_message = await conversion_task()
        
        # Limpiar registro de conversión
        conversion_manager.remove_conversion(user_id, file_number)
        
        if not result:
            # Verificar si fue cancelada
            if "cancelada" in status_message.lower():
                await status_msg.edit_text("❌ **Conversión cancelada por el usuario.**")
            else:
                await status_msg.edit_text(status_message)
            return
        
        # Mostrar resultados de la conversión REAL
        parts_info = f" ({result['parts']} partes)" if result.get('parts', 1) > 1 else ""
        
        response_text = f"""✅ **Conversión REAL Completada Exitosamente{parts_info}**

📹 **Video Original:** `{result['original_name']}`
🎬 **Video Convertido:** `{result['converted_name']}`
📺 **Resolución:** 320x240 (Optimizado)

📊 **Reducción REAL de Tamaño:**
• **Original:** {file_service.format_bytes(result['original_size'])}
• **Convertido:** {file_service.format_bytes(result['converted_size'])}
• **Reducción:** **{result['reduction_percent']:.1f}%**

🔗 **Enlace de Descarga:**
📎 [{result['converted_name']}]({result['download_url']})

⚡ **Tecnología:** Conversión REAL con FFmpeg"""

        # Crear teclado con enlace de descarga
        download_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Descargar Video Convertido", url=result['download_url'])],
            [InlineKeyboardButton("📂 Ver Todos los Archivos", callback_data="files_list")]
        ])

        await status_msg.edit_text(
            response_text,
            disable_web_page_preview=True,
            reply_markup=download_keyboard
        )
        
        logger.info(f"✅ Conversión REAL completada para usuario {user_id}, archivo {file_number}")
        
    except Exception as e:
        conversion_manager.remove_conversion(user_id, file_number)
        logger.error(f"❌ Error en execute_conversion: {e}")
        await status_msg.edit_text("❌ **Error en el proceso de conversión.**")

# ===== MANEJADOR DE ARCHIVOS =====
async def handle_file(client, message):
    """Maneja la recepción de archivos"""
    try:
        user = message.from_user
        user_id = user.id

        logger.info(f"📥 Archivo recibido de {user_id}")

        user_dir = file_service.get_user_directory(user_id)

        if message.document:
            file_obj = message.document
            file_type = "video" if "video" in getattr(file_obj, 'mime_type', '') else "documento"
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

        # Sanitizar nombre y obtener número
        sanitized_name = file_service.sanitize_filename(original_filename)
        file_number = file_service.get_next_file_number(user_id)
        
        # Crear nombre almacenado con número
        _, ext = os.path.splitext(sanitized_name)
        stored_filename = f"{file_number:03d}_{sanitized_name}"
        file_path = os.path.join(user_dir, stored_filename)

        # Evitar sobreescritura
        counter = 1
        original_name_no_ext = os.path.splitext(sanitized_name)[0]
        while os.path.exists(file_path):
            stored_filename = f"{file_number:03d}_{original_name_no_ext}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        # Registrar archivo en metadata
        file_service.register_file(user_id, original_filename, stored_filename)

        # Mensaje inicial de progreso
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

        # Variables para tracking de progreso
        progress_data = {'last_update': 0}

        async def progress_callback(current, total, message, filename, user_id, start_time):
            """Callback para mostrar el progreso de la descarga"""
            try:
                # Calcular velocidad
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0

                # Actualizar cada 2 segundos o cuando haya cambio significativo
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

        # Función de progreso para Pyrogram
        async def update_progress(current, total):
            await progress_callback(current, total, progress_msg, original_filename, user_id, start_time)

        # Descargar el archivo con progreso
        downloaded_path = await message.download(
            file_path,
            progress=update_progress
        )

        if not downloaded_path:
            await progress_msg.edit_text("❌ **Error al descargar el archivo.**")
            return

        # Verificar que el archivo se descargó completamente
        final_size = os.path.getsize(file_path)
        size_mb = final_size / (1024 * 1024)

        # Generar enlace seguro
        download_url = file_service.create_download_url(user_id, stored_filename)

        success_text = f"""✅ **¡Archivo #{file_number} Almacenado Exitosamente!**

📄 **Nombre:** `{original_filename}`
📦 **Tipo:** {file_type}
💾 **Tamaño:** {size_mb:.2f} MB

🔗 **Enlace de Descarga:**
📎 [{original_filename}]({download_url})

🌐 **Explorador Web:** {RENDER_DOMAIN}/files/{user_id}"""

        try:
            # Generar hash único para el callback_data
            file_hash = file_service.create_file_hash(user_id, stored_filename)
            file_service.store_file_mapping(file_hash, user_id, stored_filename)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Abrir Enlace Web", url=download_url)],
                [
                    InlineKeyboardButton("📂 Ver Mis Archivos", callback_data="files_list"),
                    InlineKeyboardButton("🗑️ Eliminar", callback_data=f"del_{file_hash}")
                ]
            ])

            await progress_msg.edit_text(success_text, reply_markup=keyboard)

        except Exception as button_error:
            logger.error(f"❌ Error con botones: {button_error}")
            # Fallback: enviar sin botones
            await progress_msg.edit_text(success_text)

        logger.info(f"✅ Archivo guardado: {stored_filename} para usuario {user_id}")

    except Exception as e:
        logger.error(f"❌ Error procesando archivo: {e}")
        try:
            await message.reply_text("❌ **Error al procesar el archivo.** Por favor, intenta nuevamente.")
        except:
            pass

# ===== MANEJADORES DE CALLBACKS =====
async def files_callback(client, callback_query):
    """Maneja el callback de listar archivos"""
    try:
        user_id = callback_query.from_user.id
        files = file_service.list_user_files(user_id)
        
        if files:
            text = f"📁 **Tus Archivos ({len(files)}):**\n\n"
            for file in files[:5]:
                text += f"**{file['number']}.** `{file['name']}`\n"
                text += f"   🔗 [Descargar]({file['url']})\n\n"
            if len(files) > 5:
                text += f"\n... y {len(files) - 5} más"
            text += f"\n\n💡 Usa `/files` para ver la lista completa con enlaces"
        else:
            text = "📂 **No tienes archivos almacenados.**"
        
        await callback_query.message.reply_text(text, disable_web_page_preview=True)
        await callback_query.answer()

    except Exception as e:
        logger.error(f"❌ Error en callback: {e}")
        await callback_query.answer("❌ Error", show_alert=True)

async def delete_file_callback(client, callback_query):
    """Maneja el callback de eliminar archivos individuales"""
    try:
        data = callback_query.data
        
        if data.startswith("delete_"):
            file_number_str = data.replace("delete_", "")
            
            if file_number_str == "all":
                # Eliminar todos los archivos
                success, message = file_service.delete_all_files(callback_query.from_user.id)
                if success:
                    await callback_query.message.edit_text(f"✅ **{message}**")
                else:
                    await callback_query.message.edit_text(f"❌ **{message}**")
                await callback_query.answer()
                return
            
            try:
                file_number = int(file_number_str)
            except ValueError:
                await callback_query.answer("❌ Número de archivo inválido", show_alert=True)
                return
            
            user_id = callback_query.from_user.id
            
            # Confirmar eliminación
            confirm_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"confirm_delete_{file_number}"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel_delete")
                ]
            ])
            
            file_info = file_service.get_file_by_number(user_id, file_number)
            if file_info:
                await callback_query.message.edit_text(
                    f"⚠️ **¿Estás seguro de que quieres eliminar el archivo #{file_number}?**\n\n"
                    f"📄 **Archivo:** `{file_info['original_name']}`\n\n"
                    f"**Esta acción no se puede deshacer.**",
                    reply_markup=confirm_keyboard
                )
            else:
                await callback_query.answer("❌ Archivo no encontrado", show_alert=True)
            
        elif data.startswith("confirm_delete_"):
            file_number = int(data.replace("confirm_delete_", ""))
            user_id = callback_query.from_user.id
            
            success, message = file_service.delete_file_by_number(user_id, file_number)
            if success:
                await callback_query.message.edit_text(f"✅ **{message}**")
            else:
                await callback_query.message.edit_text(f"❌ **{message}**")
            
        elif data == "cancel_delete":
            await callback_query.message.edit_text("❌ **Eliminación cancelada.** Tus archivos están seguros.")
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"❌ Error eliminando archivo: {e}")
        await callback_query.answer("❌ Error eliminando archivo", show_alert=True)

async def stop_conversion_callback(client, callback_query):
    """Maneja el callback para detener una conversión"""
    try:
        data = callback_query.data.replace("stop_convert_", "")
        parts = data.split("_")
        
        if len(parts) >= 2:
            user_id = int(parts[0])
            file_number = int(parts[1])
            
            # Verificar que el usuario que cancela es el mismo que inició la conversión
            if callback_query.from_user.id != user_id:
                await callback_query.answer("❌ Solo puedes cancelar tus propias conversiones", show_alert=True)
                return
            
            # Detener la conversión
            success = conversion_manager.stop_conversion(user_id, file_number)
            
            if success:
                await callback_query.answer("⏹️ Conversión cancelada")
                await callback_query.message.edit_text(
                    "❌ **Conversión cancelada por el usuario.**\n\n"
                    "El proceso se ha detenido y se están limpiando los archivos temporales..."
                )
                logger.info(f"✅ Conversión cancelada por usuario {user_id} para archivo {file_number}")
            else:
                await callback_query.answer("❌ No se pudo cancelar la conversión", show_alert=True)
                
        else:
            await callback_query.answer("❌ Error en la solicitud de cancelación", show_alert=True)
            
    except Exception as e:
        logger.error(f"❌ Error en stop_conversion_callback: {e}")
        await callback_query.answer("❌ Error al cancelar la conversión", show_alert=True)

async def clear_compressed_callback(client, callback_query):
    """Maneja el callback para vaciar la carpeta comprimida"""
    try:
        user_id = callback_query.from_user.id
        
        # Confirmación antes de eliminar
        confirm_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Sí, eliminar todo", callback_data=f"confirm_clear_{user_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_clear")
            ]
        ])
        
        await callback_query.message.edit_text(
            "⚠️ **¿Estás seguro de que quieres eliminar TODOS tus archivos comprimidos?**\n\n"
            "**Esta acción no se puede deshacer.**",
            reply_markup=confirm_keyboard
        )
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"❌ Error en clear_compressed_callback: {e}")
        await callback_query.answer("❌ Error", show_alert=True)

async def confirm_clear_callback(client, callback_query):
    """Maneja la confirmación para vaciar la carpeta comprimida"""
    try:
        data = callback_query.data.replace("confirm_clear_", "")
        user_id = int(data)
        
        if callback_query.from_user.id != user_id:
            await callback_query.answer("❌ No puedes realizar esta acción", show_alert=True)
            return
        
        success, message = compression_service.clear_compressed_folder(user_id)
        
        if success:
            await callback_query.message.edit_text(f"✅ **{message}**")
        else:
            await callback_query.message.edit_text(f"❌ **{message}**")
            
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"❌ Error en confirm_clear_callback: {e}")
        await callback_query.answer("❌ Error al eliminar archivos", show_alert=True)

async def cancel_clear_callback(client, callback_query):
    """Maneja la cancelación de limpieza"""
    try:
        await callback_query.message.edit_text("❌ **Operación cancelada.** Tus archivos comprimidos están seguros.")
        await callback_query.answer("Operación cancelada")
    except Exception as e:
        logger.error(f"❌ Error en cancel_clear_callback: {e}")

# ===== BOT DE TELEGRAM =====
class TelegramBot:
    def __init__(self):
        self.client = None
        self.is_running = False

    async def setup_handlers(self):
        """Configura todos los handlers del bot"""
        # Comandos
        self.client.on_message(filters.command("start") & filters.private)(start_command)
        self.client.on_message(filters.command("files") & filters.private)(files_command)
        self.client.on_message(filters.command("status") & filters.private)(status_command)
        self.client.on_message(filters.command("compress") & filters.private)(compress_command)
        self.client.on_message(filters.command("rename") & filters.private)(rename_command)
        self.client.on_message(filters.command("convert") & filters.private)(convert_command)
        
        # Archivos
        self.client.on_message(
            (filters.document | filters.video | filters.audio | filters.photo) &
            filters.private
        )(handle_file)
        
        # Callbacks
        self.client.on_callback_query(filters.regex("files_list"))(files_callback)
        self.client.on_callback_query(filters.regex(r"^del_"))(delete_file_callback)
        self.client.on_callback_query(filters.regex(r"^delete_"))(delete_file_callback)
        self.client.on_callback_query(filters.regex(r"^confirm_delete_"))(delete_file_callback)
        self.client.on_callback_query(filters.regex("cancel_delete"))(delete_file_callback)
        self.client.on_callback_query(filters.regex(r"^stop_convert_"))(stop_conversion_callback)
        self.client.on_callback_query(filters.regex("clear_compressed"))(clear_compressed_callback)
        self.client.on_callback_query(filters.regex(r"^confirm_clear_"))(confirm_clear_callback)
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
            
            logger.info("🤖 Iniciando cliente de Telegram...")
            await self.client.start()

            bot_info = await self.client.get_me()
            logger.info(f"✅ Bot iniciado: @{bot_info.username}")
            
            # Verificar FFmpeg al inicio
            if video_service._check_ffmpeg():
                logger.info("✅ FFmpeg disponible para conversión de videos")
            else:
                logger.warning("❌ FFmpeg no disponible - la conversión de videos no funcionará")
            
            logger.info("🤖 El bot está listo y respondiendo a comandos")

            self.is_running = True
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"❌ Error crítico en el bot: {e}")
            self.is_running = False

    def run_bot(self):
        """Ejecuta el bot en un loop asyncio"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start_bot())
        except Exception as e:
            logger.error(f"❌ Error en el loop del bot: {e}")

# ===== INICIALIZACIÓN =====
def start_telegram_bot():
    """Inicia el bot de Telegram en un hilo separado"""
    logger.info("🤖 Iniciando bot de Telegram...")
    bot = TelegramBot()
    bot.run_bot()

def start_web_server():
    """Inicia el servidor web Flask"""
    logger.info(f"🌐 Iniciando servidor web en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    logger.info("📁 Directorio static creado/verificado")

    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()

    logger.info("🧵 Hilo del bot iniciado")

    time.sleep(10)

    logger.info("🚀 Iniciando servidor web principal...")

    start_web_server()
