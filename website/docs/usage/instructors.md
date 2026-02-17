---
sidebar_position: 1
---

# For Instructors: Managing Classrooms

## Access the Instance Manager

1. Navigate to: `https://ec2-management-{environment}.testingfantasy.com`
2. Login with the password from AWS Secrets Manager

## Create Tutorial Sessions

1. Click "Create Tutorial Session"
2. Configure pool size, admin count, cleanup days
3. Session manages instance lifecycle automatically

## Manage EC2 Instances

- View all instances (pool, admin, assigned)
- Create new instances on-demand
- Assign instances to students
- Enable HTTPS for individual instances
- Delete instances when no longer needed

## Configure Timeout Settings

- Set stop timeout (default: 4 minutes)
- Set terminate timeout (default: 20 minutes)
- Set hard terminate timeout (default: 45 minutes)
