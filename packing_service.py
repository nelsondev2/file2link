import os
import zipfile
import time
import logging
import sys
import concurrent.futures
from config import BASE_DIR, MAX_PART_SIZE_MB
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)

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
        """Empaqueta en un solo archivo ZIP SIN compresión - CORREGIDO"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            # Obtener lista completa de archivos
            all_files = []
            total_files = 0
            
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    all_files.append((filename, file_path))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar"
            
            logger.info(f"Empaquetando {total_files} archivos en {output_file}")
            
            # Crear ZIP con todos los archivos
            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename, file_path in all_files:
                    try:
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado al ZIP: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP: {e}")
                        continue
            
            file_size = os.path.getsize(output_file)
            size_mb = file_size / (1024 * 1024)
            
            # Registrar archivo empaquetado
            file_num = file_service.register_file(user_id, f"{base_filename}.zip", f"{base_filename}.zip", "packed")
            
            download_url = file_service.create_packed_url(user_id, f"{base_filename}.zip")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'size_mb': size_mb,
                'total_files': total_files
            }], f"Empaquetado completado: {total_files} archivos, {size_mb:.1f}MB"
            
        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            logger.error(f"Error en _pack_single_simple: {e}")
            raise e
    
    def _pack_split_simple(self, user_id, user_dir, packed_dir, base_filename, split_size_mb):
        """Empaqueta y divide en partes SIN compresión - CORREGIDO"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            # Obtener lista completa de archivos
            all_files = []
            total_files = 0
            
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    all_files.append((filename, file_path))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar"
            
            # Primero empaquetar todo en un ZIP temporal SIN compresión
            temp_file = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            
            logger.info(f"Creando archivo temporal con {total_files} archivos")
            
            with zipfile.ZipFile(temp_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename, file_path in all_files:
                    try:
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado al ZIP temporal: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP temporal: {e}")
                        continue
            
            # Dividir el archivo empaquetado
            part_files = []
            part_num = 1
            
            logger.info(f"Dividiendo archivo temporal en partes de {split_size_mb}MB")
            
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
                    
                    # Registrar cada parte
                    file_num = file_service.register_file(user_id, part_filename, part_filename, "packed")
                    
                    part_files.append({
                        'number': file_num,
                        'filename': part_filename,
                        'url': download_url,
                        'size_mb': part_size / (1024 * 1024)
                    })
                    
                    logger.info(f"Creada parte {part_num}: {part_filename} ({part_size/(1024*1024):.1f}MB)")
                    part_num += 1
            
            os.remove(temp_file)
            
            total_size = sum(part['size_mb'] for part in part_files)
            return part_files, f"Empaquetado completado: {len(part_files)} partes, {total_files} archivos, {total_size:.1f}MB total"
            
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            logger.error(f"Error en _pack_split_simple: {e}")
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

packing_service = SimplePackingService()
