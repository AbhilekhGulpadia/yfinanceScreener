import React, { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import './KiteConnectionManager.css';

const KITE_API_KEY = 'iyi9a2huwplqqzvg'; // From config.py

const KiteConnectionManager = forwardRef(({ compact = false, onStatusChange }, ref) => {
    const [connectionStatus, setConnectionStatus] = useState({
        connected: false,
        checking: true,
        error: null
    });

    // Expose methods to parent component via ref
    useImperativeHandle(ref, () => ({
        refreshStatus: () => {
            checkConnection();
        }
    }));

    // Notify parent of status changes
    useEffect(() => {
        if (onStatusChange) {
            onStatusChange(connectionStatus);
        }
    }, [connectionStatus, onStatusChange]);

    useEffect(() => {
        checkConnection();
        // Check connection status every 30 seconds
        const interval = setInterval(checkConnection, 30000);
        return () => clearInterval(interval);
    }, []);

    const checkConnection = async () => {
        try {
            const response = await fetch('/api/kite/status');
            const data = await response.json();
            setConnectionStatus({
                connected: data.connected,
                checking: false,
                error: null
            });
        } catch (error) {
            setConnectionStatus({
                connected: false,
                checking: false,
                error: error.message
            });
        }
    };

    const handleConnect = () => {
        // Directly redirect to Kite login URL with API key
        const kiteLoginUrl = `https://kite.zerodha.com/connect/login?api_key=${KITE_API_KEY}&v=3`;
        window.open(kiteLoginUrl, '_blank');
    };

    if (compact) {
        return (
            <div className="kite-connection-compact">
                <div className={`connection-status ${connectionStatus.connected ? 'connected' : 'disconnected'}`}>
                    <span className="status-indicator"></span>
                    <span className="status-text">
                        {connectionStatus.checking ? 'Checking...' :
                            connectionStatus.connected ? 'Kite Connected' : 'Kite Disconnected'}
                    </span>
                </div>
                {!connectionStatus.connected && (
                    <button
                        className="connect-button"
                        onClick={handleConnect}
                    >
                        Connect
                    </button>
                )}
            </div>
        );
    }

    return (
        <div className="kite-connection-manager">
            <h2>Kite Connection</h2>
            <div className={`status-card ${connectionStatus.connected ? 'connected' : 'disconnected'}`}>
                <div className="status-icon">
                    {connectionStatus.connected ? '✓' : '○'}
                </div>
                <div className="status-info">
                    <h3>
                        {connectionStatus.checking ? 'Checking Connection...' :
                            connectionStatus.connected ? 'Connected to Kite' : 'Not Connected'}
                    </h3>
                    {connectionStatus.error && (
                        <p className="error-message">{connectionStatus.error}</p>
                    )}
                </div>
            </div>
            {!connectionStatus.connected && (
                <button
                    className="connect-button-large"
                    onClick={handleConnect}
                >
                    Connect to Kite
                </button>
            )}
        </div>
    );
});

export default KiteConnectionManager;
