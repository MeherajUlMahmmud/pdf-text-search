import fitz
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea, QSpinBox,
)

from ocr.pdf_processor import SearchResult


class PDFViewer(QWidget):
    page_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.current_pdf = None
        self.current_page = 0
        self.highlights = []  # List of bbox tuples to highlight
        self.zoom_level = 1.0

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Navigation controls
        nav_layout = QHBoxLayout()

        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_page)

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.page_spin_changed)

        self.total_pages_label = QLabel("/ 0")

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_page)

        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_in_button.clicked.connect(self.zoom_in)

        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_out_button.clicked.connect(self.zoom_out)

        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.page_spin)
        nav_layout.addWidget(self.total_pages_label)
        nav_layout.addWidget(self.next_button)
        nav_layout.addWidget(self.zoom_in_button)
        nav_layout.addWidget(self.zoom_out_button)

        layout.addLayout(nav_layout)

        # Scroll area for PDF content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.content_label = QLabel()
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.content_label)

        layout.addWidget(self.scroll_area)

    def load_pdf(self, pdf_path):
        try:
            self.current_pdf = fitz.open(pdf_path)
            self.page_spin.setMaximum(len(self.current_pdf))
            self.total_pages_label.setText(f"/ {len(self.current_pdf)}")
            self.show_page(0)
        except Exception as e:
            self.content_label.setText(f"Error loading PDF: {str(e)}")

    def show_page(self, page_num):
        if not self.current_pdf:
            return

        if 0 <= page_num < len(self.current_pdf):
            self.current_page = page_num
            self.page_spin.setValue(page_num + 1)
            self.render_page()
            self.page_changed.emit(page_num)

    def render_page(self):
        if not self.current_pdf:
            return

        page = self.current_pdf[self.current_page]
        zoom_matrix = fitz.Matrix(2.0 * self.zoom_level, 2.0 * self.zoom_level)
        pix = page.get_pixmap(matrix=zoom_matrix)

        # Convert to QPixmap
        img_data = pix.tobytes("ppm")
        qpixmap = QPixmap()
        qpixmap.loadFromData(img_data)

        # Draw highlights if any
        if self.highlights:
            painter = QPainter(qpixmap)
            painter.setOpacity(0.3)
            painter.setPen(QPen(QColor('yellow'), 2))
            painter.setBrush(QColor('yellow'))

            for bbox in self.highlights:
                x0, y0, x1, y1 = [coord * 2 * self.zoom_level for coord in bbox]
                painter.drawRect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))

            painter.end()

        self.content_label.setPixmap(qpixmap)

    def set_highlights(self, highlights):
        self.highlights = highlights
        self.render_page()

    def clear_highlights(self):
        self.highlights = []
        self.render_page()

    def previous_page(self):
        if self.current_page > 0:
            self.show_page(self.current_page - 1)

    def next_page(self):
        if self.current_page < len(self.current_pdf) - 1:
            self.show_page(self.current_page + 1)

    def page_spin_changed(self, value):
        self.show_page(value - 1)

    def zoom_in(self):
        self.zoom_level = min(3.0, self.zoom_level + 0.2)
        self.render_page()

    def zoom_out(self):
        self.zoom_level = max(0.4, self.zoom_level - 0.2)
        self.render_page()

    def jump_to_result(self, result: SearchResult):
        self.show_page(result.page - 1)
        self.set_highlights([result.bbox])
