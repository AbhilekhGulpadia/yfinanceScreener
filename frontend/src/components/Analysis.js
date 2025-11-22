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

  const calculateConfidenceScore = (stock) => {
    let score = 0;
    const scores = {};

    // RSI Score (0-30 points)
    // Lower RSI (oversold) gets higher score
    if (stock.rsi !== null) {
      if (stock.rsi < 30) {
        scores.rsi = 30; // Oversold - highest score
      } else if (stock.rsi < 40) {
        scores.rsi = 20; // Near oversold
      } else if (stock.rsi < 50) {
        scores.rsi = 10; // Below neutral
      } else if (stock.rsi > 70) {
        scores.rsi = -10; // Overbought - negative score
      } else {
        scores.rsi = 5; // Neutral
      }
    } else {
      scores.rsi = 0;
    }

    // MACD Score (0-25 points)
    if (stock.macd_signal === 'Bullish') {
      scores.macd = 25; // Bullish crossover
    } else if (stock.macd_signal === 'Bearish') {
      scores.macd = -10; // Bearish crossover - negative
    } else {
      scores.macd = 0; // Neutral
    }

    // EMA Crossover Score (0-25 points)
    if (stock.ema_crossover_21_44 === 'Yes') {
      scores.ema_crossover = 25; // Strong bullish signal
    } else if (stock.ema_crossover_21_44 === 'Above') {
      scores.ema_crossover = 15; // Above but no recent crossover
    } else {
      scores.ema_crossover = 0;
    }

    // Price Above EMA 200 Score (0-20 points)
    if (stock.price_above_ema_200 === 'Yes') {
      scores.ema_200 = 20; // Above long-term trend
    } else {
      scores.ema_200 = 0;
    }

    // Calculate total score
    score = scores.rsi + scores.macd + scores.ema_crossover + scores.ema_200;

    return {
      total: score,
      breakdown: scores
    };
  };

  const loadAnalysisData = async () => {
    setLoading(true);
    try {
      const data = await fetchAnalysisData();

      // Calculate confidence scores and sort by total score
      const dataWithScores = (data.analysis_data || []).map(stock => ({
        ...stock,
        confidenceScore: calculateConfidenceScore(stock)
      }));

      // Sort by confidence score (highest first)
      const sortedData = dataWithScores.sort((a, b) => {
        return b.confidenceScore.total - a.confidenceScore.total;
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
                  <th onClick={() => handleSort('confidenceScore.total')}>
                    Score {getSortIndicator('confidenceScore.total')}
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
                    <td>
                      <span
                        className="confidence-score"
                        style={{
                          color: stock.confidenceScore.total > 60 ? '#26a69a' :
                            stock.confidenceScore.total > 30 ? '#ffa726' : '#666',
                          fontWeight: 'bold',
                          fontSize: '16px'
                        }}
                        title={`RSI: ${stock.confidenceScore.breakdown.rsi}, MACD: ${stock.confidenceScore.breakdown.macd}, EMA Cross: ${stock.confidenceScore.breakdown.ema_crossover}, EMA 200: ${stock.confidenceScore.breakdown.ema_200}`}
                      >
                        {stock.confidenceScore.total}
                      </span>
                    </td>
                    <td className={getRSIClass(stock.rsi)}>
                      {stock.rsi !== null ? stock.rsi.toFixed(2) : 'N/A'}
                    </td>
                    <td className={getMACDClass(stock.macd_signal)}>
                      {stock.macd_signal}
                    </td>
                    <td className={getEMAClass(stock.ema_crossover_21_44)}>
                      {stock.ema_crossover_21_44}
                    </td>
                    <td className={getEMAClass(stock.price_above_ema_200)}>
                      {stock.price_above_ema_200}
                    </td>
                    <td>₹{stock.current_price.toFixed(2)}</td>
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
