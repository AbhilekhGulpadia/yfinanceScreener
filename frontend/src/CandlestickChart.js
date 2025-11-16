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
      const response = await fetch(`http://localhost:5000/api/analysis/chart/${symbol}`);
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
  const volumes = chartData.chart_data.map(d => d.volume);
  const rsi = chartData.chart_data.map(d => d.rsi);
  const ema21 = chartData.chart_data.map(d => d.ema_21);
  const ema44 = chartData.chart_data.map(d => d.ema_44);
  const ema200 = chartData.chart_data.map(d => d.ema_200);
  const macd = chartData.chart_data.map(d => d.macd);
  const macdSignal = chartData.chart_data.map(d => d.macd_signal);
  const macdHist = chartData.chart_data.map(d => d.macd_hist);

  // Create traces for the main chart
  const traces = [
    // Candlestick
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
      xaxis: 'x',
      yaxis: 'y',
    },
    // EMA 21
    {
      x: dates,
      y: ema21,
      type: 'scatter',
      mode: 'lines',
      name: 'EMA 21',
      line: { color: '#ffd700', width: 1.5 },
      xaxis: 'x',
      yaxis: 'y',
    },
    // EMA 44
    {
      x: dates,
      y: ema44,
      type: 'scatter',
      mode: 'lines',
      name: 'EMA 44',
      line: { color: '#ff6b6b', width: 1.5 },
      xaxis: 'x',
      yaxis: 'y',
    },
    // EMA 200
    {
      x: dates,
      y: ema200,
      type: 'scatter',
      mode: 'lines',
      name: 'EMA 200',
      line: { color: '#4ecdc4', width: 1.5 },
      xaxis: 'x',
      yaxis: 'y',
    },
    // Volume
    {
      x: dates,
      y: volumes,
      type: 'bar',
      name: 'Volume',
      marker: {
        color: volumes.map((v, i) => closes[i] >= opens[i] ? 'rgba(38, 166, 154, 0.3)' : 'rgba(239, 83, 80, 0.3)')
      },
      xaxis: 'x',
      yaxis: 'y2',
    },
    // RSI
    {
      x: dates,
      y: rsi,
      type: 'scatter',
      mode: 'lines',
      name: 'RSI',
      line: { color: '#9c27b0', width: 2 },
      xaxis: 'x',
      yaxis: 'y3',
    },
    // RSI Reference Lines
    {
      x: dates,
      y: Array(dates.length).fill(70),
      type: 'scatter',
      mode: 'lines',
      name: 'Overbought',
      line: { color: 'rgba(239, 83, 80, 0.5)', width: 1, dash: 'dash' },
      xaxis: 'x',
      yaxis: 'y3',
      showlegend: false,
    },
    {
      x: dates,
      y: Array(dates.length).fill(30),
      type: 'scatter',
      mode: 'lines',
      name: 'Oversold',
      line: { color: 'rgba(38, 166, 154, 0.5)', width: 1, dash: 'dash' },
      xaxis: 'x',
      yaxis: 'y3',
      showlegend: false,
    },
    // MACD
    {
      x: dates,
      y: macd,
      type: 'scatter',
      mode: 'lines',
      name: 'MACD',
      line: { color: '#2196f3', width: 2 },
      xaxis: 'x',
      yaxis: 'y4',
    },
    // MACD Signal
    {
      x: dates,
      y: macdSignal,
      type: 'scatter',
      mode: 'lines',
      name: 'Signal',
      line: { color: '#ff9800', width: 2 },
      xaxis: 'x',
      yaxis: 'y4',
    },
    // MACD Histogram
    {
      x: dates,
      y: macdHist,
      type: 'bar',
      name: 'Histogram',
      marker: {
        color: macdHist.map(h => h >= 0 ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)')
      },
      xaxis: 'x',
      yaxis: 'y4',
    },
  ];

  const layout = {
    title: {
      text: `${name || symbol} - ${chartData.sector || 'N/A'}`,
      font: { color: '#d1d4dc', size: 20 }
    },
    paper_bgcolor: '#1a1a2e',
    plot_bgcolor: '#1a1a2e',
    font: { color: '#d1d4dc' },
    showlegend: true,
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.02,
      xanchor: 'right',
      x: 1,
      bgcolor: 'rgba(26, 26, 46, 0.8)',
      bordercolor: '#2a2e39',
      borderwidth: 1
    },
    xaxis: {
      domain: [0, 1],
      rangeslider: { visible: false },
      type: 'date',
      gridcolor: '#2a2e39',
      showgrid: true,
    },
    yaxis: {
      domain: [0.45, 1],
      title: 'Price',
      gridcolor: '#2a2e39',
      showgrid: true,
    },
    yaxis2: {
      domain: [0.35, 0.43],
      title: 'Volume',
      gridcolor: '#2a2e39',
      showgrid: false,
    },
    yaxis3: {
      domain: [0.18, 0.32],
      title: 'RSI',
      range: [0, 100],
      gridcolor: '#2a2e39',
      showgrid: true,
    },
    yaxis4: {
      domain: [0, 0.15],
      title: 'MACD',
      gridcolor: '#2a2e39',
      showgrid: true,
    },
    height: 900,
    hovermode: 'x unified',
    dragmode: 'zoom',
  };

  const config = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: `${symbol}_chart`,
      height: 900,
      width: 1400,
      scale: 2
    }
  };

  return (
    <div className="chart-container">
      <div className="chart-info">
        <p className="chart-data-range">
          Data Range: {new Date(dates[0]).toLocaleDateString()} to {new Date(dates[dates.length - 1]).toLocaleDateString()}
          {' • '}
          {chartData.chart_data.length} data points
        </p>
      </div>
      <Plot
        data={traces}
        layout={layout}
        config={config}
        style={{ width: '100%', height: '900px' }}
        useResizeHandler={true}
      />
    </div>
  );
}

export default CandlestickChart;
