import os
import urllib.parse
import hashlib
import json
import time
import logging
import sys
from config import BASE_DIR, RENDER_DOMAIN

logger = logging.getLogger(__name__)

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
        """Obtiene información de archivo por número (usa números mostrados)"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return None
        
        file_data = None
        original_number = None
        
        # Para archivos descargados, usar list_user_files
        if file_type == "download":
            files_list = self.list_user_files(user_id)
            for file_info in files_list:
                if file_info['number'] == file_number:
                    original_number = file_info['original_number']
                    file_data = self.metadata[user_key]["files"].get(str(original_number))
                    break
        else:
            # Para archivos empaquetados, buscar por número secuencial
            files_list = []
            packed_dir = os.path.join(BASE_DIR, str(user_id), "packed")
            if os.path.exists(packed_dir):
                file_list = os.listdir(packed_dir)
                for i, filename in enumerate(file_list, 1):
                    files_list.append({
                        'number': i,
                        'name': filename
                    })
            
            # Buscar el archivo por número mostrado
            for file_info in files_list:
                if file_info['number'] == file_number:
                    file_data = self.metadata[user_key]["files"].get(str(file_number))
                    original_number = file_number
                    break
        
        if not file_data:
            return None
        
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        file_path = os.path.join(user_dir, file_data["stored_name"])
        
        if not os.path.exists(file_path):
            return None
        
        if file_type == "download":
            download_url = self.create_download_url(user_id, file_data["stored_name"])
        else:
            download_url = self.create_packed_url(user_id, file_data["stored_name"])
        
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
            
            if file_type == "download":
                new_url = self.create_download_url(user_id, new_stored_name)
            else:
                new_url = self.create_packed_url(user_id, new_stored_name)
            
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

file_service = FileService()
