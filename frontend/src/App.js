import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import SectorHeatmap from './components/SectorHeatmap';
import Analysis from './components/Analysis';
import WiensteinScoring from './components/WiensteinScoring';
import Shortlist from './components/Shortlist';
import KiteConnectionManager from './components/KiteConnectionManager';

function App() {
  const [activeTab, setActiveTab] = useState('heatmap');
  const [connectionStatus, setConnectionStatus] = useState({
    connected: false,
    checking: true,
    error: null,
    needsCertApproval: false
  });
  const kiteManagerRef = useRef(null);

  // Detect Kite auth callback
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const kiteAuth = urlParams.get('kite_auth');

    if (kiteAuth) {
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);

      if (kiteAuth === 'success') {
        // Trigger connection status refresh
        if (kiteManagerRef.current && kiteManagerRef.current.refreshStatus) {
          kiteManagerRef.current.refreshStatus();
        }
      } else if (kiteAuth === 'error') {
        const message = urlParams.get('message') || 'Authentication failed';
        console.error('Kite auth error:', message);
      }
    }
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-left">
          <h1>Stock Analyzer</h1>
          <p>Real-time Nifty 500 Analysis</p>
        </div>
        <div className="header-right">
          <KiteConnectionManager
            compact={true}
            ref={kiteManagerRef}
            onStatusChange={setConnectionStatus}
          />
        </div>
      </header>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'heatmap' ? 'active' : ''}`}
          onClick={() => setActiveTab('heatmap')}
        >
          Sector Heatmap
        </button>
        <button
          className={`tab ${activeTab === 'analysis' ? 'active' : ''}`}
          onClick={() => setActiveTab('analysis')}
        >
          Analysis
        </button>
        <button
          className={`tab ${activeTab === 'wienstein' ? 'active' : ''}`}
          onClick={() => setActiveTab('wienstein')}
        >
          Wienstein Scoring
        </button>
        <button
          className={`tab ${activeTab === 'shortlist' ? 'active' : ''}`}
          onClick={() => setActiveTab('shortlist')}
        >
          Shortlist
        </button>
      </div>

      <main className="App-main">
        {activeTab === 'heatmap' && <SectorHeatmap />}
        {activeTab === 'analysis' && <Analysis />}
        {activeTab === 'wienstein' && <WiensteinScoring />}
        {activeTab === 'shortlist' && <Shortlist />}
      </main>

      <footer className="App-footer">
        <p>Powered by Kite Connect API | Manual data refresh</p>
      </footer>
    </div>
  );
}

export default App;
