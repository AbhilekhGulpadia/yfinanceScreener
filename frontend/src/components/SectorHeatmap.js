import React, { useEffect, useState } from 'react';
import { triggerRefresh } from '../services/api';
import DataDownload from './DataDownload';
import './SectorHeatmap.css';

function SectorHeatmap() {
  const [heatmapData, setHeatmapData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [filterInfo, setFilterInfo] = useState(null);
  const [expandedSector, setExpandedSector] = useState(null);

  // Filter states
  const [duration, setDuration] = useState('1d');
  const [customMode, setCustomMode] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const fetchHeatmapData = async (filterParams = {}) => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();

      if (customMode && startDate && endDate) {
        params.append('start_date', startDate);
        params.append('end_date', endDate);
      } else {
        params.append('duration', filterParams.duration || duration);
      }

      const response = await fetch(`/api/ohlcv/sector-heatmap?${params}`);
      if (!response.ok) {
        throw new Error('Failed to fetch heatmap data');
      }
      const result = await response.json();
      setHeatmapData(result.heatmap_data);
      setLastUpdate(new Date(result.timestamp).toLocaleString());
      setFilterInfo(result.filter);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHeatmapData();
    // Refresh every 5 minutes
    const interval = setInterval(() => fetchHeatmapData(), 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [duration, customMode, startDate, endDate]);

  const handleDurationChange = (newDuration) => {
    setDuration(newDuration);
    setCustomMode(false);
  };

  const handleCustomDateApply = () => {
    if (startDate && endDate) {
      setCustomMode(true);
      fetchHeatmapData();
    } else {
      alert('Please select both start and end dates');
    }
  };

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState('');

  // Import triggerRefresh from api service
  // Note: We need to update imports at the top of the file first

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true);
      setRefreshMessage('Starting data refresh...');

      // Trigger backend refresh
      await triggerRefresh();

      setRefreshMessage('Refresh started in background. Data will update shortly.');

      // Poll for updates or just wait a bit and re-fetch heatmap
      setTimeout(() => {
        fetchHeatmapData();
        setIsRefreshing(false);
        setRefreshMessage('');
      }, 5000);

    } catch (err) {
      setError('Failed to trigger refresh: ' + err.message);
      setIsRefreshing(false);
    }
  };

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

  if (error) return <div className="heatmap-error">Error: {error}</div>;

  return (
    <div className="heatmap-container" onClick={() => setExpandedSector(null)}>
      <div className="heatmap-header" onClick={(e) => e.stopPropagation()}>
        <div className="header-left">
          <h2>Sector Heatmap</h2>
          {lastUpdate && <p className="last-update">Last updated: {lastUpdate}</p>}
        </div>
        <div className="header-right">
          <DataDownload />
        </div>
      </div>

      {/* Filter Controls */}
      <div className="filter-section">
        <div className="filter-group">
          <label>Duration:</label>
          <div className="duration-buttons">
            <button
              className={`duration-btn ${!customMode && duration === '1d' ? 'active' : ''}`}
              onClick={() => handleDurationChange('1d')}
            >
              1 Day
            </button>
            <button
              className={`duration-btn ${!customMode && duration === '1w' ? 'active' : ''}`}
              onClick={() => handleDurationChange('1w')}
            >
              1 Week
            </button>
            <button
              className={`duration-btn ${!customMode && duration === '1m' ? 'active' : ''}`}
              onClick={() => handleDurationChange('1m')}
            >
              1 Month
            </button>
            <button
              className={`duration-btn ${!customMode && duration === '3m' ? 'active' : ''}`}
              onClick={() => handleDurationChange('3m')}
            >
              3 Months
            </button>
            <button
              className={`duration-btn ${!customMode && duration === '6m' ? 'active' : ''}`}
              onClick={() => handleDurationChange('6m')}
            >
              6 Months
            </button>
            <button
              className={`duration-btn ${!customMode && duration === '1y' ? 'active' : ''}`}
              onClick={() => handleDurationChange('1y')}
            >
              1 Year
            </button>
            <button
              className={`duration-btn ${!customMode && duration === 'ytd' ? 'active' : ''}`}
              onClick={() => handleDurationChange('ytd')}
            >
              YTD
            </button>
          </div>
        </div>

        <div className="filter-group custom-date-group">
          <label>Custom Date Range:</label>
          <div className="custom-date-inputs">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="date-input"
            />
            <span className="date-separator">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="date-input"
            />
            <button
              className="apply-btn"
              onClick={handleCustomDateApply}
              disabled={!startDate || !endDate}
            >
              Apply
            </button>
          </div>
        </div>

        <div className="filter-actions">
          <button className="refresh-btn" onClick={handleRefresh}>
            🔄 Refresh
          </button>
          {filterInfo && (
            <span className="filter-info-text">
              Showing: {new Date(filterInfo.start_date).toLocaleDateString()} to{' '}
              {new Date(filterInfo.end_date).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>

      {refreshMessage && (
        <div className="refresh-message" style={{
          padding: '10px',
          marginBottom: '15px',
          backgroundColor: '#e8f4f8',
          color: '#0056b3',
          borderRadius: '4px',
          textAlign: 'center'
        }}>
          {refreshMessage}
        </div>
      )}

      {loading && <div className="heatmap-loading">Loading sector heatmap...</div>}

      {!loading && (
        <div className="heatmap-grid">
          {heatmapData.map((sector) => {
            const isExpanded = expandedSector === sector.sector;
            const stocksToShow = isExpanded ? sector.stocks : sector.stocks.slice(0, 3);

            return (
              <div
                key={sector.sector}
                className={`heatmap-cell ${isExpanded ? 'expanded' : ''}`}
                style={{
                  backgroundColor: getColorForChange(sector.avg_price_change),
                  color: getTextColor(sector.avg_price_change)
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  setExpandedSector(isExpanded ? null : sector.sector);
                }}
              >
                <div className="sector-header">
                  <div className="sector-name">{sector.sector}</div>
                  <div className="sector-change-badge">
                    {sector.avg_price_change > 0 ? '+' : ''}
                    {sector.avg_price_change}%
                  </div>
                </div>

                <div className="sector-movers">
                  {stocksToShow.map((stock) => (
                    <div key={stock.symbol} className="mover-row">
                      <div className="mover-info">
                        <span className="mover-symbol">{stock.name.split(' ')[0]}</span>
                        <span className="mover-percent">
                          {stock.price_change > 0 ? '+' : ''}
                          {stock.price_change.toFixed(1)}%
                        </span>
                      </div>
                      <div className="mover-bar-container">
                        <div
                          className={`mover-bar ${stock.price_change >= 0 ? 'positive' : 'negative'}`}
                          style={{
                            width: `${Math.min(Math.abs(stock.price_change) * 5, 100)}%`
                          }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="sector-footer">
                  {sector.stock_count} stocks {isExpanded ? `(showing ${stocksToShow.length})` : '(click to expand)'}
                </div>
              </div>
            );
          })}
        </div>
      )}

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
