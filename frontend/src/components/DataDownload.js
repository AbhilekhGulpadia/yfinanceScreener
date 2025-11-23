import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import './DataDownload.css';

function DataDownload() {
    const [showModal, setShowModal] = useState(false);
    const [kiteConnected, setKiteConnected] = useState(false);
    const [downloading, setDownloading] = useState(false);
    const [progress, setProgress] = useState({ current: 0, total: 0, percentage: 0 });
    const [message, setMessage] = useState('');
    const [recordsInserted, setRecordsInserted] = useState(0);
    const [completed, setCompleted] = useState(false);
    const [currentSymbol, setCurrentSymbol] = useState('');

    useEffect(() => {
        checkKiteStatus();
    }, []);

    useEffect(() => {
        if (showModal) {
            // Connect to Socket.IO for progress updates
            const socket = io('http://localhost:5000');

            socket.on('refresh_progress', (data) => {
                setProgress({
                    current: data.current || 0,
                    total: data.total || 0,
                    percentage: data.progress || 0
                });
                setMessage(data.message || '');
                setCurrentSymbol(data.symbol || '');
                setRecordsInserted(data.records_added || 0);

                if (data.status === 'completed') {
                    setDownloading(false);
                    setCompleted(true);
                }
            });

            return () => {
                socket.disconnect();
            };
        }
    }, [showModal]);

    const checkKiteStatus = async () => {
        try {
            const response = await fetch('http://localhost:5000/api/kite/status');
            const data = await response.json();
            setKiteConnected(data.connected);
        } catch (error) {
            console.error('Error checking Kite status:', error);
            setKiteConnected(false);
        }
    };

    const handleKiteLogin = async () => {
        try {
            const response = await fetch('http://localhost:5000/api/kite/login');
            const data = await response.json();
            window.open(data.login_url, '_blank');
            setMessage('Please complete Kite login in the new window, then click "Start Download" again.');
        } catch (error) {
            setMessage('Error getting Kite login URL: ' + error.message);
        }
    };

    const handleOpenModal = () => {
        checkKiteStatus();
        setShowModal(true);
    };

    const handleStartDownload = async () => {
        if (!kiteConnected) {
            setMessage('Please connect to Kite first using the Connect button in the header.');
            return;
        }

        setDownloading(true);
        setMessage('Starting data download...');
        setProgress({ current: 0, total: 0, percentage: 0 });
        setRecordsInserted(0);

        try {
            const response = await fetch('http://localhost:5000/api/ohlcv/refresh', {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Failed to start data download');
            }

            setMessage('Data download started. Progress will update automatically...');
        } catch (error) {
            setMessage('Error: ' + error.message);
            setDownloading(false);
        }
    };

    return (
        <>
            <button className="download-data-btn" onClick={handleOpenModal}>
                📥 Download Data
            </button>

            {showModal && (
                <div className="modal-overlay" onClick={() => !downloading && setShowModal(false)}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Download 5-Year OHLCV Data</h2>
                            {!downloading && (
                                <button className="close-btn" onClick={() => setShowModal(false)}>×</button>
                            )}
                        </div>

                        <div className="modal-body">
                            <div className="status-section">
                                <div className="status-item">
                                    <span className="status-label">Kite Connection:</span>
                                    <span className={`status-value ${kiteConnected ? 'connected' : 'disconnected'}`}>
                                        {kiteConnected ? 'Connected' : 'Disconnected'}
                                    </span>
                                </div>
                            </div>

                            {!kiteConnected && (
                                <div className="info-box">
                                    <p><strong>⚠️ Not connected to Kite</strong></p>
                                    <p>Please use the "Connect" button in the header to connect to Kite before downloading data.</p>
                                </div>
                            )}

                            {kiteConnected && (
                                <div className="info-box">
                                    <p><strong>📊 About to download:</strong></p>
                                    <p>• 5 years of daily OHLCV data</p>
                                    <p>• All Nifty 500 stocks</p>
                                    <p>• Existing data will be cleared</p>
                                    {!downloading && ( // Added condition to show button only when not downloading
                                        <button className="start-download-btn" onClick={handleStartDownload}>
                                            Start Download
                                        </button>
                                    )}
                                </div>
                            )}

                            {downloading && (
                                <div className="progress-section">
                                    <div className="progress-info">
                                        <div className="progress-stats">
                                            <span className="current-stock">
                                                {currentSymbol && `Processing: ${currentSymbol}`}
                                            </span>
                                            <span className="progress-numbers">
                                                {progress.current} / {progress.total} stocks
                                            </span>
                                        </div>
                                        <div className="progress-percentage">
                                            {progress.percentage}%
                                        </div>
                                    </div>

                                    <div className="progress-bar-container">
                                        <div
                                            className="progress-bar-fill"
                                            style={{ width: `${progress.percentage}%` }}
                                        >
                                            <span className="progress-bar-text">{progress.percentage}%</span>
                                        </div>
                                    </div>

                                    {message && (
                                        <div className="status-message">
                                            {message}
                                        </div>
                                    )}

                                    {recordsInserted > 0 && (
                                        <div className="records-info">
                                            Records added: {recordsInserted.toLocaleString()}
                                        </div>
                                    )}
                                </div>
                            )}

                            {progress.percentage === 100 && !downloading && (
                                <div className="completion-message">
                                    <div className="completion-icon">✓</div>
                                    <h3>Download Complete!</h3>
                                    <p>{message}</p>
                                    <button className="close-btn-bottom" onClick={() => setShowModal(false)}>
                                        Close
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

export default DataDownload;
