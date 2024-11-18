from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QFileDialog, QProgressBar,
    QTextEdit, QSplitter, QFrame,
)

from gui.pdf_viewer import PDFViewer
from ocr.pdf_processor import PDFProcessor


class OCRWorker(QThread):
    finished = pyqtSignal()

    def __init__(self, pdf_processor):
        super().__init__()
        self.pdf_processor = pdf_processor

    def run(self):
        self.pdf_processor.process_pages()
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Search")
        self.setGeometry(100, 100, 1000, 550)

        self.pdf_processor = PDFProcessor()
        self.setup_ui()
        self.setup_connections()
        self.current_results = []

    def setup_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Top section frame
        top_frame = QFrame()
        top_frame.setFrameShape(QFrame.Shape.StyledPanel)
        top_layout = QVBoxLayout(top_frame)
        top_layout.setSpacing(4)  # Tighter spacing
        top_layout.setContentsMargins(8, 8, 8, 8)

        # File selection controls
        file_controls = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("PDF file path...")
        self.browse_button = QPushButton("Browse")
        self.browse_button.setFixedWidth(80)
        self.process_button = QPushButton("Process PDF")
        self.process_button.setFixedWidth(100)
        file_controls.addWidget(self.file_path_input)
        file_controls.addWidget(self.browse_button)
        file_controls.addWidget(self.process_button)
        top_layout.addLayout(file_controls)

        # Status bar with progress
        status_layout = QHBoxLayout()
        status_layout.setSpacing(4)
        status_layout.setContentsMargins(0, 0, 0, 0)  # Remove internal margins

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)  # Make progress bar smaller
        self.progress_bar.setTextVisible(False)  # Hide percentage text
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: none; background-color: #ddd; } QProgressBar::chunk { background-color: #4caf50; }")

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; font-size: 11px;")  # Subtle status text

        status_layout.addWidget(self.progress_bar, 1)  # Progress bar takes 1 part
        status_layout.addWidget(self.status_label, 2)  # Status label takes 2 parts
        top_layout.addLayout(status_layout)

        # Search controls
        search_controls = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search term...")
        self.search_button = QPushButton("Search")
        self.search_button.setFixedWidth(80)
        search_controls.addWidget(self.search_input)
        search_controls.addWidget(self.search_button)
        top_layout.addLayout(search_controls)

        layout.addWidget(top_frame)

        # Main content area
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # PDF viewer
        self.pdf_viewer = PDFViewer()
        splitter.addWidget(self.pdf_viewer)

        # Results pane
        results_frame = QFrame()
        results_frame.setFrameShape(QFrame.Shape.StyledPanel)
        results_layout = QVBoxLayout(results_frame)
        results_layout.setContentsMargins(4, 4, 4, 4)

        results_label = QLabel("Search Results")
        results_label.setStyleSheet("font-weight: bold;")
        results_layout.addWidget(results_label)

        self.results_pane = QTextEdit()
        self.results_pane.setReadOnly(True)
        self.results_pane.setStyleSheet("font-size: 11px; color: #333; background-color: #f9f9f9;")
        results_layout.addWidget(self.results_pane)

        splitter.addWidget(results_frame)

        # Set initial splitter sizes (give more space to PDF viewer)
        splitter.setSizes([700, 200])
        layout.addWidget(splitter)

    def setup_connections(self):
        self.browse_button.clicked.connect(self.browse_file)
        self.process_button.clicked.connect(self.process_pdf)
        self.search_button.clicked.connect(self.search_text)
        self.search_input.returnPressed.connect(self.search_text)
        self.pdf_processor.progress_updated.connect(self.update_progress)
        self.pdf_processor.status_updated.connect(self.update_status)

        # Connect PDF viewer page changes to clear highlights
        self.pdf_viewer.page_changed.connect(self.on_page_changed)

        # Make results clickable
        self.results_pane.mouseDoubleClickEvent = self.result_clicked

    def browse_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select PDF File", "", "PDF Files (*.pdf)")
        if file_name:
            self.file_path_input.setText(file_name)
            self.pdf_viewer.load_pdf(file_name)

            # Check if we have cached results
            if self.pdf_processor.load_pdf(file_name):
                if self.pdf_processor.page_texts:
                    self.update_status("Loaded OCR results from cache")
                    self.process_button.setEnabled(False)
                    self.search_button.setEnabled(True)
                else:
                    self.update_status("PDF loaded. Click 'Process PDF' to perform OCR.")
                    self.process_button.setEnabled(True)
                    self.search_button.setEnabled(False)

    def process_pdf(self):
        pdf_path = self.file_path_input.text()
        if not pdf_path:
            self.update_status("Please select a PDF file first")
            return

        if self.pdf_processor.load_pdf(pdf_path):
            self.progress_bar.setMaximum(0)  # Indeterminate progress
            self.process_button.setEnabled(False)
            self.search_button.setEnabled(False)
            self.ocr_worker = OCRWorker(self.pdf_processor)
            self.ocr_worker.finished.connect(self.on_processing_finished)
            self.ocr_worker.start()

    def on_processing_finished(self):
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(100)
        self.process_button.setEnabled(False)  # Disable since we've processed
        self.search_button.setEnabled(True)
        self.update_status("PDF processing completed")

    def search_text(self):
        keyword = self.search_input.text()
        if not keyword:
            self.update_status("Please enter a search term")
            return

        self.current_results = self.pdf_processor.search_text(keyword)
        self.display_results(self.current_results)

    def display_results(self, results):
        self.results_pane.clear()
        if not results:
            self.results_pane.append("No matches found")
            return

        self.results_pane.append(f"Found {len(results)} matches:\n")
        for i, result in enumerate(results):
            # Add result as clickable text
            cursor = self.results_pane.textCursor()
            format = cursor.charFormat()
            format.setAnchor(True)
            format.setAnchorHref(str(i))  # Store result index as href
            format.setFontUnderline(True)

            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(f"Page {result.page}: ", format)
            cursor.insertText(f"{result.context}\n\n")

    def result_clicked(self, event):
        cursor = self.results_pane.cursorForPosition(event.pos())
        format = cursor.charFormat()
        if format.isAnchor():
            result_index = int(format.anchorHref())
            if result_index < len(self.current_results):
                result = self.current_results[result_index]
                self.pdf_viewer.jump_to_result(result)

    def on_page_changed(self, page_num):
        # Clear highlights when manually changing pages
        self.pdf_viewer.clear_highlights()

    def update_progress(self, current, total):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            percentage = (current / total) * 100
            self.update_status(f"Processing page {current} of {total} ({percentage:.1f}%)")

    def update_status(self, message):
        self.status_label.setText(message)
