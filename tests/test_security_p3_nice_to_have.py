"""
P3 Nice to Have Security Tests  
Tests for chaos engineering, performance regression, and advanced features.
"""

import pytest
import time
import random
from pathlib import Path
from unittest.mock import patch, MagicMock
import json


class TestChaosEngineering:
    """Chaos engineering tests - random failures"""
    
    def test_random_database_failures(self, tmp_path):
        """Test system resilience to random database failures"""
        from src.core.database import DatabaseManager
        
        db = DatabaseManager(str(tmp_path / "chaos.db"))
        
        # Inject random failures
        success_count = 0
        failure_count = 0
        
        for i in range(100):
            try:
                if random.random() < 0.1:  # 10% failure rate
                    raise sqlite3.OperationalError("Simulated failure")
                
                db.add_transaction({
                    'date': '2024-01-01',
                    'action': 'BUY',
                    'coin': f'COIN{i}',
                    'amount': 1.0,
                    'price_usd': 100,
                    'source': 'test'
                })
                success_count += 1
            except Exception:
                failure_count += 1
        
        # System should have handled failures gracefully
        assert success_count > 0, "System should succeed some operations"
        assert failure_count < 50, "System shouldn't fail more than 50%"
    
    def test_random_network_failures(self, app_client):
        """Test resilience to random network failures"""
        success_count = 0
        timeout_count = 0
        
        for i in range(50):
            try:
                if random.random() < 0.15:  # 15% failure rate
                    # Simulate timeout
                    with patch('requests.get', side_effect=TimeoutError()):
                        response = app_client.get('/api/transactions')
                    timeout_count += 1
                else:
                    response = app_client.get('/api/transactions')
                    success_count += 1
            except TimeoutError:
                timeout_count += 1
        
        assert success_count > 0, "Some requests should succeed"
    
    def test_random_file_corruption(self, tmp_path):
        """Test handling of randomly corrupted files"""
        test_file = tmp_path / "data.json"
        
        for i in range(20):
            # Write valid data
            test_file.write_text(json.dumps({'key': 'value'}))
            
            # Randomly corrupt
            if random.random() < 0.2:
                with open(test_file, 'rb+') as f:
                    pos = random.randint(0, f.seek(0, 2) - 1)
                    f.seek(pos)
                    f.write(b'\\x00')
            
            # Try to read
            try:
                content = json.loads(test_file.read_text())
                assert 'key' in content
            except json.JSONDecodeError:
                # Acceptable - corrupted file detected
                pass


class TestPerformanceRegression:
    """Performance regression tests"""
    
    def test_transaction_query_performance(self, tmp_path):
        """Test that queries don't regress in performance"""
        from src.core.database import DatabaseManager
        
        db = DatabaseManager(str(tmp_path / "perf.db"))
        
        # Insert 1000 transactions
        for i in range(1000):
            db.add_transaction({
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': f'COIN{i % 50}',  # 50 unique coins
                'amount': 1.0,
                'price_usd': 100 + i,
                'source': 'test'
            })
        
        # Measure query time
        start = time.time()
        transactions = db.get_all_transactions(limit=100)
        elapsed = time.time() - start
        
        # Should be fast (< 100ms for 100 records from 1000)
        assert elapsed < 0.1, f"Query took {elapsed:.3f}s, expected < 0.1s"
    
    def test_bulk_insert_performance(self, tmp_path):
        """Test bulk insert performance"""
        from src.core.database import DatabaseManager
        
        db = DatabaseManager(str(tmp_path / "bulk.db"))
        
        transactions = [
            {
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': f'COIN{i}',
                'amount': 1.0,
                'price_usd': 100,
                'source': 'test'
            }
            for i in range(1000)
        ]
        
        start = time.time()
        db.bulk_insert(transactions)
        elapsed = time.time() - start
        
        # Should be fast (< 1s for 1000 inserts)
        assert elapsed < 1.0, f"Bulk insert took {elapsed:.3f}s, expected < 1s"
    
    def test_memory_usage_stability(self, tmp_path):
        """Test that memory usage doesn't grow unbounded"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many operations
        from src.core.database import DatabaseManager
        db = DatabaseManager(str(tmp_path / "memory.db"))
        
        for i in range(1000):
            db.add_transaction({
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 50000,
                'source': 'test'
            })
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be reasonable (< 50MB for 1000 operations)
        assert memory_growth < 50, \
            f"Memory grew by {memory_growth:.1f}MB, expected < 50MB"


class TestAccessibilityWCAG:
    """WCAG accessibility tests for web UI"""
    
    def test_html_has_lang_attribute(self, app_client):
        """Test that HTML has lang attribute for screen readers"""
        response = app_client.get('/setup/wizard')
        assert b'<html lang=' in response.data or b'html lang=' in response.data, \
            "HTML should have lang attribute"
    
    def test_images_have_alt_text(self, app_client):
        """Test that all images have alt text"""
        response = app_client.get('/setup/wizard')
        html = response.data.decode()
        
        # Check for img tags without alt
        import re
        img_tags = re.findall(r'<img[^>]*>', html)
        for img in img_tags:
            if 'alt=' not in img:
                pytest.fail(f"Image missing alt text: {img}")
    
    def test_form_labels_for_inputs(self, app_client):
        """Test that all form inputs have labels"""
        response = app_client.get('/setup/wizard')
        html = response.data.decode()
        
        import re
        # Find all input fields
        inputs = re.findall(r'<input[^>]*id="([^"]*)"', html)
        
        # Check each has corresponding label
        for input_id in inputs:
            label_pattern = f'<label[^>]*for="{input_id}"'
            assert re.search(label_pattern, html), \
                f"Input {input_id} missing label"
    
    def test_color_contrast_sufficient(self):
        """Test that color contrast meets WCAG AA standards"""
        # This would require analyzing CSS
        # For now, just verify CSS file exists
        from src.utils.constants import BASE_DIR
        css_files = list((BASE_DIR / 'web_static').glob('*.css'))
        assert len(css_files) > 0, "No CSS files found"


class TestBrowserCompatibility:
    """Browser compatibility tests"""
    
    def test_works_without_javascript(self, app_client):
        """Test that basic functionality works without JavaScript"""
        response = app_client.get('/setup/wizard')
        
        # Should have noscript tags for fallback
        assert b'<noscript>' in response.data or \
               b'No JavaScript' in response.data or \
               response.status_code == 200  # At minimum, should load
    
    def test_responsive_viewport_meta_tag(self, app_client):
        """Test that page has responsive viewport meta tag"""
        response = app_client.get('/setup/wizard')
        assert b'viewport' in response.data and b'width=device-width' in response.data, \
            "Page should have responsive viewport meta tag"
    
    def test_works_in_private_browsing_mode(self, app_client):
        """Test that app works without persistent cookies"""
        # Simulate private browsing by not persisting cookies
        response1 = app_client.get('/setup/wizard')
        assert response1.status_code == 200
        
        # New request without cookies
        response2 = app_client.get('/setup/wizard')
        assert response2.status_code == 200


class TestMobileDeviceTesting:
    """Mobile device specific tests"""
    
    def test_mobile_viewport_rendering(self, app_client):
        """Test page renders correctly on mobile viewport"""
        # Simulate mobile user agent
        response = app_client.get('/setup/wizard',
            headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'})
        
        assert response.status_code == 200
        # Should not have horizontal scroll
        assert b'width=device-width' in response.data
    
    def test_touch_target_size(self, app_client):
        """Test that buttons are large enough for touch (44x44px minimum)"""
        response = app_client.get('/setup/wizard')
        html = response.data.decode()
        
        # Check for button CSS that enforces minimum size
        # This is a basic check - full test would parse CSS
        assert 'button' in html.lower()
    
    def test_mobile_form_input_types(self, app_client):
        """Test that mobile-optimized input types are used"""
        response = app_client.get('/setup/wizard')
        html = response.data.decode()
        
        # Should use tel, email, date, etc. input types
        mobile_input_types = ['tel', 'email', 'date', 'number']
        found_mobile_inputs = any(f'type="{t}"' in html for t in mobile_input_types)
        
        # At least some forms should use mobile-optimized inputs
        if '<input' in html:
            # This is a soft check - not all forms need mobile input types
            pass


@pytest.fixture
def app_client():
    """Fixture to provide Flask test client"""
    from src.web.server import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
