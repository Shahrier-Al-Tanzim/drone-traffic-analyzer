import os
import uuid
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from engine import start_task, stop_task, get_task_state, pause_task, resume_task

app = FastAPI(title="Smart Drone Traffic Analyzer API")

# Allow CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename.endswith(('.mp4', '.avi', '.mkv', '.mov')):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    task_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}{ext}")
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    return {"task_id": task_id, "file_path": file_path, "filename": file.filename}

@app.post("/api/process/{task_id}")
async def process_video(task_id: str, file_path: str):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    start_task(task_id, file_path)
    return {"message": "Processing started", "task_id": task_id}

@app.post("/api/stop/{task_id}")
async def stop_processing(task_id: str):
    if stop_task(task_id):
        return {"message": "Processing stopped"}
    raise HTTPException(status_code=400, detail="Task not running or not found")

@app.post("/api/pause/{task_id}")
async def pause_processing(task_id: str):
    if pause_task(task_id):
        return {"message": "Processing paused"}
    raise HTTPException(status_code=400, detail="Task not processing or not found")

@app.post("/api/resume/{task_id}")
async def resume_processing(task_id: str):
    if resume_task(task_id):
        return {"message": "Processing resumed"}
    raise HTTPException(status_code=400, detail="Task not paused or not found")

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    state = get_task_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
        
    response = {
        "status": state["status"],
        "progress": state["progress"],
        "class_counts": state["class_counts"],
        "error_msg": state["error_msg"]
    }
    
    if state["status"] == "completed":
        # Return detection records, excluding internal columns
        records = state.get("records", [])
        exclude = ['confidence', 'detected_at_y']
        response["records"] = [
            {k: v for k, v in r.items() if k not in exclude}
            for r in records
        ]
        
    return response

def generate_frames(task_id: str):
    while True:
        state = get_task_state(task_id)
        if not state:
            break
            
        if state["status"] in ["completed", "error", "stopped"] and state["latest_frame"] is None:
            break
            
        frame = state.get("latest_frame")
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # Wait a bit if frame is not ready
            import time
            time.sleep(0.05)
            
        if state["status"] in ["completed", "error", "stopped"]:
            # Optionally yield the last frame a few times then break
            break

@app.get("/api/video_feed/{task_id}")
async def video_feed(task_id: str):
    state = get_task_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return StreamingResponse(generate_frames(task_id), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/report/{task_id}")
async def download_report(task_id: str):
    state = get_task_state(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if state["status"] != "completed":
        raise HTTPException(status_code=400, detail="Report not ready yet")
        
    report_path = state.get("report_path")
    if not report_path or not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Report file not found")
        
    return FileResponse(
        path=report_path,
        filename=f"traffic_report.csv",
        media_type="text/csv"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
