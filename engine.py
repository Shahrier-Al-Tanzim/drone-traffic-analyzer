import cv2
import time
import threading
import os
import traceback
import glob
import re
from tracker import VehicleTracker
from report_generator import generate_report

# Global dictionary to store the state of all tasks
# Structure:
# {
#   task_id: {
#       "status": "pending" | "processing" | "completed" | "error",
#       "progress": 0-100,
#       "class_counts": {},
#       "error_msg": "",
#       "latest_frame": None,  # Will hold the latest annotated frame (numpy array)
#       "records": [],
#       "duration": 0.0,
#       "report_path": "",
#       "_stop_event": threading.Event(),
#       "_pause_event": threading.Event() # Set = running, Clear = paused
#   }
# }
task_states = {}

def get_next_report_number():
    """Finds the next available report number by scanning the directory."""
    files = glob.glob("traffic_report_*.csv")
    max_num = 0
    for f in files:
        # Match filenames like traffic_report_1.csv, traffic_report_10.csv
        match = re.search(r"traffic_report_(\d+)\.csv", f)
        if match:
            try:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
    return max_num + 1

def get_task_state(task_id):
    if task_id not in task_states:
        return None
    return task_states[task_id]

def stop_task(task_id):
    state = get_task_state(task_id)
    if state and "status" in state and state["status"] in ["processing", "paused"]:
        if "_stop_event" in state:
            state["_stop_event"].set()
        if "_pause_event" in state:
            state["_pause_event"].set() # Unblock if paused
        return True
    return False

def pause_task(task_id):
    state = get_task_state(task_id)
    if state and state["status"] == "processing":
        state["_pause_event"].clear()
        state["status"] = "paused"
        return True
    return False

def resume_task(task_id):
    state = get_task_state(task_id)
    if state and state["status"] == "paused":
        state["_pause_event"].set()
        state["status"] = "processing"
        return True
    return False

def _process_video(task_id, video_path):
    state = task_states[task_id]
    state["status"] = "processing"
    
    tracker = None
    try:
        tracker = VehicleTracker()
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            state["status"] = "error"
            state["error_msg"] = f"Failed to open video: {video_path}"
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            fps = 30.0

        frame_idx = 0
        start_time = time.time()

        while not state["_stop_event"].is_set():
            # Check for pause
            state["_pause_event"].wait()
            
            if state["_stop_event"].is_set():
                break

            ret, frame = cap.read()
            if not ret:
                break

            timestamp = frame_idx / fps
            
            # Process frame
            annotated_frame, class_counts = tracker.process_frame(
                frame, frame_idx, timestamp
            )

            # Update state
            state["latest_frame"] = annotated_frame
            state["class_counts"] = class_counts
            
            progress = int(((frame_idx + 1) / total_frames) * 100)
            state["progress"] = progress

            frame_idx += 1

            # Small sleep to yield to other threads
            time.sleep(0.01)

        cap.release()
        
        duration = time.time() - start_time
        state["duration"] = duration
        state["records"] = tracker.records
        
        if not state["_stop_event"].is_set():
            # Generate report with sequential numerical naming
            report_num = get_next_report_number()
            report_filename = f"traffic_report_{report_num}.csv"
            generate_report(tracker.records, duration, report_filename)
            state["report_path"] = report_filename
            state["status"] = "completed"
            state["progress"] = 100
        else:
            state["status"] = "stopped"

    except Exception as e:
        traceback.print_exc()
        state["status"] = "error"
        state["error_msg"] = str(e)

def start_task(task_id, video_path):
    task_states[task_id] = {
        "status": "pending",
        "progress": 0,
        "class_counts": {},
        "error_msg": "",
        "latest_frame": None,
        "records": [],
        "duration": 0.0,
        "report_path": "",
        "_stop_event": threading.Event(),
        "_pause_event": threading.Event()
    }
    task_states[task_id]["_pause_event"].set() # Start in running state
    
    thread = threading.Thread(target=_process_video, args=(task_id, video_path), daemon=True)
    thread.start()
    return task_id
