---
sidebar_position: 2
---

# For Students: Accessing Resources

:::note
Students access workshop-specific Lambda functions directly, not the EC2 Manager interface.
:::

## Get User Account and Credentials

1. Visit the workshop-specific URL (provided by instructor):
   - **Testus Patronus**: `https://testus-patronus.testingfantasy.com`
   - **Fellowship**: `https://fellowship-of-the-build.testingfantasy.com`

2. The Lambda function serves an HTML page with:
   - Your assigned EC2 instance details
   - Dify AI or Jenkins access credentials
   - Azure LLM API keys (if applicable)
   - Instance connection information

## Access EC2 Instance

- Via HTTPS (if enabled): `https://{instance-id}.{workshop}.testingfantasy.com`
- Via SSH (if configured): Use provided credentials
- Direct IP access: Use the public IP shown on your HTML page

## Get a New User Account

- Click "Get a new user" button on the workshop HTML page
- A new account will be created and assigned automatically
