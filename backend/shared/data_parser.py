"""
Shared utilities for parsing raw data from the ingestion layer.
"""

import json
from typing import Dict, List, Optional, Any


class DataParser:
    """Parses the data from FRED API and port congestion sources."""
    
    @staticmethod
    def parse_fred_data(data: Dict[str, Any]):
        """
        Parse FRED API data.
        Args:
            data: Raw FRED JSON
        Returns:
            Parsed data dict with metric, value, timestamp, or None if invalid
        """
        try:
            # FRED format with series data
            if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                latest = data['data'][-1]
                return {
                    'metric': data.get('series_id', 'inflation_rate_cpi'),
                    'value': float(latest.get('value', 0)),
                    'timestamp': latest.get('date', ''),
                    'source': 'fred'
                }
            # FRED simplified format
            if 'value' in data and 'metric' in data:
                return {
                    'metric': data['metric'],
                    'value': float(data['value']),
                    'timestamp': data.get('date', data.get('timestamp', '')),
                    'source': 'fred'
                }

            return None

        except (ValueError, KeyError, TypeError) as e:
            print(f"Error parsing FRED data: {e}")
            return None
    
    @staticmethod
    def parse_port_congestion_data(data: Dict[str, Any]):
        """
        Parse port congestion data.        
        Args:
            data: Raw port congestion JSON
        Returns:
            List of parsed data with metric, value, timestamp
        """
        results = []
        try:
            # Multiple ports format
            if 'ports' in data and isinstance(data['ports'], list):
                for port_data in data['ports']:
                    port_name = port_data.get('port', 'unknown')
                    metric = f"port_congestion_{port_name}"
                    results.append({
                        'metric': metric,
                        'value': float(port_data.get('congestion_count', port_data.get('value', 0))),
                        'timestamp': port_data.get('date', port_data.get('timestamp', '')),
                        'source': 'port_congestion',
                        'port': port_name
                    })
            
            # Single port format
            elif 'port' in data or 'congestion_count' in data:
                port_name = data.get('port', 'unknown')
                metric = f"port_congestion_{port_name}"
                results.append({
                    'metric': metric,
                    'value': float(data.get('congestion_count', data.get('value', 0))),
                    'timestamp': data.get('date', data.get('timestamp', '')),
                    'source': 'port_congestion',
                    'port': port_name
                })
            
            # Freight cost index format
            elif 'freight_cost_index' in data or 'freight_index' in data:
                value = data.get('freight_cost_index') or data.get('freight_index')
                results.append({
                    'metric': 'freight_cost_index',
                    'value': float(value),
                    'timestamp': data.get('date', data.get('timestamp', '')),
                    'source': 'freight'
                })
            
            return results

        except (ValueError, KeyError, TypeError) as e:
            print(f"Error parsing port congestion data: {e}")
            return []
    
    @staticmethod
    def parse_s3_object(data: bytes, content_type: str = 'application/json'):
        """
        Parse data from S3 object.
        Args:
            data: Bytes from S3 object
            content_type: Type of the data
        Returns:
            Parsed JSON dict or None if invalid
        """
        try:
            if content_type == 'application/json' or content_type.endswith('json'):
                text = data.decode('utf-8')  # converts bytes into string
                return json.loads(text)
            else:
                print("Unsupported content type")
                return None
        