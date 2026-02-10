import json
import boto3
import os
import base64
import gzip
from datetime import datetime

logs_client = boto3.client('logs')
log_group_name = os.environ['LOG_GROUP_NAME']

def handler(event, context):
    """
    Process CloudFront real-time logs from Kinesis stream and send to CloudWatch Logs.
    
    CloudFront real-time logs are sent as JSON records in Kinesis.
    Each Kinesis record contains a base64-encoded JSON string (not gzip-compressed).
    """
    log_stream_name = f"cloudfront-{datetime.utcnow().strftime('%Y-%m-%d-%H-%M')}"
    
    log_events = []
    
    for record in event['Records']:
        try:
            # Kinesis data is base64 encoded
            payload = base64.b64decode(record['kinesis']['data'])
            
            # Try to parse as JSON directly (CloudFront real-time logs are JSON, not gzip)
            try:
                log_entry = json.loads(payload.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If direct JSON parsing fails, try gzip decompression (fallback)
                try:
                    decompressed = gzip.decompress(payload)
                    log_entry = json.loads(decompressed.decode('utf-8'))
                except Exception:
                    # If both fail, treat as plain text
                    log_entry = {'raw_message': payload.decode('utf-8', errors='ignore')}
            
            # Extract timestamp from log entry (CloudFront uses Unix timestamp in milliseconds)
            timestamp = log_entry.get('timestamp')
            if timestamp:
                # Ensure timestamp is in milliseconds
                if isinstance(timestamp, str):
                    try:
                        timestamp = int(float(timestamp) * 1000)
                    except ValueError:
                        timestamp = int(datetime.utcnow().timestamp() * 1000)
                elif isinstance(timestamp, (int, float)):
                    # If timestamp is in seconds, convert to milliseconds
                    if timestamp < 1e12:  # Less than year 2001 in milliseconds
                        timestamp = int(timestamp * 1000)
                    else:
                        timestamp = int(timestamp)
                else:
                    timestamp = int(datetime.utcnow().timestamp() * 1000)
            else:
                timestamp = int(datetime.utcnow().timestamp() * 1000)
            
            # Convert to CloudWatch Logs format
            log_events.append({
                'timestamp': timestamp,
                'message': json.dumps(log_entry)
            })
            
        except Exception as e:
            print(f"Error processing record: {str(e)}")
            # Log the error as a CloudWatch Log event
            log_events.append({
                'timestamp': int(datetime.utcnow().timestamp() * 1000),
                'message': json.dumps({
                    'error': str(e),
                    'record_id': record.get('eventID', 'unknown')
                })
            })
    
    # Send logs to CloudWatch Logs in batches
    if log_events:
        try:
            # Ensure log stream exists
            try:
                logs_client.create_log_stream(
                    logGroupName=log_group_name,
                    logStreamName=log_stream_name
                )
            except logs_client.exceptions.ResourceAlreadyExistsException:
                pass  # Log stream already exists
            
            # Put log events (max 10,000 events per request)
            batch_size = 10000
            for i in range(0, len(log_events), batch_size):
                batch = log_events[i:i + batch_size]
                logs_client.put_log_events(
                    logGroupName=log_group_name,
                    logStreamName=log_stream_name,
                    logEvents=batch
                )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'processed': len(log_events),
                    'log_stream': log_stream_name
                })
            }
        except Exception as e:
            print(f"Error sending logs to CloudWatch: {str(e)}")
            raise
    
    return {
        'statusCode': 200,
        'body': json.dumps({'processed': 0})
    }
