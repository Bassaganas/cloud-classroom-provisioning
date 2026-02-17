# Route 53 Migration Fix - Add Missing CNAME Records

## 🔴 Problem

After migrating from GoDaddy DNS to Route 53, your AWS Lambda functions (via CloudFront) stopped working because the **CNAME records for subdomains are missing** in Route 53.

**Error:** `DNS_PROBE_FINISHED_NXDOMAIN` when accessing `ec2-management.testingfantasy.com`

**Root Cause:** The subdomain CNAME records that point to CloudFront distributions were not migrated to Route 53.

---

## ✅ Solution: Add CNAME Records in Route 53

You need to create **CNAME records** in Route 53 for each subdomain pointing to their respective CloudFront distributions.

### CloudFront Distribution Domains

From your Terraform configuration:

1. **Instance Manager (EC2 Management):**
   - Subdomain: `ec2-management.testingfantasy.com`
   - CloudFront Domain: `d2ywu8d99c3npt.cloudfront.net`

2. **User Management:**
   - Subdomain: `testus-patronus.testingfantasy.com`
   - CloudFront Domain: `dysguswjzuwmm.cloudfront.net`

3. **Dify Jira API:**
   - Subdomain: `dify-jira.testingfantasy.com`
   - CloudFront Domain: `d2yrhm0hdl21x6.cloudfront.net`

---

## 📋 Step-by-Step Instructions

### Step 1: Add CNAME for `ec2-management.testingfantasy.com`

1. Go to **Route 53 Console** → **Hosted zones** → `testingfantasy.com`
2. Click **"Create record"**
3. Configure:
   - **Record name:** `ec2-management`
   - **Record type:** `CNAME`
   - **Value:** `d2ywu8d99c3npt.cloudfront.net` (include trailing dot: `d2ywu8d99c3npt.cloudfront.net.`)
   - **TTL:** `300` (or use default)
   - **Routing policy:** Simple routing
4. Click **"Create records"**

### Step 2: Add CNAME for `testus-patronus.testingfantasy.com`

1. In the same hosted zone, click **"Create record"**
2. Configure:
   - **Record name:** `testus-patronus`
   - **Record type:** `CNAME`
   - **Value:** `dysguswjzuwmm.cloudfront.net.` (include trailing dot)
   - **TTL:** `300`
   - **Routing policy:** Simple routing
3. Click **"Create records"**

### Step 3: Add CNAME for `dify-jira.testingfantasy.com`

1. In the same hosted zone, click **"Create record"**
2. Configure:
   - **Record name:** `dify-jira`
   - **Record type:** `CNAME`
   - **Value:** `d2yrhm0hdl21x6.cloudfront.net.` (include trailing dot)
   - **TTL:** `300`
   - **Routing policy:** Simple routing
3. Click **"Create records"**

---

## 🔍 Verify Certificate Validation Records

Your ACM certificates are already validated (status: Issued), but verify these validation CNAME records exist in Route 53:

### For `ec2-management.testingfantasy.com`:
- **Record name:** `_add7b2dcf428fa760e92d0013697ce93.ec2-management`
- **Type:** `CNAME`
- **Value:** `_33d59d59fde28e92099116f13c9f1416.jkddzztszm.acm-validations.aws.`

**Note:** If this record is missing, your certificate might become invalid. Check Route 53 to ensure it exists.

---

## ✅ Verification Steps

### 1. Wait for DNS Propagation (1-5 minutes)

Route 53 propagates changes quickly, but wait a few minutes.

### 2. Test DNS Resolution

```bash
# Test ec2-management subdomain
dig ec2-management.testingfantasy.com +short
# Should return: d2ywu8d99c3npt.cloudfront.net

# Test testus-patronus subdomain
dig testus-patronus.testingfantasy.com +short
# Should return: dysguswjzuwmm.cloudfront.net

# Test dify-jira subdomain
dig dify-jira.testingfantasy.com +short
# Should return: d2yrhm0hdl21x6.cloudfront.net
```

### 3. Test in Browser

After DNS propagation:
- ✅ `https://ec2-management.testingfantasy.com` should work
- ✅ `https://testus-patronus.testingfantasy.com` should work
- ✅ `https://dify-jira.testingfantasy.com` should work

### 4. Check Route 53 Records

Go to Route 53 → Hosted zones → `testingfantasy.com` → Records

You should now see:
- ✅ `ec2-management` (CNAME) → `d2ywu8d99c3npt.cloudfront.net`
- ✅ `testus-patronus` (CNAME) → `dysguswjzuwmm.cloudfront.net`
- ✅ `dify-jira` (CNAME) → `d2yrhm0hdl21x6.cloudfront.net`

---

## 🎯 Summary

**What was wrong:**
- After migrating DNS from GoDaddy to Route 53, the CNAME records for subdomains were not created
- CloudFront distributions exist and are configured correctly
- ACM certificates are validated
- But DNS doesn't know where to route the subdomain requests

**What you fixed:**
- Added CNAME records in Route 53 pointing subdomains to CloudFront distributions
- DNS can now resolve subdomain names to CloudFront domains
- Your Lambda functions (via CloudFront) will work again

---

## 📝 Quick Reference: All Required Records

| Subdomain | Type | Value | Purpose |
|-----------|------|-------|---------|
| `ec2-management` | CNAME | `d2ywu8d99c3npt.cloudfront.net.` | Route to CloudFront |
| `testus-patronus` | CNAME | `dysguswjzuwmm.cloudfront.net.` | Route to CloudFront |
| `dify-jira` | CNAME | `d2yrhm0hdl21x6.cloudfront.net.` | Route to CloudFront |

**Note:** The trailing dot (`.`) in the CNAME value is optional in Route 53 console - it will add it automatically.

---

## ⚠️ Important Notes

1. **Trailing Dots:** Route 53 console may automatically add trailing dots to CNAME values. If you see an error, try with and without the trailing dot.

2. **Certificate Validation:** Your certificates are already validated, but if you see certificate errors later, check that the ACM validation CNAME records still exist in Route 53.

3. **CloudFront Configuration:** Your CloudFront distributions are already configured with the correct alternate domain names and certificates. You don't need to change anything in CloudFront.

4. **Root Domain:** The root domain (`testingfantasy.com`) already has an A record pointing to CloudFront - that's working correctly.

---

## 🆘 Troubleshooting

### If subdomain still doesn't work after adding CNAME:

1. **Check DNS propagation:**
   ```bash
   dig ec2-management.testingfantasy.com
   ```
   Should show CNAME record pointing to CloudFront domain.

2. **Check CloudFront distribution:**
   - Go to CloudFront console
   - Verify "Alternate domain names" includes your subdomain
   - Verify SSL certificate is attached

3. **Check certificate status:**
   - Go to ACM console (us-east-1 region)
   - Verify certificate status is "Issued"
   - Verify domain validation is "Success"

4. **Clear browser cache:**
   - DNS errors can be cached by browsers
   - Try incognito/private browsing mode

---

**Time to complete:** ~5-10 minutes (plus 1-5 minutes for DNS propagation)


