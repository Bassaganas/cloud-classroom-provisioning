/**
 * k6 Test: Scenario 2 - User Instance Persistence
 * 
 * Scenario: 20 instances, 10 users, each user requests an instance and then refreshes 10 times
 * Business Logic: Each user should be assigned the same instance and machine on every refresh
 * 
 * Prerequisites:
 * - 20 instances must be pre-created using prepare_instances.js or instance manager API
 * - Set USER_MANAGEMENT_URL environment variable
 * 
 * Usage:
 *   k6 run --vus 10 --iterations 110 k6_scenario2_user_persistence.js
 *   (10 users × 11 requests each = 110 iterations: 1 initial + 10 refreshes)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom metrics
const userPersistenceRate = new Rate('user_persistence'); // Same instance on refresh
const responseTime = new Trend('response_time');
const errorRate = new Rate('errors');
const refreshSuccessRate = new Rate('refresh_success');
const initialAssignmentRate = new Rate('initial_assignment'); // Track successful initial assignments

// Configuration
const USER_MANAGEMENT_URL = __ENV.USER_MANAGEMENT_URL || 'https://your-lambda-url.lambda-url.region.on.aws';
const NUM_USERS = parseInt(__ENV.NUM_USERS || '10');
const REFRESHES_PER_USER = parseInt(__ENV.REFRESHES_PER_USER || '10');
const INSTANCE_POOL_SIZE = parseInt(__ENV.INSTANCE_POOL_SIZE || '20');

// Test options
// Each VU will make (1 + REFRESHES_PER_USER) requests: 1 initial + N refreshes
// For large user counts, use shared-iterations to control total requests
export const options = {
    scenarios: {
        persistence_test: {
            executor: 'shared-iterations',
            vus: NUM_USERS,
            iterations: NUM_USERS * (REFRESHES_PER_USER + 1), // 1 initial + N refreshes per user
            maxDuration: '10m', // Allow up to 10 minutes for large user counts
        },
    },
    thresholds: {
        'http_req_duration': ['p(95)<5000'],      // 95% of requests under 5s
        'http_req_failed': ['rate<0.05'],          // Less than 5% errors
        'user_persistence': ['rate>0.95'],         // 95% of refreshes get same instance
        'refresh_success': ['rate>0.95'],         // 95% of refreshes succeed
        'initial_assignment': ['rate>0.99'],       // 99%+ of users get initial assignment (should be 100%)
    },
};

// Per-VU state to track user assignments
// Each VU represents one user
const vuState = {};

export default function () {
    const vuId = __VU; // Virtual User ID (1-10)
    const iter = __ITER; // Iteration number (0-10 for each VU)
    
    // Initialize state for this VU if first iteration
    if (!vuState[vuId]) {
        vuState[vuId] = {
            userName: null,
            instanceId: null,
            ipAddress: null,
            requestCount: 0,
        };
    }
    
    const state = vuState[vuId];
    state.requestCount++;
    
    // Prepare headers with cookies if this is a refresh (not first request)
    const headers = {
        'User-Agent': `k6-test-user-${vuId}`,
    };
    
    // If we have cookies from previous request, include them
    if (state.instanceId && state.userName) {
        headers['Cookie'] = [
            `testus_patronus_user=${encodeURIComponent(state.userName)}`,
            `testus_patronus_instance_id=${encodeURIComponent(state.instanceId)}`,
            state.ipAddress ? `testus_patronus_ip=${encodeURIComponent(state.ipAddress)}` : null,
        ].filter(Boolean).join('; ');
    }
    
    const startTime = Date.now();
    
    // Make request to user management endpoint
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
        sleep(1);
        return;
    }
    
    // Extract cookies from response
    // Lambda Function URLs return cookies in multiValueHeaders format
    // k6 may or may not parse them automatically, so we check multiple sources
    let cookies = {};
    
    // Method 1: Use k6's built-in cookie parsing (preferred)
    if (response.cookies && typeof response.cookies === 'object') {
        for (const cookieName in response.cookies) {
            const cookieArray = response.cookies[cookieName];
            if (Array.isArray(cookieArray) && cookieArray.length > 0) {
                // k6 stores cookies as array of objects with 'value' property
                cookies[cookieName] = cookieArray[0].value || cookieArray[0];
            } else if (cookieArray && typeof cookieArray === 'object' && cookieArray.value) {
                cookies[cookieName] = cookieArray.value;
            }
        }
    }
    
    // Method 2: Parse from Set-Cookie headers manually
    // Lambda Function URLs may expose Set-Cookie headers in different ways
    if (Object.keys(cookies).length === 0) {
        // Check all possible header variations
        const headerKeys = Object.keys(response.headers);
        let cookieHeaders = [];
        
        // Look for Set-Cookie headers (case-insensitive)
        for (const key of headerKeys) {
            const lowerKey = key.toLowerCase();
            if (lowerKey === 'set-cookie') {
                const value = response.headers[key];
                // Handle both string and array formats
                if (Array.isArray(value)) {
                    cookieHeaders.push(...value);
                } else if (typeof value === 'string') {
                    cookieHeaders.push(value);
                }
            }
        }
        
        // If no Set-Cookie found, check for comma-separated values
        if (cookieHeaders.length === 0) {
            const setCookieHeader = response.headers['Set-Cookie'] || 
                                   response.headers['set-cookie'] ||
                                   response.headers['Set-Cookie'.toLowerCase()];
            
            if (setCookieHeader) {
                if (Array.isArray(setCookieHeader)) {
                    cookieHeaders = setCookieHeader;
                } else if (typeof setCookieHeader === 'string') {
                    // Split by comma if multiple cookies in one header
                    cookieHeaders = setCookieHeader.split(',').map(s => s.trim());
                }
            }
        }
        
        // Parse all cookie headers
        if (cookieHeaders.length > 0) {
            cookies = parseCookies(cookieHeaders);
        }
    }
    
    let currentUserName = cookies['testus_patronus_user'];
    let currentInstanceId = cookies['testus_patronus_instance_id'];
    let currentIpAddress = cookies['testus_patronus_ip'];
    
    // Fallback: If cookies not parsed, try to extract from HTML
    if (!currentInstanceId || !currentUserName) {
        const body = response.body.toLowerCase();
        const bodyHasInstanceInfo = body.includes('instance') || body.includes('conference-user');
        
        if (bodyHasInstanceInfo) {
            // Try to extract instance_id from HTML (must start with 'i-')
            const instanceIdMatch = response.body.match(/instance[_-]?id["\s:=]+(i-[a-z0-9-]+)/i) || 
                                   response.body.match(/instanceId["\s:=]+(i-[a-z0-9-]+)/i) ||
                                   response.body.match(/["']instance[_-]?id["']\s*:\s*["'](i-[a-z0-9-]+)["']/i);
            const userNameMatch = response.body.match(/conference-user-([a-f0-9]{8})/i);
            
            if (instanceIdMatch && instanceIdMatch[1].startsWith('i-')) {
                currentInstanceId = instanceIdMatch[1];
            }
            if (userNameMatch) {
                currentUserName = `conference-user-${userNameMatch[1]}`;
            }
            
            // Debug logging for first request of each user
            if (state.requestCount === 1 && vuId <= 3) {
                if (!cookies['testus_patronus_user']) {
                    console.warn(`[User ${vuId}] ⚠️  Cookies not parsed, using HTML fallback`);
                    console.warn(`[User ${vuId}]   Cookies found: ${Object.keys(cookies).join(', ')}`);
                    console.warn(`[User ${vuId}]   HTML extraction: user=${currentUserName || 'none'}, instance=${currentInstanceId || 'none'}`);
                }
            }
        }
    }
    
    // First request: Store initial assignment
    if (state.requestCount === 1) {
        if (currentInstanceId && currentUserName) {
            state.userName = currentUserName;
            state.instanceId = currentInstanceId;
            state.ipAddress = currentIpAddress;
            
            refreshSuccessRate.add(1);
            initialAssignmentRate.add(1);
            console.log(`[User ${vuId}] ✅ Initial assignment: User ${currentUserName}, Instance ${currentInstanceId}`);
        } else {
            refreshSuccessRate.add(0);
            initialAssignmentRate.add(0);
            console.error(`[User ${vuId}] ❌ Initial request failed: No instance assigned`);
            console.error(`[User ${vuId}]   Cookies parsed: ${Object.keys(cookies).length > 0 ? Object.keys(cookies).join(', ') : 'none'}`);
            console.error(`[User ${vuId}]   Response status: ${response.status}`);
            console.error(`[User ${vuId}]   Response body preview: ${response.body.substring(0, 200)}`);
            console.error(`[User ${vuId}]   Extracted values: userName=${currentUserName || 'undefined'}, instanceId=${currentInstanceId || 'undefined'}`);
        }
    } else {
        // Subsequent requests: Verify persistence
        // Skip persistence check if initial assignment failed
        if (!state.instanceId || !state.userName) {
            refreshSuccessRate.add(0);
            console.error(`[User ${vuId}] ❌ Refresh ${state.requestCount - 1}: Cannot verify - no initial assignment`);
            return;
        }
        
        refreshSuccessRate.add(1);
        
        // Check if we got valid values (not undefined)
        const hasValidValues = currentInstanceId && currentUserName;
        
        const isPersistent = hasValidValues && check(response, {
            'same user name': () => currentUserName === state.userName,
            'same instance ID': () => currentInstanceId === state.instanceId,
            'same IP address': () => {
                // IP might be null/undefined initially, so allow for that
                if ((!state.ipAddress || state.ipAddress === 'unknown') && (!currentIpAddress || currentIpAddress === 'unknown')) return true;
                return currentIpAddress === state.ipAddress;
            },
        });
        
        if (isPersistent) {
            userPersistenceRate.add(1);
            console.log(`[User ${vuId}] ✅ Refresh ${state.requestCount - 1}: Same instance (${currentInstanceId})`);
        } else {
            userPersistenceRate.add(0);
            console.error(`[User ${vuId}] ❌ Refresh ${state.requestCount - 1}: Instance changed!`);
            console.error(`   Expected: User=${state.userName}, Instance=${state.instanceId}, IP=${state.ipAddress || 'none'}`);
            console.error(`   Got: User=${currentUserName || 'undefined'}, Instance=${currentInstanceId || 'undefined'}, IP=${currentIpAddress || 'none'}`);
            
            // Only update state if we got valid new values
            if (hasValidValues) {
                state.userName = currentUserName;
                state.instanceId = currentInstanceId;
                state.ipAddress = currentIpAddress;
            }
        }
    }
    
    // Small delay between requests (simulate user behavior)
    sleep(0.5 + Math.random() * 0.5); // 0.5-1.0 seconds
}

/**
 * Parse cookies from Set-Cookie header(s)
 * Handles both single string, array of strings, and array of arrays
 */
function parseCookies(cookieHeader) {
    const cookies = {};
    
    if (!cookieHeader) {
        return cookies;
    }
    
    // Normalize to array of cookie strings
    let cookieStrings = [];
    
    if (Array.isArray(cookieHeader)) {
        // Handle array of cookie strings
        for (const item of cookieHeader) {
            if (typeof item === 'string') {
                cookieStrings.push(item);
            } else if (Array.isArray(item)) {
                // Nested array (unlikely but handle it)
                cookieStrings.push(...item.filter(s => typeof s === 'string'));
            }
        }
    } else if (typeof cookieHeader === 'string') {
        // Single cookie string - split by comma if multiple cookies
        cookieStrings = cookieHeader.split(',').map(s => s.trim());
    }
    
    // Parse each cookie string
    for (const cookieString of cookieStrings) {
        if (!cookieString || typeof cookieString !== 'string') {
            continue;
        }
        
        // Split by semicolon and get the first part (name=value)
        // Format: "name=value; Path=/; Max-Age=604800; Secure; SameSite=Lax"
        const parts = cookieString.split(';');
        if (parts.length > 0) {
            const nameValuePart = parts[0].trim();
            const equalIndex = nameValuePart.indexOf('=');
            
            if (equalIndex > 0) {
                const name = nameValuePart.substring(0, equalIndex).trim();
                const value = nameValuePart.substring(equalIndex + 1).trim();
                
                if (name && value) {
                    try {
                        // Decode URL-encoded values
                        cookies[name] = decodeURIComponent(value);
                    } catch (e) {
                        // If decoding fails, use raw value
                        cookies[name] = value;
                    }
                }
            }
        }
    }
    
    return cookies;
}

/**
 * Summary function called at the end of the test
 */
export function handleSummary(data) {
    const summary = {
        timestamp: new Date().toISOString(),
        scenario: 'Scenario 2: User Instance Persistence',
        configuration: {
            user_management_url: USER_MANAGEMENT_URL,
            num_users: NUM_USERS,
            refreshes_per_user: REFRESHES_PER_USER,
            instance_pool_size: INSTANCE_POOL_SIZE,
        },
        metrics: {
            http_req_duration: data.metrics.http_req_duration,
            http_req_failed: data.metrics.http_req_failed,
            user_persistence_rate: data.metrics.user_persistence,
            refresh_success_rate: data.metrics.refresh_success,
            initial_assignment_rate: data.metrics.initial_assignment,
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
    console.log(`   Success Rate: ${(1 - summary.metrics.http_req_failed.values.rate) * 100}%`);
    console.log(`   Initial Assignments: ${(summary.metrics.initial_assignment_rate.values.rate * 100).toFixed(1)}% (${Math.round(summary.metrics.initial_assignment_rate.values.rate * NUM_USERS)}/${NUM_USERS} users)`);
    console.log(`   User Persistence: ${summary.metrics.user_persistence_rate.values.rate * 100}%`);
    console.log(`   Refresh Success: ${summary.metrics.refresh_success_rate.values.rate * 100}%`);
    console.log(`   Avg Response Time: ${summary.metrics.http_req_duration.values.avg.toFixed(2)}ms`);
    console.log(`   P95 Response Time: ${summary.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms`);
    
    // Business logic validation
    const initialAssignmentRate = summary.metrics.initial_assignment_rate.values.rate;
    const actualAssignedUsers = Math.round(initialAssignmentRate * NUM_USERS);
    const persistenceRate = summary.metrics.user_persistence_rate.values.rate;
    
    if (actualAssignedUsers < NUM_USERS) {
        console.log(`\n⚠️  WARNING: Only ${actualAssignedUsers}/${NUM_USERS} users got initial assignments!`);
        console.log(`   Check the instance manager UI to verify all instances are assigned.`);
    }
    
    if (initialAssignmentRate >= 0.99 && persistenceRate >= 0.95) {
        console.log('\n✅ Business Logic: PASSED - All users assigned and maintain same instance across refreshes');
    } else if (initialAssignmentRate < 0.99) {
        console.log(`\n❌ Business Logic: FAILED - Not all users got initial assignments (${actualAssignedUsers}/${NUM_USERS})`);
    } else {
        console.log('\n❌ Business Logic: FAILED - Some users got different instances on refresh');
    }
    
    return {
        'stdout': JSON.stringify(summary, null, 2),
        'summary.json': JSON.stringify(summary, null, 2),
    };
}

