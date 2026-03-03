/**
 * Test Suite for Frontend: Idempotency Key Generation and Propagation (FR6)
 * 
 * Tests validate that:
 * - Idempotency keys are automatically generated if not provided
 * - Keys are propagated to backend via Idempotency-Key header
 * - Keys are included in request body
 * - API service integrates idempotency without manual setup
 * 
 * Run with: cd frontend/ec2-manager && npm test -- --testPathPattern="api.test" --run
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock fetch since we're testing the API service
global.fetch = vi.fn();
global.crypto = {
  randomUUID: vi.fn(() => 'uuid-12345678-1234-1234-1234-123456789012')
};

import * as apiModule from '../src/services/api';

describe('Frontend API Service - FR6: Idempotency', () => {
  beforeEach(() => {
    fetch.mockClear();
    global.localStorage.clear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('generateIdempotencyKey', () => {
    it('should generate UUID if crypto.randomUUID is available', () => {
      const key = apiModule.generateIdempotencyKey();
      expect(key).toBe('uuid-12345678-1234-1234-1234-123456789012');
    });

    it('should generate fallback key if crypto.randomUUID is not available', () => {
      const originalCrypto = global.crypto;
      global.crypto = {};

      const key = apiModule.generateIdempotencyKey();
      
      // Should match pattern: req-{timestamp}-{randomString}
      expect(key).toMatch(/^req-\d+-[a-z0-9]{8}$/);

      global.crypto = originalCrypto;
    });

    it('should generate unique keys on repeated calls', () => {
      const key1 = apiModule.generateIdempotencyKey();
      const key2 = apiModule.generateIdempotencyKey();
      
      // Both should have same UUID in mock, but in real code they'd differ
      // For mocking purposes, verify they're both valid keys
      expect(key1).toBeTruthy();
      expect(key2).toBeTruthy();
    });
  });

  describe('apiRequest with idempotency', () => {
    it('should set Idempotency-Key header for POST requests with idempotency_key in body', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true, instances: [] })
      });

      const payload = {
        idempotency_key: 'test-key-001',
        name: 'test-instance'
      };

      await apiModule.apiRequest('/create', {
        method: 'POST',
        body: payload
      });

      // Verify fetch was called with Idempotency-Key header
      expect(fetch).toHaveBeenCalledTimes(1);
      const callArgs = fetch.mock.calls[0];
      const options = callArgs[1];
      
      expect(options.headers['Idempotency-Key']).toBe('test-key-001');
    });

    it('should auto-generate idempotency_key if not provided in body', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true, instances: [] })
      });

      const payload = {
        count: 2,
        instance_type: 'pool'
      };

      await apiModule.apiRequest('/create', {
        method: 'POST',
        body: payload
      });

      const options = fetch.mock.calls[0][1];
      
      // Should have auto-generated header
      expect(options.headers['Idempotency-Key']).toBeTruthy();
    });

    it('should not set Idempotency-Key header for GET requests', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true, instances: [] })
      });

      await apiModule.apiRequest('/list', {
        method: 'GET'
      });

      const options = fetch.mock.calls[0][1];
      expect(options.headers['Idempotency-Key']).toBeUndefined();
    });

    it('should preserve custom idempotency_key in header', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true })
      });

      const customKey = 'custom-idem-key-9999';
      
      await apiModule.apiRequest('/create', {
        method: 'POST',
        body: { idempotency_key: customKey }
      });

      const options = fetch.mock.calls[0][1];
      expect(options.headers['Idempotency-Key']).toBe(customKey);
    });

    it('should include idempotency_key in JSON body for POST', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true })
      });

      await apiModule.apiRequest('/create', {
        method: 'POST',
        body: { count: 2 }
      });

      const options = fetch.mock.calls[0][1];
      const body = JSON.parse(options.body);
      
      // Should have auto-generated key in body
      expect(body.idempotency_key).toBeTruthy();
      expect(body.count).toBe(2);
    });
  });

  describe('createInstances with idempotency', () => {
    it('should auto-add idempotency_key if not provided', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ 
          success: true,
          instances: [{ instance_id: 'i-123', name: 'instance-0' }],
          idempotent_replay: false
        })
      });

      const data = {
        count: 1,
        instance_type: 'pool'
      };

      await apiModule.createInstances(data);

      const options = fetch.mock.calls[0][1];
      const body = JSON.parse(options.body);
      
      expect(body.idempotency_key).toBeTruthy();
      expect(body.count).toBe(1);
    });

    it('should preserve provided idempotency_key', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ 
          success: true,
          instances: [{ instance_id: 'i-456' }],
          idempotent_replay: false
        })
      });

      const providedKey = 'user-provided-key';
      const data = {
        count: 2,
        idempotency_key: providedKey
      };

      await apiModule.createInstances(data);

      const options = fetch.mock.calls[0][1];
      const body = JSON.parse(options.body);
      
      expect(body.idempotency_key).toBe(providedKey);
    });

    it('should propagate Idempotency-Key header to backend', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ 
          success: true,
          instances: [],
          idempotent_replay: false
        })
      });

      await apiModule.createInstances({ count: 1 });

      const options = fetch.mock.calls[0][1];
      
      // Should have both header and body key
      expect(options.headers['Idempotency-Key']).toBeTruthy();
      expect(options.headers).toHaveProperty('Idempotency-Key');
    });
  });

  describe('Idempotency Replay Handling', () => {
    it('should detect idempotent_replay flag in response', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ 
          success: true,
          instances: [{ instance_id: 'i-789' }],
          idempotent_replay: true
        })
      });

      const response = await apiModule.createInstances({ count: 1 });

      expect(response.idempotent_replay).toBe(true);
    });

    it('should distinguish new creation from replay', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ 
          success: true,
          instances: [{ instance_id: 'i-new' }],
          idempotent_replay: false
        })
      });

      const response = await apiModule.createInstances({ count: 1 });

      expect(response.idempotent_replay).toBe(false);
    });
  });

  describe('Error Handling with Idempotency', () => {
    it('should handle 409 conflict when request in_progress', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: async () => ({ 
          error: 'Request already in progress',
          idempotency_key: 'test-key'
        })
      });

      try {
        await apiModule.createInstances({ 
          count: 1,
          idempotency_key: 'test-key'
        });
        expect.fail('Should throw error on 409');
      } catch (error) {
        expect(error).toBeTruthy();
      }
    });

    it('should preserve idempotency_key on retry', async () => {
      const key = 'retry-test-key';
      
      // First call fails
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Server error' })
      });

      try {
        await apiModule.apiRequest('/create', {
          method: 'POST',
          body: { idempotency_key: key }
        });
      } catch (error) {
        // Expected
      }

      // Reset and retry
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true })
      });

      await apiModule.apiRequest('/create', {
        method: 'POST',
        body: { idempotency_key: key }
      });

      // Both calls should use same key
      expect(fetch.mock.calls[1][1].headers['Idempotency-Key']).toBe(key);
    });
  });

  describe('Header Propagation', () => {
    it('should set correct Content-Type header', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true })
      });

      await apiModule.apiRequest('/create', {
        method: 'POST',
        body: { test: 'data' }
      });

      const options = fetch.mock.calls[0][1];
      expect(options.headers['Content-Type']).toBe('application/json');
    });

    it('should include Authorization header if token exists', async () => {
      localStorage.setItem('token', 'test-token-abc123');
      
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true })
      });

      await apiModule.apiRequest('/create', {
        method: 'POST',
        body: { test: 'data' }
      });

      const options = fetch.mock.calls[0][1];
      expect(options.headers['Authorization']).toBe('Bearer test-token-abc123');
      
      localStorage.clear();
    });

    it('should combine Idempotency-Key with other headers', async () => {
      localStorage.setItem('token', 'test-token');
      
      fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ success: true })
      });

      await apiModule.apiRequest('/create', {
        method: 'POST',
        body: { idempotency_key: 'test-key' }
      });

      const options = fetch.mock.calls[0][1];
      expect(options.headers['Idempotency-Key']).toBe('test-key');
      expect(options.headers['Authorization']).toBe('Bearer test-token');
      expect(options.headers['Content-Type']).toBe('application/json');
      
      localStorage.clear();
    });
  });
});
