const API_BASE_URL = '/api';

export const fetchAnalysisData = async () => {
    const response = await fetch(`${API_BASE_URL}/analysis/stocks`);
    if (!response.ok) {
        throw new Error('Failed to fetch analysis data');
    }
    return response.json();
};

export const fetchSectorHeatmap = async (params) => {
    const queryString = new URLSearchParams(params).toString();
    const response = await fetch(`${API_BASE_URL}/ohlcv/sector-heatmap?${queryString}`);
    if (!response.ok) {
        throw new Error('Failed to fetch heatmap data');
    }
    return response.json();
};

export const fetchChartData = async (symbol) => {
    const response = await fetch(`${API_BASE_URL}/analysis/chart/${symbol}`);
    if (!response.ok) {
        throw new Error('Failed to fetch chart data');
    }
    return response.json();
};

export const triggerRefresh = async () => {
    const response = await fetch(`${API_BASE_URL}/ohlcv/refresh`, {
        method: 'POST'
    });
    if (!response.ok) {
        throw new Error('Failed to start refresh');
    }
    return response.json();
};

export const triggerInitialization = async () => {
    const response = await fetch(`${API_BASE_URL}/ohlcv/initialize-all`, {
        method: 'POST'
    });
    if (!response.ok) {
        throw new Error('Failed to start initialization');
    }
    return response.json();
};
