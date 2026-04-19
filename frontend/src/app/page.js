'use client';

import { useState, useRef, useEffect } from 'react';
import styles from './page.module.css';

const API_BASE = 'http://localhost:8000/api';

export default function Home() {
  const [file, setFile] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, uploading, ready, processing, completed, error
  const [progress, setProgress] = useState(0);
  const [stats, setStats] = useState({});
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
            if (data.status === 'completed' || data.status === 'error' || data.status === 'stopped') {
              setStatus(data.status);
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
      setTaskId(null);
      setErrorMsg('');

      const formData = new FormData();
      formData.append('file', selectedFile);

      try {
        const res = await fetch(`${API_BASE}/upload`, {
          method: 'POST',
          body: formData,
        });
        
        if (!res.ok) throw new Error('Upload failed');
        
        const data = await res.json();
        setTaskId(data.task_id);
        setStatus('ready');
      } catch (err) {
        setErrorMsg(err.message);
        setStatus('error');
      }
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
    } catch (err) {
      setErrorMsg(err.message);
      setStatus('error');
    }
  };

  const stopProcessing = async () => {
    if (!taskId) return;
    
    try {
      await fetch(`${API_BASE}/stop/${taskId}`, { method: 'POST' });
      setStatus('stopped');
    } catch (err) {
      console.error(err);
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
            {(status === 'processing' || status === 'completed' || status === 'stopped') ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img 
                src={`${API_BASE}/video_feed/${taskId}`} 
                alt="Live Processing Feed" 
                className={styles.videoStream}
                onError={(e) => { e.target.style.display = 'none'; }}
              />
            ) : (
              <div className={styles.videoPlaceholder}>
                {status === 'uploading' ? 'Uploading...' : file ? `Ready to process: ${file.name}` : 'No video selected'}
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
              {status === 'uploading' ? 'Uploading...' : 'Upload Video'}
            </button>
            
            <button 
              className="primary-btn" 
              onClick={startProcessing}
              disabled={!(status === 'ready' || status === 'stopped')}
            >
              Start Processing
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
    </main>
  );
}
