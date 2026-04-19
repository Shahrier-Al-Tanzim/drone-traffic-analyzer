import cv2
import time
from PyQt6.QtCore import QThread, pyqtSignal
from tracker import VehicleTracker
import numpy as np

class VideoProcessorWorker(QThread):
    # Signals to communicate with the main GUI thread
    frame_ready = pyqtSignal(np.ndarray)
    progress_updated = pyqtSignal(int)
    stats_updated = pyqtSignal(dict)
    finished_processing = pyqtSignal(list, float) # passes records and duration
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.is_running = True
        self.tracker = None

    def run(self):
        try:
            self.tracker = VehicleTracker()
            cap = cv2.VideoCapture(self.video_path)
            
            if not cap.isOpened():
                self.error_occurred.emit(f"Failed to open video: {self.video_path}")
                return

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps == 0:
                fps = 30.0

            frame_idx = 0
            start_time = time.time()

            # For drone videos, capture dimensions if needed
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    break

                timestamp = frame_idx / fps
                
                # Process frame
                annotated_frame, class_counts = self.tracker.process_frame(
                    frame, frame_idx, timestamp
                )

                # Emit updates
                self.frame_ready.emit(annotated_frame)
                self.stats_updated.emit(class_counts)
                
                # Update progress
                progress = int(((frame_idx + 1) / total_frames) * 100)
                self.progress_updated.emit(progress)

                frame_idx += 1

                # Add a small sleep to prevent freezing the UI thread completely
                # and to allow visual observation of the playback
                QThread.msleep(10)

            cap.release()
            
            duration = time.time() - start_time
            if self.is_running: # natural finish
                self.finished_processing.emit(self.tracker.records, duration)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.is_running = False
