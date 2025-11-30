import React, { useState, useEffect } from 'react';
import './Shortlist.css';
import CandlestickChart from './CandlestickChart';

function Shortlist() {
    const [shortlistedStocks, setShortlistedStocks] = useState([]);
    const [trades, setTrades] = useState([]);
    const [portfolio, setPortfolio] = useState([]);
    const [pnlAnalysis, setPnlAnalysis] = useState(null);
    const [selectedStock, setSelectedStock] = useState(null);
    const [loading, setLoading] = useState(true);
    const [notification, setNotification] = useState(null);

    // Trade form state
    const [tradeForm, setTradeForm] = useState({
        symbol: '',
        trade_type: 'BUY',
        quantity: '',
        price: '',
        notes: ''
    });

    useEffect(() => {
        loadAllData();
    }, []);

    const loadAllData = async () => {
        setLoading(true);
        await Promise.all([
            fetchShortlist(),
            fetchTrades(),
            fetchPortfolio(),
            fetchPnLAnalysis()
        ]);
        setLoading(false);
    };

    const fetchShortlist = async () => {
        try {
            const response = await fetch('/api/shortlist');
            const data = await response.json();
            if (data.success) {
                setShortlistedStocks(data.data || []);
            }
        } catch (err) {
            console.error('Error fetching shortlist:', err);
        }
    };

    const fetchTrades = async () => {
        try {
            const response = await fetch('/api/trades');
            const data = await response.json();
            if (data.success) {
                setTrades(data.data || []);
            }
        } catch (err) {
            console.error('Error fetching trades:', err);
        }
    };

    const fetchPortfolio = async () => {
        try {
            const response = await fetch('/api/trades/portfolio');
            const data = await response.json();
            if (data.success) {
                setPortfolio(data.data || []);
            }
        } catch (err) {
            console.error('Error fetching portfolio:', err);
        }
    };

    const fetchPnLAnalysis = async () => {
        try {
            const response = await fetch('/api/trades/pnl');
            const data = await response.json();
            if (data.success) {
                setPnlAnalysis(data.data);
            }
        } catch (err) {
            console.error('Error fetching P/L analysis:', err);
        }
    };

    const handleRemoveFromShortlist = async (id) => {
        try {
            const response = await fetch(`/api/shortlist/${id}`, {
                method: 'DELETE'
            });
            const data = await response.json();

            if (data.success) {
                showNotification('success', data.message);
                fetchShortlist();
            } else {
                showNotification('error', data.error);
            }
        } catch (err) {
            showNotification('error', 'Failed to remove from shortlist');
        }
    };

    const handleTradeSubmit = async (e) => {
        e.preventDefault();

        try {
            const response = await fetch('/api/trades', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ...tradeForm,
                    quantity: parseInt(tradeForm.quantity),
                    price: parseFloat(tradeForm.price)
                })
            });

            const data = await response.json();

            if (data.success) {
                showNotification('success', 'Trade recorded successfully');
                setTradeForm({
                    symbol: '',
                    trade_type: 'BUY',
                    quantity: '',
                    price: '',
                    notes: ''
                });
                loadAllData(); // Refresh all data
            } else {
                showNotification('error', data.error);
            }
        } catch (err) {
            showNotification('error', 'Failed to record trade');
        }
    };

    const handleDeleteTrade = async (id) => {
        if (!window.confirm('Are you sure you want to delete this trade?')) {
            return;
        }

        try {
            const response = await fetch(`/api/trades/${id}`, {
                method: 'DELETE'
            });
            const data = await response.json();

            if (data.success) {
                showNotification('success', 'Trade deleted');
                loadAllData();
            } else {
                showNotification('error', data.error);
            }
        } catch (err) {
            showNotification('error', 'Failed to delete trade');
        }
    };

    const showNotification = (type, message) => {
        setNotification({ type, message });
        setTimeout(() => setNotification(null), 3000);
    };

    if (loading) {
        return (
            <div className="shortlist-container">
                <div className="loading">Loading shortlist data...</div>
            </div>
        );
    }

    return (
        <div className="shortlist-container">
            {notification && (
                <div className={`notification ${notification.type}`}>
                    {notification.message}
                </div>
            )}

            {/* Shortlisted Stocks Section */}
            <div className="section">
                <div className="section-header">
                    <h2>📋 Shortlisted Stocks</h2>
                    <button onClick={fetchShortlist} className="refresh-btn">
                        🔄 Refresh
                    </button>
                </div>

                <div className="table-container">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Symbol</th>
                                <th>Name</th>
                                <th>Sector</th>
                                <th>Shortlisted At</th>
                                <th>Price @ Shortlist</th>
                                <th>Current Price</th>
                                <th>Change %</th>
                                <th>Score</th>
                                <th>Stage</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {shortlistedStocks.length === 0 ? (
                                <tr>
                                    <td colSpan="10" className="empty-message">
                                        No stocks shortlisted yet. Add stocks from the Weinstein Scoring tab!
                                    </td>
                                </tr>
                            ) : (
                                shortlistedStocks.map((stock) => (
                                    <tr
                                        key={stock.id}
                                        onClick={() => setSelectedStock(stock)}
                                        className={selectedStock?.id === stock.id ? 'selected' : ''}
                                    >
                                        <td className="symbol-cell">{stock.symbol}</td>
                                        <td>{stock.name}</td>
                                        <td>{stock.sector}</td>
                                        <td>{new Date(stock.shortlisted_at).toLocaleString()}</td>
                                        <td>₹{stock.price_at_shortlist?.toFixed(2)}</td>
                                        <td>₹{stock.current_price?.toFixed(2)}</td>
                                        <td className={stock.change_percent >= 0 ? 'positive' : 'negative'}>
                                            {stock.change_percent >= 0 ? '+' : ''}{stock.change_percent}%
                                        </td>
                                        <td>{stock.score}</td>
                                        <td>{stock.stage}</td>
                                        <td>
                                            <button
                                                className="remove-btn"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleRemoveFromShortlist(stock.id);
                                                }}
                                            >
                                                ❌ Remove
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
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

            {/* Trade Recording Section */}
            <div className="section">
                <div className="section-header">
                    <h2>💼 Record Trade</h2>
                </div>

                <form onSubmit={handleTradeSubmit} className="trade-form">
                    <div className="form-row">
                        <div className="form-group">
                            <label>Stock Symbol</label>
                            <input
                                type="text"
                                value={tradeForm.symbol}
                                onChange={(e) => setTradeForm({ ...tradeForm, symbol: e.target.value.toUpperCase() })}
                                placeholder="e.g., RELIANCE.NS"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label>Trade Type</label>
                            <div className="radio-group">
                                <label>
                                    <input
                                        type="radio"
                                        value="BUY"
                                        checked={tradeForm.trade_type === 'BUY'}
                                        onChange={(e) => setTradeForm({ ...tradeForm, trade_type: e.target.value })}
                                    />
                                    Buy
                                </label>
                                <label>
                                    <input
                                        type="radio"
                                        value="SELL"
                                        checked={tradeForm.trade_type === 'SELL'}
                                        onChange={(e) => setTradeForm({ ...tradeForm, trade_type: e.target.value })}
                                    />
                                    Sell
                                </label>
                            </div>
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Quantity</label>
                            <input
                                type="number"
                                value={tradeForm.quantity}
                                onChange={(e) => setTradeForm({ ...tradeForm, quantity: e.target.value })}
                                placeholder="Number of shares"
                                min="1"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label>Price per Share (₹)</label>
                            <input
                                type="number"
                                step="0.01"
                                value={tradeForm.price}
                                onChange={(e) => setTradeForm({ ...tradeForm, price: e.target.value })}
                                placeholder="0.00"
                                min="0.01"
                                required
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Notes (Optional)</label>
                        <textarea
                            value={tradeForm.notes}
                            onChange={(e) => setTradeForm({ ...tradeForm, notes: e.target.value })}
                            placeholder="Add any notes about this trade..."
                            rows="3"
                        />
                    </div>

                    <button type="submit" className="submit-btn">
                        Record Trade
                    </button>
                </form>

                {/* Trade History */}
                <div className="subsection">
                    <h3>Trade History</h3>
                    <div className="table-container">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Date</th>
                                    <th>Symbol</th>
                                    <th>Type</th>
                                    <th>Quantity</th>
                                    <th>Price</th>
                                    <th>Total</th>
                                    <th>Charges</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades.length === 0 ? (
                                    <tr>
                                        <td colSpan="8" className="empty-message">
                                            No trades recorded yet
                                        </td>
                                    </tr>
                                ) : (
                                    trades.map((trade) => (
                                        <tr key={trade.id}>
                                            <td>{new Date(trade.trade_date).toLocaleString()}</td>
                                            <td className="symbol-cell">{trade.symbol}</td>
                                            <td>
                                                <span className={`trade-type ${trade.trade_type.toLowerCase()}`}>
                                                    {trade.trade_type}
                                                </span>
                                            </td>
                                            <td>{trade.quantity}</td>
                                            <td>₹{trade.price.toFixed(2)}</td>
                                            <td>₹{(trade.quantity * trade.price).toFixed(2)}</td>
                                            <td>₹{trade.total_charges.toFixed(2)}</td>
                                            <td>
                                                <button
                                                    className="delete-btn"
                                                    onClick={() => handleDeleteTrade(trade.id)}
                                                >
                                                    🗑️
                                                </button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* P/L Analysis Section */}
            <div className="section">
                <div className="section-header">
                    <h2>📊 P/L Analysis</h2>
                </div>

                {pnlAnalysis && (
                    <>
                        <div className="pnl-cards">
                            <div className="pnl-card">
                                <div className="card-label">Total Investment</div>
                                <div className="card-value">₹{pnlAnalysis.total_investment.toLocaleString()}</div>
                            </div>
                            <div className="pnl-card">
                                <div className="card-label">Current Value</div>
                                <div className="card-value">₹{pnlAnalysis.total_current_value.toLocaleString()}</div>
                            </div>
                            <div className="pnl-card">
                                <div className="card-label">Unrealized P/L</div>
                                <div className={`card-value ${pnlAnalysis.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>
                                    ₹{pnlAnalysis.unrealized_pnl.toLocaleString()}
                                </div>
                            </div>
                            <div className="pnl-card">
                                <div className="card-label">Realized P/L</div>
                                <div className={`card-value ${pnlAnalysis.realized_pnl >= 0 ? 'positive' : 'negative'}`}>
                                    ₹{pnlAnalysis.realized_pnl.toLocaleString()}
                                </div>
                            </div>
                            <div className="pnl-card highlight">
                                <div className="card-label">Net P/L (After Charges)</div>
                                <div className={`card-value ${pnlAnalysis.net_pnl >= 0 ? 'positive' : 'negative'}`}>
                                    ₹{pnlAnalysis.net_pnl.toLocaleString()}
                                </div>
                            </div>
                        </div>

                        {/* Portfolio Holdings */}
                        <div className="subsection">
                            <h3>Current Holdings</h3>
                            <div className="table-container">
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Symbol</th>
                                            <th>Quantity</th>
                                            <th>Avg Buy Price</th>
                                            <th>Current Price</th>
                                            <th>Investment</th>
                                            <th>Current Value</th>
                                            <th>Unrealized P/L</th>
                                            <th>P/L %</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {portfolio.length === 0 ? (
                                            <tr>
                                                <td colSpan="8" className="empty-message">
                                                    No open positions
                                                </td>
                                            </tr>
                                        ) : (
                                            portfolio.map((position) => (
                                                <tr key={position.symbol}>
                                                    <td className="symbol-cell">{position.symbol}</td>
                                                    <td>{position.quantity}</td>
                                                    <td>₹{position.avg_buy_price.toFixed(2)}</td>
                                                    <td>₹{position.current_price.toFixed(2)}</td>
                                                    <td>₹{position.investment.toLocaleString()}</td>
                                                    <td>₹{position.current_value.toLocaleString()}</td>
                                                    <td className={position.unrealized_pnl >= 0 ? 'positive' : 'negative'}>
                                                        ₹{position.unrealized_pnl.toLocaleString()}
                                                    </td>
                                                    <td className={position.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'}>
                                                        {position.unrealized_pnl_pct >= 0 ? '+' : ''}{position.unrealized_pnl_pct.toFixed(2)}%
                                                    </td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Charges Breakdown */}
                        <div className="subsection">
                            <h3>Total Charges Breakdown</h3>
                            <div className="charges-grid">
                                <div className="charge-item">
                                    <span>Brokerage:</span>
                                    <span>₹{pnlAnalysis.charges_breakdown.brokerage.toFixed(2)}</span>
                                </div>
                                <div className="charge-item">
                                    <span>STT:</span>
                                    <span>₹{pnlAnalysis.charges_breakdown.stt.toFixed(2)}</span>
                                </div>
                                <div className="charge-item">
                                    <span>Exchange Charges:</span>
                                    <span>₹{pnlAnalysis.charges_breakdown.exchange_charges.toFixed(2)}</span>
                                </div>
                                <div className="charge-item">
                                    <span>GST:</span>
                                    <span>₹{pnlAnalysis.charges_breakdown.gst.toFixed(2)}</span>
                                </div>
                                <div className="charge-item">
                                    <span>SEBI Charges:</span>
                                    <span>₹{pnlAnalysis.charges_breakdown.sebi_charges.toFixed(2)}</span>
                                </div>
                                <div className="charge-item">
                                    <span>Stamp Duty:</span>
                                    <span>₹{pnlAnalysis.charges_breakdown.stamp_duty.toFixed(2)}</span>
                                </div>
                                <div className="charge-item total">
                                    <span>Total Charges:</span>
                                    <span>₹{pnlAnalysis.charges_breakdown.total.toFixed(2)}</span>
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

export default Shortlist;
