import concurrent.futures
import requests
import logging
import time
import random
import boto3
from bs4 import BeautifulSoup  # pip install beautifulsoup4
from botocore.exceptions import ClientError
import webbrowser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LAMBDA_URL = "https://tgilw5l4loeq2dkrtbsta27csm0entsv.lambda-url.eu-west-3.on.aws/"

def cleanup_test_environment():
    """Clean up the test environment by stopping instances and cleaning DynamoDB"""
    logger.info("Starting cleanup of test environment...")
    
    # Initialize AWS clients
    ec2_client = boto3.client('ec2', region_name='eu-west-3')
    dynamodb = boto3.resource('dynamodb', region_name='eu-west-3')
    table = dynamodb.Table('instance-assignments-dev')
    
    try:
        # 1. Find all instances with conference-user assignments
        filters = [
            {'Name': 'tag:Project', 'Values': ['classroom']},
            {'Name': 'tag:Student', 'Values': ['conference-user-*']}
        ]
        response = ec2_client.describe_instances(Filters=filters)
        
        instance_ids = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
        
        if instance_ids:
            logger.info(f"Found {len(instance_ids)} instances to clean up")
            
            # 2. Stop the instances
            try:
                ec2_client.stop_instances(InstanceIds=instance_ids)
                logger.info(f"Stopping instances: {instance_ids}")
                
                # Wait for instances to stop
                waiter = ec2_client.get_waiter('instance_stopped')
                waiter.wait(InstanceIds=instance_ids, WaiterConfig={'Delay': 5, 'MaxAttempts': 12})
                logger.info("All instances stopped successfully")
                
                # 3. Reset instance tags
                for instance_id in instance_ids:
                    ec2_client.create_tags(
                        Resources=[instance_id],
                        Tags=[
                            {'Key': 'Status', 'Value': 'available'},
                            {'Key': 'Student', 'Value': ''}
                        ]
                    )
                logger.info("Reset instance tags to available")
                
            except ClientError as e:
                logger.error(f"Error stopping instances: {str(e)}")
        
        # 4. Clean up DynamoDB records
        try:
            # Scan for conference user assignments
            response = table.scan(
                FilterExpression='begins_with(student_name, :prefix)',
                ExpressionAttributeValues={':prefix': 'conference-user-'}
            )
            
            # Delete all matching records
            with table.batch_writer() as batch:
                for item in response.get('Items', []):
                    batch.delete_item(
                        Key={
                            'instance_id': item['instance_id']
                        }
                    )
            logger.info(f"Cleaned up {len(response.get('Items', []))} DynamoDB records")
            
        except ClientError as e:
            logger.error(f"Error cleaning up DynamoDB: {str(e)}")
            
        logger.info("Cleanup completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        return False

def simulate_user_get_request(user_id: str, use_browser=True) -> dict:
    url = LAMBDA_URL + "?r=" + str(random.randint(1000, 9999))
    if use_browser:
        webbrowser.open(url)
        return {"user_id": user_id, "status": "browser_opened", "url": url}
    else:
        response = requests.get(url, timeout=30)
        logger.info(f"User {user_id} got status {response.status_code}")
        content = response.text

        # Parse HTML and check for expected content
        soup = BeautifulSoup(content, "html.parser")
        main_title = soup.find("div", class_="main-title")
        user_heading = soup.find("h2")
        warning = soup.find("div", class_="warning")

        # Example checks
        checks = {
            "main_title": main_title.text.strip() if main_title else None,
            "user_heading": user_heading.text.strip() if user_heading else None,
            "warning": warning.text.strip() if warning else None,
        }

        return {
            "user_id": user_id,
            "status_code": response.status_code,
            "checks": checks,
            "ok": response.status_code == 200 and main_title is not None and user_heading is not None
        }

def run_lambda_concurrency_test(num_users: int = 20, max_workers: int = 10):
    logger.info(f"Starting Lambda concurrency test with {num_users} users")
    start_time = time.time()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_user = {
            executor.submit(simulate_user_get_request, f"user-{i}"): f"user-{i}"
            for i in range(num_users)
        }
        for future in concurrent.futures.as_completed(future_to_user):
            user_id = future_to_user[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing user {user_id}: {str(e)}")
                results.append({'user_id': user_id, 'status': 'error', 'error': str(e)})
    logger.info(f"\nTest completed in {time.time() - start_time:.2f} seconds")
    return results

if __name__ == "__main__":
    try:
        # First, clean up any existing test environment
        cleanup_test_environment()
        
        # Run the concurrency test
        results = run_lambda_concurrency_test(num_users=4, max_workers=4)
        print("\nDetailed Results:")
        for result in results:
            print(result)
            
        # Clean up after the test
        cleanup_test_environment()
        
    except Exception as e:
        logger.error(f"Error during test execution: {str(e)}")
        # Ensure cleanup happens even if test fails
        cleanup_test_environment() 