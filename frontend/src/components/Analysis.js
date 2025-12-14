import React, { useState, useEffect } from 'react';
import './Analysis.css';
import CandlestickChart from './CandlestickChart';

import { fetchAnalysisData } from '../services/api';

function Analysis() {
  const [filteredData, setFilteredData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedStock, setSelectedStock] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

  useEffect(() => {
    loadAnalysisData();
  }, []);



  const loadAnalysisData = async () => {
    setLoading(true);
    try {
      const data = await fetchAnalysisData();

      // Use backend score directly, no client-side calculation needed
      const dataWithScores = (data.analysis_data || []).map(stock => ({
        ...stock
      }));

      // Sort by backend score (highest first)
      const sortedData = dataWithScores.sort((a, b) => {
        return (b.score || 0) - (a.score || 0);
      });

      setFilteredData(sortedData);
    } catch (error) {
      console.error('Error fetching analysis data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }

    const sorted = [...filteredData].sort((a, b) => {
      let aVal = a[key];
      let bVal = b[key];

      // Handle null values
      if (aVal === null) return 1;
      if (bVal === null) return -1;

      // Convert to lowercase for string comparison
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();

      if (aVal < bVal) return direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return direction === 'asc' ? 1 : -1;
      return 0;
    });

    setFilteredData(sorted);
    setSortConfig({ key, direction });
  };

  const getSortIndicator = (key) => {
    if (sortConfig.key !== key) return '⇅';
    return sortConfig.direction === 'asc' ? '↑' : '↓';
  };


  // Helper function to get score color class
  const getScoreClass = (score) => {
    if (score >= 80) return 'score-excellent';  // Green
    if (score >= 60) return 'score-good';       // Yellow
    if (score >= 40) return 'score-moderate';   // Orange
    return 'score-weak';                         // Red
  };

  const handleStockSelect = (stock) => {
    setSelectedStock(stock);
  };

  const getRSIClass = (rsi) => {
    if (rsi === null) return '';
    if (rsi < 30) return 'rsi-oversold';
    if (rsi > 70) return 'rsi-overbought';
    return 'rsi-neutral';
  };

  const getMACDClass = (macd) => {
    if (macd === 'Bullish') return 'macd-bullish';
    if (macd === 'Bearish') return 'macd-bearish';
    return 'macd-neutral';
  };

  const getEMAClass = (crossover) => {
    if (crossover === 'Yes') return 'ema-crossover-yes';
    if (crossover === 'Above') return 'ema-above';
    return 'ema-no';
  };

  return (
    <div className="analysis-container">
      <div className="analysis-header">
        <h2>Technical Analysis</h2>
        <button className="refresh-btn" onClick={loadAnalysisData} disabled={loading}>
          {loading ? 'Loading...' : '🔄 Refresh Analysis'}
        </button>
      </div>

      {loading ? (
        <div className="loading">Loading analysis data...</div>
      ) : (
        <>
          <div className="table-container">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th onClick={() => handleSort('symbol')}>
                    Symbol {getSortIndicator('symbol')}
                  </th>
                  <th onClick={() => handleSort('name')}>
                    Name {getSortIndicator('name')}
                  </th>
                  <th onClick={() => handleSort('sector')}>
                    Sector {getSortIndicator('sector')}
                  </th>
                  <th onClick={() => handleSort('score')}>
                    Score {getSortIndicator('score')}
                  </th>
                  <th onClick={() => handleSort('rsi')}>
                    RSI {getSortIndicator('rsi')}
                  </th>
                  <th onClick={() => handleSort('macd_signal')}>
                    MACD {getSortIndicator('macd_signal')}
                  </th>
                  <th onClick={() => handleSort('ema_crossover_21_44')}>
                    EMA 21/44 {getSortIndicator('ema_crossover_21_44')}
                  </th>
                  <th onClick={() => handleSort('price_above_ema_200')}>
                    Above EMA 200 {getSortIndicator('price_above_ema_200')}
                  </th>
                  <th onClick={() => handleSort('current_price')}>
                    Price (₹) {getSortIndicator('current_price')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredData.map((stock) => (
                  <tr
                    key={stock.symbol}
                    onClick={() => handleStockSelect(stock)}
                    className={selectedStock?.symbol === stock.symbol ? 'selected' : ''}
                  >
                    <td className="symbol-cell">{stock.symbol}</td>
                    <td>{stock.name}</td>
                    <td>{stock.sector}</td>
                    <td className={`score-cell ${getScoreClass(stock.score || 0)}`}>
                      {stock.score || 0}
                    </td>
                    <td className={getRSIClass(stock.rsi)}>
                      {stock.rsi !== null ? stock.rsi.toFixed(2) : 'N/A'}
                    </td>
                    <td className={getMACDClass(stock.macd_signal)}>
                      {stock.macd_signal || 'N/A'}
                    </td>
                    <td className={getEMAClass(stock.ema_crossover_21_44)}>
                      {stock.ema_crossover_21_44 || 'N/A'}
                    </td>
                    <td className={getEMAClass(stock.price_above_ema_200)}>
                      {stock.price_above_ema_200 || 'N/A'}
                    </td>
                    <td className="price-cell">
                      ₹{stock.current_price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedStock && (
            <div className="chart-section">
              <CandlestickChart
                symbol={selectedStock.symbol}
                name={selectedStock.name}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default Analysis;
