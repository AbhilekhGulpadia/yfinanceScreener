import React, { useState, useEffect } from 'react';
import './Analysis.css';
import CandlestickChart from './CandlestickChart';

function Analysis() {
  const [filteredData, setFilteredData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedStock, setSelectedStock] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

  useEffect(() => {
    fetchAnalysisData();
  }, []);

  const fetchAnalysisData = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `http://localhost:5000/api/analysis/stocks`
      );
      const data = await response.json();
      setFilteredData(data.analysis_data || []);
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
                  <th onClick={() => handleSort('rsi')}>
                    RSI {getSortIndicator('rsi')}
                  </th>
                  <th onClick={() => handleSort('macd_crossover')}>
                    MACD {getSortIndicator('macd_crossover')}
                  </th>
                  <th onClick={() => handleSort('ema_21_crossover')}>
                    21 EMA {getSortIndicator('ema_21_crossover')}
                  </th>
                  <th onClick={() => handleSort('ema_44_crossover')}>
                    44 EMA {getSortIndicator('ema_44_crossover')}
                  </th>
                  <th onClick={() => handleSort('ema_200_crossover')}>
                    200 EMA {getSortIndicator('ema_200_crossover')}
                  </th>
                  <th onClick={() => handleSort('current_price')}>
                    Price {getSortIndicator('current_price')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredData.map((stock, index) => (
                  <tr
                    key={index}
                    onClick={() => handleStockSelect(stock)}
                    className={selectedStock?.symbol === stock.symbol ? 'selected' : ''}
                  >
                    <td className="symbol-cell">{stock.symbol}</td>
                    <td>{stock.name}</td>
                    <td>{stock.sector}</td>
                    <td className={getRSIClass(stock.rsi)}>
                      {stock.rsi !== null ? stock.rsi.toFixed(2) : 'N/A'}
                    </td>
                    <td className={getMACDClass(stock.macd_crossover)}>
                      {stock.macd_crossover}
                    </td>
                    <td className={getEMAClass(stock.ema_21_crossover)}>
                      {stock.ema_21_crossover}
                    </td>
                    <td className={getEMAClass(stock.ema_44_crossover)}>
                      {stock.ema_44_crossover}
                    </td>
                    <td className={getEMAClass(stock.ema_200_crossover)}>
                      {stock.ema_200_crossover}
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
