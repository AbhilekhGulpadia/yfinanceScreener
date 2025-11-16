import React, { useEffect, useState } from 'react';
import io from 'socket.io-client';
import './InitializationProgress.css';

function InitializationProgress() {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');
  const [current, setCurrent] = useState(0);
  const [total, setTotal] = useState(0);
  const [currentSymbol, setCurrentSymbol] = useState('');
  const [isInitializing, setIsInitializing] = useState(false);

  useEffect(() => {
    // Connect to Socket.IO
    const socket = io('http://localhost:5000');

    socket.on('connect', () => {
      console.log('Connected to WebSocket');
    });

    socket.on('initialization_progress', (data) => {
      setProgress(data.progress || 0);
      setStatus(data.status || 'processing');
      setMessage(data.message || '');
      setCurrent(data.current || 0);
      setTotal(data.total || 0);
      setCurrentSymbol(data.symbol || '');

      if (data.status === 'completed') {
        setIsInitializing(false);
      }
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from WebSocket');
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const startInitialization = async () => {
    setIsInitializing(true);
    setProgress(0);
    setStatus('starting');
    setMessage('Starting initialization...');

    try {
      const response = await fetch('/api/ohlcv/initialize-all', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to start initialization');
      }

      const result = await response.json();
      console.log(result.message);
    } catch (error) {
      console.error('Error starting initialization:', error);
      setStatus('error');
      setMessage('Failed to start initialization: ' + error.message);
      setIsInitializing(false);
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'completed':
        return '#28a745';
      case 'error':
        return '#dc3545';
      case 'processing':
      case 'started':
        return '#007bff';
      default:
        return '#6c757d';
    }
  };

  return (
    <div className="initialization-container">
      <div className="initialization-header">
        <h2>Historical Data Initialization</h2>
        <p>Load 5 years of historical OHLCV data for all Nifty 500 stocks</p>
      </div>

      {!isInitializing && status !== 'processing' && status !== 'started' && (
        <button
          className="btn-initialize"
          onClick={startInitialization}
          disabled={isInitializing}
        >
          Start Initialization (5 Years of Data)
        </button>
      )}

      {(isInitializing || status === 'processing' || status === 'started') && (
        <div className="progress-section">
          <div className="progress-info">
            <div className="progress-stats">
              <span className="current-stock">
                {current > 0 && `Processing: ${currentSymbol}`}
              </span>
              <span className="progress-numbers">
                {current} / {total} stocks
              </span>
            </div>
            <div className="progress-percentage">
              {progress}%
            </div>
          </div>

          <div className="progress-bar-container">
            <div
              className="progress-bar-fill"
              style={{
                width: `${progress}%`,
                backgroundColor: getStatusColor(),
              }}
            >
              <span className="progress-bar-text">{progress}%</span>
            </div>
          </div>

          {message && (
            <div className={`status-message status-${status}`}>
              {message}
            </div>
          )}
        </div>
      )}

      {status === 'completed' && (
        <div className="completion-message">
          <div className="completion-icon">✓</div>
          <h3>Initialization Complete!</h3>
          <p>{message}</p>
        </div>
      )}

      {status === 'error' && (
        <div className="error-message">
          <div className="error-icon">✗</div>
          <h3>Initialization Failed</h3>
          <p>{message}</p>
          <button
            className="btn-retry"
            onClick={startInitialization}
          >
            Retry
          </button>
        </div>
      )}

      <div className="initialization-info">
        <h4>What does initialization do?</h4>
        <ul>
          <li>Fetches 5 years of historical OHLCV data for all Nifty 500 stocks</li>
          <li>Data is collected at 15-minute intervals</li>
          <li>After initialization, data auto-updates every 15 minutes</li>
          <li>This process may take 30-60 minutes depending on your internet connection</li>
        </ul>
      </div>
    </div>
  );
}

export default InitializationProgress;
