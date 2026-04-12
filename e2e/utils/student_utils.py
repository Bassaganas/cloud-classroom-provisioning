"""Utilities for student-related test operations."""
import os
import logging
import time
import boto3
from typing import Dict, Optional, List, Tuple
from uuid import uuid4
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()


class StudentTestHelper:
    """Helper class for managing test students and their resources."""
    
    def __init__(self):
        """Initialize student test helper."""
        self.workshop_name = os.getenv('WORKSHOP_NAME', 'fellowship')
        self.region = os.getenv('AWS_REGION', 'eu-west-1')
        self.ec2_client = boto3.client('ec2', region_name=self.region)
        self.route53_client = boto3.client('route53', region_name=self.region)
        
        # Load existing DNS zone
        self.hosted_zone_id = os.getenv('INSTANCE_MANAGER_HOSTED_ZONE_ID')
        self.base_domain = os.getenv('INSTANCE_MANAGER_BASE_DOMAIN', 'testingfantasy.com')
    
    def generate_student_id(self, student_name: str = None) -> str:
        """
        Generate a unique student ID.
        
        Args:
            student_name: Optional name to include in ID
            
        Returns:
            Unique student ID
        """
        unique_id = str(uuid4())[:8]
        if student_name:
            return f"{student_name}-{unique_id}"
        return f"student-{unique_id}"
    
    def get_instances_for_student(self, student_id: str) -> List[Dict]:
        """
        Get all EC2 instances for a student.
        
        Args:
            student_id: Student identifier
            
        Returns:
            List of instance details
        """
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {'Name': 'tag:StudentId', 'Values': [student_id]},
                    {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped']}
                ]
            )
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances.append({
                        'InstanceId': instance['InstanceId'],
                        'InstanceType': instance['InstanceType'],
                        'PrivateIpAddress': instance.get('PrivateIpAddress'),
                        'PublicIpAddress': instance.get('PublicIpAddress'),
                        'State': instance['State']['Name'],
                        'Tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                    })
            return instances
        except Exception as e:
            logger.error(f"Failed to get instances for student {student_id}: {e}")
            return []
    
    def get_instance_ide_url(self, instance_id: str) -> Optional[str]:
        """
        Get the IDE URL for an instance.
        
        Args:
            instance_id: EC2 instance ID
            
        Returns:
            IDE URL (http://private-ip:port or similar)
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            if not response['Reservations']:
                return None
            
            instance = response['Reservations'][0]['Instances'][0]
            private_ip = instance.get('PrivateIpAddress')
            
            # Check for IDE port in tags (typically 3001 for code-server)
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            ide_port = tags.get('IdePort', '3001')
            
            if private_ip:
                return f"http://{private_ip}:{ide_port}"
            return None
        except Exception as e:
            logger.error(f"Failed to get IDE URL for {instance_id}: {e}")
            return None
    
    def get_instance_details(self, instance_id: str) -> Optional[Dict]:
        """Get detailed information for an instance."""
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            if not response['Reservations']:
                return None
            
            instance = response['Reservations'][0]['Instances'][0]
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            
            return {
                'InstanceId': instance_id,
                'InstanceType': instance['InstanceType'],
                'PrivateIpAddress': instance.get('PrivateIpAddress'),
                'PublicIpAddress': instance.get('PublicIpAddress'),
                'State': instance['State']['Name'],
                'LaunchTime': instance['LaunchTime'].isoformat(),
                'Tags': tags
            }
        except Exception as e:
            logger.error(f"Failed to get instance details for {instance_id}: {e}")
            return None
    
    def verify_instance_isolation(self, student_a_id: str, student_b_id: str) -> Tuple[bool, str]:
        """
        Verify that two students have completely different instances.
        
        Args:
            student_a_id: First student ID
            student_b_id: Second student ID
            
        Returns:
            Tuple of (is_isolated, message)
        """
        instances_a = self.get_instances_for_student(student_a_id)
        instances_b = self.get_instances_for_student(student_b_id)
        
        if not instances_a:
            return False, f"Student A ({student_a_id}) has no instances"
        if not instances_b:
            return False, f"Student B ({student_b_id}) has no instances"
        
        ids_a = set(inst['InstanceId'] for inst in instances_a)
        ids_b = set(inst['InstanceId'] for inst in instances_b)
        
        if ids_a & ids_b:
            shared = ids_a & ids_b
            return False, f"Students share instances: {shared}"
        
        return True, f"Student A has {len(instances_a)} unique instances, Student B has {len(instances_b)} unique instances"
    
    def wait_for_instance_ready(self, instance_id: str, timeout: int = 300) -> bool:
        """
        Wait for an instance to be ready (running + passes status checks).
        
        Args:
            instance_id: EC2 instance ID
            timeout: Max seconds to wait
            
        Returns:
            True if instance is ready
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check instance state
                response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
                if not response['Reservations']:
                    time.sleep(5)
                    continue
                
                instance = response['Reservations'][0]['Instances'][0]
                state = instance['State']['Name']
                
                if state == 'running':
                    # Check status checks
                    try:
                        status_response = self.ec2_client.describe_instance_status(
                            InstanceIds=[instance_id],
                            IncludeAllInstances=False
                        )
                        if status_response['InstanceStatuses']:
                            status = status_response['InstanceStatuses'][0]
                            if (status['InstanceStatus']['Status'] == 'ok' and 
                                status['SystemStatus']['Status'] == 'ok'):
                                logger.info(f"Instance {instance_id} is ready")
                                return True
                    except Exception as e:
                        logger.debug(f"Status check not yet available: {e}")
                
                if state in ['stopped', 'stopping', 'terminated', 'terminating']:
                    logger.error(f"Instance {instance_id} is in state {state}")
                    return False
                
            except Exception as e:
                logger.warning(f"Error checking instance status: {e}")
            
            time.sleep(10)
        
        logger.error(f"Timeout waiting for instance {instance_id} to be ready")
        return False
    
    def cleanup_student_instances(self, student_id: str, force: bool = False) -> bool:
        """
        Terminate all instances for a student.
        
        Args:
            student_id: Student ID
            force: Force termination even if tagged as persistent
            
        Returns:
            True if cleanup was successful
        """
        instances = self.get_instances_for_student(student_id)
        if not instances:
            logger.info(f"No instances to clean up for student {student_id}")
            return True
        
        try:
            instance_ids = [inst['InstanceId'] for inst in instances]
            
            # Check if instances are marked as persistent
            if not force:
                for inst in instances:
                    tags = inst.get('Tags', {})
                    if tags.get('Persistent') == 'true':
                        logger.warning(f"Instance {inst['InstanceId']} is marked as persistent, skipping")
                        instance_ids.remove(inst['InstanceId'])
            
            if instance_ids:
                self.ec2_client.terminate_instances(InstanceIds=instance_ids)
                logger.info(f"Terminated {len(instance_ids)} instances for student {student_id}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup instances for student {student_id}: {e}")
            return False
    
    def get_dns_records_for_student(self, student_id: str) -> List[Dict]:
        """
        Get Route53 DNS records for a student.
        
        Args:
            student_id: Student ID
            
        Returns:
            List of DNS records
        """
        if not self.hosted_zone_id:
            logger.warning("Route53 hosted zone ID not configured")
            return []
        
        try:
            response = self.route53_client.list_resource_record_sets(
                HostedZoneId=self.hosted_zone_id
            )
            
            records = []
            for record in response.get('ResourceRecordSets', []):
                # Check if record is associated with student (in subdomain)
                name = record['Name'].rstrip('.')
                if student_id.lower() in name.lower():
                    records.append({
                        'Name': name,
                        'Type': record['Type'],
                        'Value': record.get('ResourceRecords', []),
                        'TTL': record.get('TTL')
                    })
            return records
        except Exception as e:
            logger.error(f"Failed to get DNS records for student {student_id}: {e}")
            return []
    
    def verify_student_dns_isolation(self, student_a_id: str, student_b_id: str) -> Tuple[bool, str]:
        """
        Verify that students have different DNS records.
        
        Args:
            student_a_id: First student ID
            student_b_id: Second student ID
            
        Returns:
            Tuple of (is_isolated, message)
        """
        records_a = self.get_dns_records_for_student(student_a_id)
        records_b = self.get_dns_records_for_student(student_b_id)
        
        # Check for overlap
        names_a = set(r['Name'] for r in records_a)
        names_b = set(r['Name'] for r in records_b)
        
        overlap = names_a & names_b
        if overlap:
            return False, f"Students share DNS records: {overlap}"
        
        return True, f"Student A has {len(records_a)} DNS records, Student B has {len(records_b)} DNS records"
