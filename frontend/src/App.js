import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [amount, setAmount] = useState('1');
  const [price, setPrice] = useState(null);
  const [assetCap, setAssetCap] = useState('');
  const [totalCapital, setTotalCapital] = useState('');
  const [assets, setAssets] = useState([{ symbol: '', mcap: '' }]);
  const [rebalanceResults, setRebalanceResults] = useState(null);

  const fetchPrice = async (usdtAmount) => {
    try {
      const response = await axios.get(`http://localhost:8000/price?usdt=${usdtAmount}`);
      setPrice(response.data.price);
    } catch (error) {
      console.error('Error fetching price:', error);
    }
  };

  const handleInputChange = (event) => {
    const newValue = event.target.value;
    setAmount(newValue);
    fetchPrice(newValue);
  };

  const handleAssetChange = (index, field, value) => {
    const newAssets = [...assets];
    newAssets[index][field] = value;
    setAssets(newAssets);
  };

  const addAsset = () => {
    setAssets([...assets, { symbol: '', mcap: '' }]);
  };

  const removeAsset = (index) => {
    const newAssets = assets.filter((_, i) => i !== index);
    setAssets(newAssets);
  };

  const handleRebalance = async () => {
    try {
      const rebalanceData = {
        asset_cap: parseFloat(assetCap),
        total_capital: parseFloat(totalCapital),
        assets: assets.map(asset => ({
          symbol: asset.symbol,
          mcap: parseFloat(asset.mcap)
        })),
      };

      const response = await axios.post('http://localhost:8000/rebalance', rebalanceData, {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      setRebalanceResults(response.data);
    } catch (error) {
      console.error('Error rebalancing fund:', error);
    }
  };

  useEffect(() => {
    fetchPrice(amount);
  }, [amount]);

  return (
    <div className="App">
      <header className="App-header">
        <h1>USDT to ZAR Price Calculator</h1>
        <div className="input-container">
          <label>USDT amount to buy:</label>
          <input
            type="text"
            value={amount}
            onChange={handleInputChange}
            placeholder="Enter USDT amount"
          />
        </div>
        {price !== null && (
          <div className="price-container">
            <div>Price:</div>
            <div className="price">{price.toFixed(4)}</div>
          </div>
        )}
        <h2>Rebalance Fund</h2>
        <div className="rebalance-form">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Market Cap</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset, index) => (
                <tr key={index}>
                  <td>
                    <input
                      type="text"
                      value={asset.symbol}
                      onChange={(e) => handleAssetChange(index, 'symbol', e.target.value)}
                      placeholder="Enter symbol"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={asset.mcap}
                      onChange={(e) => handleAssetChange(index, 'mcap', e.target.value)}
                      placeholder="Enter market cap"
                    />
                  </td>
                  <td>
                    <button onClick={() => removeAsset(index)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button onClick={addAsset}>Add Asset</button>
          <div className="input-container">
            <label>Asset Cap:</label>
            <input
              type="text"
              value={assetCap}
              onChange={(e) => setAssetCap(e.target.value)}
              placeholder="Enter asset cap (0-1)"
            />
          </div>
          <div className="input-container">
            <label>Total Capital (ZAR):</label>
            <input
              type="text"
              value={totalCapital}
              onChange={(e) => setTotalCapital(e.target.value)}
              placeholder="Enter total capital in ZAR"
            />
          </div>
          <button onClick={handleRebalance}>Rebalance</button>
        </div>
        {rebalanceResults && (
          <div className="rebalance-results">
            <h3>Rebalance Results</h3>
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Price</th>
                  <th>Amount</th>
                  <th>USD Value</th>
                  <th>Percentage</th>
                </tr>
              </thead>
              <tbody>
                {rebalanceResults.map((asset, index) => (
                  <tr key={index}>
                    <td>{asset.symbol}</td>
                    <td>{asset.price.toFixed(2)}</td>
                    <td>{asset.amount.toFixed(6)}</td>
                    <td>{asset.usd_value.toFixed(2)}</td>
                    <td>{asset.final_percentage.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </header>
    </div>
  );
}

export default App;
