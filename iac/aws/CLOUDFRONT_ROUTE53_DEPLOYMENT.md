# CloudFront Deployment Guide - Route 53 Configuration

## 🎯 Overview

This guide covers deploying CloudFront distributions for Lambda functions after migrating DNS from GoDaddy to Route 53. The `testing_fantasy` application is now deployed with AWS Amplify (handled separately), so this Terraform only manages CloudFront for Lambda functions.

## 📋 Prerequisites

- ✅ Route 53 hosted zone for `testingfantasy.com` is configured
- ✅ GoDaddy nameservers point to Route 53
- ✅ Terraform is initialized and configured
- ✅ AWS credentials are configured

## 🚀 Deployment Steps

### Step 1: Review Terraform Configuration

The following CloudFront distributions are configured:
1. **Instance Manager**: `ec2-management.testingfantasy.com`
2. **User Management**: `testus-patronus.testingfantasy.com`
3. **Dify Jira API**: `dify-jira.testingfantasy.com`

**Note:** The static website module (`testingfantasy.com`) is disabled since Amplify handles it.

### Step 2: Get CloudFront Distribution Domains

Run Terraform to get the CloudFront distribution domains:

```bash
cd cloud-classroom-provisioning/iac/aws

# Get all CloudFront domains
terraform output instance_manager_cloudfront_domain
terraform output user_management_cloudfront_domain
terraform output dify_jira_cloudfront_domain
```

Expected output:
- Instance Manager: `d2ywu8d99c3npt.cloudfront.net`
- User Management: `dysguswjzuwmm.cloudfront.net`
- Dify Jira: `d2yrhm0hdl21x6.cloudfront.net`

### Step 3: Get Certificate Validation Records

Get the ACM certificate validation records:

```bash
terraform output instance_manager_acm_certificate_validation_records
terraform output user_management_acm_certificate_validation_records
terraform output dify_jira_acm_certificate_validation_records
```

### Step 4: Add DNS Records to Route 53

Go to **Route 53 Console** → **Hosted zones** → `testingfantasy.com` → **Records**

#### 4.1: Add CNAME Records for CloudFront

Create CNAME records pointing subdomains to CloudFront distributions:

**Record 1: Instance Manager**
- **Record name:** `ec2-management`
- **Record type:** `CNAME`
- **Value:** `d2ywu8d99c3npt.cloudfront.net.` (include trailing dot)
- **TTL:** `300`
- **Routing policy:** Simple routing

**Record 2: User Management**
- **Record name:** `testus-patronus`
- **Record type:** `CNAME`
- **Value:** `dysguswjzuwmm.cloudfront.net.` (include trailing dot)
- **TTL:** `300`
- **Routing policy:** Simple routing

**Record 3: Dify Jira API**
- **Record name:** `dify-jira`
- **Record type:** `CNAME`
- **Value:** `d2yrhm0hdl21x6.cloudfront.net.` (include trailing dot)
- **TTL:** `300`
- **Routing policy:** Simple routing

#### 4.2: Add Certificate Validation CNAME Records

These records are required for ACM certificate validation. Add them if they don't already exist:

**For `ec2-management.testingfantasy.com`:**
- **Record name:** `_add7b2dcf428fa760e92d0013697ce93.ec2-management`
- **Type:** `CNAME`
- **Value:** `_33d59d59fde28e92099116f13c9f1416.jkddzztszm.acm-validations.aws.`
- **TTL:** `300`

**For `testus-patronus.testingfantasy.com`:**
- **Record name:** `_a9b2636c7ee14a1687584ddbfee119ed.testus-patronus`
- **Type:** `CNAME`
- **Value:** `_5fffa912da4f50c1b46a47b9fc1bb4c5.jkddzztszm.acm-validations.aws.`
- **TTL:** `300`

**For `dify-jira.testingfantasy.com`:**
- **Record name:** `_6cbc2ed0ce00549a0cf934bf8ba4ae0b.dify-jira`
- **Type:** `CNAME`
- **Value:** `_5d0f7293223dcadcc3af1b428accd471.jkddzztszm.acm-validations.aws.`
- **TTL:** `300`

**Note:** Remove the trailing `.testingfantasy.com` from the record name when creating in Route 53. Route 53 will automatically append the hosted zone domain.

### Step 5: Wait for Certificate Validation

After adding the validation records:
1. Wait 5-10 minutes for DNS propagation
2. Check ACM Console (us-east-1 region) → Certificates
3. Verify certificate status is **"Issued"** and validation is **"Success"**

### Step 6: Update Terraform Configuration

For subdomains that need certificate validation enabled, update `main.tf`:

```hcl
# For testus-patronus (currently false, set to true after validation)
wait_for_certificate_validation = true
```

Current status:
- ✅ `ec2-management`: `wait_for_certificate_validation = true`
- ⚠️ `testus-patronus`: `wait_for_certificate_validation = false` (set to `true` after validation)
- ✅ `dify-jira`: `wait_for_certificate_validation = true`

### Step 7: Deploy with Terraform

```bash
# Initialize (if needed)
terraform init

# Plan changes
terraform plan

# Apply changes
terraform apply
```

This will:
- Create/update CloudFront distributions
- Configure SSL certificates
- Add alternate domain names to CloudFront
- Enable HTTPS for custom domains

### Step 8: Verify Deployment

#### 8.1: Check DNS Resolution

```bash
# Test DNS resolution
dig ec2-management.testingfantasy.com +short
# Should return: d2ywu8d99c3npt.cloudfront.net

dig testus-patronus.testingfantasy.com +short
# Should return: dysguswjzuwmm.cloudfront.net

dig dify-jira.testingfantasy.com +short
# Should return: d2yrhm0hdl21x6.cloudfront.net
```

#### 8.2: Test in Browser

After DNS propagation (1-5 minutes):
- ✅ `https://ec2-management.testingfantasy.com/ui` - Instance Manager UI
- ✅ `https://testus-patronus.testingfantasy.com` - User Management API
- ✅ `https://dify-jira.testingfantasy.com` - Dify Jira API

#### 8.3: Check CloudFront Console

Verify in CloudFront Console:
- Distributions are **Enabled**
- **Alternate domain names** include your subdomains
- **SSL certificate** is attached and valid
- **Status** is **Deployed**

## 📊 Summary of DNS Records

### CNAME Records (Route Traffic to CloudFront)

| Subdomain | Type | Value | Purpose |
|-----------|------|-------|---------|
| `ec2-management` | CNAME | `d2ywu8d99c3npt.cloudfront.net.` | Route to CloudFront |
| `testus-patronus` | CNAME | `dysguswjzuwmm.cloudfront.net.` | Route to CloudFront |
| `dify-jira` | CNAME | `d2yrhm0hdl21x6.cloudfront.net.` | Route to CloudFront |

### Certificate Validation Records (ACM)

| Record Name | Type | Value | Purpose |
|-------------|------|-------|---------|
| `_add7b2dcf428fa760e92d0013697ce93.ec2-management` | CNAME | `_33d59d59fde28e92099116f13c9f1416.jkddzztszm.acm-validations.aws.` | Certificate validation |
| `_a9b2636c7ee14a1687584ddbfee119ed.testus-patronus` | CNAME | `_5fffa912da4f50c1b46a47b9fc1bb4c5.jkddzztszm.acm-validations.aws.` | Certificate validation |
| `_6cbc2ed0ce00549a0cf934bf8ba4ae0b.dify-jira` | CNAME | `_5d0f7293223dcadcc3af1b428accd471.jkddzztszm.acm-validations.aws.` | Certificate validation |

## ⚠️ Important Notes

1. **Trailing Dots:** Route 53 console may automatically add trailing dots to CNAME values. If you see an error, try with and without the trailing dot.

2. **Certificate Validation:** Certificates must be validated before CloudFront can use them. Ensure validation records exist and certificates show "Issued" status.

3. **DNS Propagation:** Route 53 propagates changes quickly (usually within 60 seconds), but allow 1-5 minutes for full propagation.

4. **CloudFront Deployment:** After Terraform apply, CloudFront distributions take 10-15 minutes to fully deploy. Check the CloudFront console for deployment status.

5. **Amplify Configuration:** The root domain (`testingfantasy.com`) is handled by Amplify, not this Terraform. Do not create CNAME records for the root domain pointing to CloudFront.

## 🆘 Troubleshooting

### Issue: DNS_PROBE_FINISHED_NXDOMAIN

**Cause:** CNAME record missing or incorrect in Route 53

**Solution:**
1. Verify CNAME record exists in Route 53
2. Check record name matches subdomain (without `.testingfantasy.com`)
3. Verify value points to correct CloudFront domain
4. Wait for DNS propagation

### Issue: Certificate Not Validated

**Cause:** Validation CNAME record missing or incorrect

**Solution:**
1. Check ACM Console (us-east-1) for certificate status
2. Verify validation CNAME record exists in Route 53
3. Wait 5-10 minutes after adding validation record
4. Re-check certificate status

### Issue: CloudFront Returns 403 or Certificate Error

**Cause:** Certificate not attached or domain not in alternate names

**Solution:**
1. Verify `wait_for_certificate_validation = true` in Terraform
2. Check CloudFront distribution has alternate domain name configured
3. Verify SSL certificate is attached in CloudFront console
4. Wait for CloudFront deployment to complete

### Issue: Terraform Apply Fails

**Cause:** Certificate validation not complete or DNS conflict

**Solution:**
1. Ensure validation records are in Route 53
2. Wait for certificate to show "Issued" status
3. Check Route 53 doesn't have conflicting records
4. Run `terraform plan` to see specific errors

## 📝 Quick Reference Commands

```bash
# Get CloudFront domains
terraform output instance_manager_cloudfront_domain
terraform output user_management_cloudfront_domain
terraform output dify_jira_cloudfront_domain

# Get certificate validation records
terraform output instance_manager_acm_certificate_validation_records
terraform output user_management_acm_certificate_validation_records
terraform output dify_jira_acm_certificate_validation_records

# Test DNS resolution
dig ec2-management.testingfantasy.com +short
dig testus-patronus.testingfantasy.com +short
dig dify-jira.testingfantasy.com +short

# Deploy
terraform init
terraform plan
terraform apply
```

## ✅ Deployment Checklist

- [ ] Route 53 hosted zone configured
- [ ] CNAME records added for all three subdomains
- [ ] Certificate validation CNAME records added
- [ ] Certificates show "Issued" status in ACM
- [ ] Terraform configuration updated (wait_for_certificate_validation)
- [ ] Terraform apply completed successfully
- [ ] CloudFront distributions deployed
- [ ] DNS resolution working (dig commands)
- [ ] HTTPS URLs accessible in browser
- [ ] Lambda functions responding correctly

---

**Time to complete:** ~30-45 minutes (including DNS propagation and CloudFront deployment)

