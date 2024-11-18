import io
import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Dict

import fitz
import numpy as np
from PIL import Image
from PyQt6.QtCore import QObject, pyqtSignal
from paddleocr import PaddleOCR


@dataclass
class SearchResult:
    page: int
    context: str
    position: int
    bbox: tuple  # (x0, y0, x1, y1)


class PDFProcessor(QObject):
    progress_updated = pyqtSignal(int, int)  # current, total
    status_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ocr = PaddleOCR(use_angle_cls=True, lang='en')
        self.current_pdf = None
        self.page_texts = []
        self.word_locations = {}  # Store word locations for highlighting
        self.cache_dir = "ocr_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_path(self, pdf_path: str) -> str:
        pdf_hash = str(hash(pdf_path + str(os.path.getmtime(pdf_path))))
        return os.path.join(self.cache_dir, f"{pdf_hash}.json")

    def load_pdf(self, pdf_path: str) -> bool:
        try:
            self.current_pdf = fitz.open(pdf_path)
            cache_path = self.get_cache_path(pdf_path)

            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    self.page_texts = cached_data['texts']
                    self.word_locations = cached_data['locations']
                    self.status_updated.emit("Loaded OCR results from cache")
                    return True

            self.page_texts = []
            self.word_locations = {}
            return True
        except Exception as e:
            self.status_updated.emit(f"Error loading PDF: {str(e)}")
            return False

    def process_pages(self):
        if not self.current_pdf:
            return

        total_pages = len(self.current_pdf)
        self.page_texts = []
        self.word_locations = {}

        for page_num in range(total_pages):
            try:
                page = self.current_pdf[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                img_array = np.array(img)

                result = self.ocr.ocr(img_array, cls=True)

                page_text = []
                page_locations = {}

                if result:
                    for line in result:
                        for word_info in line:
                            text = word_info[1][0]
                            bbox = word_info[0]  # [[x0,y0], [x1,y1], [x2,y2], [x3,y3]]
                            # Convert coordinates to simple rectangle
                            x0 = min(point[0] for point in bbox) / 2  # Divide by 2 due to Matrix(2, 2)
                            y0 = min(point[1] for point in bbox) / 2
                            x1 = max(point[0] for point in bbox) / 2
                            y1 = max(point[1] for point in bbox) / 2

                            page_text.append(text)
                            page_locations[len(page_text) - 1] = (x0, y0, x1, y1)

                self.page_texts.append(' '.join(page_text))
                self.word_locations[page_num] = page_locations
                self.progress_updated.emit(page_num + 1, total_pages)

            except Exception as e:
                self.status_updated.emit(f"Error processing page {page_num + 1}: {str(e)}")
                continue

        # Save to cache
        try:
            cache_path = self.get_cache_path(self.current_pdf.name)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'texts': self.page_texts,
                    'locations': self.word_locations
                }, f)
        except Exception as e:
            self.status_updated.emit(f"Error saving cache: {str(e)}")

    def search_text(self, keyword: str) -> List[SearchResult]:
        matches = []
        for page_num, page_text in enumerate(self.page_texts, 1):
            found = re.finditer(re.escape(keyword), page_text, re.IGNORECASE)
            for match in found:
                start = max(0, match.start() - 50)
                end = min(len(page_text), match.end() + 50)
                context = page_text[start:end]
                context = re.sub(
                    f'({re.escape(keyword)})',
                    r'**\1**',
                    context,
                    flags=re.IGNORECASE
                )

                # Get bbox from word_locations
                word_index = len(page_text[:match.start()].split())
                bbox = self.word_locations.get(page_num - 1, {}).get(word_index, (0, 0, 0, 0))

                matches.append(SearchResult(
                    page=page_num,
                    context=f"...{context}...",
                    position=match.start(),
                    bbox=bbox
                ))
        return matches
