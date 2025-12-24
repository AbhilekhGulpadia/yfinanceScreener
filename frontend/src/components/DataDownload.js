import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import './DataDownload.css';

function DataDownload() {
    const [showModal, setShowModal] = useState(false);
    const [downloading, setDownloading] = useState(false);
    const [progress, setProgress] = useState({ current: 0, total: 0, percentage: 0 });
    const [message, setMessage] = useState('');
    const [recordsInserted, setRecordsInserted] = useState(0);
    const [currentSymbol, setCurrentSymbol] = useState('');

    useEffect(() => {
        if (showModal) {
            // Connect to Socket.IO for progress updates
            const socket = io();

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
                }
            });

            return () => {
                socket.disconnect();
            };
        }
    }, [showModal]);

    const handleOpenModal = () => {
        setShowModal(true);
    };

    const handleStartDownload = async () => {
        setDownloading(true);
        setMessage('Starting data download from Yahoo Finance...');
        setProgress({ current: 0, total: 0, percentage: 0 });
        setRecordsInserted(0);

        try {
            const response = await fetch('/api/ohlcv/refresh', {
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

                            <div className="info-box">
                                <p><strong>📊 About to download:</strong></p>
                                <p>• 5 years of daily OHLCV data from Yahoo Finance</p>
                                <p>• All Nifty 500 stocks</p>
                                <p>• Existing data will be cleared</p>
                                {!downloading && (
                                    <button className="start-download-btn" onClick={handleStartDownload}>
                                        Start Download
                                    </button>
                                )}
                            </div>

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
