import asyncio
import time
import json
import os
import logging
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
import tempfile

import websockets
from aiohttp import web
import aiofiles

# Ensure logs directory exists before configuring logging
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/price_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FilePriceStorage:
    """File-based storage for price data instead of SQLite database"""
    
    def __init__(self, data_dir: str = 'data', log_dir: str = 'logs'):
        self.data_dir = data_dir
        self.log_dir = log_dir
        self._ensure_directories()
        self.prices_file = os.path.join(data_dir, 'prices.json')
        self._init_storage()
    
    def _ensure_directories(self):
        """Create directories if they don't exist"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
    
    def _init_storage(self):
        """Initialize the prices file if it doesn't exist"""
        if not os.path.exists(self.prices_file):
            with open(self.prices_file, 'w') as f:
                json.dump([], f)
            logger.info(f"Initialized prices file: {self.prices_file}")
    
    async def insert_price(self, symbol: str, price: float, timestamp: int, round_id: int):
        """Insert price data into the JSON file"""
        try:
            # Read existing data
            async with aiofiles.open(self.prices_file, 'r') as f:
                content = await f.read()
                data = json.loads(content) if content else []
            
            # Check if this round already exists for this symbol
            for record in data:
                if record['symbol'] == symbol and record['round_id'] == round_id:
                    return  # Round already exists, skip
            
            # Add new record
            new_record = {
                'symbol': symbol,
                'price': price,
                'timestamp': timestamp,
                'round_id': round_id,
                'created_at': int(time.time())
            }
            data.append(new_record)
            
            # Write back to file
            async with aiofiles.open(self.prices_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
                
            logger.info(f"Saved {symbol}: ${price:.2f} @ {timestamp} (round: {round_id})")
            
        except Exception as e:
            logger.error(f"Error saving price data: {e}")
    
    async def get_price_at_timestamp(self, symbol: str, target_timestamp: int, tolerance: int = 60) -> Optional[Dict]:
        """Get price closest to target_timestamp"""
        try:
            async with aiofiles.open(self.prices_file, 'r') as f:
                content = await f.read()
                data = json.loads(content) if content else []
            
            # Filter by symbol and tolerance
            matching_records = [
                record for record in data
                if record['symbol'] == symbol and abs(record['timestamp'] - target_timestamp) <= tolerance
            ]
            
            if not matching_records:
                return None
            
            # Find the closest record
            closest_record = min(matching_records, key=lambda x: abs(x['timestamp'] - target_timestamp))
            
            return {
                'price': closest_record['price'],
                'timestamp': closest_record['timestamp'],
                'round_id': closest_record['round_id']
            }
            
        except Exception as e:
            logger.error(f"Error retrieving price data: {e}")
            return None
    
    async def cleanup_old_records(self, hours: int = 6):
        """Remove records older than N hours"""
        try:
            cutoff = int(time.time()) - (hours * 3600)
            
            async with aiofiles.open(self.prices_file, 'r') as f:
                content = await f.read()
                data = json.loads(content) if content else []
            
            # Filter out old records
            original_count = len(data)
            data = [record for record in data if record['created_at'] >= cutoff]
            deleted_count = original_count - len(data)
            
            # Write back filtered data
            async with aiofiles.open(self.prices_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old records")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
            return 0
    
    async def get_latest_prices(self) -> List[Dict]:
        """Get the latest price for each symbol"""
        try:
            async with aiofiles.open(self.prices_file, 'r') as f:
                content = await f.read()
                data = json.loads(content) if content else []
            
            # Group by symbol and get the latest record for each
            latest_prices = {}
            for record in data:
                symbol = record['symbol']
                if symbol not in latest_prices or record['created_at'] > latest_prices[symbol]['created_at']:
                    latest_prices[symbol] = record
            
            return list(latest_prices.values())
            
        except Exception as e:
            logger.error(f"Error getting latest prices: {e}")
            return []


class PolymarketPriceCollector:
    """Collect prices from Polymarket RTDS WebSocket - no rate limits!"""

    SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    RTDS_ENDPOINT = "wss://ws-live-data.polymarket.com"
    RTDS_TOPIC = "crypto_prices_chainlink"

    def __init__(self):
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.price_buffers: Dict[str, List[Dict]] = {}
        self.last_prices: Dict[str, float] = {}
        self.last_save_time = time.time()

        # Create data directory
        Path("data").mkdir(exist_ok=True)

        # Initialize buffers for each symbol
        for symbol in self.SYMBOLS:
            self.price_buffers[symbol] = []

        # Load existing data
        self._load_existing_data()
        logger.info("PolymarketPriceCollector initialized")

    def _load_existing_data(self) -> None:
        """Load existing data from file."""
        prices_file = Path("data/prices.json")
        try:
            if prices_file.exists():
                with open(prices_file, 'r') as f:
                    data = json.load(f)
                    prices_data = data.get('prices', {})

                    for symbol in self.SYMBOLS:
                        self.price_buffers[symbol] = prices_data.get(symbol, [])

                    total_entries = sum(len(buffer) for buffer in self.price_buffers.values())
                    logger.info(f"Loaded {total_entries} price entries")
        except Exception as e:
            logger.warning(f"Error loading existing data: {e}")

    def _save_data(self) -> None:
        """Save data to file atomically."""
        try:
            # Remove old entries (older than 6 hours)
            cutoff = time.time() - (6 * 3600)
            for symbol in self.price_buffers:
                self.price_buffers[symbol] = [
                    e for e in self.price_buffers[symbol]
                    if e.get('timestamp', 0) > cutoff
                ]

            data = {
                'last_updated': datetime.now().isoformat(),
                'prices': self.price_buffers
            }

            # Atomic write
            prices_file = Path("data/prices.json")
            fd, tmp_path = tempfile.mkstemp(dir=prices_file.parent, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp_path, str(prices_file))
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

            total_entries = sum(len(buffer) for buffer in self.price_buffers.values())
            logger.info(f"Saved {total_entries} price entries to {prices_file}")
            self.last_save_time = time.time()

        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def _normalize_symbol(self, raw_symbol: str) -> str:
        """Normalize symbol from RTDS."""
        sym = raw_symbol.strip().upper()
        if "/" in sym:
            base = sym.split("/", 1)[0]
            return f"{base}USDT"
        return sym

    async def _handle_price_update(self, msg: dict) -> None:
        """Handle price update from RTDS."""
        payload = msg.get("payload", {})
        symbol_raw = payload.get("symbol", "")
        symbol = self._normalize_symbol(symbol_raw)
        price = payload.get("value")
        ts_ms = payload.get("timestamp", 0)

        if not symbol or price is None or symbol not in self.SYMBOLS:
            return

        timestamp = int(ts_ms / 1000)
        price_float = float(price)

        # Update last price
        self.last_prices[symbol] = price_float

        # Add to buffer
        entry = {
            'timestamp': timestamp,
            'price': price_float,
            'datetime': datetime.fromtimestamp(timestamp).isoformat(),
            'source': 'polymarket_rtds'
        }

        self.price_buffers[symbol].append(entry)
        logger.info(f"💰 Price update: {symbol} = ${price_float:.2f} @ {timestamp}")

        # Save periodically
        if time.time() - self.last_save_time >= 60:  # Every minute
            self._save_data()

    async def _receive_messages(self) -> None:
        """Receive messages from WebSocket."""
        while self.running and self.websocket:
            try:
                raw = await self.websocket.recv()
                if not raw:
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type", "")
                if msg_type == "update":
                    await self._handle_price_update(msg)

            except Exception as exc:
                logger.error(f"Error in receive_messages: {exc}")
                self.running = False
                break

    async def _ping_loop(self) -> None:
        """Send ping every 30 seconds."""
        while self.running and self.websocket:
            try:
                await asyncio.sleep(30)
                if self.websocket and self.running:
                    await self.websocket.send(json.dumps({"type": "ping"}))
            except Exception as exc:
                logger.error(f"Error in ping loop: {exc}")
                self.running = False
                break

    def get_latest_price(self, symbol: str) -> Optional[Dict]:
        """Get latest price for symbol."""
        if symbol not in self.last_prices:
            return None

        # Find the most recent entry in buffer
        buffer = self.price_buffers.get(symbol, [])
        if not buffer:
            return None

        latest_entry = max(buffer, key=lambda x: x['timestamp'])

        return {
            'symbol': symbol,
            'price': latest_entry['price'],
            'timestamp': latest_entry['timestamp'],
            'round_id': 0,  # Not applicable for RTDS
            'source': 'polymarket_rtds'
        }

    async def start_collection(self) -> None:
        """Start WebSocket collection."""
        self.running = True
        logger.info(f"Starting Polymarket RTDS collection for {', '.join(self.SYMBOLS)}")

        while self.running:
            try:
                # Connect to WebSocket
                self.websocket = await websockets.connect(
                    self.RTDS_ENDPOINT,
                    ping_interval=None,
                    close_timeout=5,
                )

                # Subscribe to price updates
                msg = {
                    "action": "subscribe",
                    "subscriptions": [{
                        "topic": self.RTDS_TOPIC,
                        "type": "update",
                    }],
                }
                await self.websocket.send(json.dumps(msg))
                logger.info("Subscribed to Polymarket RTDS")

                # Start ping loop
                ping_task = asyncio.create_task(self._ping_loop())

                # Receive messages
                await self._receive_messages()

                # Clean up
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass

            except Exception as conn_exc:
                logger.error(f"WebSocket connection error: {conn_exc}")
                if self.running:
                    logger.info("Retrying connection in 5 seconds...")
                    await asyncio.sleep(5)

            finally:
                if self.websocket:
                    try:
                        await self.websocket.close()
                    except:
                        pass
                    self.websocket = None

        logger.info("Polymarket RTDS collection stopped")

    def stop_collection(self) -> None:
        """Stop collection."""
        self.running = False
        logger.info("Stopping Polymarket RTDS collection")


class PriceCollectorService:
    """Main service for collecting prices from Polymarket RTDS"""

    def __init__(self, config: Dict):
        self.config = config
        self.storage = FilePriceStorage(
            data_dir=config['storage']['data_directory'],
            log_dir=config['storage']['log_directory']
        )
        self.collector = PolymarketPriceCollector()
        self.running = False

    async def collect_prices(self):
        """Start WebSocket collection from Polymarket RTDS"""
        await self.collector.start_collection()

    async def cleanup_task(self):
        """Clean up old records every 10 minutes"""
        while self.running:
            try:
                await asyncio.sleep(self.config['cleanup_interval'])  # 10 minutes
                await self.storage.cleanup_old_records(hours=self.config['data_retention_hours'])
            except Exception as e:
                logger.error(f"Error in cleanup_task: {e}")

    async def start(self):
        """Start the price collection service"""
        self.running = True
        logger.info("Starting Polymarket RTDS Price Collector Service...")

        await asyncio.gather(
            self.collect_prices(),
            self.cleanup_task()
        )

    def stop(self):
        """Stop the service"""
        self.running = False
        self.collector.stop_collection()
        logger.info("Stopping Polymarket RTDS Price Collector Service...")


class PriceAPIServer:
    """REST API server for querying prices"""

    def __init__(self, collector: PolymarketPriceCollector, config: Dict):
        self.collector = collector
        self.config = config
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get('/price/{symbol}', self.get_price)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/latest', self.get_latest_prices)

    async def get_price(self, request):
        """
        GET /price/BTC - Returns latest price for symbol
        """
        symbol = request.match_info['symbol'].upper()

        if symbol not in PolymarketPriceCollector.SYMBOLS:
            return web.json_response({'error': f'Unsupported symbol: {symbol}'}, status=400)

        result = self.collector.get_latest_price(symbol)

        if result:
            return web.json_response({
                'symbol': symbol,
                'price': result['price'],
                'timestamp': result['timestamp'],
                'source': 'polymarket_rtds'
            })
        else:
            return web.json_response({
                'error': f'No price data available for {symbol}'
            }, status=404)

    async def get_latest_prices(self, request):
        """GET /latest - Get the latest prices for all symbols"""
        try:
            latest_prices = []
            for symbol in PolymarketPriceCollector.SYMBOLS:
                price_data = self.collector.get_latest_price(symbol)
                if price_data:
                    latest_prices.append({
                        'symbol': symbol,
                        'price': price_data['price'],
                        'timestamp': price_data['timestamp'],
                        'source': 'polymarket_rtds'
                    })

            return web.json_response({
                'prices': latest_prices,
                'source': 'polymarket_rtds'
            })
        except Exception as e:
            logger.error(f"Error getting latest prices: {e}")
            return web.json_response({'error': 'Failed to get latest prices'}, status=500)

    async def health_check(self, request):
        return web.json_response({
            'status': 'ok',
            'timestamp': int(time.time()),
            'source': 'polymarket_rtds',
            'symbols': PolymarketPriceCollector.SYMBOLS,
            'websocket_connected': self.collector.websocket is not None
        })

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.config['api_port'])
        await site.start()
        logger.info(f"API server running on http://0.0.0.0:{self.config['api_port']}")
        logger.info("Data source: Polymarket RTDS WebSocket (Chainlink prices)")


async def main():
    """Main entry point"""
    # Load configuration
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return
    
    # Initialize services
    storage = FilePriceStorage(
        data_dir=config['storage']['data_directory'],
        log_dir=config['storage']['log_directory']
    )
    
    collector = PriceCollectorService(config)
    api_server = PriceAPIServer(collector.collector, config)
    
    try:
        await asyncio.gather(
            collector.start(),
            api_server.start()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        collector.stop()


if __name__ == '__main__':
    asyncio.run(main())