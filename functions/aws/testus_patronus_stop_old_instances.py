import boto3
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(f"Lambda stop_old_instances invoked. Event: {event}")
    ec2 = boto3.client('ec2', region_name='eu-west-3')
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=10)
    logger.info(f"Cutoff time for stopping: {cutoff}")

    # Only check instances that are running and are part of the classroom pool
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['running']},
            {'Name': 'tag:Type', 'Values': ['pool']},
            {'Name': 'tag:Status', 'Values': ['assigned']}
        ]
    )
    logger.info(f"DescribeInstances response: {response}")

    instances_to_stop = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            launch_time = instance['LaunchTime']
            instance_id = instance['InstanceId']
            logger.info(f"Instance {instance_id} launch_time: {launch_time}")
            if launch_time < cutoff:
                instances_to_stop.append(instance_id)

    if instances_to_stop:
        logger.info(f"Stopping instances: {instances_to_stop}")
        ec2.stop_instances(InstanceIds=instances_to_stop)
        # After stopping, clear Student tag and set Status=available
        for instance_id in instances_to_stop:
            ec2.create_tags(
                Resources=[instance_id],
                Tags=[
                    {'Key': 'Status', 'Value': 'available'},
                    {'Key': 'Student', 'Value': ''}
                ]
            )
            logger.info(f"Updated tags for instance {instance_id}: Status=available, Student='' ")
    else:
        logger.info("No instances to stop.") 