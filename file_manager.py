import os
import math
import random
import time
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
import unicodedata
import re

from config import SERVER_DIR, BASE_URL

class FileManager:
    def __init__(self, user_id):
        self.user_id = str(user_id)
        self.base_dir = f"{SERVER_DIR}/{self.user_id}"
        self.downloads_dir = f"{self.base_dir}/Descargas"
        self.compressed_dir = f"{self.base_dir}/Comprimidos"
        self._create_directories()
    
    def _create_directories(self):
        """Crear directorios del usuario si no existen"""
        for directory in [self.base_dir, self.downloads_dir, self.compressed_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def get_user_directory(self):
        return self.base_dir
    
    def get_downloads_directory(self):
        return self.downloads_dir
    
    def get_compressed_directory(self):
        return self.compressed_dir
    
    def sanitize_filename(self, filename, allow_unicode=False):
        """Sanitizar nombre de archivo"""
        name = filename.strip()
        
        if allow_unicode:
            name = unicodedata.normalize('NFKC', name)
        else:
            name = unicodedata.normalize('NFKD', name)
            name = name.encode('ascii', 'ignore').decode('ascii')
        
        name = name.replace(" ", "_")
        
        if allow_unicode:
            name = re.sub(r'[^\w.-]', '', name, flags=re.UNICODE)
        else:
            name = re.sub(r'[^a-zA-Z0-9._-]', '', name)
        
        name = re.sub(r'[_\-]+', '_', name)
        name = re.sub(r'[.]+', '.', name)
        name = name.strip('_.-')
        
        return name or "archivo"
    
    def save_uploaded_file(self, file_content, filename):
        """Guardar archivo subido por el usuario"""
        sanitized_name = self.sanitize_filename(filename)
        file_path = f"{self.downloads_dir}/{sanitized_name}"
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return file_path, sanitized_name
    
    def generate_download_link(self, file_path):
        """Generar enlace de descarga directa"""
        # Convertir ruta local a ruta web
        web_path = file_path.replace(SERVER_DIR, "").lstrip('/')
        return f"{BASE_URL}/{web_path}"
    
    def get_file_info(self, file_path):
        """Obtener información del archivo"""
        file = Path(file_path)
        if not file.exists():
            return None
        
        stat = file.stat()
        size = stat.st_size
        
        # Convertir tamaño a unidades legibles
        units = ['B', 'KB', 'MB', 'GB']
        human_size = size
        for unit in units:
            if human_size < 1024:
                break
            human_size /= 1024
        
        return {
            'name': file.name,
            'size_bytes': size,
            'size_human': f"{human_size:.2f} {unit}",
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'created': datetime.fromtimestamp(stat.st_ctime),
            'download_link': self.generate_download_link(file_path)
        }
    
    def list_user_files(self, subdirectory=""):
        """Listar archivos del usuario"""
        if subdirectory:
            target_dir = f"{self.base_dir}/{subdirectory}"
        else:
            target_dir = self.base_dir
        
        path = Path(target_dir)
        if not path.exists() or not path.is_dir():
            return []
        
        files = []
        folders = []
        
        for item in path.iterdir():
            if item.is_dir():
                folders.append({
                    'name': item.name,
                    'type': 'folder',
                    'path': str(item),
                    'modified': datetime.fromtimestamp(item.stat().st_mtime)
                })
            else:
                size = item.stat().st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024*1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size/(1024*1024):.1f} MB"
                
                files.append({
                    'name': item.name,
                    'type': 'file',
                    'path': str(item),
                    'size': size_str,
                    'size_bytes': size,
                    'modified': datetime.fromtimestamp(item.stat().st_mtime),
                    'download_link': self.generate_download_link(str(item))
                })
        
        # Ordenar
        folders.sort(key=lambda x: x['name'].lower())
        files.sort(key=lambda x: x['name'].lower())
        
        return folders + files
    
    def compress_folder(self, folder_path):
        """Comprimir carpeta en ZIP"""
        folder_name = Path(folder_path).name
        zip_id = random.randint(100, 999)
        zip_filename = f"{folder_name}_{zip_id}.zip"
        zip_path = f"{self.compressed_dir}/{zip_filename}"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for foldername, subfolders, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)
                    zip_file.write(file_path, os.path.relpath(file_path, folder_path))
        
        return zip_path, zip_filename
    
    def split_file(self, file_path, part_size_mb=100):
        """Dividir archivo en partes"""
        if not os.path.isfile(file_path):
            return False
        
        file_name = os.path.basename(file_path)
        total_size = os.path.getsize(file_path)
        part_size_bytes = int(part_size_mb * 1024 * 1024)
        
        split_id = random.randint(100, 999)
        split_dir = f"{self.compressed_dir}/{file_name}_{split_id}/"
        os.makedirs(split_dir, exist_ok=True)
        
        num_parts = math.ceil(total_size / part_size_bytes)
        parts_info = []
        
        with open(file_path, 'rb') as f:
            for i in range(num_parts):
                start = i * part_size_bytes
                end = min((i + 1) * part_size_bytes, total_size)
                part_size = end - start
                
                part_name = f"{file_name}.{i+1:03d}"
                part_path = os.path.join(split_dir, part_name)
                
                with open(part_path, 'wb') as part_f:
                    f.seek(start)
                    remaining = part_size
                    while remaining > 0:
                        chunk = f.read(min(8192, remaining))
                        if not chunk:
                            break
                        part_f.write(chunk)
                        remaining -= len(chunk)
                
                parts_info.append({
                    'name': part_name,
                    'path': part_path,
                    'download_link': self.generate_download_link(part_path)
                })
        
        # Crear archivo de lista
        list_content = f"**{file_name}** - {num_parts} partes\n\n"
        for part in parts_info:
            list_content += f"{part['download_link']}\n\n"
        
        list_path = f"{split_dir}{file_name}.txt"
        with open(list_path, 'w', encoding='utf-8') as f:
            f.write(list_content)
        
        return {
            'original_file': file_name,
            'total_parts': num_parts,
            'part_size_mb': part_size_mb,
            'split_dir': split_dir,
            'parts': parts_info,
            'list_file': list_path
        }
    
    def delete_file(self, file_path):
        """Eliminar archivo o carpeta"""
        path = Path(file_path)
        if not path.exists():
            return False
        
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            return True
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
            return False
    
    def clear_directory(self, dir_path):
        """Limpiar directorio"""
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            return False
        
        try:
            for item in path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            return True
        except Exception as e:
            print(f"Error clearing directory {dir_path}: {e}")
            return False
