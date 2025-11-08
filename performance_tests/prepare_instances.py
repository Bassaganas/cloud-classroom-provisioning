#!/usr/bin/env python3
"""
Helper script to prepare instance pool for k6 tests using the Instance Manager API

This script uses the Instance Manager Lambda API to create a pool of instances
that will be used by the k6 test scenarios.

Usage:
    python3 prepare_instances.py --url <INSTANCE_MANAGER_URL> --count 20 --type pool
    python3 prepare_instances.py --url <INSTANCE_MANAGER_URL> --count 100 --type pool --password <PASSWORD>
"""

import argparse
import requests
import json
import sys
import time
from typing import Dict, List, Optional

def authenticate(instance_manager_url: str, password: str) -> Optional[str]:
    """Authenticate with the instance manager and return auth token/cookie"""
    try:
        response = requests.post(
            f"{instance_manager_url}/login",
            json={"password": password},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Authentication successful")
            # Extract auth cookie if present
            cookies = response.cookies
            if cookies:
                return "; ".join([f"{k}={v}" for k, v in cookies.items()])
            return None
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        return None

def create_instances(
    instance_manager_url: str,
    count: int,
    instance_type: str = "pool",
    auth_cookie: Optional[str] = None
) -> bool:
    """Create instances using the instance manager API"""
    print(f"\n📦 Creating {count} {instance_type} instances...")
    
    # For large batches, warn about potential timeout
    if count > 50:
        print(f"⚠️  Large batch ({count} instances) - Lambda may timeout, but instances will still be created")
        print("   We'll verify instances after the request completes or times out")
    
    payload = {
        "count": count,
        "type": instance_type,
    }
    
    headers = {"Content-Type": "application/json"}
    if auth_cookie:
        headers["Cookie"] = auth_cookie
    
    try:
        response = requests.post(
            f"{instance_manager_url}/create",
            json=payload,
            headers=headers,
            timeout=600  # 10 minutes for large instance creation
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ Successfully created {count} {instance_type} instances")
                if "instances" in data:
                    instance_ids = [i.get("instance_id") for i in data["instances"]]
                    print(f"   Instance IDs: {', '.join(instance_ids[:5])}")
                    if len(instance_ids) > 5:
                        print(f"   ... and {len(instance_ids) - 5} more")
                return True
            else:
                print(f"❌ Create request returned success=false: {data.get('error', 'Unknown error')}")
                return False
        elif response.status_code == 504:
            # Gateway timeout - Lambda timed out but instances may still be creating
            print(f"⚠️  Gateway timeout (504) - Lambda timed out, but instances may still be creating")
            print("   EC2 instances are being created asynchronously in the background...")
            
            # Calculate wait time based on instance count
            # EC2 instances typically take 1-2 minutes to launch
            # For large batches, we need to wait longer
            if count > 50:
                # Large batch: wait longer and check progressively
                wait_times = [60, 120, 180]  # Check after 1, 2, 3 minutes
                print(f"   Large batch detected ({count} instances) - will check progressively")
            else:
                # Smaller batch: shorter wait times
                wait_times = [30, 60, 90]  # Check after 30s, 1m, 1.5m
            
            headers_verify = {}
            if auth_cookie:
                headers_verify["Cookie"] = auth_cookie
            
            # Progressive checking with increasing wait times
            for wait_time in wait_times:
                print(f"   ⏳ Waiting {wait_time} seconds before checking...")
                time.sleep(wait_time)
                
                try:
                    verify_response = requests.get(
                        f"{instance_manager_url}/list",
                        headers=headers_verify,
                        timeout=30
                    )
                    if verify_response.status_code == 200:
                        verify_data = verify_response.json()
                        if "instances" in verify_data:
                            pool_instances = [
                                i for i in verify_data["instances"]
                                if i.get("type") == instance_type
                            ]
                            current_count = len(pool_instances)
                            print(f"   Found {current_count}/{count} {instance_type} instances")
                            
                            if current_count >= count:
                                print(f"✅ All {count} instances were created successfully!")
                                print("   The Lambda timed out, but all instances are now available")
                                return True
                            elif current_count >= count * 0.8:  # At least 80% created
                                print(f"✅ Most instances ({current_count}/{count}) were created")
                                if wait_time < wait_times[-1]:
                                    print("   Continuing to wait for remaining instances...")
                                    continue
                                else:
                                    print("   Remaining instances may still be creating. Wait a few minutes and verify again.")
                                    return True
                            elif current_count > 0:
                                print(f"   Progress: {current_count}/{count} instances created")
                                if wait_time < wait_times[-1]:
                                    print("   Continuing to wait...")
                                    continue
                                else:
                                    print(f"⚠️  Only {current_count}/{count} instances created so far")
                                    print("   Instances may still be creating. Wait a few minutes and verify again.")
                                    return True  # Still consider it a partial success
                            else:
                                if wait_time < wait_times[-1]:
                                    print("   No instances found yet, continuing to wait...")
                                    continue
                except Exception as verify_error:
                    print(f"   Error checking instances: {str(verify_error)}")
                    if wait_time < wait_times[-1]:
                        print("   Will retry after next wait period...")
                        continue
            
            # Final check - if we got here, we've exhausted all wait periods
            print("   ⚠️  Could not verify all instances were created after waiting")
            print("   The Lambda timed out - instances may still be creating in the background")
            print("   Wait a few more minutes and check the instance list manually")
            return False
        else:
            print(f"❌ Failed to create instances: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
    except requests.exceptions.Timeout:
        # Request timeout (not Lambda timeout)
        print(f"⚠️  Request timeout - Lambda may still be processing")
        print("   Checking if instances were created...")
        
        # Wait a bit
        time.sleep(10)
        
        # Verify instances
        if verify_instances(instance_manager_url, count, instance_type, auth_cookie):
            print(f"✅ Instances were created successfully despite timeout!")
            return True
        else:
            print("   ⚠️  Could not verify if instances were created")
            print("   Wait a few minutes and check the instance list manually")
            return False
    except Exception as e:
        print(f"❌ Error creating instances: {str(e)}")
        # Even on error, check if instances were created
        if count > 50:
            print("   Checking if any instances were created before the error...")
            time.sleep(5)
            verify_instances(instance_manager_url, count, instance_type, auth_cookie)
        return False

def verify_instances(
    instance_manager_url: str,
    expected_count: int,
    instance_type: str = "pool",
    auth_cookie: Optional[str] = None,
    strict: bool = False
) -> bool:
    """Verify that instances were created successfully
    
    Args:
        strict: If True, requires exact count. If False, accepts 80%+ of expected count.
    """
    print("\n🔍 Verifying instances...")
    
    headers = {}
    if auth_cookie:
        headers["Cookie"] = auth_cookie
    
    try:
        response = requests.get(
            f"{instance_manager_url}/list",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "instances" in data:
                # Count all instances of this type (not just "available")
                all_instances = [
                    i for i in data["instances"]
                    if i.get("type") == instance_type
                ]
                available_instances = [
                    i for i in all_instances
                    if i.get("status") == "available" or i.get("state") in ["running", "stopped", "pending"]
                ]
                
                print(f"✅ Found {len(all_instances)} total {instance_type} instances")
                if len(available_instances) != len(all_instances):
                    print(f"   Available/Running: {len(available_instances)}")
                
                # For large batches, be more lenient
                min_required = expected_count * 0.8 if not strict else expected_count
                
                if len(all_instances) >= min_required:
                    if len(all_instances) == expected_count:
                        print(f"✅ All {expected_count} instances found!")
                        return True
                    else:
                        print(f"✅ Found {len(all_instances)}/{expected_count} instances ({len(all_instances)/expected_count*100:.1f}%)")
                        if len(all_instances) < expected_count:
                            print("   Remaining instances may still be creating. Wait a few minutes and check again.")
                        return True
                else:
                    print(f"⚠️  Warning: Expected {expected_count} instances, found {len(all_instances)}")
                    print("   Note: Instances may still be starting. Wait a few minutes and check again.")
                    return False
            else:
                print("⚠️  Could not parse list response")
                return False
        else:
            print(f"⚠️  Could not list instances: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠️  Error verifying instances: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Prepare instance pool for k6 tests")
    parser.add_argument("--url", required=True, help="Instance Manager Lambda URL")
    parser.add_argument("--count", type=int, default=20, help="Number of instances to create (default: 20)")
    parser.add_argument("--type", default="pool", choices=["pool", "admin"], help="Instance type (default: pool)")
    parser.add_argument("--password", help="Instance Manager password (if required)")
    parser.add_argument("--verify", action="store_true", help="Verify instances after creation")
    parser.add_argument("--wait", type=int, default=0, help="Wait N seconds after creation before verifying")
    
    args = parser.parse_args()
    
    print(f"\n🔧 Preparing {args.count} {args.type} instances...")
    print(f"   Instance Manager URL: {args.url}\n")
    
    # Step 1: Authenticate if password is provided
    auth_cookie = None
    if args.password:
        auth_cookie = authenticate(args.url, args.password)
        if auth_cookie is None and args.password:
            print("❌ Authentication failed. Exiting.")
            sys.exit(1)
    
    # Step 2: Create instances
    success = create_instances(args.url, args.count, args.type, auth_cookie)
    
    # Step 3: Always verify for large batches or if creation reported failure
    # This helps catch cases where Lambda timed out but instances were created
    if not success or args.count > 50 or args.verify:
        if not success:
            print("\n⚠️  Creation reported failure, but verifying if instances were actually created...")
        else:
            print("\n🔍 Verifying instances...")
        
        # Wait a bit for instances to appear in the list
        if args.count > 50:
            wait_time = max(args.wait, 60)  # At least 30 seconds for large batches
        else:
            wait_time = args.wait
        
        if wait_time > 0:
            print(f"⏳ Waiting {wait_time} seconds for instances to initialize...")
            time.sleep(wait_time)
        
        verification_success = verify_instances(args.url, args.count, args.type, auth_cookie, strict=False)
        
        if verification_success:
            print("\n✅ Instance pool preparation complete!")
            print("   You can now run the k6 test scenarios.\n")
            sys.exit(0)
        elif success:
            # Creation succeeded but verification failed - instances may still be starting
            print("\n⚠️  Instances created but not all are ready yet")
            print("   Wait a few minutes and check the instance list manually")
            print("   You can proceed with tests, but some instances may not be available immediately\n")
            sys.exit(0)
        else:
            # Both creation and verification failed
            print("\n❌ Failed to create/verify instances.")
            print("   For large batches (>50), the Lambda may timeout but instances may still be creating")
            print("   Wait a few minutes and check the instance list manually")
            sys.exit(1)
    else:
        # Small batch, creation succeeded, no verification needed
        print("\n✅ Instance pool preparation complete!")
        print("   You can now run the k6 test scenarios.\n")

if __name__ == "__main__":
    main()

