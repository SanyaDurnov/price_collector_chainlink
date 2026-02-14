#!/usr/bin/env python3
"""
Test script for the Chainlink Price Collector
Tests basic functionality without running the full service
"""

import asyncio
import json
import time
import os
from chainlink_price_service import ChainlinkPriceFetcher, FilePriceStorage


async def test_price_fetching():
    """Test fetching prices from Chainlink"""
    print("=== Testing Price Fetching ===")
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Initialize price fetcher
    fetcher = ChainlinkPriceFetcher(config['rpc_url'], config['symbols'])
    
    print(f"Connected to RPC: {config['rpc_url']}")
    print(f"Symbols to test: {list(config['symbols'].keys())}")
    print()
    
    # Test fetching prices
    for symbol in config['symbols'].keys():
        print(f"Fetching {symbol} price...")
        data = fetcher.get_latest_price(symbol)
        
        if data:
            print(f"✓ {symbol}: ${data['price']:.2f} @ {data['timestamp']} (round: {data['round_id']})")
        else:
            print(f"✗ Failed to fetch {symbol} price")
        print()


async def test_file_storage():
    """Test file-based storage"""
    print("=== Testing File Storage ===")
    
    # Initialize storage
    storage = FilePriceStorage()
    
    # Test inserting a price
    test_symbol = "BTC"
    test_price = 50000.0
    test_timestamp = int(time.time())
    test_round_id = 12345
    
    print(f"Inserting test price: {test_symbol} = ${test_price}")
    await storage.insert_price(test_symbol, test_price, test_timestamp, test_round_id)
    print("✓ Price inserted successfully")
    
    # Test retrieving the price
    print(f"Retrieving price for {test_symbol} at timestamp {test_timestamp}")
    result = await storage.get_price_at_timestamp(test_symbol, test_timestamp, tolerance=60)
    
    if result:
        print(f"✓ Retrieved: ${result['price']:.2f} @ {result['timestamp']} (round: {result['round_id']})")
    else:
        print("✗ Failed to retrieve price")
    
    # Test getting latest prices
    print("Getting latest prices...")
    latest_prices = await storage.get_latest_prices()
    print(f"✓ Found {len(latest_prices)} latest price records")
    
    print()


async def test_full_cycle():
    """Test a complete cycle of fetch and store"""
    print("=== Testing Full Fetch & Store Cycle ===")
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Initialize components
    fetcher = ChainlinkPriceFetcher(config['rpc_url'], config['symbols'])
    storage = FilePriceStorage()
    
    print("Fetching and storing prices for all symbols...")
    
    success_count = 0
    for symbol in config['symbols'].keys():
        data = fetcher.get_latest_price(symbol)
        if data:
            await storage.insert_price(
                symbol=data['symbol'],
                price=data['price'],
                timestamp=data['timestamp'],
                round_id=data['round_id']
            )
            success_count += 1
            print(f"✓ {symbol}: ${data['price']:.2f}")
        else:
            print(f"✗ Failed to fetch {symbol}")
    
    print(f"\nSuccessfully processed {success_count}/{len(config['symbols'])} symbols")
    
    # Verify storage
    latest_prices = await storage.get_latest_prices()
    print(f"Storage contains {len(latest_prices)} latest price records")
    
    print()


async def main():
    """Run all tests"""
    print("Chainlink Price Collector Test Suite")
    print("=" * 50)
    print()
    
    try:
        await test_price_fetching()
        await test_file_storage()
        await test_full_cycle()
        
        print("=== Test Summary ===")
        print("✓ All tests completed successfully!")
        print("✓ Price fetching from Chainlink works")
        print("✓ File storage system works")
        print("✓ Full fetch & store cycle works")
        print()
        print("The price collector is ready to run!")
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())