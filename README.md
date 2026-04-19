# Smart Drone Traffic Analyzer

A robust, production-ready full-stack application designed to process drone video footage, detect and track vehicles with high accuracy, and generate detailed traffic analysis reports.

---

## 1. Computer Vision & Tracking Methodology

The core of this application relies on a state-of-the-art computer vision pipeline designed specifically for overhead drone footage.

- **Detection**: Utilizes **YOLOv8** (Large/Medium) configured with a high resolution (**`imgsz=1280`**) to accurately identify small vehicles from high altitudes. The base confidence threshold is kept low (`conf=0.05`) to maximize recall for distant vehicles.
- **Tracking**: Integrates **ByteTrack** (`bytetrack.yaml`) for resilient bounding box association across multiple frames, smoothly handling temporary occlusions (e.g., vehicles passing under trees or signs).

### Advanced Classification Logic
Since a vehicle's appearance can drastically change angle frame-by-frame, the tracker utilizes a **Weighted Voting System**. The tracker stores the rolling history of predicted classes for a given tracking ID. Because large vehicles are often temporarily misclassified as cars, the voting system heavily prioritizes larger vehicles:
- `Train: 5 points`
- `Truck: 3 points`
- `Bus: 1 point`
- `Car: 1 point`
- `Motorcycle: 1 point`

### The Challenge
The most significant challenge in this project is accurately counting unique vehicles passing through the scene while accounting for edge cases such as vehicles stopping, slowing down, or temporary occlusions. Handling these false positives and double-counting scenarios is achieved through strict spatial and temporal deduplication logic:
- **Temporary Occlusions**: The underlying **ByteTrack** algorithm inherently handles vehicles passing under trees or signs by maintaining track ID history even when bounding boxes temporarily vanish.
- **Vehicles Stopping or Slowing Down**: To prevent double-counting vehicles that stop (like at a traffic light or parked cars) and then move again or lose tracking ID, the system compares the exact Euclidean distance of the centroid of new IDs against recently expired/lost IDs. If a new ID appears within 40 pixels of an old ID's last known location within a short 15-frame gap, it is classified as the same vehicle and ignored in the final count.
- **Train Handling**: Trains are exceptionally long and span across hundreds of frames, heavily disrupting standard trackers. We implemented a custom temporal threshold allowing up to a 150-frame gap for train IDs to be merged, preventing a single train from being counted as multiple vehicles.
- **Billboard False Positives**: To prevent stationary background elements (like billboards) from being repeatedly identified as vehicles across different track IDs, the pipeline enforces a strict, independent confidence threshold (strictly **conf >= 0.50** for trains and buses) before they are admitted into the count logic. Standard vehicles remain at the high-recall 0.05 baseline.

---

## 2. Architecture Breakdown

The project transitioned from a monolithic Desktop GUI to a modern, decoupled **Web Application Architecture**.

### Backend (Python / FastAPI)
The backend acts as a highly concurrent REST API server serving the computer vision engine.
- **Endpoints**: Exposes `/api/upload`, `/api/process`, `/api/pause`, `/api/resume`, `/api/stop`, `/api/status`, `/api/video_feed`, and `/api/report`.
- **Threading Model**: Processing heavy video files directly blocks HTTP requests. To solve this, the processing engine (`engine.py`) initializes a native Python background daemon thread for each `task_id`. 
- **State Management**: The background thread continually updates a global memory dictionary with the latest processing progress, current statistics, and the most recent annotated frame buffer.
- **Real-time Data Delivery**: The `/api/status` endpoint now provides a live JSON array of detection records (timestamp, track ID, vehicle class) alongside general progress, allowing the frontend to render a real-time detection table.
- **Video Streaming**: The `video_feed` endpoint leverages a `StreamingResponse` using the `multipart/x-mixed-replace` content type. This allows the API to continuously push JPEG-encoded frames directly to the browser over a single HTTP connection.

### Frontend (Next.js / React)
The frontend is a lightweight, fully decoupled client utilizing Next.js (App Router).
- **Polling**: While the video processes, a React `useEffect` hook polls the `/api/status` endpoint every 1000ms. This keeps the progress bar and live breakdown statistics perfectly synchronized with the backend.
- **Dynamic UI**: The React state securely manages the transitions (idle -> uploading -> ready -> processing -> completed), ensuring the user interface only presents valid actions (disabling the start button until an upload completes, and allowing seamless re-uploads).

---

## 3. Engineering Assumptions

1. **Resolution & Resources**: We assume the host machine possesses decent processing capabilities. `imgsz=1280` is computationally expensive but mandatory for small-object drone detection.
2. **Prioritization of Recall**: The system prioritizes capturing every moving vehicle over aggressively filtering the scene. The low `0.05` base threshold guarantees cars aren't missed, while specific logic (like the **0.50 train and bus** check) precisely surgical-strikes the edge-case false positives.
3. **Sequential Reporting**: Reports are generated with sequential numerical naming (e.g., `traffic_report_1.csv`) to prevent accidental overwrites during multi-session analysis.
4. **Stateless Operations**: Currently, the `task_states` dictionary is stored in application memory. If the server crashes, active processing data is lost.

---

## 4. Local Setup Instructions & Requirements

Follow these steps to deploy the Smart Drone Analyzer on your local machine.

### Step 1: System Prerequisites
- **Python 3.10+**: We recommend using [Conda](https://docs.conda.io/en/latest/) for environment management.
- **Node.js 18+**: Required to run the Next.js frontend.
- **NVIDIA GPU (Recommended specifically for this codebase)**: If you have an NVIDIA GPU, ensure [CUDA](https://developer.nvidia.com/cuda-toolkit) is installed for 10x faster processing.

### Step 2: Backend Environment Setup
1. Open your terminal in the project root directory.
2. Create and activate a new virtual environment:
   ```bash
   # Using Conda (Recommended)
   conda env create -f environment.yml
   conda activate vehicle-detection

   # OR using standard venv
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate

   pip install fastapi uvicorn python-multipart ultralytics opencv-python pandas openpyxl lapx
   ```
3. Start the FastAPI backend server:
   ```bash
   python server.py
   ```
   > [!NOTE]
   > The backend will initialize at `http://localhost:8000`. It will automatically download the YOLOv8 model weights on the first run.

### Step 3: Frontend Interface Setup
1. Open a **new and separate** terminal window.
2. Navigate into the `frontend` directory:
   ```bash
   cd frontend
   ```
3. Install the dependencies and start the development server:
   ```bash
   npm install
   npm run dev
   ```
   > [!TIP]
   > The frontend is now running at `http://localhost:3000`.

### Step 4: Running the Analysis
1. Open your browser to `http://localhost:3000`.
2. Click **Upload Video** to select your drone footage.
3. Once the upload percentage hits 100%, click **Start Processing**.
4. Monitor the live AI feed and progress bar.
5. Once complete, click **Download Traffic Report** to get your detailed CSV/Excel analysis.
