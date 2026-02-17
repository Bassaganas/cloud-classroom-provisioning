# Dify Jira API Performance Testing Suite

This directory contains comprehensive performance testing tools for the `dify_jira_api.py` Lambda function.

## 🎯 Overview

The performance testing suite includes:
- **k6 Load Testing**: Realistic load patterns and detailed metrics
- **Python Concurrency Testing**: Lambda-specific concurrency testing
- **Dataset Management**: Automated dataset creation and cleanup
- **Comprehensive Reporting**: Detailed performance analysis

## 📁 Files

- `k6_dify_jira_test.js` - k6 load testing script
- `enhanced_concurrency_test.py` - Python concurrency testing
- `dataset_manager.py` - Dataset management utilities
- `run_performance_tests.sh` - Main test runner script
- `README.md` - This documentation

## 🚀 Quick Start

### Prerequisites

1. **k6** (for load testing):
   ```bash
   # macOS
   brew install k6
   
   # Linux
   sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
   echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
   sudo apt-get update
   sudo apt-get install k6
   
   # Windows
   # Download from https://k6.io/docs/getting-started/installation/
   ```

2. **Python 3** with required packages:
   ```bash
   pip3 install requests
   ```

3. **jq** (optional, for JSON processing):
   ```bash
   # macOS
   brew install jq
   
   # Linux
   sudo apt-get install jq
   ```

### Configuration

Set the required environment variables:

```bash
export LAMBDA_URL="https://your-lambda-url.amazonaws.com"
export DIFY_BASE_URL="http://your-dify-instance:5001/v1"
export DIFY_API_KEY="your-dify-api-key"
export TEST_DURATION="300"  # 5 minutes
export NUM_USERS="50"      # Concurrent users
```

### Running Tests

#### Option 1: Run All Tests (Recommended)
```bash
chmod +x run_performance_tests.sh
./run_performance_tests.sh
```

#### Option 2: Run Individual Tests

**k6 Load Test:**
```bash
k6 run --duration 300s --vus 20 k6_dify_jira_test.js
```

**Python Concurrency Test:**
```bash
python3 enhanced_concurrency_test.py \
  --lambda-url "$LAMBDA_URL" \
  --dify-base-url "$DIFY_BASE_URL" \
  --dify-api-key "$DIFY_API_KEY" \
  --users 50
```

**Dataset Management:**
```bash
# Test connection
python3 dataset_manager.py --dify-base-url "$DIFY_BASE_URL" --dify-api-key "$DIFY_API_KEY" --action test

# List datasets
python3 dataset_manager.py --dify-base-url "$DIFY_BASE_URL" --dify-api-key "$DIFY_API_KEY" --action list

# Create test datasets
python3 dataset_manager.py --dify-base-url "$DIFY_BASE_URL" --dify-api-key "$DIFY_API_KEY" --action create --count 5

# Cleanup test datasets
python3 dataset_manager.py --dify-base-url "$DIFY_BASE_URL" --dify-api-key "$DIFY_API_KEY" --action cleanup
```

## 📊 Test Scenarios

### k6 Load Test Scenarios

The k6 test simulates realistic usage patterns:

1. **Health Checks (30%)** - Lightweight endpoint testing
2. **Project Listing (20%)** - Get available projects
3. **Dify Status (20%)** - Check Dify connection
4. **Dataset Listing (10%)** - List available datasets
5. **Jira Ingestion (20%)** - Heavy workload testing

### Python Concurrency Test Scenarios

The Python test focuses on Lambda concurrency:

1. **Endpoint Distribution**:
   - Health: 20%
   - Projects: 20%
   - Dify Status: 20%
   - Dify Datasets: 10%
   - Jira Ingestion: 30%

2. **Concurrency Testing**:
   - Tests Lambda concurrency limits
   - Measures response times under load
   - Analyzes error rates
   - Tracks ingestion performance

## 📈 Metrics and Thresholds

### k6 Thresholds
- **Response Time**: 95% of requests under 2 seconds
- **Error Rate**: Under 10%
- **Dify Ingestion**: 90% under 5 seconds

### Python Metrics
- **Success Rate**: Percentage of successful requests
- **Response Time**: Average response time per endpoint
- **Ingestion Analysis**: Issues ingested per request
- **Error Analysis**: Detailed error tracking

## 🔧 Dataset Management

### Automatic Dataset Creation

Your `dify_jira_api.py` already handles dataset creation automatically! When a dataset ID is not provided or is set to "your-dataset-id", the API will:

1. Create a new dataset with a random name
2. Use the dataset for ingestion
3. Return the dataset ID for future use

### Manual Dataset Management

Use the `dataset_manager.py` script for advanced dataset management:

```bash
# Test connection
python3 dataset_manager.py --action test

# Create test datasets
python3 dataset_manager.py --action create --count 10

# Get statistics
python3 dataset_manager.py --action stats

# Cleanup test datasets
python3 dataset_manager.py --action cleanup --pattern "perf_test_"
```

## 📋 Results Analysis

### k6 Results
- **JSON Output**: Detailed metrics in `results_k6_*.json`
- **Custom Metrics**: Dify-specific timing and error rates
- **Threshold Analysis**: Pass/fail based on defined thresholds

### Python Results
- **Console Output**: Real-time progress and summary
- **JSON Output**: Detailed results in `performance_results_*.json`
- **Endpoint Analysis**: Per-endpoint performance breakdown

### Key Metrics to Monitor

1. **Response Times**:
   - Health: < 100ms
   - Projects: < 200ms
   - Dify Status: < 500ms
   - Jira Ingestion: < 5s

2. **Success Rates**:
   - Overall: > 95%
   - Per endpoint: > 90%

3. **Throughput**:
   - Requests per second
   - Concurrent users supported
   - Lambda concurrency utilization

## 🚨 Troubleshooting

### Common Issues

1. **Connection Timeouts**:
   - Check Dify instance accessibility
   - Verify API key permissions
   - Ensure network connectivity

2. **Dataset Creation Failures**:
   - Verify Dify instance has sufficient resources
   - Check API key has dataset creation permissions
   - Monitor Dify instance logs

3. **High Error Rates**:
   - Check Lambda function logs
   - Verify Dify instance stability
   - Monitor resource utilization

### Debug Mode

Enable detailed logging:

```bash
# Python tests
export PYTHONPATH=.
python3 -c "import logging; logging.basicConfig(level=logging.DEBUG)"

# k6 tests
k6 run --log-level debug k6_dify_jira_test.js
```

## 🔄 Continuous Testing

### Automated Testing Pipeline

1. **Pre-test Setup**:
   ```bash
   # Clean up old test data
   python3 dataset_manager.py --action cleanup
   
   # Create fresh test datasets
   python3 dataset_manager.py --action create --count 5
   ```

2. **Run Performance Tests**:
   ```bash
   ./run_performance_tests.sh
   ```

3. **Post-test Cleanup**:
   ```bash
   # Clean up test datasets
   python3 dataset_manager.py --action cleanup --pattern "perf_test_"
   ```

### CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Performance Tests
on: [push, pull_request]
jobs:
  performance-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup k6
        run: |
          sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6
      - name: Run Performance Tests
        run: |
          export LAMBDA_URL="${{ secrets.LAMBDA_URL }}"
          export DIFY_BASE_URL="${{ secrets.DIFY_BASE_URL }}"
          export DIFY_API_KEY="${{ secrets.DIFY_API_KEY }}"
          ./run_performance_tests.sh
```

## 📚 Additional Resources

- [k6 Documentation](https://k6.io/docs/)
- [Dify API Documentation](https://docs.dify.ai/)
- [AWS Lambda Performance Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

## 🤝 Contributing

When adding new test scenarios:

1. Update the endpoint weights in both k6 and Python tests
2. Add new metrics to the analysis functions
3. Update the documentation
4. Test with different load patterns

## 📞 Support

For issues with the performance testing suite:

1. Check the troubleshooting section
2. Review the logs for specific error messages
3. Verify your Dify instance is accessible
4. Ensure all environment variables are set correctly



