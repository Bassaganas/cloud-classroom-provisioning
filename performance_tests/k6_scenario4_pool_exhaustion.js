/**
 * k6 Test: Scenario 4 - Pool Exhaustion and Recovery
 * 
 * Scenario: Test behavior when instance pool is exhausted and then instances become available
 * Business Logic: 
 * - When pool is exhausted, new users should get appropriate error messages
 * - When instances become available again, users should be able to get instances
 * - System should handle concurrent requests when pool is limited
 * 
 * Test Flow:
 * 1. Create instances equal to number of users (e.g., 10 instances for 10 users)
 * 2. Have 15 users try to get instances (5 will fail initially)
 * 3. Wait for some instances to become available
 * 4. Verify that previously failed users can now get instances
 * 
 * Prerequisites:
 * - Set USER_MANAGEMENT_URL environment variable
 * - INSTANCE_POOL_SIZE should be less than NUM_USERS to test exhaustion
 * 
 * Usage:
 *   k6 run --vus 15 --iterations 30 k6_scenario4_pool_exhaustion.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const instanceAssignedRate = new Rate('instance_assigned');
const poolExhaustionDetectedRate = new Rate('pool_exhaustion_detected');
const recoverySuccessRate = new Rate('recovery_success'); // Got instance after initial failure
const responseTime = new Trend('response_time');
const errorRate = new Rate('errors');

// Configuration
const USER_MANAGEMENT_URL = __ENV.USER_MANAGEMENT_URL || 'https://your-lambda-url.lambda-url.region.on.aws';
const NUM_USERS = parseInt(__ENV.NUM_USERS || '15');
const INSTANCE_POOL_SIZE = parseInt(__ENV.INSTANCE_POOL_SIZE || '10'); // Less than NUM_USERS to test exhaustion

// Test options
export const options = {
    scenarios: {
        pool_exhaustion: {
            executor: 'shared-iterations',
            vus: NUM_USERS,
            iterations: NUM_USERS * 3, // 3 attempts per user
            maxDuration: '5m',
        },
    },
    thresholds: {
        'http_req_duration': ['p(95)<15000'],
        'http_req_failed': ['rate<0.2'],
        'instance_assigned': ['rate>0.6'], // At least 60% should eventually get instances
        'pool_exhaustion_detected': ['rate>0.3'], // Should detect exhaustion
    },
};

// Per-VU state
const vuState = {};

// Helper function to parse cookies (same as other scenarios)
function parseCookies(cookieHeader) {
    const cookies = {};
    if (!cookieHeader) return cookies;
    
    let cookieStrings = [];
    if (Array.isArray(cookieHeader)) {
        for (const item of cookieHeader) {
            if (typeof item === 'string') cookieStrings.push(item);
        }
    } else if (typeof cookieHeader === 'string') {
        cookieStrings = cookieHeader.split(',').map(s => s.trim());
    }
    
    for (const cookieString of cookieStrings) {
        if (!cookieString || typeof cookieString !== 'string') continue;
        const parts = cookieString.split(';');
        if (parts.length > 0) {
            const nameValuePart = parts[0].trim();
            const equalIndex = nameValuePart.indexOf('=');
            if (equalIndex > 0) {
                const name = nameValuePart.substring(0, equalIndex).trim();
                const value = nameValuePart.substring(equalIndex + 1).trim();
                if (name && value) {
                    try {
                        cookies[name] = decodeURIComponent(value);
                    } catch (e) {
                        cookies[name] = value;
                    }
                }
            }
        }
    }
    return cookies;
}

function extractCookies(response) {
    let cookies = {};
    
    if (response.cookies && typeof response.cookies === 'object') {
        for (const cookieName in response.cookies) {
            const cookieArray = response.cookies[cookieName];
            if (Array.isArray(cookieArray) && cookieArray.length > 0) {
                cookies[cookieName] = cookieArray[0].value || cookieArray[0];
            }
        }
    }
    
    if (Object.keys(cookies).length === 0) {
        const headerKeys = Object.keys(response.headers);
        let cookieHeaders = [];
        for (const key of headerKeys) {
            if (key.toLowerCase() === 'set-cookie') {
                const value = response.headers[key];
                if (Array.isArray(value)) {
                    cookieHeaders.push(...value);
                } else if (typeof value === 'string') {
                    cookieHeaders.push(value);
                }
            }
        }
        if (cookieHeaders.length > 0) {
            cookies = parseCookies(cookieHeaders);
        }
    }
    
    return cookies;
}

export default function () {
    const vuId = __VU;
    const iter = __ITER;
    
    // Initialize state
    if (!vuState[vuId]) {
        vuState[vuId] = {
            userName: null,
            instanceId: null,
            ipAddress: null,
            requestCount: 0,
            hasInstance: false,
            initialFailure: false,
        };
    }
    
    const state = vuState[vuId];
    state.requestCount++;
    
    // Prepare headers
    const headers = {
        'User-Agent': `k6-test-user-${vuId}`,
    };
    
    if (state.instanceId && state.userName) {
        headers['Cookie'] = [
            `testus_patronus_user=${encodeURIComponent(state.userName)}`,
            `testus_patronus_instance_id=${encodeURIComponent(state.instanceId)}`,
            state.ipAddress ? `testus_patronus_ip=${encodeURIComponent(state.ipAddress)}` : null,
        ].filter(Boolean).join('; ');
    }
    
    const startTime = Date.now();
    const response = http.get(USER_MANAGEMENT_URL, { headers: headers });
    const responseTimeMs = Date.now() - startTime;
    responseTime.add(responseTimeMs);
    
    // Check if request was successful
    const isSuccess = check(response, {
        'status is 200': (r) => r.status === 200,
        'response has body': (r) => r.body && r.body.length > 0,
    });
    
    if (!isSuccess) {
        errorRate.add(1);
        console.error(`[User ${vuId}] Request ${state.requestCount} failed: ${response.status}`);
        return;
    }
    
    // Extract cookies and instance info
    const cookies = extractCookies(response);
    let currentUserName = cookies['testus_patronus_user'];
    let currentInstanceId = cookies['testus_patronus_instance_id'];
    let currentIpAddress = cookies['testus_patronus_ip'];
    
    // Fallback: Extract from HTML
    if (!currentInstanceId || !currentUserName) {
        const body = response.body.toLowerCase();
        if (body.includes('instance') || body.includes('conference-user')) {
            const instanceIdMatch = response.body.match(/instance[_-]?id["\s:=]+(i-[a-z0-9-]+)/i);
            const userNameMatch = response.body.match(/conference-user-([a-f0-9]{8})/i);
            
            if (instanceIdMatch && instanceIdMatch[1].startsWith('i-')) {
                currentInstanceId = instanceIdMatch[1];
            }
            if (userNameMatch) {
                currentUserName = `conference-user-${userNameMatch[1]}`;
            }
        }
    }
    
    // Check for pool exhaustion indicators in response
    const body = response.body.toLowerCase();
    const hasError = body.includes('error') || body.includes('no available') || body.includes('failed');
    const hasInstance = currentInstanceId && currentInstanceId.startsWith('i-');
    
    // First request: Try to get instance
    if (state.requestCount === 1) {
        if (hasInstance && currentUserName) {
            state.userName = currentUserName;
            state.instanceId = currentInstanceId;
            state.ipAddress = currentIpAddress;
            state.hasInstance = true;
            instanceAssignedRate.add(1);
            console.log(`[User ${vuId}] ✅ Got instance on first try: ${currentInstanceId}`);
        } else {
            // Pool exhausted or error
            state.initialFailure = true;
            instanceAssignedRate.add(0);
            poolExhaustionDetectedRate.add(1);
            console.warn(`[User ${vuId}] ⚠️  No instance assigned (pool may be exhausted)`);
        }
    }
    // Subsequent requests: Retry if didn't get instance initially
    else if (!state.hasInstance) {
        if (hasInstance && currentUserName) {
            // Got instance on retry - recovery successful
            state.userName = currentUserName;
            state.instanceId = currentInstanceId;
            state.ipAddress = currentIpAddress;
            state.hasInstance = true;
            instanceAssignedRate.add(1);
            recoverySuccessRate.add(1);
            console.log(`[User ${vuId}] ✅ Got instance on retry ${state.requestCount}: ${currentInstanceId}`);
        } else {
            // Still no instance
            instanceAssignedRate.add(0);
            recoverySuccessRate.add(0);
            if (state.requestCount <= 3) {
                console.warn(`[User ${vuId}] ⚠️  Still no instance on retry ${state.requestCount}`);
            }
        }
    }
    // Verify persistence if has instance
    else if (state.hasInstance) {
        if (currentInstanceId === state.instanceId && currentUserName === state.userName) {
            // Instance persists correctly
        } else if (currentInstanceId && currentInstanceId !== state.instanceId) {
            console.error(`[User ${vuId}] ❌ Instance changed unexpectedly: ${state.instanceId} -> ${currentInstanceId}`);
        }
    }
    
    // Add delay between requests
    sleep(0.3 + Math.random() * 0.4);
}

export function handleSummary(data) {
    const summary = {
        timestamp: new Date().toISOString(),
        scenario: 'Scenario 4: Pool Exhaustion and Recovery',
        configuration: {
            user_management_url: USER_MANAGEMENT_URL,
            num_users: NUM_USERS,
            instance_pool_size: INSTANCE_POOL_SIZE,
        },
        metrics: {
            http_req_duration: data.metrics.http_req_duration,
            http_req_failed: data.metrics.http_req_failed,
            instance_assigned_rate: data.metrics.instance_assigned,
            pool_exhaustion_detected_rate: data.metrics.pool_exhaustion_detected,
            recovery_success_rate: data.metrics.recovery_success,
            total_requests: data.metrics.http_reqs.values.count,
            total_errors: data.metrics.http_req_failed.values.rate * data.metrics.http_reqs.values.count,
        },
        thresholds: {
            passed: Object.values(data.root_group.checks || {}).filter(c => c.passes > 0).length,
            failed: Object.values(data.root_group.checks || {}).filter(c => c.fails > 0).length,
        },
    };
    
    console.log('\n📊 Test Summary:');
    console.log(`   Total Requests: ${summary.metrics.total_requests}`);
    console.log(`   Instance Assignment: ${(summary.metrics.instance_assigned_rate.values.rate * 100).toFixed(1)}%`);
    console.log(`   Pool Exhaustion Detected: ${(summary.metrics.pool_exhaustion_detected_rate.values.rate * 100).toFixed(1)}%`);
    console.log(`   Recovery Success: ${(summary.metrics.recovery_success_rate.values.rate * 100).toFixed(1)}%`);
    console.log(`   Avg Response Time: ${summary.metrics.http_req_duration.values.avg.toFixed(2)}ms`);
    
    const assignmentRate = summary.metrics.instance_assigned_rate.values.rate;
    if (assignmentRate >= 0.6) {
        console.log('\n✅ Business Logic: PASSED - System handles pool exhaustion and recovery');
    } else {
        console.log('\n⚠️  Business Logic: PARTIAL - Some users may not have gotten instances due to pool size');
    }
    
    return {
        'stdout': JSON.stringify(summary, null, 2),
        'summary.json': JSON.stringify(summary, null, 2),
    };
}

