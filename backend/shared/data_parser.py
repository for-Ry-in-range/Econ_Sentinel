"""
Shared utilities for parsing raw JSON data from S3
"""

import json
from typing import Dict, List, Optional, Any


class DataParser:
    """Parses the data from FRED API and port congestion sources."""
    
    @staticmethod
    def parse_fred_data(data: Dict[str, Any]):
        """
        Parse FRED API data.
        Daily files hold one observation; backfill files hold a whole history.
        Args:
            data: Raw FRED JSON
        Returns:
            List of parsed data dicts with metric, value, timestamp, oldest first
        """
        try:
            # FRED format with series data
            if 'data' in data and isinstance(data['data'], list):
                metric = data.get('metric_name') or data.get('series_id', 'unknown')
                results = []
                for observation in data['data']:
                    # Skip bad points one at a time, so one doesn't sink a whole backfill
                    try:
                        results.append({
                            'metric': metric,
                            'value': float(observation['value']),
                            'timestamp': observation.get('date', ''),
                            'source': 'fred'
                        })
                    except (ValueError, KeyError, TypeError) as e:
                        print(f"Skipping bad FRED observation {observation}: {e}")
                # Oldest first, since each score depends on the ones before it
                results.sort(key=lambda r: r['timestamp'])
                return results

            # FRED simplified format
            if 'value' in data and 'metric' in data:
                return [{
                    'metric': data['metric'],
                    'value': float(data['value']),
                    'timestamp': data.get('date', data.get('timestamp', '')),
                    'source': 'fred'
                }]

            return []

        except (ValueError, KeyError, TypeError) as e:
            print(f"Error parsing FRED data: {e}")
            return []
    
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
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Error parsing S3 object: {e}")
            return None
    
    @staticmethod
    def normalize_timestamp(timestamp: str) -> str:
        """
        Switch timestamp to ISO 8601 format.
        Args:
            timestamp: various time formats
        Returns:
            ISO 8601 timestamp string
        """

        # If already in ISO format
        if 'T' in timestamp and ('Z' in timestamp or '+' in timestamp or '-' in timestamp[-6:]):
            return timestamp
        
        # If only date then add time
        if len(timestamp) == 10 and timestamp.count('-') == 2:
            return f"{timestamp}T00:00:00Z"
        
        # Try to reformat
        try:
            from datetime import datetime
            # Try a couple common formats
            for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                try:
                    dt = datetime.strptime(timestamp, fmt)
                    return dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
                except ValueError:
                    continue
        except Exception:
            pass
        
        # Return unchanged if it couldn't be parsed
        return timestamp
