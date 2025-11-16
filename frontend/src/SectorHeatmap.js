import React, { useEffect, useState } from 'react';
import './SectorHeatmap.css';

function SectorHeatmap() {
  const [heatmapData, setHeatmapData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchHeatmapData = async () => {
    try {
      const response = await fetch('/api/ohlcv/sector-heatmap');
      if (!response.ok) {
        throw new Error('Failed to fetch heatmap data');
      }
      const result = await response.json();
      setHeatmapData(result.heatmap_data);
      setLastUpdate(new Date(result.timestamp).toLocaleString());
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHeatmapData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchHeatmapData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const getColorForChange = (change) => {
    if (change > 3) return '#006400'; // Dark green
    if (change > 1.5) return '#228B22'; // Forest green
    if (change > 0.5) return '#32CD32'; // Lime green
    if (change > 0) return '#90EE90'; // Light green
    if (change > -0.5) return '#FFE4E1'; // Misty rose
    if (change > -1.5) return '#FFA07A'; // Light salmon
    if (change > -3) return '#FF6347'; // Tomato
    return '#DC143C'; // Crimson
  };

  const getTextColor = (change) => {
    return Math.abs(change) > 1 ? '#ffffff' : '#000000';
  };

  if (loading) return <div className="heatmap-loading">Loading sector heatmap...</div>;
  if (error) return <div className="heatmap-error">Error: {error}</div>;

  return (
    <div className="heatmap-container">
      <div className="heatmap-header">
        <h2>Sector Performance Heatmap</h2>
        {lastUpdate && <p className="last-update">Last Updated: {lastUpdate}</p>}
      </div>
      
      <div className="heatmap-grid">
        {heatmapData.map((sector) => (
          <div
            key={sector.sector}
            className="heatmap-cell"
            style={{
              backgroundColor: getColorForChange(sector.avg_price_change),
              color: getTextColor(sector.avg_price_change)
            }}
            title={`${sector.sector}\n${sector.stock_count} stocks\nAvg Change: ${sector.avg_price_change}%`}
          >
            <div className="sector-name">{sector.sector}</div>
            <div className="sector-change">
              {sector.avg_price_change > 0 ? '+' : ''}
              {sector.avg_price_change}%
            </div>
            <div className="sector-stocks">{sector.stock_count} stocks</div>
            
            {sector.stocks && sector.stocks.length > 0 && (
              <div className="sector-tooltip">
                <strong>{sector.sector}</strong>
                <div className="tooltip-stats">
                  <div>Stocks: {sector.stock_count}</div>
                  <div>Avg Change: {sector.avg_price_change}%</div>
                  <div>Total Volume: {sector.total_volume.toLocaleString()}</div>
                </div>
                <div className="top-stocks">
                  <strong>Top Movers:</strong>
                  {sector.stocks.map((stock) => (
                    <div key={stock.symbol} className="tooltip-stock">
                      <span>{stock.name}</span>
                      <span className={stock.price_change >= 0 ? 'positive' : 'negative'}>
                        {stock.price_change > 0 ? '+' : ''}
                        {stock.price_change.toFixed(2)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      
      <div className="heatmap-legend">
        <div className="legend-title">Performance Scale:</div>
        <div className="legend-items">
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#DC143C' }}></div>
            <span>&lt; -3%</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#FF6347' }}></div>
            <span>-3% to -1.5%</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#FFE4E1' }}></div>
            <span>-0.5% to 0%</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#90EE90' }}></div>
            <span>0% to 0.5%</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#32CD32' }}></div>
            <span>0.5% to 1.5%</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#006400' }}></div>
            <span>&gt; 3%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SectorHeatmap;
