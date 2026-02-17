/**
 * k6 Test: Scenario 1 - New User Instance Assignment (Conference Burst Pattern)
 * 
 * Scenario: Simulate a conference where users arrive within seconds of each other
 * - Users click the access link around the same time (burst arrival pattern)
 * - All users arrive within 1 minute (realistic conference scenario)
 * - Pattern: All VUs start simultaneously, sharing exactly INSTANCE_POOL_SIZE iterations
 * 
 * IMPORTANT: This test assumes SKIP_IAM_USER_CREATION=true
 * - IAM operations (CreateUser, CreateLoginProfile, AttachUserPolicy) are skipped
 * - Only EC2 instance assignment happens (much faster, no IAM rate limits)
 * - Allows realistic burst arrival (10-20 users/second) without throttling
 * 
 * Business Logic: All machines should be assigned to users, each new user gets an instance
 * 
 * Prerequisites:
 * - Instances must be pre-created using prepare_instances.py or instance manager API
 * - Set USER_MANAGEMENT_URL environment variable
 * - Set INSTANCE_POOL_SIZE environment variable (default: 20)
 * - Lambda must have SKIP_IAM_USER_CREATION=true environment variable set
 * 
 * Usage:
 *   k6 run -e INSTANCE_POOL_SIZE=100 k6_scenario1_new_users.js
 *   k6 run -e INSTANCE_POOL_SIZE=100 -e USER_MANAGEMENT_URL=https://... k6_scenario1_new_users.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom metrics
const newUserSuccessRate = new Rate('new_user_success');
const instanceAssignmentRate = new Rate('instance_assigned');
const responseTime = new Trend('response_time');
const errorRate = new Rate('errors');

// Configuration
const USER_MANAGEMENT_URL = __ENV.USER_MANAGEMENT_URL || 'https://your-lambda-url.lambda-url.region.on.aws';
const INSTANCE_POOL_SIZE = parseInt(__ENV.INSTANCE_POOL_SIZE || '20');
const EXPECTED_USERS = INSTANCE_POOL_SIZE; // Match users to instance pool size

// Conference scenario: Users arrive within seconds of each other (burst pattern)
// This simulates a real conference where users click the access link around the same time
// 
// IMPORTANT: With SKIP_IAM_USER_CREATION=true, IAM operations are skipped
// This means we can handle much higher rates without throttling
// - No IAM CreateUser, CreateLoginProfile, or AttachUserPolicy calls
// - Only EC2 instance assignment (much faster, no rate limits)
// - Users can arrive at 10-20 per second realistically
//
// Configuration:
// - All users arrive within 1 minute (realistic conference scenario)
// - Use shared-iterations to limit exactly to INSTANCE_POOL_SIZE
// - Ramp up VUs quickly to simulate burst arrival

// Burst arrival configuration (with IAM skipped)
// Since IAM is skipped, we can handle much higher rates
// Target: All 100 users arrive within 60 seconds (realistic conference burst)
const TARGET_DURATION_SECONDS = 60; // All users should arrive within 1 minute
const RAMP_UP_DURATION = 10; // Quick ramp-up to simulate users clicking link at same time

// Test options
// Use shared-iterations to limit exactly to INSTANCE_POOL_SIZE
// This ensures we don't make more requests than we have instances
export const options = {
    scenarios: {
        conference_burst: {
            executor: 'shared-iterations',
            vus: INSTANCE_POOL_SIZE, // One VU per instance
            iterations: INSTANCE_POOL_SIZE, // Exactly match instance pool size
            maxDuration: `${TARGET_DURATION_SECONDS + 30}s`, // Allow up to 90s total (60s target + 30s buffer)
            // Ramp up quickly to simulate burst arrival
            // All VUs start within RAMP_UP_DURATION seconds
            startTime: '0s',
        },
    },
    thresholds: {
        // With IAM skipped, we expect much better performance
        'http_req_duration': ['p(95)<10000'],     // 95% under 10s (no IAM operations, just EC2 assignment)
        'http_req_failed': ['rate<0.05'],          // Less than 5% errors (should be very low without IAM throttling)
        'new_user_success': ['rate>0.95'],         // 95%+ success rate (should be high without IAM throttling)
        'instance_assigned': ['rate>0.95'],        // 95%+ get instances (should be high, but may be lower if pool exhausted)
    },
};

// Shared state to track assignments across VUs
// Note: In k6, each VU is independent, so we'll track per-VU and aggregate
const userAssignments = {};

// Global counter to track total successful assignments
// This helps us understand if pool exhaustion occurred
let globalAssignmentCount = 0;

export default function () {
    const vuId = __VU; // Virtual User ID
    const iter = __ITER; // Iteration number (available in shared-iterations)
    
    // With shared-iterations, iterations are already limited to INSTANCE_POOL_SIZE
    // But we still check as a safety measure
    if (iter >= INSTANCE_POOL_SIZE) {
        return; // Skip this iteration - we've created enough users
    }
    
    // Simulate a new user (no cookies)
    const headers = {
        'User-Agent': `k6-test-user-${vuId}-${iter}`,
    };
    
    const startTime = Date.now();
    
    // Make request to user management endpoint (GET /)
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
        newUserSuccessRate.add(0);
        console.error(`[VU ${vuId}] Request failed: ${response.status} - ${response.body.substring(0, 200)}`);
        return;
    }
    
    newUserSuccessRate.add(1);
    
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
    
    // Debug: Log cookie detection (only for first few requests)
    if (iter < 3) {
        console.log(`[VU ${vuId}] Debug - Cookies found: ${Object.keys(cookies).join(', ')}`);
        console.log(`[VU ${vuId}] Debug - Response.cookies exists: ${!!response.cookies}`);
        if (response.cookies) {
            console.log(`[VU ${vuId}] Debug - Response.cookies keys: ${Object.keys(response.cookies).join(', ')}`);
            // Log cookie structure for debugging
            for (const key in response.cookies) {
                console.log(`[VU ${vuId}] Debug - Cookie '${key}': ${JSON.stringify(response.cookies[key])}`);
            }
        }
        // Log all headers that might contain cookies
        const cookieRelatedHeaders = Object.keys(response.headers).filter(k => 
            k.toLowerCase().includes('cookie') || k.toLowerCase().includes('set')
        );
        console.log(`[VU ${vuId}] Debug - Cookie-related headers: ${cookieRelatedHeaders.join(', ')}`);
        if (cookieRelatedHeaders.length > 0) {
            for (const header of cookieRelatedHeaders) {
                console.log(`[VU ${vuId}] Debug - Header '${header}': ${JSON.stringify(response.headers[header])}`);
            }
        }
    }
    
    // Check if we received user cookies
    const hasUserCookie = cookies['testus_patronus_user'] !== undefined;
    const hasInstanceCookie = cookies['testus_patronus_instance_id'] !== undefined;
    const hasIpCookie = cookies['testus_patronus_ip'] !== undefined;
    
    // Verify business logic: New user should get an instance assigned
    // Also check response body for instance information as fallback
    const body = response.body.toLowerCase();
    const bodyHasInstanceInfo = body.includes('instance') || body.includes('conference-user') || body.includes('ec2_ip');
    
    const instanceAssigned = check(response, {
        'user cookie set': () => hasUserCookie,
        'instance cookie set': () => hasInstanceCookie,
        'ip cookie set': () => hasIpCookie,
        'response contains user info': () => bodyHasInstanceInfo,
    });
    
    // If cookies not found but response has instance info, try to extract from HTML
    let instanceIdMatch = null;
    let userNameMatch = null;
    
    if (!hasInstanceCookie && bodyHasInstanceInfo) {
        // Try to extract instance_id from HTML response (fallback)
        // Look for patterns like: instance_id="i-1234567890abcdef0" or instanceId: "i-..."
        // Be more specific to avoid matching the word "cookie"
        // Match instance IDs that start with 'i-' (EC2 instance ID format)
        instanceIdMatch = response.body.match(/instance[_-]?id["\s:=]+(i-[a-z0-9-]+)/i) || 
                       response.body.match(/instanceId["\s:=]+(i-[a-z0-9-]+)/i) ||
                       response.body.match(/["']instance[_-]?id["']\s*:\s*["'](i-[a-z0-9-]+)["']/i);
        userNameMatch = response.body.match(/conference-user-([a-f0-9]{8})/i);
        
        if (instanceIdMatch || userNameMatch) {
            // Found instance info in HTML but not in cookies - this is a cookie parsing issue
            if (iter < 3) {
                console.warn(`[VU ${vuId}] ⚠️  Found instance info in HTML but cookies not parsed correctly`);
                console.warn(`[VU ${vuId}]   Instance ID in HTML: ${instanceIdMatch ? instanceIdMatch[1] : 'not found'}`);
                console.warn(`[VU ${vuId}]   User name in HTML: ${userNameMatch ? userNameMatch[1] : 'not found'}`);
            }
        }
    }
    
    // Determine if instance was assigned
    // Priority: cookies > HTML extraction
    // We consider it assigned if we have instance cookie OR if HTML contains valid instance info
    const hasInstanceInfo = hasInstanceCookie || (bodyHasInstanceInfo && instanceIdMatch && instanceIdMatch[1].startsWith('i-'));
    
    if (hasInstanceInfo) {
        instanceAssignmentRate.add(1);
        globalAssignmentCount++; // Track global assignment count
        
        // Extract values from cookies (preferred) or HTML fallback
        let userName = cookies['testus_patronus_user'];
        let instanceId = cookies['testus_patronus_instance_id'];
        let ipAddress = cookies['testus_patronus_ip'];
        
        // Fallback: Extract from HTML if cookies not parsed correctly
        if (!instanceId && instanceIdMatch && instanceIdMatch[1].startsWith('i-')) {
            instanceId = instanceIdMatch[1];
        }
        if (!userName && userNameMatch) {
            userName = `conference-user-${userNameMatch[1]}`;
        }
        
        // Log cookie parsing status for debugging (only first few)
        if (iter < 3) {
            if (hasInstanceCookie) {
                console.log(`[VU ${vuId}] ✅ Cookies parsed successfully from headers`);
            } else {
                console.warn(`[VU ${vuId}] ⚠️  Using HTML fallback - cookies not parsed from headers`);
            }
        }
        
        // Store assignment for this VU
        if (!userAssignments[vuId]) {
            userAssignments[vuId] = [];
        }
        userAssignments[vuId].push({
            userName: userName || 'unknown',
            instanceId: instanceId || 'unknown',
            ipAddress: ipAddress || 'unknown',
            timestamp: new Date().toISOString(),
        });
        
        // Log first few assignments and every 10th assignment
        if (iter < 5 || vuId <= 3 || globalAssignmentCount % 10 === 0) {
            console.log(`[VU ${vuId}] ✅ User ${userName || 'unknown'} assigned instance ${instanceId || 'unknown'} (IP: ${ipAddress || 'unknown'})`);
        }
    } else {
        instanceAssignmentRate.add(0);
        // Only log warning for first few requests to avoid spam
        // This typically happens when pool is exhausted
        if (iter < 5 || vuId <= 3 || globalAssignmentCount < 5) {
            console.warn(`[VU ${vuId}] ⚠️  User request succeeded but instance not assigned`);
            console.warn(`[VU ${vuId}]   Cookies: user=${hasUserCookie}, instance=${hasInstanceCookie}, ip=${hasIpCookie}`);
            console.warn(`[VU ${vuId}]   Body has instance info: ${bodyHasInstanceInfo}`);
            console.warn(`[VU ${vuId}]   Instance ID match: ${instanceIdMatch ? instanceIdMatch[1] : 'none'}`);
            if (globalAssignmentCount >= INSTANCE_POOL_SIZE) {
                console.warn(`[VU ${vuId}]   ⚠️  Pool may be exhausted (${globalAssignmentCount} assignments so far)`);
            }
        }
    }
    
    // Small random delay to simulate realistic user behavior
    // With shared-iterations, we add a small delay to avoid overwhelming the system
    sleep(0.2 + Math.random() * 0.3); // 0.2-0.5 seconds
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
    const totalRequests = data.metrics.http_reqs.values.count;
    const successRate = (1 - data.metrics.http_req_failed.values.rate) * 100;
    const instanceAssignmentRate = data.metrics.instance_assigned.values.rate * 100;
    const expectedAssignments = INSTANCE_POOL_SIZE;
    const actualAssignments = Math.round(totalRequests * data.metrics.instance_assigned.values.rate);
    
    const summary = {
        timestamp: new Date().toISOString(),
        scenario: 'Scenario 1: New User Instance Assignment',
        configuration: {
            user_management_url: USER_MANAGEMENT_URL,
            instance_pool_size: INSTANCE_POOL_SIZE,
            expected_users: EXPECTED_USERS,
            test_duration: `${TARGET_DURATION_SECONDS}s (target: all users within 1 minute)`,
            iam_skipped: true, // IAM operations are skipped, allowing faster rates
            ramp_up_duration: `${RAMP_UP_DURATION}s`,
        },
        metrics: {
            http_req_duration: data.metrics.http_req_duration,
            http_req_failed: data.metrics.http_req_failed,
            new_user_success_rate: data.metrics.new_user_success,
            instance_assignment_rate: data.metrics.instance_assigned,
            total_requests: totalRequests,
            total_errors: data.metrics.http_req_failed.values.rate * totalRequests,
            expected_instance_assignments: expectedAssignments,
            actual_instance_assignments: actualAssignments,
        },
        thresholds: {
            passed: Object.values(data.root_group.checks || {}).filter(c => c.passes > 0).length,
            failed: Object.values(data.root_group.checks || {}).filter(c => c.fails > 0).length,
        },
    };
    
    console.log('\n📊 Test Summary:');
    console.log(`   Total Requests: ${totalRequests}`);
    console.log(`   Expected Users: ${EXPECTED_USERS} (matches instance pool size)`);
    console.log(`   Success Rate: ${successRate.toFixed(1)}%`);
    console.log(`   New User Success: ${(data.metrics.new_user_success.values.rate * 100).toFixed(1)}%`);
    console.log(`   Instance Assignment: ${instanceAssignmentRate.toFixed(1)}%`);
    console.log(`   Expected Assignments: ${expectedAssignments}`);
    console.log(`   Actual Assignments: ${actualAssignments}`);
    console.log(`   Avg Response Time: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms`);
    console.log(`   P95 Response Time: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms`);
    
    // Business logic validation
    const assignmentRatio = actualAssignments / expectedAssignments;
    if (assignmentRatio >= 0.9) {
        console.log(`\n✅ Business Logic: PASSED - ${(assignmentRatio * 100).toFixed(1)}% of instances assigned`);
    } else {
        console.log(`\n⚠️  Business Logic: PARTIAL - Only ${(assignmentRatio * 100).toFixed(1)}% of instances assigned`);
        console.log(`   This may be due to IAM rate limiting or instances not being ready`);
    }
    
    return {
        'stdout': JSON.stringify(summary, null, 2),
        'summary.json': JSON.stringify(summary, null, 2),
    };
}

