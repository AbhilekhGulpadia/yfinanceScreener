import React, { useState } from 'react';
import './App.css';
import SectorHeatmap from './components/SectorHeatmap';
import Analysis from './components/Analysis';
import WiensteinScoring from './components/WiensteinScoring';
import Shortlist from './components/Shortlist';

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
        <p>Powered by Yahoo Finance | Manual data refresh</p>
      </footer>
    </div>
  );
}

export default App;
