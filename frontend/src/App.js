import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newItem, setNewItem] = useState({ name: '', value: '' });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const response = await fetch('/api/data');
      if (!response.ok) {
        throw new Error('Failed to fetch data');
      }
      const result = await response.json();
      setData(result.items);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/data', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newItem),
      });
      
      if (!response.ok) {
        throw new Error('Failed to submit data');
      }
      
      const result = await response.json();
      alert(`Success: ${result.message}`);
      setNewItem({ name: '', value: '' });
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  if (loading) return <div className="App"><p>Loading...</p></div>;
  if (error) return <div className="App"><p>Error: {error}</p></div>;

  return (
    <div className="App">
      <header className="App-header">
        <h1>Stock Analyzer</h1>
        <p>React + Python Web App</p>
      </header>

      <main className="App-main">
        <section className="data-section">
          <h2>Data from Backend</h2>
          <div className="data-grid">
            {data.map((item) => (
              <div key={item.id} className="data-card">
                <h3>{item.name}</h3>
                <p>Value: {item.value}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="form-section">
          <h2>Add New Item</h2>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="name">Name:</label>
              <input
                type="text"
                id="name"
                value={newItem.name}
                onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="value">Value:</label>
              <input
                type="number"
                id="value"
                value={newItem.value}
                onChange={(e) => setNewItem({ ...newItem, value: e.target.value })}
                required
              />
            </div>
            <button type="submit">Submit</button>
          </form>
        </section>
      </main>
    </div>
  );
}

export default App;
