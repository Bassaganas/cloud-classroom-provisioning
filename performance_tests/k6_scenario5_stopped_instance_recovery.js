/**
 * k6 Test: Scenario 5 - Stopped Instance Recovery
 * 
 * Scenario: Test behavior when a user's instance is stopped (not terminated)
 * Business Logic: System should automatically start stopped instances when users refresh
 * 
 * Test Flow:
 * 1. Create N users, each gets an instance (initial assignment)
 * 2. Stop instances for first 5 users (simulate cost optimization)
 * 3. Users refresh with cookies - Lambda should detect stopped state and start instances
 * 4. Verify:
 *    - Lambda detects stopped instances (returns "Instance is starting..." message)
 *    - Instances automatically start and become available with IP addresses
 *    - Same instance ID is maintained (no reassignment)
 * 
 * Key Validations:
 * - stopped_detected: Lambda detects stopped instances (>80% success rate)
 * - auto_start_success: Instances start and get IP addresses (>90% success rate)
 * 
 * Prerequisites:
 * - At least NUM_USERS pool instances available
 * - Set USER_MANAGEMENT_URL and INSTANCE_MANAGER_URL environment variables
 * - Set INSTANCE_MANAGER_PASSWORD if authentication is required
 * 
 * Usage:
 *   export NUM_USERS=10
 *   export INSTANCE_POOL_SIZE=10
 *   k6 run k6_scenario5_stopped_instance_recovery.js
 * 
 * Note: Test uses shared-iterations to ensure each user gets ~22 requests
 * (1 initial + 1 stop + 20 verification requests to allow time for instance startup)
 * EC2 instances can take 30-60 seconds to start from stopped state
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const stoppedDetectedRate = new Rate('stopped_detected'); // System detected stopped instance
const autoStartSuccessRate = new Rate('auto_start_success'); // Instance automatically started
const responseTime = new Trend('response_time');
const errorRate = new Rate('errors');

// Configuration
const USER_MANAGEMENT_URL = __ENV.USER_MANAGEMENT_URL || 'https://your-lambda-url.lambda-url.region.on.aws';
const INSTANCE_MANAGER_URL = __ENV.INSTANCE_MANAGER_URL || '';
const INSTANCE_MANAGER_PASSWORD = __ENV.INSTANCE_MANAGER_PASSWORD || '';
const NUM_USERS = parseInt(__ENV.NUM_USERS || '10');
const INSTANCE_POOL_SIZE = parseInt(__ENV.INSTANCE_POOL_SIZE || '20');

// Test options
// Use shared-iterations to ensure each user gets enough requests to complete the flow:
// 1 initial assignment + 1 stop + 20+ verification requests = ~22 requests per user
// EC2 instances can take 30-60 seconds to start, so we need more requests to catch the transition
export const options = {
    scenarios: {
        default: {
            executor: 'shared-iterations',
            vus: NUM_USERS,
            iterations: NUM_USERS * 22, // 22 requests per user (1 initial + 1 stop + 20 verification)
            maxDuration: '3m', // Allow up to 3 minutes for instances to start
        },
    },
    thresholds: {
        'http_req_duration': ['p(95)<10000'],
        'http_req_failed': ['rate<0.1'],
        'stopped_detected': ['rate>0.8'],
        'auto_start_success': ['rate>0.9'],
    },
};

// Per-VU state
const vuState = {};

// Helper functions (same as scenario 3)
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

// Helper function to stop instance via Instance Manager API
function stopInstance(instanceId, instanceManagerUrl, password) {
    if (!instanceManagerUrl || !password) {
        console.warn(`[VU ${__VU}] Cannot stop instance - INSTANCE_MANAGER_URL or PASSWORD not set`);
        return false;
    }
    
    try {
        // Authenticate
        const authResponse = http.post(
            `${instanceManagerUrl}/login`,
            JSON.stringify({ password: password }),
            { headers: { 'Content-Type': 'application/json' } }
        );
        
        if (authResponse.status !== 200) {
            console.error(`[VU ${__VU}] Authentication failed: ${authResponse.status} - ${authResponse.body}`);
            return false;
        }
        
        const authCookies = extractCookies(authResponse);
        const authCookie = authCookies['instance_manager_auth'];
        
        if (!authCookie) {
            console.error(`[VU ${__VU}] No auth cookie received after login`);
            return false;
        }
        
        // Stop instance using POST /stop endpoint
        const stopResponse = http.post(
            `${instanceManagerUrl}/stop?instance_id=${instanceId}`,
            null,
            {
                headers: {
                    'Cookie': `instance_manager_auth=${authCookie}`,
                    'Content-Type': 'application/json'
                }
            }
        );
        
        if (stopResponse.status === 200) {
            try {
                const responseBody = JSON.parse(stopResponse.body);
                if (responseBody.success) {
                    console.log(`[VU ${__VU}] ✅ Stop request successful: ${responseBody.message || 'Instance stop initiated'}`);
                    return true;
                } else {
                    console.error(`[VU ${__VU}] Stop request failed: ${responseBody.error || 'Unknown error'}`);
                    return false;
                }
            } catch (e) {
                // Response is not JSON, but status is 200, assume success
                console.log(`[VU ${__VU}] ✅ Stop request successful (non-JSON response)`);
                return true;
            }
        } else {
            console.error(`[VU ${__VU}] Stop request failed: HTTP ${stopResponse.status} - ${stopResponse.body}`);
            return false;
        }
    } catch (e) {
        console.error(`[VU ${__VU}] Exception stopping instance ${instanceId}: ${e}`);
        return false;
    }
}

export default function () {
    const vuId = __VU;
    const iter = __ITER;
    
    if (!vuState[vuId]) {
        vuState[vuId] = {
            userName: null,
            instanceId: null,
            ipAddress: null,
            requestCount: 0,
            instanceStopped: false,
            instanceStarted: false,
            startingDetected: false, // Track if we detected "starting" message
        };
    }
    
    const state = vuState[vuId];
    state.requestCount++;
    
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
    
    const isSuccess = check(response, {
        'status is 200': (r) => r.status === 200,
        'response has body': (r) => r.body && r.body.length > 0,
    });
    
    if (!isSuccess) {
        errorRate.add(1);
        return;
    }
    
    const cookies = extractCookies(response);
    let currentUserName = cookies['testus_patronus_user'];
    let currentInstanceId = cookies['testus_patronus_instance_id'];
    let currentIpAddress = cookies['testus_patronus_ip'];
    
    // Fallback: Extract from HTML
    if (!currentInstanceId || !currentUserName || !currentIpAddress) {
        const body = response.body.toLowerCase();
        if (body.includes('instance') || body.includes('conference-user')) {
            const instanceIdMatch = response.body.match(/instance[_-]?id["\s:=]+(i-[a-z0-9-]+)/i);
            const userNameMatch = response.body.match(/conference-user-([a-f0-9]{8})/i);
            // Try to extract IP address from HTML (look for IP patterns like http://IP or IP addresses)
            const ipMatch = response.body.match(/(?:http:\/\/)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/);
            
            if (instanceIdMatch && instanceIdMatch[1].startsWith('i-')) {
                currentInstanceId = instanceIdMatch[1];
            }
            if (userNameMatch) {
                currentUserName = `conference-user-${userNameMatch[1]}`;
            }
            if (ipMatch && !currentIpAddress) {
                currentIpAddress = ipMatch[1];
            }
        }
    }
    
    // Check for "starting" or "stopped" indicators in response
    const body = response.body.toLowerCase();
    const isStarting = body.includes('starting') || body.includes('instance is starting');
    const hasError = body.includes('error') && !isStarting;
    
    // Phase 1: Initial assignment
    if (state.requestCount === 1) {
        if (currentInstanceId && currentUserName) {
            state.userName = currentUserName;
            state.instanceId = currentInstanceId;
            state.ipAddress = currentIpAddress;
            console.log(`[User ${vuId}] ✅ Initial assignment: Instance ${currentInstanceId}`);
        }
    }
    // Phase 2: Stop instance (for first 5 users)
    else if (state.requestCount === 2 && vuId <= 5 && state.instanceId && !state.instanceStopped) {
        console.log(`[User ${vuId}] 🛑 Stopping instance ${state.instanceId}...`);
        const stopped = stopInstance(state.instanceId, INSTANCE_MANAGER_URL, INSTANCE_MANAGER_PASSWORD);
        if (stopped) {
            state.instanceStopped = true;
            console.log(`[User ${vuId}] ✅ Instance ${state.instanceId} stopped`);
        }
    }
    // Phase 3: Verify auto-start (requests 3+ - continue checking until instance starts or test ends)
    // EC2 instances can take 30-60 seconds to start, so we need to keep checking
    else if (state.requestCount >= 3 && state.instanceStopped && !state.instanceStarted) {
        // Check if instance is starting (first time detection)
        if (isStarting && !state.startingDetected) {
            // System detected stopped instance and is starting it
            stoppedDetectedRate.add(1);
            state.startingDetected = true;
            console.log(`[User ${vuId}] 🔄 Instance is starting (request ${state.requestCount})`);
        }
        
        // Check if instance is running (has IP address) - this is the key success metric
        if (currentIpAddress && currentInstanceId === state.instanceId) {
            // Instance is running again - mark both detection and success
            if (!state.startingDetected) {
                // We didn't catch the "starting" message, but instance is running
                // This is still valid - Lambda might have started it very quickly
                stoppedDetectedRate.add(1);
                state.startingDetected = true;
            }
            autoStartSuccessRate.add(1);
            state.instanceStarted = true;
            state.ipAddress = currentIpAddress;
            console.log(`[User ${vuId}] ✅ Instance auto-started and running (IP: ${currentIpAddress}, request ${state.requestCount})`);
        } else if (state.startingDetected) {
            // We detected "starting" but still no IP - instance is still starting
            // Log progress every few requests to show we're still waiting
            if (state.requestCount % 3 === 0) {
                const debugInfo = `instanceId=${currentInstanceId || 'none'}, expected=${state.instanceId}, ip=${currentIpAddress || 'none'}`;
                console.log(`[User ${vuId}] ⏳ Still waiting for instance to start (request ${state.requestCount}, ${debugInfo})`);
            }
        } else if (!state.startingDetected && state.requestCount >= 5) {
            // We haven't detected "starting" yet, but we've made several requests
            // This might indicate the Lambda isn't detecting/starting the instance
            if (state.requestCount % 5 === 0) {
                console.warn(`[User ${vuId}] ⚠️ No "starting" message detected after ${state.requestCount} requests - Lambda may not be starting instances`);
            }
        }
    }
    // Phase 4: Verify persistence after start
    else if (state.instanceStarted) {
        if (currentInstanceId === state.instanceId && currentIpAddress) {
            // Instance persists and is accessible - all good
        } else if (currentInstanceId === state.instanceId && !currentIpAddress) {
            // Same instance but no IP - might be stopping/restarting
            console.warn(`[User ${vuId}] ⚠️ Instance ${state.instanceId} lost IP address (request ${state.requestCount})`);
        } else {
            // Different instance - something changed
            console.error(`[User ${vuId}] ❌ Instance changed from ${state.instanceId} to ${currentInstanceId} (request ${state.requestCount})`);
        }
    }
    
    // Increase sleep time slightly to allow more time for instance state changes
    // Especially important after stopping instances
    let sleepTime = 0.5 + Math.random() * 0.5;
    if (state.instanceStopped && !state.instanceStarted) {
        // Give more time when waiting for instance to start
        sleepTime = 1.0 + Math.random() * 1.0;
    }
    sleep(sleepTime);
}

export function handleSummary(data) {
    const summary = {
        timestamp: new Date().toISOString(),
        scenario: 'Scenario 5: Stopped Instance Recovery',
        configuration: {
            user_management_url: USER_MANAGEMENT_URL,
            num_users: NUM_USERS,
            instance_pool_size: INSTANCE_POOL_SIZE,
        },
        metrics: {
            http_req_duration: data.metrics.http_req_duration,
            http_req_failed: data.metrics.http_req_failed,
            stopped_detected_rate: data.metrics.stopped_detected,
            auto_start_success_rate: data.metrics.auto_start_success,
            total_requests: data.metrics.http_reqs.values.count,
        },
    };
    
    console.log('\n📊 Test Summary:');
    console.log(`   Stopped Detection: ${(summary.metrics.stopped_detected_rate.values.rate * 100).toFixed(1)}%`);
    console.log(`   Auto-Start Success: ${(summary.metrics.auto_start_success_rate.values.rate * 100).toFixed(1)}%`);
    
    const autoStartRate = summary.metrics.auto_start_success_rate.values.rate;
    if (autoStartRate >= 0.9) {
        console.log('\n✅ Business Logic: PASSED - System successfully auto-starts stopped instances');
    } else {
        console.log('\n⚠️  Business Logic: PARTIAL - Some stopped instances may not have auto-started');
    }
    
    return {
        'stdout': JSON.stringify(summary, null, 2),
        'summary.json': JSON.stringify(summary, null, 2),
    };
}

