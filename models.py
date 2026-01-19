from dataclasses import dataclass, field
from typing import List, Dict, Optional
import os
from datetime import datetime
import re

@dataclass
class FB2Image:
    id: str
    content_type: str
    data: bytes
    original_ref: str
    actual_extension: str = ""
    
    def get_size(self) -> int:
        return len(self.data) if self.data else 0
    
    def detect_extension(self) -> str:
        if self.actual_extension:
            return self.actual_extension
            
        if not self.data:
            return ".jpg"
        
        if self.data.startswith(b'\xff\xd8'):
            return ".jpg"
        elif self.data.startswith(b'\x89PNG\r\n\x1a\n'):
            return ".png"
        elif self.data.startswith(b'GIF8'):
            return ".gif"
        elif self.data.startswith(b'BM'):
            return ".bmp"
        elif self.data.startswith(b'RIFF') and len(self.data) > 12 and self.data[8:12] == b'WEBP':
            return ".webp"
        elif self.data.startswith(b'II*\x00') or self.data.startswith(b'MM\x00*'):
            return ".tiff"
        elif self.data.startswith(b'\x00\x00\x01\x00'):
            return ".ico"
        
        if 'jpeg' in self.content_type.lower() or 'jpg' in self.content_type.lower():
            return ".jpg"
        elif 'png' in self.content_type.lower():
            return ".png"
        elif 'gif' in self.content_type.lower():
            return ".gif"
        elif 'bmp' in self.content_type.lower():
            return ".bmp"
        elif 'webp' in self.content_type.lower():
            return ".webp"
        
        return ".jpg"
    
    def get_correct_content_type(self) -> str:
        extension = self.detect_extension()
        
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
            return self.content_type

@dataclass
class BookContent:
    content: str
    filename: str
    title: str = "Unknown"
    images: Dict[str, FB2Image] = field(default_factory=dict)
    processed_content: str = ""
    sort_order: int = 0
    file_path: str = ""
    
    def get_total_size(self) -> int:
        content_size = len(self.content.encode('utf-8')) if self.content else 0
        processed_size = len(self.processed_content.encode('utf-8')) if self.processed_content else 0
        images_size = sum(img.get_size() for img in self.images.values())
        return content_size + processed_size + images_size
    
    def load_content_from_file(self):
        if not self.content and self.file_path and os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.content = f.read()
            except:
                try:
                    with open(self.file_path, 'r', encoding='cp1251') as f:
                        self.content = f.read()
                except:
                    self.content = ""

@dataclass
class UserSession:
    user_id: int
    book_contents: List[BookContent] = field(default_factory=list)
    temp_dirs: List[str] = field(default_factory=list)
    custom_series_title: str = ""
    status_message_id: Optional[int] = None
    last_file_time: Optional[datetime] = None
    
    def get_memory_usage(self) -> int:
        return sum(book.get_total_size() for book in self.book_contents)
    
    def get_book_titles(self) -> list[str]:
        return [book.title for book in self.book_contents]
    
    def get_sorted_books(self) -> list[BookContent]:
        return sorted(self.book_contents, key=lambda x: x.sort_order)
    
    def _extract_base_series_name(self, title: str) -> str:
        patterns_to_remove = [
            r'(книга|том|часть|глава|серия|часть)\s*\d+[\.,]?.*',
            r'\d+[\.,]?\s*.*',
            r'\(.*?\)',
            r'\[.*?\]',
        ]
        
        clean_title = title
        for pattern in patterns_to_remove:
            clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
        
        separators = ['\.', ':', '-', '–', '—']
        for sep in separators:
            if re.search(sep, clean_title):
                parts = re.split(sep, clean_title, 1)
                if parts[0].strip():
                    clean_title = parts[0].strip()
                    break
        
        if len(clean_title.strip()) < 3:
            match = re.match(r'^(.*?)\d', title)
            if match:
                clean_title = match.group(1).strip(' .-')
            elif '.' in title:
                clean_title = title.split('.')[0].strip()
            elif ':' in title:
                clean_title = title.split(':')[0].strip()
            else:
                words = title.split()
                clean_title = ' '.join(words[:2]) if len(words) >= 2 else title
        
        return clean_title.strip()
    
    def _get_unique_series_names(self) -> List[str]:
        series_names = []
        seen = set()
        
        for book in self.book_contents:
            series_name = self._extract_base_series_name(book.title)
            normalized = series_name.lower()
            
            is_substring = False
            for existing in list(seen):
                if normalized in existing or existing in normalized:
                    if len(normalized) < len(existing):
                        seen.remove(existing)
                        series_names = [s for s in series_names if s.lower() != existing]
                    else:
                        is_substring = True
                        break
            
            if not is_substring and normalized not in seen:
                seen.add(normalized)
                series_names.append(series_name)
        
        return series_names
    
    def get_series_title(self) -> str:
        if self.custom_series_title:
            return self.custom_series_title
        
        series_names = self._get_unique_series_names()
        
        if not series_names:
            return "Объединенные книги"
        
        if len(series_names) == 1:
            return series_names[0]
        
        if len(series_names) > 3:
            main_series = series_names[:3]
            return f"{', '.join(main_series)}, ..."
        else:
            return ', '.join(series_names)