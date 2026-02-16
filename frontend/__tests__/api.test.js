/**
 * Tests for API-related utilities from testable-utils.js
 */
const { APIError, getErrorMessage } = require('../testable-utils');

// ---------------------------------------------------------------------------
// APIError
// ---------------------------------------------------------------------------
describe('APIError', () => {
    test('creates error with correct properties', () => {
        const err = new APIError(404, 'Not Found', '/api/competitors/999');
        expect(err).toBeInstanceOf(Error);
        expect(err).toBeInstanceOf(APIError);
        expect(err.name).toBe('APIError');
        expect(err.status).toBe(404);
        expect(err.message).toBe('Not Found');
        expect(err.endpoint).toBe('/api/competitors/999');
    });

    test('has a stack trace', () => {
        const err = new APIError(500, 'Server Error', '/api/test');
        expect(err.stack).toBeDefined();
    });

    test('is catchable as Error', () => {
        expect(() => {
            throw new APIError(400, 'Bad Request', '/api/test');
        }).toThrow(Error);
    });

    test('is catchable by name check', () => {
        try {
            throw new APIError(401, 'Unauthorized', '/api/secret');
        } catch (e) {
            expect(e.name).toBe('APIError');
            expect(e.status).toBe(401);
        }
    });

    test('preserves endpoint information', () => {
        const err = new APIError(429, 'Rate limited', '/api/agents/dashboard');
        expect(err.endpoint).toBe('/api/agents/dashboard');
    });
});

// ---------------------------------------------------------------------------
// getErrorMessage mapping (API context)
// ---------------------------------------------------------------------------
describe('getErrorMessage (API context)', () => {
    test('maps timeout statuses correctly', () => {
        expect(getErrorMessage(408, '/api/long-task')).toMatch(/timed out/i);
        expect(getErrorMessage(504, '/api/long-task')).toMatch(/timed out/i);
    });

    test('maps server errors correctly', () => {
        expect(getErrorMessage(500, '/api/test')).toMatch(/server error/i);
    });

    test('maps client errors correctly', () => {
        expect(getErrorMessage(400, '/api/test')).toMatch(/input/i);
    });
});
