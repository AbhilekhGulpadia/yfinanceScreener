import React, { useState, useEffect } from 'react';
import './WiensteinScoring.css';
import CandlestickChart from './CandlestickChart';

function WiensteinScoring() {
    const [stocks, setStocks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [sortConfig, setSortConfig] = useState({ key: 'score', direction: 'desc' });
    const [selectedStock, setSelectedStock] = useState(null);
    const [notification, setNotification] = useState(null);

    useEffect(() => {
        fetchWiensteinScores();
    }, []);

    const fetchWiensteinScores = async () => {
        try {
            setLoading(true);
            setError(null);

            const response = await fetch('/api/weinstein-scores');

            if (!response.ok) {
                throw new Error('Failed to fetch Weinstein scores');
            }

            const data = await response.json();

            if (data.success) {
                setStocks(data.data || []);
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        } catch (err) {
            console.error('Error fetching Weinstein scores:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleSort = (key) => {
        let direction = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') {
            direction = 'desc';
        }
        setSortConfig({ key, direction });
    };

    const sortedStocks = [...stocks].sort((a, b) => {
        if (a[sortConfig.key] < b[sortConfig.key]) {
            return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (a[sortConfig.key] > b[sortConfig.key]) {
            return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
    });

    const getStageClass = (stage) => {
        switch (stage) {
            case 'Stage 1': return 'stage-1';
            case 'Stage 2': return 'stage-2';
            case 'Stage 3': return 'stage-3';
            case 'Stage 4': return 'stage-4';
            default: return '';
        }
    };

    const getScoreClass = (score) => {
        if (score >= 80) return 'score-high';
        if (score >= 60) return 'score-medium';
        return 'score-low';
    };

    const handleStockSelect = (stock) => {
        setSelectedStock(stock);
    };

    const handleShortlist = async (stock, event) => {
        event.stopPropagation(); // Prevent row click

        try {
            const response = await fetch('/api/shortlist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    symbol: stock.symbol,
                    name: stock.name,
                    sector: stock.sector,
                    price: stock.price,
                    score: stock.score,
                    stage: stock.stage,
                    ma30: stock.ma30,
                    rs: stock.rs
                })
            });

            const data = await response.json();

            if (data.success) {
                setNotification({ type: 'success', message: data.message });
                setTimeout(() => setNotification(null), 3000);
            } else {
                setNotification({ type: 'error', message: data.error });
                setTimeout(() => setNotification(null), 3000);
            }
        } catch (err) {
            console.error('Error adding to shortlist:', err);
            setNotification({ type: 'error', message: 'Failed to add to shortlist' });
            setTimeout(() => setNotification(null), 3000);
        }
    };

    if (loading) {
        return (
            <div className="wienstein-container">
                <div className="loading">Loading Wienstein scores...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="wienstein-container">
                <div className="error-message">
                    <h3>Error loading data</h3>
                    <p>{error}</p>
                    <button onClick={fetchWiensteinScores} className="retry-button">
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="wienstein-container">
            {notification && (
                <div className={`notification ${notification.type}`}>
                    {notification.message}
                </div>
            )}

            <div className="wienstein-header">
                <h2>Wienstein Stage Analysis</h2>
                <p className="description">
                    Stan Weinstein's Stage Analysis identifies the current market stage of each stock
                    based on price action and moving averages.
                </p>
                <button onClick={fetchWiensteinScores} className="refresh-button">
                    Refresh Data
                </button>
            </div>

            <div className="stage-legend">
                <div className="legend-item">
                    <span className="legend-badge stage-1">Stage 1</span>
                    <span>Accumulation/Basing</span>
                </div>
                <div className="legend-item">
                    <span className="legend-badge stage-2">Stage 2</span>
                    <span>Advancing/Markup</span>
                </div>
                <div className="legend-item">
                    <span className="legend-badge stage-3">Stage 3</span>
                    <span>Distribution/Topping</span>
                </div>
                <div className="legend-item">
                    <span className="legend-badge stage-4">Stage 4</span>
                    <span>Declining/Markdown</span>
                </div>
            </div>

            <div className="table-container">
                <table className="wienstein-table">
                    <thead>
                        <tr>
                            <th onClick={() => handleSort('symbol')}>
                                Symbol {sortConfig.key === 'symbol' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('name')}>
                                Name {sortConfig.key === 'name' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('sector')}>
                                Sector {sortConfig.key === 'sector' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('score')}>
                                Score {sortConfig.key === 'score' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('stage')}>
                                Stage {sortConfig.key === 'stage' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('price')}>
                                Price {sortConfig.key === 'price' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('change')}>
                                Change % {sortConfig.key === 'change' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('volume')}>
                                Volume {sortConfig.key === 'volume' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('ma30')}>
                                MA 30 {sortConfig.key === 'ma30' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('rs')}>
                                RS {sortConfig.key === 'rs' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                            </th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedStocks.map((stock) => (
                            <tr
                                key={stock.symbol}
                                onClick={() => handleStockSelect(stock)}
                                className={selectedStock?.symbol === stock.symbol ? 'selected' : ''}
                            >
                                <td className="symbol-cell">{stock.symbol}</td>
                                <td>{stock.name}</td>
                                <td>{stock.sector}</td>
                                <td>
                                    <span className={`score-badge ${getScoreClass(stock.score)}`}>
                                        {stock.score}
                                    </span>
                                </td>
                                <td>
                                    <span className={`stage-badge ${getStageClass(stock.stage)}`}>
                                        {stock.stage}
                                    </span>
                                </td>
                                <td className="price-cell">₹{stock.price}</td>
                                <td className={stock.change >= 0 ? 'positive' : 'negative'}>
                                    {stock.change >= 0 ? '+' : ''}{stock.change}%
                                </td>
                                <td className="volume-cell">{stock.volume.toLocaleString()}</td>
                                <td>₹{stock.ma30 || 'N/A'}</td>
                                <td>{stock.rs || 'N/A'}</td>
                                <td>
                                    <button
                                        className="shortlist-btn"
                                        onClick={(e) => handleShortlist(stock, e)}
                                        title="Add to Shortlist"
                                    >
                                        ⭐ Shortlist
                                    </button>
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
        </div>
    );
}

export default WiensteinScoring;
