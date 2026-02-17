---
sidebar_position: 1
---

# Architecture Overview

The system follows a **serverless modular architecture** pattern with **separate access paths for students and instructors**.

```mermaid
flowchart TB
    subgraph users[User Access Layer]
        Students[Students]
        Instructors[Instructors]
        Admins[Admins]
    end
    
    subgraph studentAccess[Student Access Path]
        StudentCF[CloudFront<br/>testus-patronus.testingfantasy.com<br/>fellowship-of-the-build.testingfantasy.com]
        StudentLambda[Workshop Lambda Functions<br/>classroom_user_management.py<br/>Serves HTML directly]
    end
    
    subgraph instructorAccess[Instructor Access Path]
        InstructorCF[CloudFront<br/>ec2-management-env.testingfantasy.com]
        InstructorS3[S3 Bucket<br/>React SPA]
        InstructorAPI[API Gateway<br/>REST API<br/>ec2-management-api-env.testingfantasy.com]
        InstanceManager[Instance Manager Lambda<br/>classroom_instance_manager.py]
    end
    
    subgraph compute[Compute Layer]
        EC2Pool[EC2 Instance Pool<br/>Pre-configured applications<br/>Dify AI, Jenkins, etc.]
        CleanupLambdas[Cleanup Lambda Functions<br/>Stop Old Instances<br/>Admin Cleanup]
    end
    
    subgraph data[Data Layer]
        DynamoDB[(DynamoDB<br/>Instance Assignments<br/>Tutorial Sessions)]
        SSM[SSM Parameter Store<br/>Templates & Configs]
        Secrets[Secrets Manager<br/>Passwords & Credentials]
    end
    
    Students --> StudentCF
    StudentCF --> StudentLambda
    StudentLambda --> EC2Pool
    StudentLambda --> DynamoDB
    StudentLambda --> SSM
    StudentLambda --> Secrets
    
    Instructors --> InstructorCF
    InstructorCF --> InstructorS3
    InstructorS3 --> InstructorAPI
    InstructorAPI --> InstanceManager
    InstanceManager --> EC2Pool
    InstanceManager --> DynamoDB
    InstanceManager --> SSM
    InstanceManager --> Secrets
    
    CleanupLambdas --> EC2Pool
    CleanupLambdas --> DynamoDB
```

## Key Components

### Student-Facing Components

1. **Workshop Lambda Functions**: Serverless functions that serve HTML pages directly to students
   - `classroom_user_management.py`: Creates student accounts and serves HTML with credentials
   - `testus_patronus_status.py`: Status checking for workshop instances
   - `dify_jira_api.py`: Dify Jira API integration
   - Accessed via CloudFront: `testus-patronus.testingfantasy.com`, `fellowship-of-the-build.testingfantasy.com`

### Instructor-Facing Components

2. **EC2 Manager Frontend (React SPA)**: Web-based management interface hosted on S3 and served via CloudFront
   - Custom domain: `ec2-management-{environment}.testingfantasy.com` (e.g., `ec2-management-dev.testingfantasy.com`)
   - Instance management, workshop configuration, tutorial session management

3. **API Gateway**: RESTful API that routes requests to Lambda functions
   - Custom domain: `ec2-management-api-{environment}.testingfantasy.com` (e.g., `ec2-management-api-dev.testingfantasy.com`)

4. **Instance Manager Lambda**: Core Lambda function handling EC2 lifecycle management
   - Manages instance creation, assignment, deletion, HTTPS setup

### Shared Components

5. **EC2 Instances**: Pre-configured compute resources for students
6. **Data Storage**: DynamoDB for state, SSM for configuration, Secrets Manager for credentials
7. **Infrastructure as Code**: Terraform modules for reproducible deployments
