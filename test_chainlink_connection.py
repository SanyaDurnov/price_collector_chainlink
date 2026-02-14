#!/usr/bin/env python3
"""
Test script to verify Chainlink connection and data
"""

import asyncio
import json
import logging
from chainlink_price_service import ChainlinkPriceFetcher, FilePriceStorage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_chainlink_connection():
    """Test Chainlink connection and fetch real prices"""
    
    # Load configuration
    try:
        with open('collector_config.json', 'r') as f:
            config = json.load(f)
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return
    
    try:
        # Initialize Chainlink fetcher
        fetcher = ChainlinkPriceFetcher(
            rpc_url=config['rpc_url'],
            symbols=config['symbols']
        )
        logger.info("Chainlink fetcher initialized successfully")
        
        # Test fetching prices
        for symbol in config['symbols'].keys():
            logger.info(f"Fetching price for {symbol}...")
            data = fetcher.get_latest_price(symbol)
            
            if data:
                logger.info(f"✅ {symbol}: ${data['price']:.2f} @ {data['timestamp']} (round: {data['round_id']})")
            else:
                logger.error(f"❌ Failed to fetch price for {symbol}")
        
        # Test storage
        storage = FilePriceStorage(
            data_dir=config['storage']['data_directory'],
            log_dir=config['storage']['log_directory']
        )
        
        # Insert test data
        await storage.insert_price("BTC", 50000.0, 1234567890, 1000)
        await storage.insert_price("ETH", 3000.0, 1234567890, 1000)
        
        # Get latest prices
        latest = await storage.get_latest_prices()
        logger.info(f"Latest prices in storage: {latest}")
        
    except Exception as e:
        logger.error(f"Error testing Chainlink connection: {e}")


if __name__ == '__main__':
    asyncio.run(test_chainlink_connection())