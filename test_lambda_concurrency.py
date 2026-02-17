import concurrent.futures
import requests
import logging
import time
import random
import boto3
from bs4 import BeautifulSoup  # pip install beautifulsoup4
from botocore.exceptions import ClientError
import webbrowser
import subprocess
import tempfile
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LAMBDA_URL = "https://5xygt5eujjlo2p7umj2arir2du0ztioi.lambda-url.eu-west-3.on.aws"

def cleanup_test_environment():
    """Clean up the test environment by stopping instances and cleaning DynamoDB"""
    logger.info("Starting cleanup of test environment...")
    
    # Initialize AWS clients
    region = 'eu-west-3'
    ec2_client = boto3.client('ec2', region_name=region)
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table('instance-assignments-testus-patronus')
    
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

def open_incognito_browser(url: str, user_id: str):
    """Open URL in a new incognito/private browser window to avoid shared cookies"""
    import platform
    import subprocess
    
    system = platform.system().lower()
    
    try:
        if system == "darwin":  # macOS
            # Try Chrome first (most reliable for automation)
            try:
                subprocess.Popen([
                    "open", "-na", "Google Chrome", "--args", 
                    "--incognito", 
                    "--new-window",
                    f"--user-data-dir=/tmp/chrome_test_{user_id}",
                    url
                ])
                logger.info(f"Opened Chrome incognito window for {user_id}")
                return
            except Exception as e:
                logger.debug(f"Chrome failed for {user_id}: {str(e)}")
                pass
            
            # Try Microsoft Edge second (InPrivate mode)
            try:
                subprocess.Popen([
                    "open", "-na", "Microsoft Edge", "--args", 
                    "--inprivate", 
                    "--new-window",
                    f"--user-data-dir=/tmp/edge_test_{user_id}",
                    url
                ])
                logger.info(f"Opened Edge InPrivate window for {user_id}")
                return
            except Exception as e:
                logger.debug(f"Edge failed for {user_id}: {str(e)}")
                pass
            
            # Safari as fallback (though it has URL loading issues)
            try:
                subprocess.Popen([
                    "open", "-na", "Safari", "--args", 
                    "--private",
                    url
                ])
                logger.info(f"Opened Safari private window for {user_id} (fallback)")
                return
            except Exception as e:
                logger.debug(f"Safari failed for {user_id}: {str(e)}")
                pass
                
        elif system == "linux":
            # Try Edge first on Linux
            try:
                subprocess.Popen([
                    "microsoft-edge", 
                    "--inprivate", 
                    "--new-window",
                    f"--user-data-dir=/tmp/edge_test_{user_id}",
                    url
                ])
                logger.info(f"Opened Edge InPrivate window for {user_id}")
                return
            except:
                pass
            
            # Try Chrome/Chromium as fallback
            for browser in ["google-chrome", "chromium-browser", "chromium"]:
                try:
                    subprocess.Popen([
                        browser, 
                        "--incognito", 
                        "--new-window",
                        f"--user-data-dir=/tmp/chrome_test_{user_id}",
                        url
                    ])
                    logger.info(f"Opened {browser} incognito window for {user_id} (fallback)")
                    return
                except:
                    continue
                    
        elif system == "windows":
            # Try Edge first on Windows
            try:
                subprocess.Popen([
                    "msedge", 
                    "--inprivate", 
                    "--new-window",
                    f"--user-data-dir=C:\\temp\\edge_test_{user_id}",
                    url
                ])
                logger.info(f"Opened Edge InPrivate window for {user_id}")
                return
            except:
                pass
            
            # Try Chrome as fallback
            try:
                subprocess.Popen([
                    "chrome", 
                    "--incognito", 
                    "--new-window",
                    f"--user-data-dir=C:\\temp\\chrome_test_{user_id}",
                    url
                ])
                logger.info(f"Opened Chrome incognito window for {user_id} (fallback)")
                return
            except:
                pass
        
        # Fallback to default browser (will share cookies but better than nothing)
        webbrowser.open(url)
        logger.info(f"Opened default browser for {user_id} (cookies may be shared)")
        
    except Exception as e:
        logger.error(f"Error opening browser for {user_id}: {str(e)}")
        # Final fallback
        webbrowser.open(url)

def simulate_user_get_request(user_id: str, use_browser=False) -> dict:
    url = LAMBDA_URL + "?r=" + str(random.randint(1000, 9999))
    
    # Always make HTTP request to validate the response
    try:
        response = requests.get(url, timeout=30)
        logger.info(f"User {user_id} got status {response.status_code}")
        content = response.text

        # Parse HTML and check for expected content
        soup = BeautifulSoup(content, "html.parser")
        main_title = soup.find("div", class_="main-title")
        user_heading = soup.find("h2")
        warning = soup.find("div", class_="warning")
        
        # Extract user name from the welcome message
        extracted_user = None
        if user_heading:
            heading_text = user_heading.text.strip()
            if "This is your user:" in heading_text:
                extracted_user = heading_text.split("This is your user:")[-1].strip()
        
        # Extract Dify IP from the dify-link element
        dify_ip = None
        dify_link_element = soup.find("a", id="dify-link")
        if dify_link_element:
            dify_link = dify_link_element.get("href")
            if dify_link and dify_link.startswith("http://"):
                dify_ip = dify_link.replace("http://", "").strip()

        # Validation checks
        checks = {
            "main_title": main_title.text.strip() if main_title else None,
            "user_heading": user_heading.text.strip() if user_heading else None,
            "warning": warning.text.strip() if warning else None,
            "extracted_user": extracted_user,
            "dify_ip": dify_ip,
            "has_dify_link": dify_link_element is not None,
            "response_length": len(content)
        }

        # Success criteria
        success = (
            response.status_code == 200 and 
            main_title is not None and 
            user_heading is not None and
            extracted_user is not None
        )
        
        result = {
            "user_id": user_id,
            "status_code": response.status_code,
            "checks": checks,
            "ok": success,
            "url": url
        }
        
    except Exception as e:
        logger.error(f"HTTP request failed for {user_id}: {str(e)}")
        result = {
            "user_id": user_id,
            "status": "http_error",
            "error": str(e),
            "ok": False,
            "url": url
        }
    
    # Also open browser window if requested (with safety check)
    if use_browser:
        # Safety check: warn if trying to open too many browsers
        if hasattr(simulate_user_get_request, '_browser_count'):
            simulate_user_get_request._browser_count += 1
        else:
            simulate_user_get_request._browser_count = 1
            
        if simulate_user_get_request._browser_count <= 10:
            open_incognito_browser(url, user_id)
            result["browser_opened"] = True
        else:
            logger.warning(f"Skipping browser for {user_id} - too many browsers already open (safety limit: 10)")
            result["browser_opened"] = False
            result["browser_skipped"] = True
        
    return result

def run_lambda_concurrency_test(num_users: int = 20, max_workers: int = 10):
    logger.info(f"Starting Lambda concurrency test with {num_users} users")
    start_time = time.time()
    results = []
    
    # Add a small delay between browser windows to make them more visible
    def delayed_simulate(user_id, delay):
        time.sleep(delay * 0.1)  # 0.1 second delay between each browser
        return simulate_user_get_request(user_id)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_user = {
            executor.submit(delayed_simulate, f"user-{i}", i): f"user-{i}"
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
    import sys
    
    # Check for browser mode flag
    use_browsers = "--browsers" in sys.argv or "-b" in sys.argv
    num_users = 110
    
    # Check for user count
    for i, arg in enumerate(sys.argv):
        if arg in ["-u", "--users"] and i + 1 < len(sys.argv):
            try:
                num_users = int(sys.argv[i + 1])
            except ValueError:
                print("Invalid user count")
                sys.exit(1)
    
    # Safety check for browsers
    if use_browsers and num_users > 10:
        print(f"⚠️  WARNING: You're trying to open {num_users} browser windows!")
        print("This might overwhelm your system and cause popup spam.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Test cancelled. Run without --browsers flag for large tests.")
            sys.exit(0)
    
    try:
        # Optional cleanup (disabled by default to avoid affecting real users)
        # Uncomment the next line only if you want to clean up ALL conference users
        # cleanup_test_environment()
        
        print(f"🚀 Running test with {num_users} users")
        print(f"🌐 Browser mode: {'ON' if use_browsers else 'OFF'}")
        if use_browsers:
            print("💡 Tip: Use 'python3 test_lambda_concurrency.py' (without --browsers) for large tests")
        
        # Reset browser counter
        if hasattr(simulate_user_get_request, '_browser_count'):
            delattr(simulate_user_get_request, '_browser_count')
        
        # Run the test with browser setting applied
        # We'll modify the default parameter of the original function
        original_default = simulate_user_get_request.__defaults__
        simulate_user_get_request.__defaults__ = (use_browsers,)
        
        results = run_lambda_concurrency_test(num_users=num_users, max_workers=min(20, num_users))
        
        # Analyze results
        successful = [r for r in results if r.get('ok', False)]
        failed = [r for r in results if not r.get('ok', False)]
        
        # Browser window analysis
        browsers_opened = [r for r in results if r.get('browser_opened', False)]
        browsers_failed = [r for r in results if not r.get('browser_opened', False)]
        
        # Instance assignment analysis
        with_instances = [r for r in results if r.get('checks', {}).get('dify_ip') is not None]
        without_instances = [r for r in results if r.get('checks', {}).get('dify_ip') is None and r.get('ok', False)]
        
        total_users = num_users
        print(f"\n📊 Test Results Summary:")
        print(f"   🌐 Browser Windows Opened: {len(browsers_opened)}/{total_users}")
        print(f"   ❌ Browser Windows Failed: {len(browsers_failed)}/{total_users}")
        print(f"   🏠 Users with EC2 Instances: {len(with_instances)}/{total_users}")
        print(f"   ⚠️  Users without EC2 Instances: {len(without_instances)}/{total_users}")
        print(f"   ✅ Overall Successful Requests: {len(successful)}/{total_users}")
        print(f"   ❌ Failed Requests: {len(failed)}/{total_users}")
        print(f"   📈 Success Rate: {len(successful)/total_users*100:.1f}%")
        
        # Expected vs Actual Analysis
        print(f"\n🎯 Expected vs Actual:")
        print(f"   Expected with instances: 5 (if instances available)")
        print(f"   Expected without instances: 0 (if instances available)")
        print(f"   Actual with instances: {len(with_instances)}")
        print(f"   Actual without instances: {len(without_instances)}")
        
        if len(with_instances) > 0:
            print(f"   ✅ Some instances assigned - pool has availability.")
        else:
            print(f"   ⚠️  No instances assigned - pool may be exhausted or unavailable.")
        
        print(f"\n📋 Sample Results (first 5 users):")
        for i, result in enumerate(results[:5]):
            checks = result.get('checks', {})
            user_id = result.get('user_id', 'unknown')
            extracted_user = checks.get('extracted_user', 'N/A')
            dify_ip = checks.get('dify_ip')
            browser_status = "🌐" if result.get('browser_opened', False) else "❌"
            
            if dify_ip:
                print(f"   ✅ {browser_status} {user_id}: {extracted_user} -> Instance: {dify_ip}")
            else:
                print(f"   ⚠️  {browser_status} {user_id}: {extracted_user} -> No instance assigned")
        
        if len(results) > 5:
            print(f"   ... and {len(results) - 5} more users")
            
        # Show some users with instances if any
        users_with_instances = [r for r in results if r.get('checks', {}).get('dify_ip') is not None]
        if users_with_instances:
            print(f"\n🏠 Sample Users with EC2 Instances:")
            for i, result in enumerate(users_with_instances[:3]):
                checks = result.get('checks', {})
                user_id = result.get('user_id', 'unknown')
                extracted_user = checks.get('extracted_user', 'N/A')
                dify_ip = checks.get('dify_ip')
                print(f"   ✅ {user_id}: {extracted_user} -> {dify_ip}")
            if len(users_with_instances) > 3:
                print(f"   ... and {len(users_with_instances) - 3} more users with instances")
            
        # Restore original function defaults
        simulate_user_get_request.__defaults__ = original_default
        
        # Optional cleanup after test (disabled by default)
        # cleanup_test_environment()
        
    except Exception as e:
        logger.error(f"Error during test execution: {str(e)}")
        # Optional cleanup on error (disabled by default)
        # cleanup_test_environment() 