#!/usr/bin/env python3
"""
Enhanced Price Collector Service for VPS deployment
- Port: 3000
- Path: /collector
- ET Time Support
- In-Memory Buffer
- Enhanced Cleanup
"""

import asyncio
import time
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Deque
from collections import deque
from aiohttp import web
import aiofiles
import random
import pytz

# Configure logging
# Create logs directory first
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/price_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TimeHelper:
    """Helper class for time zone conversions"""
    
    @staticmethod
    def utc_to_et(timestamp: int) -> datetime:
        """Convert UTC timestamp to ET datetime"""
        utc_dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        et_tz = pytz.timezone('America/New_York')
        return utc_dt.astimezone(et_tz)
    
    @staticmethod
    def et_to_utc(et_datetime: datetime) -> int:
        """Convert ET datetime to UTC timestamp"""
        et_tz = pytz.timezone('America/New_York')
        if et_datetime.tzinfo is None:
            et_datetime = et_tz.localize(et_datetime)
        utc_dt = et_datetime.astimezone(pytz.UTC)
        return int(utc_dt.timestamp())
    
    @staticmethod
    def format_time(timestamp: int, timezone: str = 'UTC') -> str:
        """Format timestamp to readable string"""
        if timezone == 'ET':
            dt = TimeHelper.utc_to_et(timestamp)
        else:
            dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        return dt.strftime('%Y-%m-%d %H:%M:%S %Z')


class InMemoryBuffer:
    """In-memory buffer for recent prices"""
    
    def __init__(self, max_age_seconds: int = 60):
        self.max_age_seconds = max_age_seconds
        self.buffer: Deque[Dict] = deque()
    
    def add_price(self, symbol: str, price: float, timestamp: int, round_id: int):
        """Add price to buffer"""
        record = {
            'symbol': symbol,
            'price': price,
            'timestamp': timestamp,
            'round_id': round_id,
            'created_at': int(time.time())
        }
        self.buffer.append(record)
        self._cleanup_old_records()
    
    def get_price_at_timestamp(self, symbol: str, target_timestamp: int, tolerance: int = 60) -> Optional[Dict]:
        """Get price from buffer closest to target_timestamp"""
        current_time = int(time.time())
        
        # Filter by symbol, age, and tolerance
        matching_records = []
        for record in self.buffer:
            # Check if record is not too old
            if current_time - record['created_at'] > self.max_age_seconds:
                continue
            
            # Check symbol and tolerance
            if record['symbol'] == symbol and abs(record['timestamp'] - target_timestamp) <= tolerance:
                matching_records.append(record)
        
        if not matching_records:
            return None
        
        # Find the closest record
        closest_record = min(matching_records, key=lambda x: abs(x['timestamp'] - target_timestamp))
        return {
            'price': closest_record['price'],
            'timestamp': closest_record['timestamp'],
            'round_id': closest_record['round_id'],
            'source': 'buffer'
        }
    
    def _cleanup_old_records(self):
        """Remove old records from buffer"""
        current_time = int(time.time())
        # Remove from the left (oldest first) for efficiency
        while self.buffer and current_time - self.buffer[0]['created_at'] > self.max_age_seconds:
            self.buffer.popleft()


class EnhancedFilePriceStorage:
    """Enhanced file-based storage with ET time support"""
    
    def __init__(self, data_dir: str = 'data', log_dir: str = 'logs', retention_hours: int = 12):
        self.data_dir = data_dir
        self.log_dir = log_dir
        self.retention_hours = retention_hours
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
            
            # Add new record with ET time info
            et_time = TimeHelper.utc_to_et(timestamp)
            new_record = {
                'symbol': symbol,
                'price': price,
                'timestamp': timestamp,
                'round_id': round_id,
                'created_at': int(time.time()),
                'et_time': {
                    'year': et_time.year,
                    'month': et_time.month,
                    'day': et_time.day,
                    'hour': et_time.hour,
                    'minute': et_time.minute,
                    'second': et_time.second,
                    'formatted': TimeHelper.format_time(timestamp, 'ET')
                }
            }
            data.append(new_record)
            
            # Write back to file
            async with aiofiles.open(self.prices_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
                
            logger.info(f"Saved {symbol}: ${price:.2f} @ {timestamp} (ET: {TimeHelper.format_time(timestamp, 'ET')}) (round: {round_id})")
            
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
                'round_id': closest_record['round_id'],
                'et_time': closest_record.get('et_time'),
                'source': 'file'
            }
            
        except Exception as e:
            logger.error(f"Error retrieving price data: {e}")
            return None
    
    async def cleanup_old_records(self, hours: Optional[int] = None):
        """Remove records older than N hours (with ET time support)"""
        if hours is None:
            hours = self.retention_hours
            
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
                logger.info(f"Cleaned up {deleted_count} old records (retention: {hours} hours)")
            
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


class MockPriceFetcher:
    """Mock price fetcher that simulates Chainlink oracle data"""
    
    def __init__(self, symbols: Dict[str, str]):
        self.symbols = symbols
        self.base_prices = {
            'BTC': 50000.0,
            'ETH': 3000.0,
            'SOL': 100.0
        }
        self.round_counters = {symbol: 1000 for symbol in symbols.keys()}
        logger.info("Initialized mock price fetcher")
    
    def get_latest_price(self, symbol: str) -> Optional[Dict]:
        """Get simulated price data"""
        try:
            # Simulate price movement (random walk)
            base_price = self.base_prices[symbol]
            # Random movement between -500 and +500 for BTC, -50 and +50 for ETH, -5 and +5 for SOL
            if symbol == 'BTC':
                movement = random.uniform(-500, 500)
            elif symbol == 'ETH':
                movement = random.uniform(-50, 50)
            else:
                movement = random.uniform(-5, 5)
            
            new_price = base_price + movement
            self.base_prices[symbol] = new_price
            
            # Increment round counter
            self.round_counters[symbol] += 1
            round_id = self.round_counters[symbol]
            timestamp = int(time.time())
            
            return {
                'symbol': symbol,
                'price': new_price,
                'timestamp': timestamp,
                'round_id': round_id
            }
        except Exception as e:
            logger.error(f"Error generating mock price for {symbol}: {e}")
            return None


class EnhancedPriceCollectorService:
    """Enhanced service with buffer support"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.storage = EnhancedFilePriceStorage(
            data_dir=config['storage']['data_directory'],
            log_dir=config['storage']['log_directory'],
            retention_hours=config.get('data_retention_hours', 12)
        )
        self.buffer = InMemoryBuffer(max_age_seconds=config.get('buffer_max_age_seconds', 60))
        self.fetcher = MockPriceFetcher(config['symbols'])
        self.running = False
    
    async def collect_prices(self):
        """Collect prices every second"""
        while self.running:
            try:
                for symbol in self.config['symbols'].keys():
                    data = self.fetcher.get_latest_price(symbol)
                    if data:
                        # Add to buffer first
                        self.buffer.add_price(
                            symbol=data['symbol'],
                            price=data['price'],
                            timestamp=data['timestamp'],
                            round_id=data['round_id']
                        )
                        
                        # Then save to file
                        await self.storage.insert_price(
                            symbol=data['symbol'],
                            price=data['price'],
                            timestamp=data['timestamp'],
                            round_id=data['round_id']
                        )
                
                await asyncio.sleep(self.config['collection_interval'])
            except Exception as e:
                logger.error(f"Error in collect_prices: {e}")
                await asyncio.sleep(5)
    
    async def cleanup_task(self):
        """Clean up old records every 10 minutes"""
        while self.running:
            try:
                await asyncio.sleep(self.config['cleanup_interval'])  # 10 minutes
                await self.storage.cleanup_old_records(hours=self.config.get('data_retention_hours', 12))
            except Exception as e:
                logger.error(f"Error in cleanup_task: {e}")
    
    async def start(self):
        """Start the enhanced price collection service"""
        self.running = True
        logger.info("Starting Enhanced Price Collector Service...")
        logger.info(f"Buffer max age: {self.buffer.max_age_seconds} seconds")
        logger.info(f"Data retention: {self.storage.retention_hours} hours")
        
        await asyncio.gather(
            self.collect_prices(),
            self.cleanup_task()
        )
    
    def stop(self):
        """Stop the service"""
        self.running = False
        logger.info("Stopping Enhanced Price Collector Service...")


class CollectorAPIServer:
    """REST API server for querying prices with /collector path"""
    
    def __init__(self, storage: EnhancedFilePriceStorage, buffer: InMemoryBuffer, config: Dict):
        self.storage = storage
        self.buffer = buffer
        self.config = config
        self.app = web.Application()
        self._setup_routes()
    
    def _setup_routes(self):
        # API endpoints with /collector prefix
        self.app.router.add_get('/collector/health', self.health_check)
        self.app.router.add_get('/collector/latest', self.get_latest_prices)
        self.app.router.add_get('/collector/price/{symbol}', self.get_price)
        self.app.router.add_get('/collector/timezones', self.get_time_info)
    
    async def get_price(self, request):
        """
        GET /collector/price/BTC?timestamp=1234567890&tolerance=60
        Returns price closest to the specified timestamp
        Priority: Buffer -> File
        """
        symbol = request.match_info['symbol'].upper()
        timestamp = request.query.get('timestamp')
        tolerance = int(request.query.get('tolerance', 60))
        
        if not timestamp:
            return web.json_response({'error': 'timestamp parameter required'}, status=400)
        
        try:
            timestamp = int(timestamp)
        except ValueError:
            return web.json_response({'error': 'Invalid timestamp'}, status=400)
        
        # First check buffer (for recent prices)
        buffer_result = self.buffer.get_price_at_timestamp(symbol, timestamp, tolerance)
        if buffer_result:
            return web.json_response({
                'symbol': symbol,
                'price': buffer_result['price'],
                'timestamp': buffer_result['timestamp'],
                'requested_timestamp': timestamp,
                'round_id': buffer_result['round_id'],
                'source': buffer_result['source'],
                'time_info': {
                    'utc': TimeHelper.format_time(buffer_result['timestamp'], 'UTC'),
                    'et': TimeHelper.format_time(buffer_result['timestamp'], 'ET')
                }
            })
        
        # Then check file
        file_result = await self.storage.get_price_at_timestamp(symbol, timestamp, tolerance)
        if file_result:
            return web.json_response({
                'symbol': symbol,
                'price': file_result['price'],
                'timestamp': file_result['timestamp'],
                'requested_timestamp': timestamp,
                'round_id': file_result['round_id'],
                'source': file_result['source'],
                'time_info': {
                    'utc': TimeHelper.format_time(file_result['timestamp'], 'UTC'),
                    'et': file_result['et_time']['formatted'] if file_result.get('et_time') else TimeHelper.format_time(file_result['timestamp'], 'ET')
                }
            })
        
        return web.json_response({
            'error': f'No price found for {symbol} at timestamp {timestamp} (±{tolerance}s)'
        }, status=404)
    
    async def get_latest_prices(self, request):
        """GET /collector/latest - Get the latest prices for all symbols"""
        try:
            latest_prices = await self.storage.get_latest_prices()
            enhanced_prices = []
            
            for price in latest_prices:
                enhanced_price = {
                    'symbol': price['symbol'],
                    'price': price['price'],
                    'timestamp': price['timestamp'],
                    'round_id': price['round_id'],
                    'time_info': {
                        'utc': TimeHelper.format_time(price['timestamp'], 'UTC'),
                        'et': price.get('et_time', {}).get('formatted', TimeHelper.format_time(price['timestamp'], 'ET'))
                    }
                }
                enhanced_prices.append(enhanced_price)
            
            return web.json_response({
                'prices': enhanced_prices,
                'source': 'enhanced'
            })
        except Exception as e:
            logger.error(f"Error getting latest prices: {e}")
            return web.json_response({'error': 'Failed to get latest prices'}, status=500)
    
    async def get_time_info(self, request):
        """GET /collector/timezones - Get current time in different timezones"""
        current_timestamp = int(time.time())
        return web.json_response({
            'current_timestamp': current_timestamp,
            'time_info': {
                'utc': TimeHelper.format_time(current_timestamp, 'UTC'),
                'et': TimeHelper.format_time(current_timestamp, 'ET'),
                'buffer_max_age_seconds': self.buffer.max_age_seconds,
                'data_retention_hours': self.storage.retention_hours
            }
        })
    
    async def health_check(self, request):
        return web.json_response({
            'status': 'ok', 
            'timestamp': int(time.time()), 
            'source': 'enhanced',
            'symbols': list(self.config['symbols'].keys()),
            'features': ['et_time_support', 'buffering', 'enhanced_cleanup'],
            'time_info': {
                'utc': TimeHelper.format_time(int(time.time()), 'UTC'),
                'et': TimeHelper.format_time(int(time.time()), 'ET')
            }
        })
    
    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.config['api_port'])
        await site.start()
        logger.info(f"Enhanced API server running on http://0.0.0.0:{self.config['api_port']}")
        logger.info("Features: ET time support, buffering, enhanced cleanup")
        logger.info("API endpoints:")
        logger.info("  - /collector/health")
        logger.info("  - /collector/latest")
        logger.info("  - /collector/price/{symbol}")
        logger.info("  - /collector/timezones")


async def main():
    """Main entry point"""
    # Load configuration
    try:
        with open('collector_config.json', 'r') as f:
            config = json.load(f)
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return
    
    # Initialize services
    storage = EnhancedFilePriceStorage(
        data_dir=config['storage']['data_directory'],
        log_dir=config['storage']['log_directory'],
        retention_hours=config.get('data_retention_hours', 12)
    )
    buffer = InMemoryBuffer(max_age_seconds=config.get('buffer_max_age_seconds', 60))
    
    collector = EnhancedPriceCollectorService(config)
    api_server = CollectorAPIServer(storage, buffer, config)
    
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