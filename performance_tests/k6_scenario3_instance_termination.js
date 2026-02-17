/**
 * k6 Test: Scenario 3 - Instance Termination and Reassignment
 * 
 * Scenario: Simulate what happens when a user's assigned instance is terminated
 * Business Logic: System should detect termination and automatically reassign a new instance
 * 
 * Test Flow:
 * 1. Create 10 users, each gets an instance
 * 2. Terminate 5 of their instances (simulate expiration/cleanup)
 * 3. Users refresh - system should detect termination and reassign new instances
 * 4. Verify all users eventually get new instances
 * 
 * Prerequisites:
 * - At least 10 pool instances available
 * - Set USER_MANAGEMENT_URL and INSTANCE_MANAGER_URL environment variables
 * - Set INSTANCE_MANAGER_PASSWORD if authentication is required
 * 
 * Usage:
 *   k6 run --vus 10 --iterations 30 k6_scenario3_instance_termination.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const terminationDetectedRate = new Rate('termination_detected'); // System detected terminated instance
const reassignmentSuccessRate = new Rate('reassignment_success'); // Successfully got new instance after termination
const responseTime = new Trend('response_time');
const errorRate = new Rate('errors');

// Configuration
const USER_MANAGEMENT_URL = __ENV.USER_MANAGEMENT_URL || 'https://your-lambda-url.lambda-url.region.on.aws';
const INSTANCE_MANAGER_URL = __ENV.INSTANCE_MANAGER_URL || '';
const INSTANCE_MANAGER_PASSWORD = __ENV.INSTANCE_MANAGER_PASSWORD || '';
const NUM_USERS = parseInt(__ENV.NUM_USERS || '10');
const INSTANCE_POOL_SIZE = parseInt(__ENV.INSTANCE_POOL_SIZE || '20');

    // Test options
export const options = {
    scenarios: {
        termination_test: {
            executor: 'shared-iterations',
            vus: NUM_USERS,
            iterations: NUM_USERS * 10, // 10 iterations per user (1 initial + 1 terminate + 8 for reassignment)
            maxDuration: '5m',
        },
    },
    thresholds: {
        'http_req_duration': ['p(95)<10000'],      // 95% of requests under 10s
        'http_req_failed': ['rate<0.1'],             // Less than 10% errors
        'termination_detected': ['rate>0.8'],        // 80% of terminations detected
        'reassignment_success': ['rate>0.7'],        // 70% successful reassignments (may be lower if pool exhausted)
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

// Helper function to extract cookies from response
function extractCookies(response) {
    let cookies = {};
    
    // Method 1: k6's built-in parsing
    if (response.cookies && typeof response.cookies === 'object') {
        for (const cookieName in response.cookies) {
            const cookieArray = response.cookies[cookieName];
            if (Array.isArray(cookieArray) && cookieArray.length > 0) {
                cookies[cookieName] = cookieArray[0].value || cookieArray[0];
            }
        }
    }
    
    // Method 2: Parse from headers
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

// Helper function to terminate instance via Instance Manager API
function terminateInstance(instanceId, instanceManagerUrl, password) {
    if (!instanceManagerUrl || !password) {
        console.warn(`[VU ${__VU}] Cannot terminate instance - INSTANCE_MANAGER_URL or PASSWORD not set`);
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
            console.error(`[VU ${__VU}] Authentication failed: ${authResponse.status}`);
            return false;
        }
        
        // Extract auth cookie
        const authCookies = extractCookies(authResponse);
        const authCookie = authCookies['instance_manager_auth'];
        
        if (!authCookie) {
            console.error(`[VU ${__VU}] No auth cookie received`);
            return false;
        }
        
        // Terminate instance (using delete endpoint)
        const deleteResponse = http.del(
            `${instanceManagerUrl}/delete?instance_id=${instanceId}`,
            {
                headers: {
                    'Cookie': `instance_manager_auth=${authCookie}`
                }
            }
        );
        
        return deleteResponse.status === 200;
    } catch (e) {
        console.error(`[VU ${__VU}] Error terminating instance: ${e}`);
        return false;
    }
}

export default function () {
    const vuId = __VU;
    const iter = __ITER;
    const users_to_terminate = Math.floor(NUM_USERS / 2); // Calculate once per function call
    
    // Initialize state
    if (!vuState[vuId]) {
        vuState[vuId] = {
            userName: null,
            instanceId: null,
            ipAddress: null,
            requestCount: 0,
            instanceTerminated: false,
            reassigned: false,
            oldInstanceId: null, // Store old instance ID after termination
        };
    }
    
    const state = vuState[vuId];
    state.requestCount++;
    
    // Prepare headers with cookies if available
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
    
    // Extract cookies
    const cookies = extractCookies(response);
    let currentUserName = cookies['testus_patronus_user'];
    let currentInstanceId = cookies['testus_patronus_instance_id'];
    let currentIpAddress = cookies['testus_patronus_ip'];
    
    // Fallback: Extract from HTML if cookies not parsed
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
    
    // Phase 1: Initial assignment (request 1)
    if (state.requestCount === 1) {
        if (currentInstanceId && currentUserName) {
            state.userName = currentUserName;
            state.instanceId = currentInstanceId;
            state.ipAddress = currentIpAddress;
            console.log(`[User ${vuId}] ✅ Initial assignment: Instance ${currentInstanceId}`);
        } else {
            errorRate.add(1);
            console.error(`[User ${vuId}] ❌ Initial request failed: No instance assigned`);
        }
    }
    // Phase 2: Terminate instance (request 2) - only for first half of users
    else if (state.requestCount === 2 && vuId <= users_to_terminate && state.instanceId && !state.instanceTerminated) {
        console.log(`[User ${vuId}] 🔪 Terminating instance ${state.instanceId}...`);
        const terminated = terminateInstance(state.instanceId, INSTANCE_MANAGER_URL, INSTANCE_MANAGER_PASSWORD);
        if (terminated) {
            state.instanceTerminated = true;
            state.oldInstanceId = state.instanceId; // Store old instance ID for comparison
            console.log(`[User ${vuId}] ✅ Instance ${state.oldInstanceId} terminated`);
            // Don't clear instanceId - we need it to detect when a NEW instance is assigned
        } else {
            console.error(`[User ${vuId}] ❌ Failed to terminate instance`);
        }
    }
    // Phase 3: Verify termination detection and reassignment (requests 3-10)
    else if (state.requestCount >= 3 && state.requestCount <= 10 && state.instanceTerminated && !state.reassigned) {
        // Check if system detected termination and reassigned (only check if not already reassigned)
        if (currentInstanceId && currentInstanceId !== state.oldInstanceId) {
            // New instance assigned - reassignment successful (first time detection)
            terminationDetectedRate.add(1);
            reassignmentSuccessRate.add(1);
            state.instanceId = currentInstanceId;
            state.userName = currentUserName;
            state.ipAddress = currentIpAddress;
            state.reassigned = true;
            console.log(`[User ${vuId}] ✅ Reassigned to new instance: ${currentInstanceId} (was ${state.oldInstanceId})`);
        } else if (currentInstanceId && currentInstanceId === state.oldInstanceId) {
            // Still showing old instance (shouldn't happen if terminated, but might be in transition)
            terminationDetectedRate.add(0);
            reassignmentSuccessRate.add(0);
            if (state.requestCount <= 5) {
                console.warn(`[User ${vuId}] ⚠️  Still showing old instance ${currentInstanceId} (request ${state.requestCount}) - may be in transition`);
            }
        } else if (!currentInstanceId) {
            // System detected termination but hasn't reassigned yet
            terminationDetectedRate.add(1);
            reassignmentSuccessRate.add(0);
            if (state.requestCount <= 6) {
                console.warn(`[User ${vuId}] ⚠️  Termination detected but no reassignment yet (request ${state.requestCount})`);
            }
        } else {
            // No instance ID at all
            terminationDetectedRate.add(0);
            reassignmentSuccessRate.add(0);
        }
    }
    // Phase 3b: Already reassigned, just verify (requests 3-10)
    else if (state.requestCount >= 3 && state.requestCount <= 10 && state.instanceTerminated && state.reassigned) {
        // Already reassigned, just verify persistence
        if (currentInstanceId === state.instanceId) {
            // Persisting correctly - no action needed
        } else if (currentInstanceId && currentInstanceId !== state.instanceId) {
            console.error(`[User ${vuId}] ❌ Instance changed after reassignment: ${state.instanceId} -> ${currentInstanceId}`);
        }
    }
    // Phase 4: Verify persistence after reassignment (requests 11+)
    else if (state.requestCount > 10 && state.reassigned) {
        // Verify user still has the reassigned instance
        if (currentInstanceId === state.instanceId && currentUserName === state.userName) {
            // Instance persists correctly
        } else if (currentInstanceId && currentInstanceId !== state.instanceId) {
            console.error(`[User ${vuId}] ❌ Refresh ${state.requestCount - 1}: Instance changed after reassignment!`);
            console.error(`   Expected: ${state.instanceId}, Got: ${currentInstanceId}`);
        }
    }
    // Phase 5: Continue checking for reassignment if not yet reassigned (requests 11+)
    else if (state.requestCount > 10 && state.instanceTerminated && !state.reassigned) {
        // Still checking for reassignment (delayed reassignment)
        if (currentInstanceId && currentInstanceId !== state.oldInstanceId) {
            // Finally got reassigned (first time detection)
            terminationDetectedRate.add(1);
            reassignmentSuccessRate.add(1);
            state.instanceId = currentInstanceId;
            state.userName = currentUserName;
            state.ipAddress = currentIpAddress;
            state.reassigned = true;
            console.log(`[User ${vuId}] ✅ Reassigned to new instance: ${currentInstanceId} (was ${state.oldInstanceId}) - delayed reassignment`);
        } else if (!currentInstanceId) {
            // Still no instance - might be pool exhaustion
            if (state.requestCount === 11) {
                console.warn(`[User ${vuId}] ⚠️  Still no reassignment after 10 requests - may be pool exhaustion`);
            }
        }
    }
    // Phase 6: Normal persistence check for users without termination (second half of users)
    else if (state.requestCount > 1 && vuId > Math.floor(NUM_USERS / 2)) {
        if (currentInstanceId === state.instanceId && currentUserName === state.userName) {
            // Normal persistence - no issues
        } else if (currentInstanceId && currentInstanceId !== state.instanceId) {
            console.error(`[User ${vuId}] ❌ Unexpected instance change: ${state.instanceId} -> ${currentInstanceId}`);
        }
    }
    
    sleep(0.5 + Math.random() * 0.5);
}

export function handleSummary(data) {
    const summary = {
        timestamp: new Date().toISOString(),
        scenario: 'Scenario 3: Instance Termination and Reassignment',
        configuration: {
            user_management_url: USER_MANAGEMENT_URL,
            num_users: NUM_USERS,
            instance_pool_size: INSTANCE_POOL_SIZE,
        },
        metrics: {
            http_req_duration: data.metrics.http_req_duration,
            http_req_failed: data.metrics.http_req_failed,
            termination_detected_rate: data.metrics.termination_detected,
            reassignment_success_rate: data.metrics.reassignment_success,
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
    console.log(`   Termination Detection: ${(summary.metrics.termination_detected_rate.values.rate * 100).toFixed(1)}%`);
    console.log(`   Reassignment Success: ${(summary.metrics.reassignment_success_rate.values.rate * 100).toFixed(1)}%`);
    console.log(`   Avg Response Time: ${summary.metrics.http_req_duration.values.avg.toFixed(2)}ms`);
    console.log(`   P95 Response Time: ${summary.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms`);
    
    const reassignmentRate = summary.metrics.reassignment_success_rate.values.rate;
    const terminationRate = summary.metrics.termination_detected_rate.values.rate;
    
    if (reassignmentRate >= 0.7 && terminationRate >= 0.8) {
        console.log('\n✅ Business Logic: PASSED - System successfully handles instance termination and reassignment');
    } else if (reassignmentRate >= 0.5 && terminationRate >= 0.8) {
        console.log('\n⚠️  Business Logic: PARTIAL - Termination detected but some reassignments failed (may be pool exhaustion)');
        console.log('   Note: If pool size is too small, reassignment may fail due to no available instances');
    } else {
        console.log('\n❌ Business Logic: FAILED - Some terminations not properly handled');
        console.log(`   Termination Detection: ${(terminationRate * 100).toFixed(1)}%`);
        console.log(`   Reassignment Success: ${(reassignmentRate * 100).toFixed(1)}%`);
    }
    
    return {
        'stdout': JSON.stringify(summary, null, 2),
        'summary.json': JSON.stringify(summary, null, 2),
    };
}

