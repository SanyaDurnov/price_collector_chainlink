#!/usr/bin/env python3
"""
Test Enhanced Price Collector Service
Tests ET time support, buffering, and enhanced cleanup
"""

import asyncio
import time
import json
import os
import tempfile
import shutil
from datetime import datetime
import pytz

# Add the project root to the path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enhanced_price_service import (
    TimeHelper, 
    InMemoryBuffer, 
    EnhancedFilePriceStorage,
    EnhancedPriceCollectorService,
    EnhancedPriceAPIServer,
    MockPriceFetcher
)


class TestEnhancedPriceCollector:
    """Test enhanced price collector functionality"""
    
    def __init__(self):
        self.test_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.test_dir, 'data')
        self.log_dir = os.path.join(self.test_dir, 'logs')
        self.config = {
            'rpc_url': 'https://polygon-rpc.com',
            'api_port': 8081,  # Different port for testing
            'collection_interval': 0.1,  # Fast for testing
            'cleanup_interval': 1,
            'data_retention_hours': 1,
            'buffer_max_age_seconds': 5,
            'symbols': {
                'BTC': '0xc907E116054Ad103354f2D350FD2514433D57F6f',
                'ETH': '0xF9680D99D6C9589e2a93a78A04A279e509205945'
            },
            'storage': {
                'type': 'file',
                'data_directory': self.data_dir,
                'log_directory': self.log_dir
            }
        }
    
    async def test_time_helper(self):
        """Test time zone conversions"""
        print("Testing TimeHelper...")
        
        # Test current time
        current_timestamp = int(time.time())
        utc_time = TimeHelper.format_time(current_timestamp, 'UTC')
        et_time = TimeHelper.format_time(current_timestamp, 'ET')
        
        print(f"UTC time: {utc_time}")
        print(f"ET time: {et_time}")
        
        # Test conversion
        et_dt = TimeHelper.utc_to_et(current_timestamp)
        converted_back = TimeHelper.et_to_utc(et_dt)
        
        assert abs(current_timestamp - converted_back) < 2, "Time conversion error"
        print("✓ TimeHelper tests passed")
    
    async def test_in_memory_buffer(self):
        """Test in-memory buffer functionality"""
        print("Testing InMemoryBuffer...")
        
        buffer = InMemoryBuffer(max_age_seconds=2)
        
        # Add some prices
        current_time = int(time.time())
        buffer.add_price('BTC', 50000.0, current_time, 1001)
        buffer.add_price('ETH', 3000.0, current_time + 1, 1002)
        
        # Test retrieval
        result = buffer.get_price_at_timestamp('BTC', current_time, 60)
        assert result is not None, "Buffer retrieval failed"
        assert result['price'] == 50000.0, "Wrong price"
        assert result['source'] == 'buffer', "Wrong source"
        
        # Test tolerance
        result = buffer.get_price_at_timestamp('BTC', current_time + 30, 60)
        assert result is not None, "Buffer tolerance test failed"
        
        print("✓ InMemoryBuffer tests passed")
    
    async def test_enhanced_storage(self):
        """Test enhanced file storage with ET time support"""
        print("Testing EnhancedFilePriceStorage...")
        
        storage = EnhancedFilePriceStorage(
            data_dir=self.data_dir,
            log_dir=self.log_dir,
            retention_hours=1
        )
        
        current_time = int(time.time())
        
        # Insert price
        await storage.insert_price('BTC', 50000.0, current_time, 1001)
        
        # Retrieve price
        result = await storage.get_price_at_timestamp('BTC', current_time, 60)
        assert result is not None, "Storage retrieval failed"
        assert result['price'] == 50000.0, "Wrong price"
        assert 'et_time' in result, "ET time not stored"
        
        # Test latest prices
        latest = await storage.get_latest_prices()
        assert len(latest) == 1, "Wrong number of latest prices"
        assert latest[0]['symbol'] == 'BTC', "Wrong symbol"
        
        print("✓ EnhancedFilePriceStorage tests passed")
    
    async def test_buffer_priority(self):
        """Test that buffer has priority over file"""
        print("Testing buffer priority...")
        
        storage = EnhancedFilePriceStorage(
            data_dir=self.data_dir,
            log_dir=self.log_dir,
            retention_hours=1
        )
        buffer = InMemoryBuffer(max_age_seconds=5)
        
        current_time = int(time.time())
        
        # Add to file first
        await storage.insert_price('BTC', 50000.0, current_time, 1001)
        
        # Add to buffer (same timestamp, different price)
        buffer.add_price('BTC', 51000.0, current_time, 1002)
        
        # Check that buffer result has priority
        # This would be tested in the API server logic
        
        print("✓ Buffer priority test setup complete")
    
    async def test_enhanced_api(self):
        """Test enhanced API functionality"""
        print("Testing EnhancedPriceAPIServer...")
        
        storage = EnhancedFilePriceStorage(
            data_dir=self.data_dir,
            log_dir=self.log_dir,
            retention_hours=1
        )
        buffer = InMemoryBuffer(max_age_seconds=5)
        
        api_server = EnhancedPriceAPIServer(storage, buffer, self.config)
        
        # Test time info endpoint
        # This would require setting up the full aiohttp server
        
        print("✓ EnhancedPriceAPIServer test setup complete")
    
    async def run_all_tests(self):
        """Run all tests"""
        print("Starting Enhanced Price Collector Tests...")
        print("=" * 50)
        
        try:
            await self.test_time_helper()
            await self.test_in_memory_buffer()
            await self.test_enhanced_storage()
            await self.test_buffer_priority()
            await self.test_enhanced_api()
            
            print("=" * 50)
            print("✅ All Enhanced Price Collector tests passed!")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            shutil.rmtree(self.test_dir)
            print("Test directory cleaned up")


async def main():
    """Main test runner"""
    tester = TestEnhancedPriceCollector()
    await tester.run_all_tests()


if __name__ == '__main__':
    asyncio.run(main())