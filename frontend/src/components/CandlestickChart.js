import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import './CandlestickChart.css';

function CandlestickChart({ symbol, name }) {
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchChartData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  const fetchChartData = async () => {
    if (!symbol) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/analysis/chart/${symbol}`);
      if (!response.ok) {
        throw new Error('Failed to fetch chart data');
      }
      const data = await response.json();
      setChartData(data);
    } catch (err) {
      console.error('Error fetching chart data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!symbol) {
    return (
      <div className="chart-container">
        <div className="chart-placeholder">
          <p>Select a stock from the table to view the chart</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="chart-container">
        <div className="chart-header">
          <h3>{name || symbol}</h3>
        </div>
        <div className="chart-loading">
          <div className="spinner"></div>
          <p>Loading chart data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="chart-container">
        <div className="chart-header">
          <h3>{name || symbol}</h3>
        </div>
        <div className="chart-error">
          <p>Error loading chart: {error}</p>
        </div>
      </div>
    );
  }

  if (!chartData || !chartData.chart_data || chartData.chart_data.length === 0) {
    return (
      <div className="chart-container">
        <div className="chart-header">
          <h3>{name || symbol}</h3>
        </div>
        <div className="chart-error">
          <p>No chart data available for this stock</p>
        </div>
      </div>
    );
  }

  // Prepare data for Plotly
  const dates = chartData.chart_data.map(d => d.timestamp);
  const opens = chartData.chart_data.map(d => d.open);
  const highs = chartData.chart_data.map(d => d.high);
  const lows = chartData.chart_data.map(d => d.low);
  const closes = chartData.chart_data.map(d => d.close);
  // const volumes = chartData.chart_data.map(d => d.volume);
  const rsi = chartData.chart_data.map(d => d.rsi);
  const ema21 = chartData.chart_data.map(d => d.ema_21);
  const ema44 = chartData.chart_data.map(d => d.ema_44);
  const ema200 = chartData.chart_data.map(d => d.ema_200);
  const macd = chartData.chart_data.map(d => d.macd);
  const macdSignal = chartData.chart_data.map(d => d.macd_signal);
  const macdHist = chartData.chart_data.map(d => d.macd_hist);

  // RSI Reference Lines at 20, 50, 80
  const rsiReferenceLines = [
    {
      x: dates,
      y: Array(dates.length).fill(80),
      type: 'scatter',
      mode: 'lines',
      name: 'RSI 80',
      line: { color: 'rgba(239, 83, 80, 0.5)', width: 1, dash: 'dash' },
      showlegend: false,
    },
    {
      x: dates,
      y: Array(dates.length).fill(50),
      type: 'scatter',
      mode: 'lines',
      name: 'RSI 50',
      line: { color: 'rgba(255, 255, 255, 0.3)', width: 1, dash: 'dot' },
      showlegend: false,
    },
    {
      x: dates,
      y: Array(dates.length).fill(20),
      type: 'scatter',
      mode: 'lines',
      name: 'RSI 20',
      line: { color: 'rgba(38, 166, 154, 0.5)', width: 1, dash: 'dash' },
      showlegend: false,
    },
  ];

  return (
    <div className="chart-container">
      <div className="chart-info">
        <p className="chart-data-range">
          Data Range: {new Date(dates[0]).toLocaleDateString()} to {new Date(dates[dates.length - 1]).toLocaleDateString()}
          {' • '}
          {chartData.chart_data.length} data points
        </p>
      </div>

      {/* Candlestick Chart with EMAs */}
      <div className="chart-section">
        <h4 className="chart-title">Price Chart with EMAs</h4>
        <Plot
          data={[
            {
              x: dates,
              open: opens,
              high: highs,
              low: lows,
              close: closes,
              type: 'candlestick',
              name: symbol,
              increasing: { line: { color: '#26a69a' } },
              decreasing: { line: { color: '#ef5350' } },
            },
            {
              x: dates,
              y: ema21,
              type: 'scatter',
              mode: 'lines',
              name: 'EMA 21',
              line: { color: '#ffd700', width: 2 },
            },
            {
              x: dates,
              y: ema44,
              type: 'scatter',
              mode: 'lines',
              name: 'EMA 44',
              line: { color: '#ff6b6b', width: 2 },
            },
            {
              x: dates,
              y: ema200,
              type: 'scatter',
              mode: 'lines',
              name: 'EMA 200',
              line: { color: '#4ecdc4', width: 2 },
            },
          ]}
          layout={{
            title: {
              text: `${name || symbol} - ${chartData.sector || 'N/A'}`,
              font: { color: '#333', size: 20 }
            },
            paper_bgcolor: '#ffffff',
            plot_bgcolor: '#ffffff',
            font: { color: '#333' },
            showlegend: true,
            legend: {
              orientation: 'h',
              yanchor: 'bottom',
              y: 1.02,
              xanchor: 'right',
              x: 1,
              bgcolor: 'rgba(255, 255, 255, 0.9)',
              bordercolor: '#e0e0e0',
              borderwidth: 1
            },
            xaxis: {
              rangeslider: { visible: false },
              type: 'date',
              gridcolor: '#e0e0e0',
              showgrid: true,
            },
            yaxis: {
              title: 'Price (₹)',
              gridcolor: '#e0e0e0',
              showgrid: true,
            },
            height: 500,
            hovermode: 'x unified',
            dragmode: 'zoom',
            margin: { t: 60, b: 40, l: 60, r: 40 },
          }}
          config={{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
          }}
          style={{ width: '100%', height: '500px' }}
          useResizeHandler={true}
        />
      </div>

      <div className="chart-separator"></div>

      {/* RSI Chart */}
      <div className="chart-section">
        <h4 className="chart-title">RSI (Relative Strength Index)</h4>
        <Plot
          data={[
            {
              x: dates,
              y: rsi,
              type: 'scatter',
              mode: 'lines',
              name: 'RSI',
              line: { color: '#9c27b0', width: 2 },
              fill: 'tozeroy',
              fillcolor: 'rgba(156, 39, 176, 0.1)',
            },
            ...rsiReferenceLines,
          ]}
          layout={{
            paper_bgcolor: '#ffffff',
            plot_bgcolor: '#ffffff',
            font: { color: '#333' },
            showlegend: false,
            xaxis: {
              type: 'date',
              gridcolor: '#e0e0e0',
              showgrid: true,
            },
            yaxis: {
              title: 'RSI',
              range: [0, 100],
              gridcolor: '#e0e0e0',
              showgrid: true,
              tickmode: 'array',
              tickvals: [0, 20, 50, 80, 100],
            },
            height: 300,
            hovermode: 'x unified',
            dragmode: 'zoom',
            margin: { t: 40, b: 40, l: 60, r: 40 },
            shapes: [
              {
                type: 'rect',
                xref: 'paper',
                yref: 'y',
                x0: 0,
                y0: 80,
                x1: 1,
                y1: 100,
                fillcolor: 'rgba(239, 83, 80, 0.05)',
                line: { width: 0 },
              },
              {
                type: 'rect',
                xref: 'paper',
                yref: 'y',
                x0: 0,
                y0: 0,
                x1: 1,
                y1: 20,
                fillcolor: 'rgba(38, 166, 154, 0.05)',
                line: { width: 0 },
              },
            ],
          }}
          config={{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
          }}
          style={{ width: '100%', height: '300px' }}
          useResizeHandler={true}
        />
      </div>

      <div className="chart-separator"></div>

      {/* MACD Chart */}
      <div className="chart-section">
        <h4 className="chart-title">MACD (Moving Average Convergence Divergence)</h4>
        <Plot
          data={[
            {
              x: dates,
              y: macdHist,
              type: 'bar',
              name: 'Histogram',
              marker: {
                color: macdHist.map(h => h >= 0 ? 'rgba(38, 166, 154, 0.6)' : 'rgba(239, 83, 80, 0.6)')
              },
            },
            {
              x: dates,
              y: macd,
              type: 'scatter',
              mode: 'lines',
              name: 'MACD',
              line: { color: '#2196f3', width: 2 },
            },
            {
              x: dates,
              y: macdSignal,
              type: 'scatter',
              mode: 'lines',
              name: 'Signal',
              line: { color: '#ff9800', width: 2 },
            },
          ]}
          layout={{
            paper_bgcolor: '#ffffff',
            plot_bgcolor: '#ffffff',
            font: { color: '#333' },
            showlegend: true,
            legend: {
              orientation: 'h',
              yanchor: 'bottom',
              y: 1.02,
              xanchor: 'right',
              x: 1,
              bgcolor: 'rgba(255, 255, 255, 0.9)',
              bordercolor: '#e0e0e0',
              borderwidth: 1
            },
            xaxis: {
              type: 'date',
              gridcolor: '#e0e0e0',
              showgrid: true,
            },
            yaxis: {
              title: 'MACD',
              gridcolor: '#e0e0e0',
              showgrid: true,
              zeroline: true,
              zerolinecolor: '#999',
              zerolinewidth: 1,
            },
            height: 300,
            hovermode: 'x unified',
            dragmode: 'zoom',
            margin: { t: 40, b: 40, l: 60, r: 40 },
          }}
          config={{
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d'],
          }}
          style={{ width: '100%', height: '300px' }}
          useResizeHandler={true}
        />
      </div>
    </div>
  );
}

export default CandlestickChart;
