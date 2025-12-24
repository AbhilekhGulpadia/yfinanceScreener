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
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [recordsAdded, setRecordsAdded] = useState(0);
  const [recordsCleaned, setRecordsCleaned] = useState(0);

  useEffect(() => {
    // Connect to Socket.IO
    const socket = io();

    socket.on('connect', () => {
      console.log('Connected to WebSocket');
    });

    // Listen for both initialization and refresh progress
    socket.on('initialization_progress', (data) => {
      setProgress(data.progress || 0);
      setStatus(data.status || 'processing');
      setMessage(data.message || '');
      setCurrent(data.current || 0);
      setTotal(data.total || 0);
      setCurrentSymbol(data.symbol || '');

      if (data.status === 'completed') {
        setIsRefreshing(false);
      }
    });

    socket.on('refresh_progress', (data) => {
      setProgress(data.progress || 0);
      setStatus(data.status || 'processing');
      setMessage(data.message || '');
      setCurrent(data.current || 0);
      setTotal(data.total || 0);
      setCurrentSymbol(data.symbol || '');
      setRecordsAdded(data.records_added || 0);
      setRecordsCleaned(data.records_cleaned || 0);

      if (data.status === 'completed') {
        setIsRefreshing(false);
      }
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from WebSocket');
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const startRefresh = async () => {
    setIsRefreshing(true);
    setProgress(0);
    setStatus('starting');
    setMessage('Starting data refresh...');
    setRecordsAdded(0);
    setRecordsCleaned(0);

    try {
      const response = await fetch('/api/ohlcv/refresh', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to start refresh');
      }

      const result = await response.json();
      console.log(result.message);
    } catch (error) {
      console.error('Error starting refresh:', error);
      setStatus('error');
      setMessage('Failed to start refresh: ' + error.message);
      setIsRefreshing(false);
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

  const startFullInitialization = async () => {
    setIsRefreshing(true);
    setProgress(0);
    setStatus('starting');
    setMessage('Starting full 5-year initialization...');
    setRecordsAdded(0);
    setRecordsCleaned(0);

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
      setIsRefreshing(false);
    }
  };

  return (
    <div className="initialization-container">
      <div className="initialization-header">
        <h2>Data Management</h2>
        <p>Initialize or refresh OHLCV data for all Nifty 500 stocks</p>
      </div>

      {!isRefreshing && status !== 'processing' && status !== 'started' && (
        <div className="button-group">
          <button
            className="btn-initialize btn-primary"
            onClick={startFullInitialization}
            disabled={isRefreshing}
          >
            Initialize 5 Years Historical Data
          </button>
          <button
            className="btn-initialize btn-secondary"
            onClick={startRefresh}
            disabled={isRefreshing}
          >
            Refresh Latest Data Only
          </button>
        </div>
      )}

      {(isRefreshing || status === 'processing' || status === 'started') && (
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
          <h3>Refresh Complete!</h3>
          <p>{message}</p>
        </div>
      )}

      {status === 'error' && (
        <div className="error-message">
          <div className="error-icon">✗</div>
          <h3>Refresh Failed</h3>
          <p>{message}</p>
          <button
            className="btn-retry"
            onClick={startRefresh}
          >
            Retry
          </button>
        </div>
      )}

      <div className="initialization-info">
        <h4>What does refresh do?</h4>
        <ul>
          <li>Fetches the latest OHLCV data (previous day) for all Nifty 500 stocks</li>
          <li>Automatically removes records older than 5 years to keep database size manageable</li>
          <li>Data is collected at 15-minute intervals</li>
          <li>Background auto-updates occur every 15 minutes</li>
          <li>This process typically takes 5-10 minutes</li>
        </ul>
      </div>
    </div>
  );
}

export default InitializationProgress;
