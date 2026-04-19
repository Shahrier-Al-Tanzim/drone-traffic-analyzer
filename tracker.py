import cv2
import time
from ultralytics import YOLO

class VehicleTracker:
    def __init__(self, model_path='yolov8l.pt'):
        # Reverting to yolov8m.pt: it provides a much better speed/accuracy trade-off than 'l' or 'n'.
        self.model = YOLO(model_path)
        self.counted_ids = set()
        self.track_history = {} # track_id -> list of (cx, cy)
        self.last_seen = {} # track_id -> (frame_idx, cx, cy, cls_name)
        self.class_counts = {}
        self.records = [] # Store detection records for the report
        
        # Add classification history for voting
        self.class_history = {} # track_id -> list of all detected classes
        self.assigned_class = {} # track_id -> current best class
        
        # Define vehicle classes we care about (COCO classes: 2=car, 3=motorcycle, 5=bus, 6=train, 7=truck)
        self.target_classes = [2, 3, 5, 6, 7] 

    def process_frame(self, frame, frame_idx, timestamp):
        # Run tracking. imgsz=1280 improves detection of tiny vehicles in the distance.
        results = self.model.track(
            frame, 
            persist=True, 
            tracker="bytetrack.yaml", 
            classes=self.target_classes,
            imgsz=1280, # 1280 is the best resolution for this model
            conf=0.05,
            verbose=False,
            device=0
        )
        
        annotated_frame = frame.copy()
        
        if results and results[0].boxes and results[0].boxes.id is not None:
            # We have tracking IDs
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            class_ids = results[0].boxes.cls.int().cpu().tolist()
            confidences = results[0].boxes.conf.cpu().numpy()
            
            for box, track_id, class_id, conf in zip(boxes, track_ids, class_ids, confidences):
                x1, y1, x2, y2 = box
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                cls_name = self.model.names[class_id]
                
                # Update class history for voting (fixes train detected as bus)
                if track_id not in self.class_history:
                    self.class_history[track_id] = []
                self.class_history[track_id].append(cls_name)
                
                # Determine the class using weighted voting (prioritizes trucks/trains/buses over cars)
                weights = {'train': 5, 'bus': 1, 'truck': 3, 'car': 1, 'motorcycle': 1}
                weighted_counts = {}
                for c in self.class_history[track_id]:
                    weighted_counts[c] = weighted_counts.get(c, 0) + weights.get(c, 1)
                best_class = max(weighted_counts, key=weighted_counts.get)
                
                # Update records and overall counts if the best class changed
                if track_id in self.assigned_class:
                    old_best = self.assigned_class[track_id]
                    if old_best != best_class and track_id in self.counted_ids:
                        # Retroactively fix the count and the report, but ONLY if it wasn't a duplicate
                        record_found = False
                        for record in self.records:
                            if record['track_id'] == track_id:
                                record['class'] = best_class
                                record_found = True
                                break
                        
                        if record_found:
                            self.class_counts[old_best] -= 1
                            self.class_counts[best_class] = self.class_counts.get(best_class, 0) + 1
                self.assigned_class[track_id] = best_class
                
                # Draw bounding box and ID using the stable best_class
                color = (0, 255, 255) if track_id in self.counted_ids else (255, 0, 0)
                cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                cv2.putText(annotated_frame, f"ID: {track_id} {best_class}", (int(x1), int(y1) - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                # Tracking history
                if track_id not in self.track_history:
                    self.track_history[track_id] = []
                self.track_history[track_id].append((cx, cy))
                
                if len(self.track_history[track_id]) > 30:
                    self.track_history[track_id].pop(0)

                # Counting logic: count immediately to catch all vehicles
                if len(self.track_history[track_id]) >= 1:
                    if track_id not in self.counted_ids:
                        # Require a much higher confidence for trains and buses to filter out background objects.
                        # Static buildings/billboards often hit 0.4, but rarely 0.5.
                        # This allows stationary trains to be counted while ignoring the billboard.
                        train_bus_thresh = 0.50 if best_class == 'train' else 0.50
                        if best_class in ['train', 'bus'] and conf < train_bus_thresh:
                            pass # Wait for a frame with much higher confidence
                        else:
                            is_duplicate = False
                            
                            # --- Smart Deduplication Logic ---
                            for old_id in list(self.counted_ids):
                                if old_id in self.last_seen and old_id != track_id:
                                    old_frame, old_cx, old_cy, old_cls = self.last_seen[old_id]
                                    if old_cls == best_class:
                                        frame_diff = frame_idx - old_frame
                                        
                                        # Train specific logic (trains are huge and span many frames)
                                        if best_class == 'train' and 0 <= frame_diff < 150:
                                            is_duplicate = True
                                            break
                                        
                                        # Other vehicles: strictly deduplicate ONLY if they are at the exact same spot 
                                        # within a split second, to avoid merging separate cars in heavy traffic
                                        elif 0 < frame_diff < 15:
                                            dist = ((cx - old_cx)**2 + (cy - old_cy)**2)**0.5
                                            if dist < 40: # Much smaller pixel distance!
                                                is_duplicate = True
                                                break
                            
                            self.counted_ids.add(track_id)
                            
                            if not is_duplicate:
                                self.class_counts[best_class] = self.class_counts.get(best_class, 0) + 1
                                
                                # Record the event for reporting
                                self.records.append({
                                    'frame_index': frame_idx,
                                    'timestamp': timestamp,
                                    'track_id': track_id,
                                    'class': best_class,
                                    'confidence': float(conf),
                                    'detected_at_y': float(cy)
                                })

                # Update last seen
                self.last_seen[track_id] = (frame_idx, cx, cy, best_class)

        return annotated_frame, self.class_counts
