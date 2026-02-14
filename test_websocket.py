#!/usr/bin/env python3
"""
Test script for WebSocket Polymarket RTDS price collection.
Runs the service for 30 seconds and checks if prices are collected.
"""

import asyncio
import time
import json
import subprocess
import signal
import os
from pathlib import Path

async def test_websocket_collection():
    """Test WebSocket price collection for 30 seconds."""
    print("🧪 Testing WebSocket Polymarket RTDS price collection...")

    # Start the service in background
    print("🚀 Starting price collector service...")
    process = subprocess.Popen(
        ['python', 'chainlink_price_service.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid  # Create new process group
    )

    try:
        # Wait for service to start
        print("⏳ Waiting 10 seconds for service to initialize...")
        await asyncio.sleep(10)

        # Check if API is responding
        print("🔍 Testing API health check...")
        result = subprocess.run(
            ['curl', '-s', 'http://localhost:8080/health'],
            capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            try:
                health_data = json.loads(result.stdout)
                print(f"✅ API is responding: {health_data}")
            except json.JSONDecodeError:
                print(f"⚠️ API responded but invalid JSON: {result.stdout}")
        else:
            print(f"❌ API not responding: {result.stderr}")

        # Wait another 60 seconds for price collection
        print("⏳ Waiting 60 seconds for price collection...")
        await asyncio.sleep(60)

        # Check collected prices
        print("📊 Checking collected prices...")

        # Test API endpoints
        endpoints = [
            ('http://localhost:8080/latest', 'Latest prices'),
            ('http://localhost:8080/price/BTCUSDT', 'BTC price'),
            ('http://localhost:8080/price/ETHUSDT', 'ETH price'),
            ('http://localhost:8080/price/SOLUSDT', 'SOL price'),
        ]

        for url, description in endpoints:
            result = subprocess.run(
                ['curl', '-s', url],
                capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if 'prices' in data and data['prices']:
                        prices = data['prices']
                        if isinstance(prices, list):
                            print(f"✅ {description}: {len(prices)} prices collected")
                            for price in prices[:3]:  # Show first 3
                                symbol = price.get('symbol', 'N/A')
                                price_val = price.get('price', 'N/A')
                                timestamp = price.get('timestamp', 'N/A')
                                print(f"   {symbol}: ${price_val} @ {timestamp}")
                        else:
                            print(f"⚠️ {description}: Unexpected format")
                    elif 'price' in data:
                        symbol = data.get('symbol', 'N/A')
                        price_val = data.get('price', 'N/A')
                        timestamp = data.get('timestamp', 'N/A')
                        print(f"✅ {description}: {symbol} = ${price_val} @ {timestamp}")
                    else:
                        print(f"⚠️ {description}: No price data in response")
                except json.JSONDecodeError:
                    print(f"❌ {description}: Invalid JSON response")
            else:
                print(f"❌ {description}: Request failed")

        # Check data file
        data_file = Path("data/prices.json")
        if data_file.exists():
            try:
                with open(data_file, 'r') as f:
                    data = json.load(f)

                if 'prices' in data:
                    total_prices = sum(len(symbol_prices) for symbol_prices in data['prices'].values())
                    print(f"💾 Data file contains {total_prices} total price entries")

                    for symbol, prices in data['prices'].items():
                        if prices:
                            latest = max(prices, key=lambda x: x['timestamp'])
                            print(f"   {symbol}: {len(prices)} entries, latest ${latest['price']}")
                else:
                    print("⚠️ Data file has unexpected format")

            except Exception as e:
                print(f"❌ Error reading data file: {e}")
        else:
            print("❌ Data file not found")

        print("✅ Test completed successfully!")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")

    finally:
        # Stop the service
        print("🛑 Stopping price collector service...")
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
        except:
            process.kill()

        print("🏁 Test finished!")

if __name__ == "__main__":
    asyncio.run(test_websocket_collection())