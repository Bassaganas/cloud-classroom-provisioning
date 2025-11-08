/**
 * Helper script to prepare instance pool for k6 tests
 * 
 * This script uses the Instance Manager Lambda API to create a pool of instances
 * that will be used by the k6 test scenarios.
 * 
 * Usage:
 *   node prepare_instances.js --url <INSTANCE_MANAGER_URL> --count 20 --type pool
 *   node prepare_instances.js --url <INSTANCE_MANAGER_URL> --count 100 --type pool --password <PASSWORD>
 */

import http from 'k6/http';
import { check } from 'k6';

// Configuration from environment or command line
const INSTANCE_MANAGER_URL = __ENV.INSTANCE_MANAGER_URL || 'https://your-instance-manager-url.lambda-url.region.on.aws';
const INSTANCE_COUNT = parseInt(__ENV.INSTANCE_COUNT || '20');
const INSTANCE_TYPE = __ENV.INSTANCE_TYPE || 'pool';
const PASSWORD = __ENV.INSTANCE_MANAGER_PASSWORD || '';

export const options = {
    vus: 1,
    iterations: 1,
};

export default function () {
    console.log(`\n🔧 Preparing ${INSTANCE_COUNT} ${INSTANCE_TYPE} instances...`);
    console.log(`   Instance Manager URL: ${INSTANCE_MANAGER_URL}\n`);
    
    // Step 1: Authenticate if password is required
    let authToken = null;
    if (PASSWORD) {
        console.log('🔐 Authenticating...');
        const authResponse = http.post(
            `${INSTANCE_MANAGER_URL}/login`,
            JSON.stringify({ password: PASSWORD }),
            { headers: { 'Content-Type': 'application/json' } }
        );
        
        const authSuccess = check(authResponse, {
            'authentication successful': (r) => r.status === 200,
        });
        
        if (!authSuccess) {
            console.error('❌ Authentication failed!');
            return;
        }
        
        // Extract auth token from response (if applicable)
        // Note: The instance manager might use cookies or headers for auth
        // Adjust based on actual implementation
        console.log('✅ Authentication successful');
    }
    
    // Step 2: Create instances
    console.log(`\n📦 Creating ${INSTANCE_COUNT} instances...`);
    
    const createPayload = {
        count: INSTANCE_COUNT,
        type: INSTANCE_TYPE,
    };
    
    const headers = {
        'Content-Type': 'application/json',
    };
    
    // Include auth cookie if we have one
    if (authToken) {
        headers['Cookie'] = `auth_token=${authToken}`;
    }
    
    const createResponse = http.post(
        `${INSTANCE_MANAGER_URL}/create`,
        JSON.stringify(createPayload),
        { headers: headers }
    );
    
    const createSuccess = check(createResponse, {
        'create request successful': (r) => r.status === 200,
        'response has body': (r) => r.body && r.body.length > 0,
    });
    
    if (!createSuccess) {
        console.error(`❌ Failed to create instances: ${createResponse.status}`);
        console.error(`   Response: ${createResponse.body.substring(0, 500)}`);
        return;
    }
    
    let responseData;
    try {
        responseData = JSON.parse(createResponse.body);
    } catch (e) {
        console.error('❌ Failed to parse response JSON');
        console.error(`   Response: ${createResponse.body.substring(0, 500)}`);
        return;
    }
    
    if (responseData.success) {
        console.log(`✅ Successfully created ${INSTANCE_COUNT} ${INSTANCE_TYPE} instances`);
        if (responseData.instances) {
            console.log(`   Instance IDs: ${responseData.instances.map(i => i.instance_id).join(', ')}`);
        }
    } else {
        console.error(`❌ Create request returned success=false: ${responseData.error || 'Unknown error'}`);
        return;
    }
    
    // Step 3: Verify instances were created
    console.log('\n🔍 Verifying instances...');
    
    const listResponse = http.get(`${INSTANCE_MANAGER_URL}/list`, { headers: headers });
    
    const listSuccess = check(listResponse, {
        'list request successful': (r) => r.status === 200,
    });
    
    if (listSuccess) {
        try {
            const listData = JSON.parse(listResponse.body);
            if (listData.instances) {
                const poolInstances = listData.instances.filter(
                    i => i.type === INSTANCE_TYPE && i.status === 'available'
                );
                console.log(`✅ Found ${poolInstances.length} available ${INSTANCE_TYPE} instances`);
                
                if (poolInstances.length < INSTANCE_COUNT) {
                    console.warn(`⚠️  Warning: Expected ${INSTANCE_COUNT} instances, found ${poolInstances.length}`);
                }
            }
        } catch (e) {
            console.warn('⚠️  Could not parse list response');
        }
    }
    
    console.log('\n✅ Instance pool preparation complete!');
    console.log('   You can now run the k6 test scenarios.\n');
}

