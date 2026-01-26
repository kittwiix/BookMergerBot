import os
import tempfile
import shutil
from pathlib import Path
from src.models import BookContent, FB2Image
from typing import List, Dict
import xml.etree.ElementTree as ET
from lxml import etree
import base64
import uuid
import re

class FB2Merger:
    def __init__(self, max_memory_mb: int = 2048):
        self.max_memory_mb = max_memory_mb
        
    def create_merged_fb2(self, book_contents: list[BookContent], output_path: str, series_title: str = None) -> bool:
        try:
            if not series_title:
                from models import UserSession
                temp_session = UserSession(user_id=0)
                temp_session.book_contents = book_contents
                series_title = temp_session.get_series_title()
            
            all_images = self._collect_all_images(book_contents)
            
            success = self._create_clean_merged_fb2(
                book_contents, 
                output_path, 
                series_title, 
                all_images
            )
            
            if success and os.path.exists(output_path):
                return True
            else:
                return False
            
        except Exception:
            return False
    
    def _collect_all_images(self, book_contents: list[BookContent]) -> Dict[str, FB2Image]:
        all_images = {}
        image_counter = 1
        
        for book in book_contents:
            for old_image_id, image in book.images.items():
                new_image_id = f"img_{image_counter:04d}"
                image_counter += 1
                
                actual_extension = image.detect_extension()
                correct_content_type = image.get_correct_content_type()
                
                all_images[new_image_id] = FB2Image(
                    id=new_image_id,
                    content_type=correct_content_type,
                    data=image.data,
                    original_ref=image.original_ref,
                    actual_extension=actual_extension
                )
                
                if not hasattr(book, 'image_mapping'):
                    book.image_mapping = {}
                book.image_mapping[old_image_id] = new_image_id
        
        return all_images
    
    def _create_clean_merged_fb2(self, book_contents: list[BookContent], 
                                output_path: str, series_title: str, 
                                all_images: Dict[str, FB2Image]) -> bool:
        
        try:
            nsmap = {
                None: 'http://www.gribuser.ru/xml/fictionbook/2.0',
                'xlink': 'http://www.w3.org/1999/xlink'
            }
            
            root = etree.Element('FictionBook', nsmap=nsmap)
            
            description = etree.SubElement(root, 'description')
            title_info = etree.SubElement(description, 'title-info')
            
            book_title = etree.SubElement(title_info, 'book-title')
            book_title.text = series_title
            
            author = etree.SubElement(title_info, 'author')
            first_name = etree.SubElement(author, 'first-name')
            first_name.text = "Объединенный"
            last_name = etree.SubElement(author, 'last-name')
            last_name.text = "Сборник"
            
            annotation = etree.SubElement(title_info, 'annotation')
            annotation_p = etree.SubElement(annotation, 'p')
            annotation_p.text = f"Объединенный сборник из {len(book_contents)} книг"
            
            date = etree.SubElement(title_info, 'date')
            date.text = "2024"
            date.set('value', '2024')
            
            for image_id, image in all_images.items():
                binary_elem = etree.Element('binary')
                binary_elem.set('id', image_id)
                binary_elem.set('content-type', image.content_type)
                
                try:
                    image_data_base64 = base64.b64encode(image.data).decode('utf-8')
                    binary_elem.text = image_data_base64
                    
                    root.append(binary_elem)
                    
                except Exception:
                    continue
            
            body = etree.SubElement(root, 'body')
            
            for i, book_content in enumerate(book_contents):
                book_section = etree.SubElement(body, 'section')
                
                book_body_content = self._get_clean_processed_content(book_content)
                if book_body_content:
                    try:
                        book_parser = etree.XMLParser(recover=True)
                        book_root = etree.fromstring(f"<root>{book_body_content}</root>".encode('utf-8'), book_parser)
                        
                        for elem in book_root:
                            book_section.append(elem)
                            
                    except Exception:
                        error_p = etree.Element('p')
                        error_p.text = f"[Ошибка загрузки книги: {book_content.title}]"
                        book_section.append(error_p)
                else:
                    empty_p = etree.Element('p')
                    empty_p.text = f"[Содержимое книги '{book_content.title}' отсутствует]"
                    book_section.append(empty_p)
            
            tree = etree.ElementTree(root)
            
            with open(output_path, 'wb') as f:
                f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
                tree.write(f, encoding='utf-8', pretty_print=True, xml_declaration=False)
            
            return True
            
        except Exception:
            return False
    
    def _get_clean_processed_content(self, book_content: BookContent) -> str:
        try:
            if hasattr(book_content, 'processed_content') and book_content.processed_content:
                content = book_content.processed_content
                
                content = self._clean_body_content(content)
                
                if hasattr(book_content, 'image_mapping'):
                    for old_id, new_id in book_content.image_mapping.items():
                        content = content.replace(f'@@IMAGE_{old_id}@@', f'#{new_id}')
                
                return content
            else:
                content = book_content.content
                return self._clean_body_content(content) if content else ""
                
        except Exception:
            return book_content.content if book_content.content else ""
    
    def _clean_body_content(self, content: str) -> str:
        try:
            parser = etree.XMLParser(recover=True)
            root = etree.fromstring(f"<root>{content}</root>".encode('utf-8'), parser)
            
            binary_elems = root.xpath('//binary')
            for binary_elem in binary_elems:
                parent = binary_elem.getparent()
                if parent is not None:
                    parent.remove(binary_elem)
            
            for elem in root.iter():
                if elem.text and len(elem.text) > 100 and self._looks_like_base64(elem.text):
                    elem.text = ""
                
                if elem.tail and len(elem.tail) > 100 and self._looks_like_base64(elem.tail):
                    elem.tail = ""
            
            cleaned_content = ''.join([etree.tostring(child, encoding='unicode', method='xml') 
                                     for child in root])
            return cleaned_content.replace('<root>', '').replace('</root>', '')
            
        except Exception:
            return content
    
    def _looks_like_base64(self, text: str) -> bool:
        if not text or len(text) < 100:
            return False
        
        base64_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        text_chars = set(text)
        
        base64_ratio = len([c for c in text if c in base64_chars]) / len(text)
        return base64_ratio > 0.9

    def _ensure_books_content_loaded(self, book_contents: list[BookContent]):
        for book in book_contents:
            if not book.content and book.file_path:
                book.load_content_from_file()
