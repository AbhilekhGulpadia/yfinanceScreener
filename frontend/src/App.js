import React, { useState } from 'react';
import './App.css';
import SectorHeatmap from './components/SectorHeatmap';
import Analysis from './components/Analysis';
import KiteConnectionManager from './components/KiteConnectionManager';

function App() {
  const [activeTab, setActiveTab] = useState('heatmap');

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-left">
          <h1>Stock Analyzer</h1>
          <p>Real-time Nifty 500 Analysis</p>
        </div>
        <div className="header-right">
          <KiteConnectionManager compact={true} />
        </div>
      </header>

      <nav className="App-nav">
        <button
          className={`nav-button ${activeTab === 'heatmap' ? 'active' : ''}`}
          onClick={() => setActiveTab('heatmap')}
        >
          Sector Heatmap
        </button>
        <button
          className={`nav-button ${activeTab === 'analysis' ? 'active' : ''}`}
          onClick={() => setActiveTab('analysis')}
        >
          Analysis
        </button>
      </nav>

      <main className="App-main">
        {activeTab === 'heatmap' && <SectorHeatmap />}
        {activeTab === 'analysis' && <Analysis />}
      </main>

      <footer className="App-footer">
        <p>Powered by Kite Connect API | Manual data refresh</p>
      </footer>
    </div>
  );
}

export default App;
