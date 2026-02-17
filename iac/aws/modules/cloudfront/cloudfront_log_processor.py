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
    Each Kinesis record contains a base64-encoded, gzip-compressed JSON string.
    """
    log_stream_name = f"cloudfront-{datetime.utcnow().strftime('%Y-%m-%d-%H-%M')}"
    
    log_events = []
    
    for record in event['Records']:
        try:
            # Kinesis data is base64 encoded
            payload = base64.b64decode(record['kinesis']['data'])
            
            # CloudFront logs are gzip compressed
            decompressed = gzip.decompress(payload)
            
            # Parse JSON log entry
            log_entry = json.loads(decompressed.decode('utf-8'))
            
            # Convert to CloudWatch Logs format
            log_events.append({
                'timestamp': int(log_entry.get('timestamp', datetime.utcnow().timestamp() * 1000)),
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
