'use client';

import { useState, useRef, useEffect } from 'react';
import styles from './page.module.css';

const API_BASE = 'http://localhost:8000/api';

export default function Home() {
  const [file, setFile] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, uploading, ready, processing, completed, error, paused
  const [progress, setProgress] = useState(0);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [stats, setStats] = useState({});
  const [records, setRecords] = useState([]);
  const [errorMsg, setErrorMsg] = useState('');
  
  const fileInputRef = useRef(null);
  const pollingInterval = useRef(null);

  // Poll status when processing
  useEffect(() => {
    if (status === 'processing') {
      pollingInterval.current = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/status/${taskId}`);
          if (res.ok) {
            const data = await res.json();
            setProgress(data.progress);
            setStats(data.class_counts);
            if (data.status === 'paused') {
              setIsPaused(true);
              setStatus('paused');
            } else if (data.status === 'processing') {
              setIsPaused(false);
              setStatus('processing');
            }
            if (data.status === 'completed' || data.status === 'error' || data.status === 'stopped') {
              setStatus(data.status);
              if (data.records) setRecords(data.records);
              if (data.error_msg) setErrorMsg(data.error_msg);
              clearInterval(pollingInterval.current);
            }
          }
        } catch (err) {
          console.error("Failed to fetch status:", err);
        }
      }, 1000);
    } else {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
    }

    return () => {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
    };
  }, [status, taskId]);

  const handleFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setStatus('uploading');
      setProgress(0);
      setStats({});
      setRecords([]);
      setTaskId(null);
      setErrorMsg('');

      const formData = new FormData();
      formData.append('file', selectedFile);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/upload`, true);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          setUploadProgress(percent);
        }
      };

      xhr.onload = () => {
        if (xhr.status === 200) {
          const data = JSON.parse(xhr.responseText);
          setTaskId(data.task_id);
          setStatus('ready');
          setUploadProgress(0); 
          setProgress(0); // Ensure processing progress is 0
        } else {
          setErrorMsg('Upload failed');
          setStatus('error');
        }
      };

      xhr.onerror = () => {
        setErrorMsg('Upload connection error');
        setStatus('error');
      };

      xhr.send(formData);
    }
  };

  const startProcessing = async () => {
    if (!taskId) return;
    
    try {
      const res = await fetch(`${API_BASE}/process/${taskId}?file_path=temp_uploads/${taskId}${file.name.substring(file.name.lastIndexOf('.'))}`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Failed to start processing');
      
      setStatus('processing');
      setIsPaused(false);
    } catch (err) {
      setErrorMsg(err.message);
      setStatus('error');
    }
  };

  const stopProcessing = async () => {
    if (!taskId) return;
    
    try {
      await fetch(`${API_BASE}/stop/${taskId}`, { method: 'POST' });
    } catch (err) {
      console.error(err);
    } finally {
      // Full reset of state as requested by the user
      setFile(null);
      setTaskId(null);
      setStatus('idle');
      setProgress(0);
      setUploadProgress(0);
      setStats({});
      setRecords([]);
      setIsPaused(false);
      setErrorMsg('');
    }
  };

  const togglePause = async () => {
    if (!taskId) return;
    
    try {
      const endpoint = isPaused ? 'resume' : 'pause';
      const res = await fetch(`${API_BASE}/${endpoint}/${taskId}`, { method: 'POST' });
      if (res.ok) {
        setIsPaused(!isPaused);
        setStatus(isPaused ? 'processing' : 'paused');
      }
    } catch (err) {
      console.error("Failed to toggle pause:", err);
    }
  };

  const downloadReport = () => {
    if (taskId && status === 'completed') {
      window.location.href = `${API_BASE}/report/${taskId}`;
    }
  };

  const totalVehicles = Object.values(stats).reduce((a, b) => a + b, 0);

  return (
    <main className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Smart Drone Analyzer</h1>
        <p className={styles.subtitle}>High-accuracy AI vehicle detection and traffic tracking</p>
      </header>

      <div className={styles.mainGrid}>
        {/* Left Column: Video & Controls */}
        <div className={styles.videoSection}>
          <div className={styles.videoContainer}>
            {(status === 'processing' || status === 'completed' || status === 'paused') ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img 
                src={`${API_BASE}/video_feed/${taskId}`} 
                alt="Live Processing Feed" 
                className={status === 'paused' ? styles.videoStreamPaused : styles.videoStream}
                onError={(e) => { e.target.style.display = 'none'; }}
              />
            ) : (
              <div className={styles.videoPlaceholder}>
                {status === 'uploading' ? `Uploading: ${uploadProgress}%` : file ? `Ready to process: ${file.name}` : 'No video selected'}
              </div>
            )}
          </div>
          
          <input 
            type="file" 
            ref={fileInputRef} 
            style={{display: 'none'}} 
            accept="video/*"
            onChange={handleFileChange}
          />

          <div className={styles.controls}>
            <button 
              className="primary-btn" 
              onClick={() => {
                if (fileInputRef.current) fileInputRef.current.value = null;
                fileInputRef.current.click();
              }}
              disabled={status === 'uploading' || status === 'processing'}
            >
              {status === 'uploading' ? `Uploading ${uploadProgress}%` : 'Upload Video'}
            </button>
            
            <button 
              className="primary-btn" 
              onClick={startProcessing}
              disabled={status !== 'ready'}
            >
              Start Processing
            </button>

            <button 
              className="secondary-btn" 
              onClick={togglePause}
              disabled={!(status === 'processing' || status === 'paused')}
            >
              {isPaused ? 'Resume' : 'Pause'}
            </button>

            <button 
              className="danger-btn" 
              onClick={stopProcessing}
              disabled={status !== 'processing'}
            >
              Stop / Cancel
            </button>
            
            <button 
              className="success-btn" 
              onClick={downloadReport}
              disabled={status !== 'completed'}
            >
              Download CSV Report
            </button>
          </div>
          
          {errorMsg && (
            <div style={{color: 'var(--danger-color)', textAlign: 'center', marginTop: '10px'}}>
              Error: {errorMsg}
            </div>
          )}
        </div>

        {/* Right Column: Stats & Progress */}
        <div className={styles.sidePanel}>
          
          <div className={`${styles.statsCard} glass-panel`}>
            <div className={styles.statsHeader}>Live Statistics</div>
            <div className={styles.totalLabel}>Total Unique Vehicles</div>
            <div className={styles.totalCount}>{totalVehicles}</div>
            
            <div className={styles.totalLabel}>Breakdown</div>
            <div className={styles.breakdownList}>
              {Object.keys(stats).length === 0 ? (
                <div className={styles.breakdownItem}>
                  <span className={styles.breakdownName}>Waiting for detections...</span>
                </div>
              ) : (
                Object.entries(stats).map(([cls, count]) => (
                  <div key={cls} className={styles.breakdownItem}>
                    <span className={styles.breakdownName}>{cls}</span>
                    <span className={styles.breakdownValue}>{count}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className={`${styles.progressSection} glass-panel`}>
            <div className={styles.progressHeader}>
              <span>Processing Progress</span>
              <span style={{color: 'var(--accent-color)'}}>{progress}%</span>
            </div>
            <div className={styles.progressBarContainer}>
              <div 
                className={styles.progressBar} 
                style={{width: `${progress}%`}}
              ></div>
            </div>
            <div className={styles.statusText}>Status: {status}</div>
          </div>

        </div>
      </div>
      
      {/* Records Table Section */}
      {status === 'completed' && records.length > 0 && (
        <div className={`${styles.tableSection} glass-panel`}>
          <div className={styles.tableHeader}>
            <h2>Detailed Traffic Report</h2>
          </div>
          <div className={styles.tableContainer}>
            <table className={styles.recordsTable}>
              <thead>
                <tr>
                  <th>Frame</th>
                  <th>Timestamp (s)</th>
                  <th>Track ID</th>
                  <th>Vehicle Class</th>
                </tr>
              </thead>
              <tbody>
                {records.map((row, idx) => (
                  <tr key={idx}>
                    <td>{row.frame_index}</td>
                    <td>{row.timestamp?.toFixed(2)}</td>
                    <td>{row.track_id}</td>
                    <td className={styles.capitalize}>{row.class}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}
