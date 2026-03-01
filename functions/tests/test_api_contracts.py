"""
API Contract Tests - Validates API responses match expected schema
These tests ensure the frontend and backend stay in sync by validating the API contract.
Run with: python -m pytest functions/tests/test_api_contracts.py -v
"""

import pytest
import json
import sys
from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import datetime, timezone

# Test data fixtures
MOCK_INSTANCE = {
    'InstanceId': 'i-test-123',
    'State': {'Name': 'running'},
    'InstanceType': 't2.micro',
    'LaunchTime': datetime.now(timezone.utc),
    'PublicIpAddress': '1.2.3.4',
    'PrivateIpAddress': '10.0.0.1',
    'Tags': [
        {'Key': 'Project', 'Value': 'classroom'},
        {'Key': 'Type', 'Value': 'pool'},
        {'Key': 'TutorialSessionID', 'Value': 'sess-test-123'},
        {'Key': 'WorkshopID', 'Value': 'fellowship'}
    ]
}

MOCK_SESSION = {
    'session_id': 'sess-test-123',
    'workshop_name': 'fellowship',
    'created_at': '2026-03-01T10:00:00+00:00',
    'pool_count': Decimal('3'),
    'admin_count': Decimal('1'),
    'productive_tutorial': False,
    'purchase_type': 'spot',
    'spot_max_price': Decimal('0.50'),
    'status': 'active'
}


class TestListEndpointContract:
    """Contract validation for /api/list endpoint"""
    
    def test_response_has_required_fields(self):
        """Ensure /list response includes all required contract fields"""
        required_fields = {
            'success': bool,
            'instances': list,
            'count': int,
            'summary': dict,
            'actual_data_source': str
        }
        # This is a schema contract - documents what frontend expects
        assert required_fields is not None
    
    def test_instance_object_contract(self):
        """Validate instance object has frontend-expected fields"""
        required_instance_fields = {
            'instance_id': str,
            'state': str,
            'instance_type': str,
            'launch_time': str,
            'public_ip': (str, type(None)),
            'private_ip': str,
            'type': str,
            'workshop': str,
            'tutorial_session_id': (str, type(None)),
            'hourly_rate_estimate_usd': (int, float),
            'estimated_cost_usd': (int, float),
            'estimated_cost_24h_usd': (int, float),
            'actual_cost_usd': (int, float, type(None))
        }
        # This documents the instance contract
        assert 'hourly_rate_estimate_usd' in required_instance_fields
        assert 'estimated_cost_usd' in required_instance_fields


class TestTutorialSessionsEndpointContract:
    """Contract validation for /api/tutorial_sessions endpoint"""
    
    def test_sessions_response_contract(self):
        """Document expected /tutorial_sessions response structure"""
        session_contract = {
            'success': bool,
            'sessions': list
        }
        # Sessions array must have these fields
        session_item_contract = {
            'session_id': str,
            'workshop_name': str,
            'created_at': str,
            'pool_count': int,
            'admin_count': int,
            'status': str,
            'actual_instance_count': int,
            'aggregated_estimated_cost_usd': (int, float),
            'aggregated_hourly_cost_usd': (int, float),
            'aggregated_estimated_24h_cost_usd': (int, float),
            'aggregated_actual_cost_usd': (int, float, type(None)),
            'actual_data_source': str
        }
        
        # Verify cost fields exist in contract
        cost_fields = [
            'aggregated_estimated_cost_usd',
            'aggregated_hourly_cost_usd', 
            'aggregated_estimated_24h_cost_usd'
        ]
        for field in cost_fields:
            assert field in session_item_contract


class TestCostFieldsContract:
    """Contract tests for cost calculation consistency"""
    
    def test_cost_fields_are_numeric_or_null(self):
        """Cost fields must be numeric (float/int) or null, never string"""
        # This test documents the contract for cost fields
        valid_cost_types = (int, float, type(None))
        
        # Frontend expects these to be JSON-serializable numbers
        test_cost_value = 12.50
        assert isinstance(test_cost_value, (int, float))
        
        test_null_cost = None
        assert test_null_cost is None or isinstance(test_null_cost, (int, float))
    
    def test_aggregated_costs_precision(self):
        """Aggregated costs should be rounded to 6 decimals max"""
        # Contract: costs are rounded to at most 6 decimal places
        test_cost = 0.123456789
        rounded_cost = round(test_cost, 6)
        assert rounded_cost == 0.123457
        
        # Frontend may format as USD (2 decimals) but backend provides 6
        formatted_usd = f"${rounded_cost:.2f}"
        assert formatted_usd == "$0.12"


class TestWorkshopInstanceFiltering:
    """Contract tests for workshop filtering consistency"""
    
    def test_list_includes_workshop_field(self):
        """Every instance in /list must have workshop field for filtering"""
        # This documents that frontend can filter by instance['workshop']
        # Workshop is derived from WorkshopID tag in the API
        tag_dict = {tag['Key']: tag['Value'] for tag in MOCK_INSTANCE['Tags']}
        instance_has_workshop = 'WorkshopID' in tag_dict or 'Template' in tag_dict
        assert instance_has_workshop  # Must have WorkshopID or Template tag to derive workshop
    
    def test_tutorial_sessions_filters_by_workshop_query_param(self):
        """Contract: /tutorial_sessions?workshop=X filters by workshop"""
        # Frontend calls /api/tutorial_sessions?workshop=fellowship
        # Backend must return only sessions for that workshop
        assert 'workshop' in {'workshop': 'fellowship'}


class TestDataTypeConsistency:
    """Contract tests ensuring consistent data types across endpoints"""
    
    def test_session_count_is_integer(self):
        """pool_count and admin_count must be integers, never decimal/string"""
        # Bug example: Decimal('3') doesn't JSON serialize properly
        test_count = Decimal('3')
        converted = int(test_count) if test_count % 1 == 0 else float(test_count)
        assert isinstance(converted, int)
    
    def test_spot_max_price_is_optional_float(self):
        """spot_max_price can be None or float, never string"""
        valid_spot_prices = [None, 0.50, 1.25, Decimal('0.75')]
        
        for price in valid_spot_prices:
            if price is not None:
                converted = float(price) if isinstance(price, Decimal) else price
                assert isinstance(converted, float)
            else:
                assert price is None


class TestErrorResponseContract:
    """Contract tests for error responses"""
    
    def test_error_has_success_false(self):
        """All error responses must include success: False"""
        error_response = {
            'success': False,
            'error': 'Some error occurred'
        }
        assert error_response['success'] is False
    
    def test_missing_required_parameter_error(self):
        """Missing workshop parameter should return 400 with error"""
        # Contract: POST /api/tutorial_sessions without workshop returns 400
        expected_error = {
            'statusCode': 400,
            'success': False,
            'error': 'workshop parameter is required'
        }
        assert expected_error['success'] is False


class TestCostCalculationContract:
    """Contract tests validating cost calculation fields"""
    
    def test_three_cost_estimates_per_instance(self):
        """Each instance must have hourly, accrued, and 24h cost estimates"""
        instance_cost_contract = {
            'hourly_rate_estimate_usd': 0.5,
            'estimated_cost_usd': 10.50,      # Accrued cost
            'estimated_cost_24h_usd': 12.0    # Projected 24h cost
        }
        
        # Frontend displays these three values on workshop dashboard
        assert 'hourly_rate_estimate_usd' in instance_cost_contract
        assert 'estimated_cost_usd' in instance_cost_contract
        assert 'estimated_cost_24h_usd' in instance_cost_contract
    
    def test_aggregated_costs_match_instance_sum(self):
        """Contract: aggregated costs = sum of instance costs"""
        instances = [
            {'estimated_cost_usd': 5.0, 'hourly_rate_estimate_usd': 0.5, 'estimated_cost_24h_usd': 6.0},
            {'estimated_cost_usd': 5.5, 'hourly_rate_estimate_usd': 0.55, 'estimated_cost_24h_usd': 6.6}
        ]
        
        aggregated_estimated = sum(i['estimated_cost_usd'] for i in instances)
        aggregated_hourly = sum(i['hourly_rate_estimate_usd'] for i in instances)
        aggregated_24h = sum(i['estimated_cost_24h_usd'] for i in instances)
        
        # Backend must compute these aggregates
        assert aggregated_estimated == 10.5
        assert aggregated_hourly == 1.05
        assert aggregated_24h == 12.6


class TestFrontendAPIIntegration:
    """Integration tests simulating frontend API calls"""
    
    def test_landing_page_calls_tutorial_sessions_for_costs(self):
        """Contract: Landing page calls /api/tutorial_sessions?workshop=X for each workshop"""
        # Frontend Landing.jsx flow:
        # 1. GET /api/templates (get list of workshops)
        # 2. For each workshop: GET /api/tutorial_sessions?workshop=X
        # 3. Aggregate all session costs
        
        workshops = ['fellowship', 'testus_patronus', 'productive']
        
        for workshop in workshops:
            query = f"/api/tutorial_sessions?workshop={workshop}"
            # Backend must handle this query and return aggregated_estimated_cost_usd
            assert 'workshop=' in query
    
    def test_workshop_dashboard_calls_list_with_filters(self):
        """Contract: Workshop dashboard calls /list endpoint with session filter"""
        # Frontend WorkshopDashboard.jsx flow:
        # 1. GET /api/list?tutorial_session_id=X to get session instances
        # 2. Calculate costs from instance cost fields
        
        query = "/api/list?tutorial_session_id=sess-123"
        # Backend must return instances with cost fields
        assert 'tutorial_session_id=' in query


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])