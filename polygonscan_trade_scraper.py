#!/usr/bin/env python3
"""
Polygonscan Trade Scraper
Pulls all trades for a specific user address and saves with price data.
"""

import requests
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import os
from web3 import Web3

# Configuration
POLYGONSCAN_API_KEY = "HWVSXWJXTRSKKNYEJRBJVD11C4N3VB1UQD"  # Etherscan API key
TARGET_ADDRESS = "0x63ce342161250d705dc0b16df89036c8e5f9ba9a"
PRICE_COLLECTOR_URL = "http://danunahbot.ru"  # Our price collector API

# Known DEX router contracts on Polygon
DEX_ROUTERS = {
    "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506": "SushiSwap",
    "0xE592427A0AEce92De3Edee1F18E0157C05861564": "Uniswap V3",
    "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff": "QuickSwap",
    "0xC0788A3aD43d79aa53B7565258c72A4204c9a2cC": "QuickSwap V3",
    "0x94930a328162957FF1dd48900aF67B5439336cBD": "ApeSwap",
    "0x3a1D87f206D12415f5b0A33E786967680AAb4f6d": "Polycat",
    "0x8c1A3cF8f83074169FE5D7aD50B978e1cD6b37Da": "DFYN",
    "0x1F98431c8aD98523631AE4a59f267346ea31F984": "Uniswap V3 Factory",
}

class EtherscanScraper:
    """Scraper using Etherscan API V2 for Polygon transactions"""

    def __init__(self, api_key: str, address: str):
        self.api_key = api_key
        self.address = address.lower()
        # Etherscan API V2 for Polygon (chainid=137)
        self.base_url = "https://api.etherscan.io/v2/api"
        self.session = requests.Session()

    def get_transactions(self, start_block: int = 0, end_block: int = 99999999) -> List[Dict]:
        """Get all transactions for the address using Etherscan V2"""
        all_txs = []
        page = 1

        print(f"🔍 Starting transaction collection for {self.address}")

        while True:
            params = {
                'chainid': '137',  # Polygon mainnet
                'module': 'account',
                'action': 'txlist',
                'address': self.address,
                'startblock': start_block,
                'endblock': end_block,
                'page': page,
                'offset': 10000,  # Max per page for V2
                'sort': 'asc',
                'apikey': self.api_key
            }

            try:
                response = self.session.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if data['status'] == '0':
                    error_msg = data.get('message', '')
                    if 'rate limit' in error_msg.lower():
                        print("⏳ Rate limited, waiting 1 second...")
                        time.sleep(1)
                        continue
                    else:
                        print(f"❌ API Error: {error_msg}")
                        print(f"📋 Full response: {data}")
                        break

                transactions = data.get('result', [])
                if not transactions:
                    break

                all_txs.extend(transactions)
                print(f"📄 Page {page}: {len(transactions)} transactions (total: {len(all_txs)})")

                # Check if we got less than max results (last page)
                if len(transactions) < 10000:
                    break

                page += 1
                time.sleep(0.2)  # Respectful delay

            except Exception as e:
                print(f"❌ Error fetching page {page}: {e}")
                time.sleep(2)
                continue

        print(f"✅ Collected {len(all_txs)} total transactions")

        # Print sample transactions for analysis
        if all_txs:
            print("\n📋 Sample transactions:")
            for i, tx in enumerate(all_txs[:3]):
                to_addr = tx.get('to', 'N/A')
                print(f"  {i+1}. To: {to_addr} | Value: {tx.get('value', '0')} | Time: {datetime.fromtimestamp(int(tx.get('timeStamp', 0))).strftime('%Y-%m-%d %H:%M:%S')}")

        return all_txs

    def filter_dex_trades(self, transactions: List[Dict]) -> List[Dict]:
        """Filter transactions to find DEX trades"""
        trades = []

        for tx in transactions:
            # Skip failed transactions
            if tx.get('isError') == '1':
                continue

            # Check if transaction interacts with known DEX routers
            to_address = tx.get('to', '').lower()

            if to_address in DEX_ROUTERS:
                dex_name = DEX_ROUTERS[to_address]

                trade = {
                    'tx_hash': tx['hash'],
                    'timestamp': int(tx['timeStamp']),
                    'block': int(tx['blockNumber']),
                    'contract': to_address,
                    'dex': dex_name,
                    'value': float(tx.get('value', 0)) / 10**18,  # Convert from wei
                    'gas_used': int(tx.get('gasUsed', 0)),
                    'gas_price': int(tx.get('gasPrice', 0)),
                    'status': 'success' if tx.get('isError') == '0' else 'failed'
                }

                trades.append(trade)

        print(f"🎯 Found {len(trades)} DEX trades")
        return trades

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
                print(f"⚠️ No price found for {symbol} at {timestamp}")
                return None

        except Exception as e:
            print(f"❌ Error getting price for {symbol} at {timestamp}: {e}")
            return None

def main():
    """Main execution"""
    print("🚀 Starting Polygonscan Trade Scraper")
    print(f"📍 Target address: {TARGET_ADDRESS}")

    # Initialize scraper
    scraper = EtherscanScraper(POLYGONSCAN_API_KEY, TARGET_ADDRESS)
    price_client = PriceCollectorClient(PRICE_COLLECTOR_URL)

    # Get all transactions
    print("\n📊 Getting transactions...")
    transactions = scraper.get_transactions()

    if not transactions:
        print("❌ No transactions found")
        return

    # Filter DEX trades
    print("\n🔍 Filtering DEX trades...")
    trades = scraper.filter_dex_trades(transactions)

    # Get prices for each trade
    print("\n💰 Getting prices for trades...")
    enriched_trades = []

    for i, trade in enumerate(trades):
        print(f"📈 Processing trade {i+1}/{len(trades)}: {trade['tx_hash'][:10]}...")

        # Get BTC and ETH prices at trade time
        btc_price = price_client.get_price_at_timestamp('BTCUSDT', trade['timestamp'])
        eth_price = price_client.get_price_at_timestamp('ETHUSDT', trade['timestamp'])
        sol_price = price_client.get_price_at_timestamp('SOLUSDT', trade['timestamp'])

        enriched_trade = {
            **trade,
            'prices': {
                'BTC': btc_price,
                'ETH': eth_price,
                'SOL': sol_price
            },
            'datetime': datetime.fromtimestamp(trade['timestamp']).isoformat()
        }

        enriched_trades.append(enriched_trade)

        # Small delay to be respectful to our API
        time.sleep(0.1)

    # Save results
    output_file = f"trades_{TARGET_ADDRESS}_{int(time.time())}.json"

    result = {
        'metadata': {
            'address': TARGET_ADDRESS,
            'total_transactions': len(transactions),
            'dex_trades': len(enriched_trades),
            'generated_at': datetime.now().isoformat(),
            'price_source': PRICE_COLLECTOR_URL
        },
        'trades': enriched_trades
    }

    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print("\n✅ Scraping completed!")
    print(f"📁 Results saved to: {output_file}")
    print(f"📊 Total trades: {len(enriched_trades)}")
    print(f"💰 Trades with prices: {sum(1 for t in enriched_trades if any(p is not None for p in t['prices'].values()))}")

    # Print summary
    dex_summary = {}
    for trade in enriched_trades:
        dex = trade['dex']
        dex_summary[dex] = dex_summary.get(dex, 0) + 1

    print("\n📈 DEX Usage Summary:")
    for dex, count in sorted(dex_summary.items(), key=lambda x: x[1], reverse=True):
        print(f"  {dex}: {count} trades")

if __name__ == "__main__":
    main()