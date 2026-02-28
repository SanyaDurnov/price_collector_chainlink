#!/usr/bin/env python3
"""
TheTradeFox Portfolio Scraper
Extracts trade data from thetradefox.com portfolio pages
"""

import requests
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re

# Configuration
TARGET_ADDRESS = "0x63ce342161250d705dc0b16df89036c8e5f9ba9a"
TRADEFOX_URL = f"https://thetradefox.com/portfolio/{TARGET_ADDRESS}"
PRICE_COLLECTOR_URL = "http://danunahbot.ru"  # Our price collector API

class TheTradeFoxScraper:
    """Scraper for TheTradeFox portfolio pages"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self._setup_driver()

    def _setup_driver(self):
        """Setup Chrome WebDriver"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            print("✅ Chrome WebDriver initialized")
        except Exception as e:
            print(f"❌ Failed to initialize WebDriver: {e}")
            print("💡 Make sure Chrome and chromedriver are installed")
            raise

    def scrape_portfolio_continuous(self, url: str, duration_seconds: int = 30, refresh_interval: int = 1) -> List[Dict]:
        """Fast continuous scraping with direct trade extraction"""
        print(f"🔍 Starting FAST monitoring for {duration_seconds}s (refresh every {refresh_interval}s)")

        all_trades = []
        seen_trade_texts = set()
        start_time = time.time()
        last_refresh = 0

        try:
            while time.time() - start_time < duration_seconds:
                current_time = time.time()

                # Refresh page every refresh_interval seconds
                if current_time - last_refresh >= refresh_interval:
                    elapsed = int(current_time - start_time)
                    print(f"🔄 Refresh {elapsed}s...")

                    self.driver.get(url)
                    time.sleep(2.0)  # Give more time for JS to load

                    # Wait for table to appear
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                        )
                        print("📊 Table loaded successfully")
                    except TimeoutException:
                        print("⚠️ Table didn't load within timeout")
                    last_refresh = current_time

                    # Extract all current trades immediately
                    current_trades = self._extract_trades_fast(1000)

                    # Check for new trades
                    new_trades = []
                    for trade in current_trades:
                        trade_text = trade.get('raw_text', '').strip()
                        if trade_text and trade_text not in seen_trade_texts and len(trade_text) > 20:
                            new_trades.append(trade)
                            seen_trade_texts.add(trade_text)

                    if new_trades:
                        all_trades.extend(new_trades)
                        print(f"🆕 FOUND {len(new_trades)} NEW TRADES! Total: {len(all_trades)}")
                        for i, trade in enumerate(new_trades[:3]):  # Show first 3
                            preview = trade.get('raw_text', '')[:80]
                            print(f"   {i+1}. {preview}...")
                    else:
                        print(f"📊 No new trades ({len(current_trades)} total visible)")

                time.sleep(0.02)  # Ultra small delay

            print(f"✅ FAST monitoring completed. Total unique trades: {len(all_trades)}")
            return all_trades

        except Exception as e:
            print(f"❌ Error in fast monitoring: {e}")
            return all_trades

    def _get_page_content_hash(self) -> str:
        """Get a hash of the current page content for change detection"""
        try:
            # Get key content areas that would change with new trades
            body_text = self.driver.find_element(By.TAG_NAME, 'body').text
            # Focus on trade-related content
            trade_indicators = ['Market', 'Outcome', 'Quantity', 'Price', 'P&L']
            relevant_content = []

            for indicator in trade_indicators:
                if indicator in body_text:
                    # Extract lines containing trade indicators
                    lines = body_text.split('\n')
                    for line in lines:
                        if indicator in line and len(line.strip()) > 10:
                            relevant_content.append(line.strip())

            content_hash = hash(''.join(relevant_content))
            return str(content_hash)

        except Exception:
            return "error"

    def _load_all_trades(self, max_clicks: int = 50):
        """Click load more buttons to get all trades"""
        clicks = 0

        while clicks < max_clicks:
            try:
                # Try different selectors for "Load More" buttons
                load_buttons = self.driver.find_elements(By.XPATH,
                    "//button[contains(text(), 'Load More') or contains(text(), 'Show More') or contains(text(), 'View More')]")

                if not load_buttons:
                    # Try other selectors
                    load_buttons = self.driver.find_elements(By.CSS_SELECTOR,
                        "button[data-testid*='load'], button[class*='load'], button[class*='more']")

                if not load_buttons:
                    break

                # Click the first load more button
                load_buttons[0].click()
                print(f"📄 Clicked load more button ({clicks + 1}/{max_clicks})")
                time.sleep(2)  # Wait for new data to load
                clicks += 1

            except Exception as e:
                print(f"⚠️ No more load buttons or error: {e}")
                break

    def _extract_trades_fast(self, max_trades: int) -> List[Dict]:
        """Fast extraction of trade data - optimized for continuous monitoring"""
        trades = []

        try:
            # Directly target table rows (we know this works)
            trade_elements = self.driver.find_elements(By.CSS_SELECTOR, "table tr")

            if not trade_elements:
                # Fallback: try other selectors quickly
                for selector in ["tbody tr", ".trade-row", "[class*='trade']"]:
                    trade_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if trade_elements:
                        print(f"🔄 Using fallback selector: {selector} ({len(trade_elements)} elements)")
                        break

            if not trade_elements:
                print("⚠️ No trade elements found with any selector")
                return trades

            print(f"📊 Found {len(trade_elements)} table rows")

            # Extract data from elements (skip debug output for speed)
            for i, element in enumerate(trade_elements[:max_trades]):
                try:
                    text = element.text.strip()
                    if text and len(text) > 10:  # Only meaningful content
                        trade_data = self._parse_trade_element(element)
                        if trade_data:
                            trades.append(trade_data)
                            if len(trades) <= 3:  # Debug first few
                                print(f"   Trade {len(trades)}: {text[:100]}...")
                except Exception as e:
                    continue  # Skip errors for speed

            print(f"✅ Extracted {len(trades)} trades with content")

        except Exception as e:
            print(f"❌ Error in fast extraction: {e}")

        return trades

    def _extract_trades(self, max_trades: int) -> List[Dict]:
        """Extract trade data from the page"""
        trades = []

        try:
            # Debug: Print page title and some basic info
            print(f"📄 Page title: {self.driver.title}")
            print(f"📄 Current URL: {self.driver.current_url}")

            # Try to find trade rows using various selectors
            trade_selectors = [
                "[data-testid*='trade']",
                ".trade-row",
                ".portfolio-trade",
                "tr[data-trade]",
                ".trade-item",
                "[class*='trade']",
                "table tr",  # Generic table rows
                ".card",     # Generic cards
                ".item"      # Generic items
            ]

            trade_elements = []
            for selector in trade_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        trade_elements = elements
                        print(f"🎯 Found {len(elements)} elements using selector: {selector}")
                        # Show sample text from first few elements
                        for i, elem in enumerate(elements[:3]):
                            try:
                                text = elem.text.strip()[:100] if elem.text else "No text"
                                print(f"   Sample {i+1}: {text}...")
                            except:
                                print(f"   Sample {i+1}: Error getting text")
                        break
                except Exception as e:
                    print(f"⚠️ Selector {selector} failed: {e}")
                    continue

            if not trade_elements:
                print("🔍 No trade elements found, checking page source...")
                # Try to find trade data in page source
                page_source = self.driver.page_source
                trades = self._extract_from_html(page_source, max_trades)
                return trades

            # Extract data from elements
            for i, element in enumerate(trade_elements[:max_trades]):
                try:
                    trade_data = self._parse_trade_element(element)
                    if trade_data:
                        trades.append(trade_data)
                except Exception as e:
                    print(f"⚠️ Error parsing trade {i}: {e}")

        except Exception as e:
            print(f"❌ Error extracting trades: {e}")

        return trades

    def _parse_trade_element(self, element) -> Optional[Dict]:
        """Parse individual trade element"""
        try:
            # This is a generic parser - would need to be customized based on actual page structure
            text = element.text.strip()

            # Extract basic trade info using regex
            trade = {
                'raw_text': text,
                'timestamp': int(time.time()),  # Placeholder
                'extracted_at': datetime.now().isoformat()
            }

            return trade

        except Exception as e:
            return None

    def _extract_from_html(self, html: str, max_trades: int) -> List[Dict]:
        """Extract trade data from HTML source"""
        trades = []

        try:
            # Look for JSON data in script tags
            json_pattern = r'<script[^>]*>.*?(\{.*?\}).*?</script>'
            json_matches = re.findall(json_pattern, html, re.DOTALL | re.IGNORECASE)

            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    # Look for trade data in the JSON
                    if 'trades' in data or 'portfolio' in data:
                        if 'trades' in data:
                            trades_data = data['trades']
                        elif 'portfolio' in data and 'trades' in data['portfolio']:
                            trades_data = data['portfolio']['trades']
                        else:
                            continue

                        if isinstance(trades_data, list):
                            for trade in trades_data[:max_trades]:
                                if isinstance(trade, dict):
                                    trades.append({
                                        'data': trade,
                                        'source': 'json_script',
                                        'timestamp': int(time.time()),
                                        'extracted_at': datetime.now().isoformat()
                                    })

                        if len(trades) >= max_trades:
                            break

                except json.JSONDecodeError:
                    continue

            if trades:
                print(f"📊 Extracted {len(trades)} trades from JSON data")

        except Exception as e:
            print(f"⚠️ Error extracting from HTML: {e}")

        return trades

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            print("🔒 Browser closed")

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
            return None

def main():
    """Main execution"""
    print("🚀 Starting TheTradeFox Portfolio Scraper")
    print(f"📍 Target portfolio: {TRADEFOX_URL}")

    # Initialize scraper
    scraper = TheTradeFoxScraper(headless=True)  # Use headless for server environment
    price_client = PriceCollectorClient(PRICE_COLLECTOR_URL)

    try:
        # Scrape portfolio data continuously for 30 minutes
        print("\n📊 Starting continuous portfolio scraping for 30 minutes...")
        trades = scraper.scrape_portfolio_continuous(TRADEFOX_URL, duration_seconds=1800, refresh_interval=5)

        if not trades:
            print("❌ No trades found")
            return

        # Get prices for each trade
        print("\n💰 Getting prices for trades...")
        enriched_trades = []

        for i, trade in enumerate(trades):
            print(f"📈 Processing trade {i+1}/{len(trades)}...")

            # Get BTC and ETH prices at trade time
            timestamp = trade.get('timestamp', int(time.time()))
            btc_price = price_client.get_price_at_timestamp('BTCUSDT', timestamp)
            eth_price = price_client.get_price_at_timestamp('ETHUSDT', timestamp)
            sol_price = price_client.get_price_at_timestamp('SOLUSDT', timestamp)

            enriched_trade = {
                **trade,
                'prices': {
                    'BTC': btc_price,
                    'ETH': eth_price,
                    'SOL': sol_price
                }
            }

            enriched_trades.append(enriched_trade)

            # Small delay to be respectful to our API
            time.sleep(0.1)

        # Save results
        output_file = f"tradefox_{TARGET_ADDRESS}_{int(time.time())}.json"

        result = {
            'metadata': {
                'address': TARGET_ADDRESS,
                'portfolio_url': TRADEFOX_URL,
                'total_trades': len(enriched_trades),
                'generated_at': datetime.now().isoformat(),
                'price_source': PRICE_COLLECTOR_URL,
                'source': 'thetradefox.com'
            },
            'trades': enriched_trades
        }

        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print("\n✅ Scraping completed!")
        print(f"📁 Results saved to: {output_file}")
        print(f"📊 Total trades: {len(enriched_trades)}")
        print(f"💰 Trades with prices: {sum(1 for t in enriched_trades if any(p is not None for p in t['prices'].values()))}")

    finally:
        scraper.close()

if __name__ == "__main__":
    main()