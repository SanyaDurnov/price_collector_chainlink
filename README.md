# Polymarket RTDS Price Collector

A Python service that collects real-time cryptocurrency prices from Polymarket RTDS (Real-Time Data Service) using WebSocket connection and provides a REST API for querying prices.

## Features

- **Real-time WebSocket Collection**: Uses Polymarket RTDS WebSocket for instant price updates (no rate limits!)
- **Chainlink Oracle Data**: Prices sourced from Chainlink oracles on Polygon (same as Polymarket)
- **File-based Storage**: Simple JSON file storage (no database required)
- **REST API**: Query latest prices by symbol
- **Configurable**: Easy to customize via JSON configuration
- **Docker Ready**: Designed for easy deployment with Dokploy

## Supported Symbols

- **BTCUSDT**: Bitcoin price
- **ETHUSDT**: Ethereum price
- **SOLUSDT**: Solana price

All prices are sourced from Chainlink oracles via Polymarket RTDS WebSocket.

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
  "rpc_urls": [
    "https://polygon-rpc.com",
    "https://polygon-mainnet.publicnode.com",
    "https://polygon-bor.publicnode.com",
    "https://polygon.drpc.org"
  ],
  "api_port": 3000,
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

- `rpc_urls`: Array of Polygon RPC endpoints for failover (WebSocket uses Polymarket RTDS)
- `api_port`: API server port (default: 3000)
- `collection_interval`: WebSocket reconnection interval in seconds (default: 1)
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
1. Connect to Polymarket RTDS WebSocket
2. Start collecting real-time prices (no rate limits!)
3. Store prices in `data/prices.json`
4. Start the API server on port 3000
5. Clean up old data every 10 minutes

### Test the Service

Test the WebSocket implementation:

```bash
# Test WebSocket price collection (runs for 60 seconds)
python test_websocket.py

# Test API endpoints
python test_api.py
```

### API Endpoints

#### Health Check
```
GET /health
```
Returns service status, WebSocket connection status, and available symbols.

**Response:**
```json
{
  "status": "ok",
  "timestamp": 1771089264,
  "source": "polymarket_rtds",
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "websocket_connected": true
}
```

#### Get Latest Prices
```
GET /latest
```
Returns the latest price for each symbol.

**Response:**
```json
{
  "prices": [
    {
      "symbol": "BTCUSDT",
      "price": 69724.98,
      "timestamp": 1771088436,
      "source": "polymarket_rtds"
    },
    {
      "symbol": "ETHUSDT",
      "price": 2080.43,
      "timestamp": 1771088436,
      "source": "polymarket_rtds"
    },
    {
      "symbol": "SOLUSDT",
      "price": 88.07,
      "timestamp": 1771088436,
      "source": "polymarket_rtds"
    }
  ],
  "source": "polymarket_rtds"
}
```

#### Get Individual Price
```
GET /price/{symbol}
```

**Parameters:**
- `symbol`: BTCUSDT, ETHUSDT, or SOLUSDT (case insensitive)

**Example:**
```
GET /price/BTCUSDT
```

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "price": 69724.98,
  "timestamp": 1771088436,
  "source": "polymarket_rtds"
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

## Deployment

### Dokploy (Recommended)

1. **Connect your GitHub repository** to Dokploy
2. **Create a new service** from the repository
3. **Configure port mapping**: Add `3000:3000` in the ports section
4. **Deploy** - Dokploy will automatically build and deploy the service

The service will be available at: `http://your-domain/collector/`

### Manual VPS Deployment

#### 1. Install Python and pip
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# CentOS/RHEL
sudo yum install python3 python3-pip
```

#### 2. Install the service
```bash
# Create project directory
mkdir price-collector
cd price-collector

# Copy project files
# (upload config.json, chainlink_price_service.py, requirements.txt, etc.)

# Install dependencies
pip3 install -r requirements.txt
```

#### 3. Run as a service

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/price-collector.service
```

Add the following content:

```ini
[Unit]
Description=Polymarket RTDS Price Collector
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

#### 4. Check logs
```bash
sudo journalctl -u price-collector -f
```

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check your internet connection
   - Service will automatically reconnect - check logs for reconnection messages
   - Verify Polymarket RTDS is accessible

2. **No Price Updates**
   - Check WebSocket connection status in `/health` endpoint
   - Look for "💰 Price update" messages in logs
   - Service may be reconnecting - wait a few seconds

3. **Permission Errors**
   - Ensure the user running the service has write permissions to the data/ and logs/ directories
   - Check file ownership and permissions

4. **API Not Responding**
   - Check if the service is running: `ps aux | grep python`
   - Check logs for errors: `tail -f logs/price_collector.log`
   - Verify the port is not in use: `netstat -tlnp | grep 3000`
   - For Dokploy: ensure port mapping `3000:3000` is configured

5. **Dokploy Port Issues**
   - In Dokploy dashboard, go to service settings
   - Add port mapping: `3000:3000` (external:internal)
   - Redeploy the service

### Monitoring

- **Service Status**: `systemctl status price-collector` (manual) or Dokploy dashboard
- **Logs**: `tail -f logs/price_collector.log` or `docker service logs pricecollector-service`
- **API Health**: `curl http://localhost:3000/health` or `curl http://your-domain/collector/health`
- **Latest Prices**: `curl http://localhost:3000/latest` or `curl http://your-domain/collector/latest`
- **WebSocket Status**: Check `websocket_connected: true` in health response

## Security Notes

- The API runs on all interfaces (0.0.0.0) by default
- Consider using a firewall to restrict access to the API port
- Monitor logs for any unusual activity
- Keep your system and Python packages updated

## License

This project is open source and available under the MIT License.