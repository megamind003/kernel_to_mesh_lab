import os
import io
from typing import List, Dict, Any
from pathlib import Path
from langchain_core.documents import Document

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class MultimodalParser:
    def __init__(self):
        self.ocr_enabled = OCR_AVAILABLE
        self.whisper_enabled = WHISPER_AVAILABLE
        self.code_parser_enabled = TREE_SITTER_AVAILABLE
        
        if self.whisper_enabled:
            self.whisper_model = whisper.load_model("base")
        
    def parse_image(self, image_path: str) -> str:
        if not self.ocr_enabled:
            return ""
        
        try:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text.strip()
        except Exception as e:
            print(f"OCR failed for {image_path}: {e}")
            return ""
    
    def parse_audio(self, audio_path: str) -> str:
        if not self.whisper_enabled:
            return ""
        
        try:
            result = self.whisper_model.transcribe(audio_path)
            return result["text"].strip()
        except Exception as e:
            print(f"Audio transcription failed for {audio_path}: {e}")
            return ""
    
    def parse_code(self, code_path: str, language: str = "python") -> Dict[str, Any]:
        if not self.code_parser_enabled:
            with open(code_path, 'r', encoding='utf-8') as f:
                return {"raw_content": f.read(), "functions": [], "classes": []}
        
        try:
            with open(code_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
            
            return {
                "raw_content": code_content,
                "functions": self._extract_functions(code_content, language),
                "classes": self._extract_classes(code_content, language)
            }
        except Exception as e:
            print(f"Code parsing failed for {code_path}: {e}")
            return {"raw_content": "", "functions": [], "classes": []}
    
    def _extract_functions(self, code: str, language: str) -> List[str]:
        if language == "python":
            import re
            pattern = r'def\s+(\w+)\s*\('
            return re.findall(pattern, code)
        return []
    
    def _extract_classes(self, code: str, language: str) -> List[str]:
        if language == "python":
            import re
            pattern = r'class\s+(\w+)\s*[\(:]'
            return re.findall(pattern, code)
        return []
    
    def parse_file(self, file_path: str) -> Document:
        ext = Path(file_path).suffix.lower()
        
        if ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            content = self.parse_image(file_path)
            return Document(
                page_content=content,
                metadata={"source": file_path, "type": "image"}
            )
        
        elif ext in ['.mp3', '.wav', '.m4a', '.flac']:
            content = self.parse_audio(file_path)
            return Document(
                page_content=content,
                metadata={"source": file_path, "type": "audio"}
            )
        
        elif ext in ['.py', '.js', '.java', '.cpp', '.c', '.rs', '.go']:
            parsed = self.parse_code(file_path)
            content = f"Code from {file_path}\n\n{parsed['raw_content']}\n\nFunctions: {', '.join(parsed['functions'])}\nClasses: {', '.join(parsed['classes'])}"
            return Document(
                page_content=content,
                metadata={"source": file_path, "type": "code", "language": ext[1:]}
            )
        
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return Document(
                    page_content=content,
                    metadata={"source": file_path, "type": "text"}
                )
            except:
                return Document(
                    page_content="",
                    metadata={"source": file_path, "type": "unknown"}
                )
