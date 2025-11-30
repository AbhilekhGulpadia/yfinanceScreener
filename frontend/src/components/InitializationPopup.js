import React, { useState, useEffect } from 'react';
import './InitializationPopup.css';

function InitializationPopup({ connectionStatus, onConnectClick }) {
    const [showPopup, setShowPopup] = useState(false);
    const [currentStep, setCurrentStep] = useState(1);

    useEffect(() => {
        // Check if user has dismissed the popup before
        const hasSeenPopup = localStorage.getItem('hasSeenInitPopup');

        // Show popup if user hasn't seen it before and not connected
        if (!hasSeenPopup && !connectionStatus.connected) {
            setShowPopup(true);
        }
    }, [connectionStatus.connected]);

    // Auto-close popup when connected
    useEffect(() => {
        if (connectionStatus.connected && showPopup) {
            setTimeout(() => {
                handleClose(true);
            }, 2000);
        }
    }, [connectionStatus.connected, showPopup]);

    const handleClose = (dontShowAgain = false) => {
        if (dontShowAgain) {
            localStorage.setItem('hasSeenInitPopup', 'true');
        }
        setShowPopup(false);
    };

    const handleConnectToKite = () => {
        setCurrentStep(2);
        if (onConnectClick) {
            onConnectClick();
        }
    };

    if (!showPopup) {
        return null;
    }

    return (
        <div className="init-popup-overlay">
            <div className="init-popup">
                <div className="init-popup-header">
                    <h2>🚀 Welcome to Stock Analyzer!</h2>
                    <button className="init-close-btn" onClick={() => handleClose(false)}>×</button>
                </div>

                <div className="init-popup-body">
                    {connectionStatus.connected ? (
                        <div className="init-success">
                            <div className="init-success-icon">✓</div>
                            <h3>All Set!</h3>
                            <p>Your app is ready to use.</p>
                        </div>
                    ) : (
                        <>
                            <p className="init-intro">
                                Let's get your app set up in just 2 quick steps:
                            </p>

                            <div className="init-steps">
                                {/* Step 1: Connect to Kite */}
                                <div className={`init-step ${currentStep >= 1 ? 'active' : ''} ${connectionStatus.connected ? 'completed' : ''}`}>
                                    <div className="init-step-number">1</div>
                                    <div className="init-step-content">
                                        <h4>Connect to Kite</h4>
                                        <p>Authenticate with your Kite account to access market data.</p>
                                        <button
                                            className="init-action-btn"
                                            onClick={handleConnectToKite}
                                        >
                                            {connectionStatus.connected ? '✓ Connected' : 'Connect to Kite'}
                                        </button>
                                        <div className="init-help-text">
                                            This will open the Kite login flow
                                        </div>
                                    </div>
                                </div>

                                {/* Step 2: Start Using */}
                                <div className={`init-step ${currentStep >= 2 ? 'active' : ''} ${connectionStatus.connected ? 'completed' : ''}`}>
                                    <div className="init-step-number">2</div>
                                    <div className="init-step-content">
                                        <h4>Start Analyzing!</h4>
                                        <p>Once connected, you can view sector heatmaps and stock analysis.</p>
                                    </div>
                                </div>
                            </div>
                        </>
                    )}
                </div>

                <div className="init-popup-footer">
                    <label className="init-checkbox">
                        <input
                            type="checkbox"
                            onChange={(e) => {
                                if (e.target.checked) {
                                    localStorage.setItem('hasSeenInitPopup', 'true');
                                } else {
                                    localStorage.removeItem('hasSeenInitPopup');
                                }
                            }}
                        />
                        <span>Don't show this again</span>
                    </label>
                    <button
                        className="init-got-it-btn"
                        onClick={() => handleClose(true)}
                    >
                        {connectionStatus.connected ? 'Get Started' : 'Got it'}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default InitializationPopup;
