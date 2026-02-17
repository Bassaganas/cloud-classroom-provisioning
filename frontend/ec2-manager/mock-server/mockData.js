// Mock data for EC2 Instance Manager API

// Default password for mock authentication
export const MOCK_PASSWORD = 'test123'

// Workshop templates
export const workshopTemplates = {
  fellowship: {
    workshop_name: 'fellowship',
    instance_type: 't3.medium',
    app_port: 8080,
    ami_id: 'ami-0ae57f93cfd6030ca',
    user_data_base64: 'mock_user_data'
  },
  testus_patronus: {
    workshop_name: 'testus_patronus',
    instance_type: 't3.medium',
    app_port: 8080,
    ami_id: 'ami-0ae57f93cfd6030ca',
    user_data_base64: 'mock_user_data'
  }
}

// Timeout settings for workshops
export const timeoutSettings = {
  fellowship: {
    stop_timeout: 4,
    terminate_timeout: 20,
    hard_terminate_timeout: 45,
    admin_cleanup_days: 7
  },
  testus_patronus: {
    stop_timeout: 4,
    terminate_timeout: 20,
    hard_terminate_timeout: 45,
    admin_cleanup_days: 7
  }
}

// In-memory state storage
export const state = {
  instances: [],
  tutorialSessions: {},
  instanceCounter: 1,
  sessionCounter: 1
}

// Initialize with some sample data
export function initializeMockData() {
  // Sample instances
  state.instances = [
    {
      instance_id: 'i-1234567890abcdef0',
      instance_type: 't3.medium',
      state: 'running',
      public_ip: '54.123.45.67',
      private_ip: '10.0.1.50',
      type: 'pool',
      workshop: 'fellowship',
      tutorial_session_id: 'tut1',
      assigned_to: null,
      created_at: new Date(Date.now() - 86400000).toISOString(),
      https_url: null,
      cleanup_days: null
    },
    {
      instance_id: 'i-0987654321fedcba0',
      instance_type: 't3.medium',
      state: 'running',
      public_ip: '54.123.45.68',
      private_ip: '10.0.1.51',
      type: 'admin',
      workshop: 'fellowship',
      tutorial_session_id: 'tut1',
      assigned_to: 'student1',
      created_at: new Date(Date.now() - 172800000).toISOString(),
      https_url: 'https://fellowship-instance1.testingfantasy.com',
      cleanup_days: 7
    },
    {
      instance_id: 'i-abcdef1234567890',
      instance_type: 't3.medium',
      state: 'stopped',
      public_ip: '54.123.45.69',
      private_ip: '10.0.1.52',
      type: 'pool',
      workshop: 'testus_patronus',
      tutorial_session_id: 'tutorial_wetest_athenes',
      assigned_to: null,
      created_at: new Date(Date.now() - 259200000).toISOString(),
      https_url: null,
      cleanup_days: null
    },
    {
      instance_id: 'i-fedcba0987654321',
      instance_type: 't3.medium',
      state: 'running',
      public_ip: '54.123.45.70',
      private_ip: '10.0.1.53',
      type: 'pool',
      workshop: 'testus_patronus',
      tutorial_session_id: 'tutorial_wetest_athenes',
      assigned_to: null,
      created_at: new Date(Date.now() - 3600000).toISOString(),
      https_url: null,
      cleanup_days: null
    }
  ]

  // Sample tutorial sessions
  state.tutorialSessions = {
    fellowship: [
      {
        session_id: 'tut1',
        workshop_name: 'fellowship',
        created_at: new Date(Date.now() - 86400000).toISOString(),
        status: 'active',
        expected_instance_count: 2,
        actual_instance_count: 2
      }
    ],
    testus_patronus: [
      {
        session_id: 'tutorial_wetest_athenes',
        workshop_name: 'testus_patronus',
        created_at: new Date(Date.now() - 259200000).toISOString(),
        status: 'active',
        expected_instance_count: 2,
        actual_instance_count: 2
      },
      {
        session_id: 'tp_tut1_prueba',
        workshop_name: 'testus_patronus',
        created_at: new Date(Date.now() - 172800000).toISOString(),
        status: 'active',
        expected_instance_count: 1,
        actual_instance_count: 1
      }
    ]
  }

  state.instanceCounter = 5
  state.sessionCounter = 3
}

// Helper function to generate instance ID
export function generateInstanceId() {
  return `i-${Math.random().toString(36).substring(2, 18)}`
}

// Helper function to generate IP address
export function generateIP() {
  return `54.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`
}
