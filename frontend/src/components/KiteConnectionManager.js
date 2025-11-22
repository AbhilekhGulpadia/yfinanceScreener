import React, { useState, useEffect } from 'react';
import './KiteConnectionManager.css';

function KiteConnectionManager({ compact = false }) {
    const [connectionStatus, setConnectionStatus] = useState({
        connected: false,
        checking: true,
        error: null
    });
    const [showModal, setShowModal] = useState(false);
    const [currentStep, setCurrentStep] = useState(1);
    const [loginUrl, setLoginUrl] = useState('');

    useEffect(() => {
        checkConnection();
        // Check connection status every 30 seconds
        const interval = setInterval(checkConnection, 30000);
        return () => clearInterval(interval);
    }, []);

    const checkConnection = async () => {
        try {
            const response = await fetch('https://localhost:5000/api/kite/status');
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

    const handleConnect = async () => {
        setShowModal(true);
        setCurrentStep(1);
    };

    const handleCertificateApproval = () => {
        // Open backend URL in new tab for certificate approval
        window.open('https://localhost:5000/api/kite/status', '_blank');
        setCurrentStep(2);
    };

    const handleKiteLogin = async () => {
        try {
            const response = await fetch('https://localhost:5000/api/kite/login');
            const data = await response.json();
            setLoginUrl(data.login_url);
            window.open(data.login_url, '_blank');
            setCurrentStep(3);
        } catch (error) {
            setConnectionStatus({
                ...connectionStatus,
                error: 'Failed to get Kite login URL: ' + error.message
            });
        }
    };

    const handleVerifyConnection = async () => {
        await checkConnection();
        if (connectionStatus.connected) {
            setShowModal(false);
            setCurrentStep(1);
        }
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setCurrentStep(1);
    };

    if (compact) {
        return (
            <div className="kite-status-compact">
                <div
                    className={`status-indicator ${connectionStatus.connected ? 'connected' : 'disconnected'}`}
                    onClick={!connectionStatus.connected ? handleConnect : null}
                    title={connectionStatus.connected ? 'Connected to Kite' : 'Click to connect to Kite'}
                >
                    <span className="status-dot"></span>
                    <span className="status-text">
                        {connectionStatus.checking ? 'Checking...' : (connectionStatus.connected ? 'Kite Connected' : 'Kite Disconnected')}
                    </span>
                </div>
                {!connectionStatus.connected && (
                    <button className="connect-btn-compact" onClick={handleConnect}>
                        Connect
                    </button>
                )}
            </div>
        );
    }

    return (
        <>
            <button
                className={`kite-connect-btn ${connectionStatus.connected ? 'connected' : 'disconnected'}`}
                onClick={connectionStatus.connected ? null : handleConnect}
                disabled={connectionStatus.checking}
            >
                <span className={`status-dot ${connectionStatus.connected ? 'connected' : 'disconnected'}`}></span>
                {connectionStatus.checking ? 'Checking...' : (connectionStatus.connected ? '✓ Connected to Kite' : 'Connect to Kite')}
            </button>

            {showModal && (
                <div className="connection-modal-overlay" onClick={handleCloseModal}>
                    <div className="connection-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Connect to Kite</h2>
                            <button className="close-btn" onClick={handleCloseModal}>×</button>
                        </div>

                        <div className="modal-body">
                            <div className="steps-indicator">
                                <div className={`step ${currentStep >= 1 ? 'active' : ''} ${currentStep > 1 ? 'completed' : ''}`}>
                                    <div className="step-number">1</div>
                                    <div className="step-label">Certificate</div>
                                </div>
                                <div className="step-line"></div>
                                <div className={`step ${currentStep >= 2 ? 'active' : ''} ${currentStep > 2 ? 'completed' : ''}`}>
                                    <div className="step-number">2</div>
                                    <div className="step-label">Login</div>
                                </div>
                                <div className="step-line"></div>
                                <div className={`step ${currentStep >= 3 ? 'active' : ''}`}>
                                    <div className="step-number">3</div>
                                    <div className="step-label">Verify</div>
                                </div>
                            </div>

                            {currentStep === 1 && (
                                <div className="step-content">
                                    <h3>Step 1: Approve Security Certificate</h3>
                                    <p>The backend uses HTTPS with a self-signed certificate. You need to approve it first.</p>
                                    <div className="instructions">
                                        <ol>
                                            <li>Click the button below to open the backend URL in a new tab</li>
                                            <li>You'll see a security warning - this is expected</li>
                                            <li>Click <strong>"Advanced"</strong> or <strong>"Show Details"</strong></li>
                                            <li>Click <strong>"Proceed to localhost (unsafe)"</strong> or <strong>"Accept the Risk"</strong></li>
                                            <li>You should see a JSON response with connection status</li>
                                            <li>Close that tab and click "Next" below</li>
                                        </ol>
                                    </div>
                                    <div className="step-actions">
                                        <button className="primary-btn" onClick={handleCertificateApproval}>
                                            Open Backend & Approve Certificate
                                        </button>
                                    </div>
                                </div>
                            )}

                            {currentStep === 2 && (
                                <div className="step-content">
                                    <h3>Step 2: Login to Kite</h3>
                                    <p>Now you need to authenticate with your Kite account.</p>
                                    <div className="instructions">
                                        <ol>
                                            <li>Click the button below to open Kite login page</li>
                                            <li>Login with your Kite credentials</li>
                                            <li>Authorize the application</li>
                                            <li>You'll be redirected back (the page may show an error - that's okay)</li>
                                            <li>Close the Kite tab and click "Next" below</li>
                                        </ol>
                                    </div>
                                    <div className="step-actions">
                                        <button className="secondary-btn" onClick={() => setCurrentStep(1)}>
                                            Back
                                        </button>
                                        <button className="primary-btn" onClick={handleKiteLogin}>
                                            Login to Kite
                                        </button>
                                    </div>
                                </div>
                            )}

                            {currentStep === 3 && (
                                <div className="step-content">
                                    <h3>Step 3: Verify Connection</h3>
                                    <p>Let's verify that the connection was successful.</p>
                                    <div className="instructions">
                                        <p>Click the button below to check if you're connected to Kite.</p>
                                        {connectionStatus.connected && (
                                            <div className="success-message">
                                                <div className="success-icon">✓</div>
                                                <p>Successfully connected to Kite!</p>
                                            </div>
                                        )}
                                        {connectionStatus.error && (
                                            <div className="error-message">
                                                <p>Connection failed: {connectionStatus.error}</p>
                                                <p>Please try the steps again.</p>
                                            </div>
                                        )}
                                    </div>
                                    <div className="step-actions">
                                        <button className="secondary-btn" onClick={() => setCurrentStep(2)}>
                                            Back
                                        </button>
                                        <button className="primary-btn" onClick={handleVerifyConnection}>
                                            {connectionStatus.connected ? 'Done' : 'Verify Connection'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

export default KiteConnectionManager;
