#!/usr/bin/env python3
"""
Add prices from danunahbot.ru to timestamps_trades file
Converts local time to ET before querying prices
"""

import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional
import time

# Configuration
PRICE_COLLECTOR_URL = "http://danunahbot.ru"
LOCAL_TIMEZONE_OFFSET = 3  # UTC+3 (Europe/Minsk)
ET_OFFSET = -5  # UTC-5 (Eastern Time, assuming no DST)

class PriceCollectorClient:
    """Client for our price collector API"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def get_price_at_timestamp(self, symbol: str, timestamp: int, tolerance: int = 300) -> Optional[float]:
        """Get price closest to timestamp"""
        try:
            url = f"{self.base_url}/price/{symbol}"
            params = {
                'timestamp': timestamp,
                'tolerance': tolerance
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'price' in data:
                return float(data['price'])
            else:
                return None

        except Exception as e:
            print(f"Error getting {symbol} price for timestamp {timestamp}: {e}")
            return None

def parse_timestamp(timestamp_str: str) -> int:
    """Parse timestamp string to Unix timestamp"""
    try:
        # Format: MM/DD/YY HH:MM:SS
        dt = datetime.strptime(timestamp_str.strip(), "%m/%d/%y %H:%M:%S")
        # Convert to Unix timestamp
        return int(dt.timestamp())
    except Exception as e:
        print(f"Error parsing timestamp '{timestamp_str}': {e}")
        return None

def convert_local_to_et(local_timestamp: int) -> int:
    """Convert local time (UTC+3) to ET (UTC-5)"""
    # Local time is UTC+3, ET is UTC-5
    # Difference is 3 - (-5) = 8 hours
    offset_hours = LOCAL_TIMEZONE_OFFSET - ET_OFFSET
    return local_timestamp - (offset_hours * 3600)

def process_timestamps_file(input_file: str, output_file: str = None) -> Dict:
    """Process timestamps file and add prices"""

    print(f"📂 Reading timestamps from: {input_file}")

    # Read all timestamps
    timestamps = []
    with open(input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                timestamp = parse_timestamp(line)
                if timestamp:
                    timestamps.append(timestamp)

    print(f"📊 Found {len(timestamps)} timestamps")

    # Deduplicate timestamps
    unique_timestamps = list(set(timestamps))
    unique_timestamps.sort()
    print(f"📊 After deduplication: {len(unique_timestamps)} unique timestamps")

    # Initialize price collector
    price_client = PriceCollectorClient(PRICE_COLLECTOR_URL)

    # Process timestamps in batches to avoid overwhelming the API
    results = []
    batch_size = 50
    total_processed = 0

    for i in range(0, len(unique_timestamps), batch_size):
        batch = unique_timestamps[i:i+batch_size]
        batch_results = []

        print(f"📈 Processing batch {i//batch_size + 1}/{(len(unique_timestamps) + batch_size - 1)//batch_size} ({len(batch)} timestamps)")

        for timestamp in batch:
            # Convert to ET
            et_timestamp = convert_local_to_et(timestamp)

            # Get prices for BTC, ETH, SOL
            btc_price = price_client.get_price_at_timestamp('BTCUSDT', et_timestamp)
            eth_price = price_client.get_price_at_timestamp('ETHUSDT', et_timestamp)
            sol_price = price_client.get_price_at_timestamp('SOLUSDT', et_timestamp)

            result = {
                'local_timestamp': timestamp,
                'et_timestamp': et_timestamp,
                'datetime_local': datetime.fromtimestamp(timestamp).isoformat(),
                'datetime_et': datetime.fromtimestamp(et_timestamp).isoformat(),
                'prices': {
                    'BTC': btc_price,
                    'ETH': eth_price,
                    'SOL': sol_price
                }
            }

            batch_results.append(result)
            total_processed += 1

            # Progress indicator
            if total_processed % 100 == 0:
                print(f"  ✅ Processed {total_processed}/{len(unique_timestamps)} timestamps")

        results.extend(batch_results)

        # Small delay between batches to be respectful to the API
        if i + batch_size < len(unique_timestamps):
            time.sleep(1)

    # Calculate statistics
    prices_found = sum(1 for r in results if any(p is not None for p in r['prices'].values()))
    btc_prices = sum(1 for r in results if r['prices']['BTC'] is not None)
    eth_prices = sum(1 for r in results if r['prices']['ETH'] is not None)
    sol_prices = sum(1 for r in results if r['prices']['SOL'] is not None)

    result_data = {
        'metadata': {
            'input_file': input_file,
            'total_timestamps': len(timestamps),
            'unique_timestamps': len(unique_timestamps),
            'timestamps_with_prices': prices_found,
            'price_coverage': prices_found / len(unique_timestamps) if unique_timestamps else 0,
            'btc_prices_found': btc_prices,
            'eth_prices_found': eth_prices,
            'sol_prices_found': sol_prices,
            'generated_at': datetime.now().isoformat(),
            'timezone_conversion': f'Local (UTC+{LOCAL_TIMEZONE_OFFSET}) to ET (UTC{ET_OFFSET})'
        },
        'timestamps': results
    }

    # Save to output file
    if not output_file:
        output_file = input_file.replace('.txt', '_with_prices.json')

    with open(output_file, 'w') as f:
        json.dump(result_data, f, indent=2)

    print(f"💾 Saved results to: {output_file}")
    print(f"📊 Final statistics:")
    print(f"  Total timestamps: {len(timestamps)}")
    print(f"  Unique timestamps: {len(unique_timestamps)}")
    print(f"  With prices: {prices_found} ({prices_found/len(unique_timestamps)*100:.1f}%)")
    print(f"  BTC prices: {btc_prices}")
    print(f"  ETH prices: {eth_prices}")
    print(f"  SOL prices: {sol_prices}")

    return result_data

def main():
    """Main execution"""
    input_file = "timestamps_trades"
    output_file = "timestamps_trades_with_prices.json"

    print("🚀 Starting Price Addition to Timestamps")
    print("=" * 50)

    result = process_timestamps_file(input_file, output_file)

    print("\n✅ Processing completed!")
    print(f"📁 Output file: {output_file}")

if __name__ == "__main__":
    main()