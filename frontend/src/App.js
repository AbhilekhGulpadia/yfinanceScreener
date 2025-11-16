import React, { useState } from 'react';
import './App.css';
import SectorHeatmap from './SectorHeatmap';
import InitializationProgress from './InitializationProgress';
import Analysis from './Analysis';

function App() {
  const [activeTab, setActiveTab] = useState('heatmap');

  return (
    <div className="App">
      <header className="App-header">
        <h1>Stock Analyzer</h1>
        <p>Real-time Nifty 500 Analysis</p>
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
        <button
          className={`nav-button ${activeTab === 'initialize' ? 'active' : ''}`}
          onClick={() => setActiveTab('initialize')}
        >
          Refresh Data
        </button>
      </nav>

      <main className="App-main">
        {activeTab === 'heatmap' && <SectorHeatmap />}
        {activeTab === 'analysis' && <Analysis />}
        {activeTab === 'initialize' && <InitializationProgress />}
      </main>

      <footer className="App-footer">
        <p>Powered by Yahoo Finance API | Auto-updates every 15 minutes</p>
      </footer>
    </div>
  );
}

export default App;
