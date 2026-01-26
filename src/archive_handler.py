import zipfile
import rarfile
import tempfile
import os
import subprocess
import base64
import uuid
from pathlib import Path
from typing import List, Tuple, Dict
from src.models import BookContent, FB2Image
import xml.etree.ElementTree as ET
from lxml import etree
import imghdr

class ArchiveHandler:
    def __init__(self, use_file_storage: bool = True):
        self.supported_formats = ['.zip', '.rar', '.fb2']
        self.use_file_storage = use_file_storage
        self._setup_rarfile()
    
    def _setup_rarfile(self):
        try:
            possible_paths = [
                r"C:\Program Files\WinRAR\UnRAR.exe",
                r"C:\Program Files (x86)\WinRAR\UnRAR.exe", 
                "unrar.exe"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    rarfile.UNRAR_TOOL = path
                    return
            
            result = subprocess.run(['where', 'unrar'], capture_output=True, text=True)
            if result.returncode == 0:
                rarfile.UNRAR_TOOL = result.stdout.strip()
            else:
                self.supported_formats = [ext for ext in self.supported_formats if ext != '.rar']
                
        except Exception:
            self.supported_formats = [ext for ext in self.supported_formats if ext != '.rar']
    
    def extract_and_parse_file(self, file_path: str, user_id: int) -> Tuple[List[BookContent], str]:
        temp_dir = tempfile.mkdtemp()
        book_contents = []
        
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.zip':
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                book_contents = self._find_and_parse_fb2_files(temp_dir)
            
            elif file_ext == '.rar':
                if not rarfile.tool_setup():
                    raise Exception("Инструмент unrar неправильно настроен")
                
                with rarfile.RarFile(file_path, 'r') as rar_ref:
                    rar_ref.extractall(temp_dir)
                book_contents = self._find_and_parse_fb2_files(temp_dir)
            
            elif file_ext == '.fb2':
                book_content = self._parse_fb2_with_images(file_path)
                if book_content:
                    book_contents.append(book_content)
                os.rmdir(temp_dir)
                temp_dir = ""
            
            else:
                raise Exception(f"Неподдерживаемый формат файла: {file_ext}")
            
            return book_contents, temp_dir
            
        except Exception as e:
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
            raise Exception(f"Ошибка обработки файла: {str(e)}")
    
    def _find_and_parse_fb2_files(self, directory: str) -> List[BookContent]:
        book_contents = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.lower().endswith('.fb2'):
                    fb2_path = os.path.join(root, file)
                    book_content = self._parse_fb2_with_images(fb2_path)
                    if book_content:
                        book_contents.append(book_content)
        return book_contents
    
    def _parse_fb2_with_images(self, fb2_path: str) -> BookContent:
        try:
            parser = etree.XMLParser(recover=True)
            tree = etree.parse(fb2_path, parser)
            root = tree.getroot()
            
            ns = {'fb': 'http://www.gribuser.ru/xml/fictionbook/2.0'}
            
            title = self._extract_book_title(fb2_path)
            images = self._extract_images(root, ns, fb2_path)
            processed_content = self._process_content_with_images(root, images, ns)
            
            if self.use_file_storage:
                original_content = ""
            else:
                original_content = self._read_full_fb2(fb2_path)
            
            book_content = BookContent(
                content=original_content,
                filename=Path(fb2_path).name,
                title=title,
                images=images,
                processed_content=processed_content,
                file_path=fb2_path
            )
            
            return book_content
            
        except Exception:
            content = self._read_full_fb2(fb2_path) if not self.use_file_storage else ""
            title = self._extract_book_title(fb2_path)
            return BookContent(
                content=content,
                filename=Path(fb2_path).name,
                title=title,
                file_path=fb2_path
            )
    
    def _detect_image_extension(self, image_data: bytes) -> str:
        if not image_data:
            return ".jpg"
        
        if image_data.startswith(b'\xff\xd8'):
            return ".jpg"
        elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return ".png"
        elif image_data.startswith(b'GIF8'):
            return ".gif"
        elif image_data.startswith(b'BM'):
            return ".bmp"
        elif len(image_data) > 12 and image_data.startswith(b'RIFF') and image_data[8:12] == b'WEBP':
            return ".webp"
        elif image_data.startswith(b'II*\x00') or image_data.startswith(b'MM\x00*'):
            return ".tiff"
        elif image_data.startswith(b'\x00\x00\x01\x00'):
            return ".ico"
        
        try:
            detected = imghdr.what(None, image_data)
            if detected:
                return f".{detected}"
        except:
            pass
        
        return ".jpg"
    
    def _get_correct_content_type(self, extension: str, original_content_type: str) -> str:
        if extension in ['.jpg', '.jpeg']:
            return 'image/jpeg'
        elif extension == '.png':
            return 'image/png'
        elif extension == '.gif':
            return 'image/gif'
        elif extension == '.bmp':
            return 'image/bmp'
        elif extension == '.webp':
            return 'image/webp'
        elif extension == '.tiff':
            return 'image/tiff'
        elif extension == '.ico':
            return 'image/x-icon'
        else:
            return original_content_type
    
    def _extract_images(self, root, ns, fb2_path: str) -> Dict[str, FB2Image]:
        images = {}
        
        try:
            binary_elems = root.xpath('//fb:binary', namespaces=ns)
            
            for binary_elem in binary_elems:
                binary_id = binary_elem.get('id')
                content_type = binary_elem.get('content-type', '')
                
                if not binary_id:
                    continue
                    
                image_data_base64 = binary_elem.text
                if not image_data_base64:
                    continue
                
                try:
                    image_data = base64.b64decode(image_data_base64)
                    
                    if not self._validate_image_data(image_data, content_type):
                        continue
                    
                    actual_extension = self._detect_image_extension(image_data)
                    correct_content_type = self._get_correct_content_type(actual_extension, content_type)
                    
                    images[binary_id] = FB2Image(
                        id=binary_id,
                        content_type=correct_content_type,
                        data=image_data,
                        original_ref=f"#{binary_id}",
                        actual_extension=actual_extension
                    )
                            
                except Exception:
                    continue
                    
            image_elems = root.xpath('//fb:image', namespaces=ns)
            
            for image_elem in image_elems:
                href = image_elem.get('{{{}}}href'.format('http://www.w3.org/1999/xlink'))
                if href and href.startswith('#'):
                    image_id = href[1:]
                    if image_id not in images:
                        pass
                            
        except Exception:
            pass
            
        return images
    
    def _validate_image_data(self, image_data: bytes, content_type: str) -> bool:
        if not image_data:
            return False
        
        min_size = 50
        if len(image_data) < min_size:
            return False
        
        try:
            if image_data.startswith(b'\xff\xd8'):
                return True
            elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                return True
            elif image_data.startswith(b'GIF8'):
                return True
            elif image_data.startswith(b'BM'):
                return True
            elif len(image_data) > 12 and image_data.startswith(b'RIFF') and image_data[8:12] == b'WEBP':
                return True
            
            return True
            
        except Exception:
            return False
    
    def _process_content_with_images(self, root, images: Dict[str, FB2Image], ns) -> str:
        try:
            processed_root = etree.fromstring(etree.tostring(root))
            image_elems = processed_root.xpath('//fb:image', namespaces=ns)
            
            for image_elem in image_elems:
                href = image_elem.get('{{{}}}href'.format('http://www.w3.org/1999/xlink'))
                if href and href.startswith('#'):
                    image_id = href[1:]
                    if image_id in images:
                        new_href = f"@@IMAGE_{image_id}@@"
                        image_elem.set('{{{}}}href'.format('http://www.w3.org/1999/xlink'), new_href)
            
            return etree.tostring(processed_root, encoding='unicode', pretty_print=True)
            
        except Exception:
            return etree.tostring(root, encoding='unicode')
    
    def _read_full_fb2(self, fb2_path: str) -> str:
        try:
            encodings = ['utf-8', 'windows-1251', 'cp1251', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    with open(fb2_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    if '<?xml' in content or '<FictionBook' in content:
                        return content
                except UnicodeDecodeError:
                    continue
            
            with open(fb2_path, 'rb') as f:
                content_bytes = f.read()
            return content_bytes.decode('utf-8', errors='ignore')
            
        except Exception:
            return ""
    
    def _extract_book_title(self, fb2_path: str) -> str:
        try:
            parser = etree.XMLParser(recover=True)
            tree = etree.parse(fb2_path, parser)
            root = tree.getroot()
            
            ns = {'fb': 'http://www.gribuser.ru/xml/fictionbook/2.0'}
            
            title_elem = root.find('.//fb:book-title', namespaces=ns)
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()
                if title and title != "Unknown Title":
                    return title
            
            title_elem = root.find('.//fb:title-info/fb:book-title', namespaces=ns)
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()
                if title:
                    return title
            
            filename = Path(fb2_path).stem
            return filename if filename else "Без названия"
            
        except Exception:
            filename = Path(fb2_path).stem
            return filename if filename else "Без названия"
    
    def is_supported_file(self, filename: str) -> bool:
        if not filename:
            return False
        return any(filename.lower().endswith(ext) for ext in self.supported_formats)