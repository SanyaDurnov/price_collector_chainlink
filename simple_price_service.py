#!/usr/bin/env python3
"""
Simple Price Collector Service (without web3 dependency)
For testing and basic functionality without blockchain dependencies
"""

import asyncio
import time
import json
import os
import logging
from datetime import datetime
from typing import Dict, Optional, List
from aiohttp import web
import aiofiles
import random

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


class FilePriceStorage:
    """File-based storage for price data"""
    
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


class PriceCollectorService:
    """Main service for collecting prices"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.storage = FilePriceStorage(
            data_dir=config['storage']['data_directory'],
            log_dir=config['storage']['log_directory']
        )
        self.fetcher = MockPriceFetcher(config['symbols'])
        self.running = False
    
    async def collect_prices(self):
        """Collect prices every second"""
        while self.running:
            try:
                for symbol in self.config['symbols'].keys():
                    data = self.fetcher.get_latest_price(symbol)
                    if data:
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
                await self.storage.cleanup_old_records(hours=self.config['data_retention_hours'])
            except Exception as e:
                logger.error(f"Error in cleanup_task: {e}")
    
    async def start(self):
        """Start the price collection service"""
        self.running = True
        logger.info("Starting Mock Price Collector Service...")
        
        await asyncio.gather(
            self.collect_prices(),
            self.cleanup_task()
        )
    
    def stop(self):
        """Stop the service"""
        self.running = False
        logger.info("Stopping Mock Price Collector Service...")


class PriceAPIServer:
    """REST API server for querying prices"""
    
    def __init__(self, storage: FilePriceStorage, config: Dict):
        self.storage = storage
        self.config = config
        self.app = web.Application()
        self._setup_routes()
    
    def _setup_routes(self):
        self.app.router.add_get('/price/{symbol}', self.get_price)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/latest', self.get_latest_prices)
    
    async def get_price(self, request):
        """
        GET /price/BTC?timestamp=1234567890&tolerance=60
        Returns price closest to the specified timestamp
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
        
        result = await self.storage.get_price_at_timestamp(symbol, timestamp, tolerance)
        
        if result:
            return web.json_response({
                'symbol': symbol,
                'price': result['price'],
                'timestamp': result['timestamp'],
                'requested_timestamp': timestamp,
                'round_id': result['round_id'],
                'source': 'mock'
            })
        else:
            return web.json_response({
                'error': f'No price found for {symbol} at timestamp {timestamp} (±{tolerance}s)'
            }, status=404)
    
    async def get_latest_prices(self, request):
        """GET /latest - Get the latest prices for all symbols"""
        try:
            latest_prices = await self.storage.get_latest_prices()
            return web.json_response({
                'prices': latest_prices,
                'source': 'mock'
            })
        except Exception as e:
            logger.error(f"Error getting latest prices: {e}")
            return web.json_response({'error': 'Failed to get latest prices'}, status=500)
    
    async def health_check(self, request):
        return web.json_response({
            'status': 'ok', 
            'timestamp': int(time.time()), 
            'source': 'mock',
            'symbols': list(self.config['symbols'].keys())
        })
    
    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.config['api_port'])
        await site.start()
        logger.info(f"API server running on http://0.0.0.0:{self.config['api_port']}")
        logger.info("Data source: Mock prices (simulating Chainlink Oracle)")


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
    api_server = PriceAPIServer(storage, config)
    
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