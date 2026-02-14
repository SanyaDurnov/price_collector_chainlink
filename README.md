# Chainlink Price Collector

A Python service that collects cryptocurrency prices from Chainlink oracles on Polygon and provides a REST API for querying historical prices.

## Features

- **Real-time Price Collection**: Fetches prices from Chainlink oracles every second
- **File-based Storage**: Simple JSON file storage (no database required)
- **REST API**: Query prices by symbol and timestamp
- **Configurable**: Easy to customize via JSON configuration
- **VPS Ready**: Designed for easy deployment on your VPS

## Supported Symbols

- **BTC/USD**: Bitcoin price
- **ETH/USD**: Ethereum price  
- **SOL/USD**: Solana price

All prices are sourced from Chainlink oracles on Polygon (same as Polymarket).

## Installation

1. **Clone or download the project files**
2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create directories** (they will be created automatically on first run):
   ```bash
   mkdir data logs
   ```

## Configuration

Edit `config.json` to customize the service:

```json
{
  "rpc_url": "https://polygon-rpc.com",
  "api_port": 5000,
  "collection_interval": 1,
  "cleanup_interval": 600,
  "data_retention_hours": 6,
  "symbols": {
    "BTC": "0xc907E116054Ad103354f2D350FD2514433D57F6f",
    "ETH": "0xF9680D99D6C9589e2a93a78A04A279e509205945",
    "SOL": "0x10C8264C0935b3B9870013e057f330Ff3e9C56dC"
  },
  "storage": {
    "type": "file",
    "data_directory": "data",
    "log_directory": "logs"
  }
}
```

### Configuration Options

- `rpc_url`: Polygon RPC endpoint (default: polygon-rpc.com)
- `api_port`: API server port (default: 5000)
- `collection_interval`: Price collection interval in seconds (default: 1)
- `cleanup_interval`: Cleanup interval in seconds (default: 600 = 10 minutes)
- `data_retention_hours`: How long to keep price data (default: 6 hours)
- `symbols`: Chainlink oracle addresses for each symbol
- `data_directory`: Directory for price data files
- `log_directory`: Directory for log files

## Usage

### Run the Service

```bash
python chainlink_price_service.py
```

The service will:
1. Connect to the Polygon RPC
2. Start collecting prices every second
3. Store prices in `data/prices.json`
4. Start the API server on port 5000
5. Clean up old data every 10 minutes

### Test the Service

Before running the full service, test the components:

```bash
# Test price fetching and storage
python test_price_collector.py

# Test API endpoints
python test_api.py
```

### API Endpoints

#### Health Check
```
GET /health
```
Returns service status and available symbols.

#### Get Latest Prices
```
GET /latest
```
Returns the latest price for each symbol.

#### Get Price at Timestamp
```
GET /price/{symbol}?timestamp={unix_timestamp}&tolerance={seconds}
```

**Parameters:**
- `symbol`: BTC, ETH, or SOL (case insensitive)
- `timestamp`: Unix timestamp to query
- `tolerance`: Maximum difference in seconds (default: 60)

**Example:**
```
GET /price/BTC?timestamp=1707825600&tolerance=60
```

**Response:**
```json
{
  "symbol": "BTC",
  "price": 52000.50,
  "timestamp": 1707825600,
  "requested_timestamp": 1707825600,
  "round_id": 12345,
  "source": "chainlink"
}
```

## File Structure

```
price-collector/
├── config.json              # Configuration file
├── chainlink_price_service.py  # Main service
├── requirements.txt         # Python dependencies
├── test_price_collector.py  # Price collection tests
├── test_api.py             # API tests
├── README.md               # This file
├── data/                   # Price data storage
│   └── prices.json         # Price data file
└── logs/                   # Log files
    └── price_collector.log # Service logs
```

## Data Storage

Prices are stored in `data/prices.json` with the following structure:

```json
[
  {
    "symbol": "BTC",
    "price": 52000.5,
    "timestamp": 1707825600,
    "round_id": 12345,
    "created_at": 1707825601
  }
]
```

- `symbol`: Cryptocurrency symbol
- `price`: Price in USD
- `timestamp`: Chainlink oracle timestamp
- `round_id`: Chainlink round ID (unique identifier)
- `created_at`: When the price was stored locally

## Deployment on VPS

### 1. Install Python and pip
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# CentOS/RHEL
sudo yum install python3 python3-pip
```

### 2. Install the service
```bash
# Create project directory
mkdir price-collector
cd price-collector

# Copy project files
# (upload config.json, chainlink_price_service.py, requirements.txt, etc.)

# Install dependencies
pip3 install -r requirements.txt
```

### 3. Run as a service

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/price-collector.service
```

Add the following content:

```ini
[Unit]
Description=Chainlink Price Collector
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/price-collector
ExecStart=/usr/bin/python3 /path/to/price-collector/chainlink_price_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable price-collector
sudo systemctl start price-collector
sudo systemctl status price-collector
```

### 4. Check logs
```bash
sudo journalctl -u price-collector -f
```

## Troubleshooting

### Common Issues

1. **RPC Connection Failed**
   - Check your internet connection
   - Try a different RPC URL in config.json
   - Verify the RPC endpoint is accessible

2. **Permission Errors**
   - Ensure the user running the service has write permissions to the data/ and logs/ directories
   - Check file ownership and permissions

3. **API Not Responding**
   - Check if the service is running: `ps aux | grep python`
   - Check logs for errors: `tail -f logs/price_collector.log`
   - Verify the port is not in use: `netstat -tlnp | grep 5000`

### Monitoring

- **Service Status**: `systemctl status price-collector`
- **Logs**: `tail -f logs/price_collector.log`
- **API Health**: `curl http://localhost:5000/health`
- **Latest Prices**: `curl http://localhost:5000/latest`

## Security Notes

- The API runs on all interfaces (0.0.0.0) by default
- Consider using a firewall to restrict access to the API port
- Monitor logs for any unusual activity
- Keep your system and Python packages updated

## License

This project is open source and available under the MIT License.