---
sidebar_position: 2
---

# Cost Optimization

## AWS Costs

### With EC2 Pool (10 instances, t3.small)

- EC2 instances: ~$50-100/month (when running)
- Lambda functions: ~$1-5/month
- Storage (S3, DynamoDB): ~$1-3/month
- CloudFront: ~$1-2/month
- **Total: ~$53-110/month**

### Lambda-Only Deployment

- Lambda functions: ~$1-5/month
- Storage: ~$1-3/month
- CloudFront: ~$1-2/month
- **Total: ~$3-10/month**

## Cost-Saving Tips

1. **Use smaller instance pool**: Start with 5-10 instances
2. **Destroy when not in use**: Use `--destroy` between classes
3. **Optimize instance types**: Use t3.micro for development, t3.small for production
4. **Monitor usage**: Check AWS Cost Explorer regularly
5. **Enable auto-stop**: Instances automatically stop after idle timeout
