import sys
import os
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox, QGroupBox, QFormLayout
)
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtCore import Qt

from worker import VideoProcessorWorker
from report_generator import generate_report

class SmartDroneAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Drone Traffic Analyzer")
        self.resize(1000, 700)
        
        self.video_path = None
        self.worker = None
        self.records = []
        self.duration = 0.0
        
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Top panel for controls
        control_layout = QHBoxLayout()
        
        self.btn_upload = QPushButton("Upload Video")
        self.btn_upload.clicked.connect(self.upload_video)
        control_layout.addWidget(self.btn_upload)
        
        self.btn_start = QPushButton("Start Processing")
        self.btn_start.clicked.connect(self.start_processing)
        self.btn_start.setEnabled(False)
        control_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("Stop/Cancel")
        self.btn_stop.clicked.connect(self.stop_processing)
        self.btn_stop.setEnabled(False)
        control_layout.addWidget(self.btn_stop)
        
        main_layout.addLayout(control_layout)
        
        # File path label
        self.lbl_file = QLabel("No video selected.")
        self.lbl_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_file)
        
        # Video display area
        self.lbl_video = QLabel("Video Player")
        self.lbl_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_video.setStyleSheet("background-color: black; color: white; border: 1px solid gray;")
        self.lbl_video.setMinimumSize(640, 360)
        main_layout.addWidget(self.lbl_video, stretch=1)
        
        # Bottom panel for stats and progress
        bottom_layout = QHBoxLayout()
        
        # Stats Group
        stats_group = QGroupBox("Live Statistics")
        stats_layout = QVBoxLayout()
        self.lbl_total_count = QLabel("Total Unique Vehicles: 0")
        self.lbl_total_count.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.lbl_breakdown = QLabel("Breakdown: None")
        stats_layout.addWidget(self.lbl_total_count)
        stats_layout.addWidget(self.lbl_breakdown)
        stats_group.setLayout(stats_layout)
        bottom_layout.addWidget(stats_group)
        
        # Progress and report
        prog_rep_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        prog_rep_layout.addWidget(self.progress_bar)
        
        self.btn_download = QPushButton("Download Report (CSV)")
        self.btn_download.clicked.connect(self.download_report)
        self.btn_download.setEnabled(False)
        prog_rep_layout.addWidget(self.btn_download)
        
        bottom_layout.addLayout(prog_rep_layout)
        
        main_layout.addLayout(bottom_layout)

    def upload_video(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if file_name:
            self.video_path = file_name
            self.lbl_file.setText(f"Selected: {os.path.basename(self.video_path)}")
            self.btn_start.setEnabled(True)
            self.btn_download.setEnabled(False)
            self.progress_bar.setValue(0)
            self.lbl_total_count.setText("Total Unique Vehicles: 0")
            self.lbl_breakdown.setText("Breakdown: None")
            self.records = []
            
            # Show first frame
            cap = cv2.VideoCapture(self.video_path)
            ret, frame = cap.read()
            if ret:
                self.update_video_frame(frame)
            cap.release()

    def start_processing(self):
        if not self.video_path:
            return
            
        self.btn_upload.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(0)
        
        self.worker = VideoProcessorWorker(self.video_path)
        self.worker.frame_ready.connect(self.update_video_frame)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.stats_updated.connect(self.update_stats)
        self.worker.finished_processing.connect(self.processing_finished)
        self.worker.error_occurred.connect(self.handle_error)
        
        self.worker.start()

    def stop_processing(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self.btn_upload.setEnabled(True)
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.lbl_file.setText("Processing Stopped.")

    def update_video_frame(self, frame):
        # Convert OpenCV BGR frame to Qt RGB
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Scale to fit label maintaining aspect ratio
        pixmap = QPixmap.fromImage(qt_img)
        scaled_pixmap = pixmap.scaled(
            self.lbl_video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_video.setPixmap(scaled_pixmap)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_stats(self, class_counts):
        total = sum(class_counts.values())
        self.lbl_total_count.setText(f"Total Unique Vehicles: {total}")
        
        breakdown_str = ", ".join([f"{k}: {v}" for k, v in class_counts.items()])
        self.lbl_breakdown.setText(f"Breakdown: {breakdown_str if breakdown_str else 'None'}")

    def processing_finished(self, records, duration):
        self.records = records
        self.duration = duration
        self.progress_bar.setValue(100)
        self.btn_upload.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_download.setEnabled(True)
        QMessageBox.information(self, "Success", "Video processing complete!")

    def handle_error(self, error_msg):
        QMessageBox.critical(self, "Error", f"An error occurred: {error_msg}")
        self.stop_processing()

    def download_report(self):
        if not self.records:
            QMessageBox.warning(self, "Warning", "No tracking data available to download.")
            return
            
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "traffic_report.csv", "CSV Files (*.csv);;Excel Files (*.xlsx)"
        )
        
        if file_name:
            try:
                generate_report(self.records, self.duration, file_name)
                QMessageBox.information(self, "Success", f"Report saved successfully to:\n{file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save report: {str(e)}")

    def resizeEvent(self, event):
        # Called when window is resized. Re-scaling of the pixmap could be handled here 
        # but for simplicity we rely on the next frame update to scale to new size.
        super().resizeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set modern dark style
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(app.palette().ColorRole.Window, Qt.GlobalColor.darkGray)
    app.setPalette(palette)
    
    window = SmartDroneAnalyzer()
    window.show()
    sys.exit(app.exec())
