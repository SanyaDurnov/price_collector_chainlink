#!/usr/bin/env python3
"""
Parse TheTradeFox raw trade data into structured format
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Optional

def parse_trade_text(raw_text: str) -> Optional[Dict]:
    """Parse raw trade text into structured data"""
    try:
        lines = raw_text.strip().split('\n')

        if len(lines) < 10:
            return None

        # Extract trade number
        trade_match = re.match(r'^(\d+)', lines[0])
        trade_id = int(trade_match.group(1)) if trade_match else None

        # Extract market name
        market = lines[1].strip() if len(lines) > 1 else ""

        # Extract outcome
        outcome = lines[2].strip() if len(lines) > 2 else ""

        # Extract prices (remove ¢ and $ symbols, convert to float)
        def clean_price(price_str: str) -> float:
            if not price_str or price_str in ['N/A', '']:
                return 0.0
            # Remove currency symbols and convert cents to dollars
            cleaned = re.sub(r'[¢$]', '', price_str.strip())
            try:
                return float(cleaned) / 100.0 if '¢' in price_str else float(cleaned)
            except ValueError:
                return 0.0

        avg_price = clean_price(lines[3]) if len(lines) > 3 else 0.0
        current_price = clean_price(lines[4]) if len(lines) > 4 else 0.0

        # Extract quantity
        quantity_str = lines[5].strip() if len(lines) > 5 else "0"
        quantity = float(re.sub(r'[,$]', '', quantity_str)) if quantity_str else 0.0

        # Extract monetary values
        def clean_money(money_str: str) -> float:
            if not money_str or money_str in ['N/A', '']:
                return 0.0
            cleaned = re.sub(r'[,$]', '', money_str.strip())
            try:
                return float(cleaned)
            except ValueError:
                return 0.0

        avg_cost_basis = clean_money(lines[6]) if len(lines) > 6 else 0.0
        current_position_value = clean_money(lines[7]) if len(lines) > 7 else 0.0
        unrealized_pnl = clean_money(lines[8]) if len(lines) > 8 else 0.0
        realized_pnl = clean_money(lines[9]) if len(lines) > 9 else 0.0

        return {
            'trade_id': trade_id,
            'market': market,
            'outcome': outcome,
            'avg_price': avg_price,
            'current_price': current_price,
            'quantity': quantity,
            'avg_cost_basis': avg_cost_basis,
            'current_position_value': current_position_value,
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': realized_pnl,
            'total_pnl': unrealized_pnl + realized_pnl
        }

    except Exception as e:
        print(f"Error parsing trade: {e}")
        return None

def parse_tradefox_file(input_file: str, output_file: str = None) -> Dict:
    """Parse entire TheTradeFox JSON file and create structured output"""

    print(f"📂 Reading file: {input_file}")

    with open(input_file, 'r') as f:
        data = json.load(f)

    trades = data.get('trades', [])
    metadata = data.get('metadata', {})

    print(f"📊 Processing {len(trades)} raw trades...")

    parsed_trades = []
    skipped = 0

    for i, trade in enumerate(trades):
        raw_text = trade.get('raw_text', '').strip()

        # Skip header rows
        if 'Market Outcome' in raw_text or not raw_text or len(raw_text.split('\n')) < 10:
            skipped += 1
            continue

        parsed = parse_trade_text(raw_text)
        if parsed:
            # Add timestamp and other metadata
            parsed['timestamp'] = trade.get('timestamp', 0)
            parsed['extracted_at'] = trade.get('extracted_at', '')
            parsed['prices'] = trade.get('prices', {})
            parsed_trades.append(parsed)
        else:
            skipped += 1

    print(f"✅ Parsed {len(parsed_trades)} trades, skipped {skipped}")

    # Calculate summary statistics
    total_trades = len(parsed_trades)
    winning_trades = sum(1 for t in parsed_trades if t['total_pnl'] > 0)
    losing_trades = sum(1 for t in parsed_trades if t['total_pnl'] < 0)
    total_pnl = sum(t['total_pnl'] for t in parsed_trades)
    total_quantity = sum(t['quantity'] for t in parsed_trades)

    # Group by market
    market_stats = {}
    for trade in parsed_trades:
        market = trade['market']
        if market not in market_stats:
            market_stats[market] = {
                'count': 0,
                'total_pnl': 0.0,
                'total_quantity': 0.0
            }
        market_stats[market]['count'] += 1
        market_stats[market]['total_pnl'] += trade['total_pnl']
        market_stats[market]['total_quantity'] += trade['quantity']

    result = {
        'metadata': {
            **metadata,
            'parsed_at': datetime.now().isoformat(),
            'total_parsed_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_pnl': total_pnl,
            'total_quantity': total_quantity,
            'avg_pnl_per_trade': total_pnl / total_trades if total_trades > 0 else 0
        },
        'market_summary': market_stats,
        'trades': parsed_trades
    }

    # Save to output file
    if not output_file:
        output_file = input_file.replace('.json', '_parsed.json')

    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"💾 Saved parsed data to: {output_file}")
    print(f"📊 Summary: {total_trades} trades, P&L: ${total_pnl:.2f}, Win rate: {winning_trades/total_trades*100:.1f}%")

    return result

def main():
    """Main execution"""
    # Process the 30-minute file
    input_file = "tradefox_0x63ce342161250d705dc0b16df89036c8e5f9ba9a_1771163480.json"
    output_file = "tradefox_0x63ce342161250d705dc0b16df89036c8e5f9ba9a_1771163480_parsed.json"

    print("🚀 Starting TheTradeFox Trade Parser")
    print("=" * 50)

    result = parse_tradefox_file(input_file, output_file)

    # Print summary
    meta = result['metadata']
    print("\n📈 TRADING SUMMARY:")
    print(f"Total Trades: {meta['total_parsed_trades']}")
    print(f"Winning Trades: {meta['winning_trades']}")
    print(f"Losing Trades: {meta['losing_trades']}")
    print(f"Win Rate: {meta['win_rate']*100:.1f}%")
    print(f"Total P&L: ${meta['total_pnl']:.2f}")
    print(f"Average P&L per Trade: ${meta['avg_pnl_per_trade']:.2f}")

    print("\n🏆 TOP MARKETS:")
    market_summary = result['market_summary']
    sorted_markets = sorted(market_summary.items(), key=lambda x: x[1]['total_pnl'], reverse=True)

    for market, stats in sorted_markets[:5]:
        print(f"  {market}")
        print(f"    Trades: {stats['count']}, P&L: ${stats['total_pnl']:.2f}")
if __name__ == "__main__":
    main()