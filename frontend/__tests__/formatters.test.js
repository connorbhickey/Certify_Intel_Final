/**
 * Tests for date and number formatting functions from testable-utils.js
 */
const { formatDate, getErrorMessage } = require('../testable-utils');

// ---------------------------------------------------------------------------
// formatDate
// ---------------------------------------------------------------------------
describe('formatDate', () => {
    test('formats ISO date string', () => {
        const result = formatDate('2026-02-14T12:00:00Z');
        expect(result).toMatch(/Feb/);
        expect(result).toMatch(/14/);
        expect(result).toMatch(/2026/);
    });

    test('formats date-only string', () => {
        const result = formatDate('2025-12-25');
        expect(result).toMatch(/Dec/);
        expect(result).toMatch(/25/);
        expect(result).toMatch(/2025/);
    });

    test('returns Unknown for null', () => {
        expect(formatDate(null)).toBe('Unknown');
    });

    test('returns Unknown for undefined', () => {
        expect(formatDate(undefined)).toBe('Unknown');
    });

    test('returns Unknown for empty string', () => {
        expect(formatDate('')).toBe('Unknown');
    });

    test('uses en-US locale format (Month Day, Year)', () => {
        const result = formatDate('2026-01-15T12:00:00Z');
        expect(result).toMatch(/Jan/);
        expect(result).toMatch(/15/);
        expect(result).toMatch(/2026/);
    });
});

// ---------------------------------------------------------------------------
// getErrorMessage
// ---------------------------------------------------------------------------
describe('getErrorMessage', () => {
    test('returns message for 400', () => {
        expect(getErrorMessage(400, '/api/test')).toBe(
            'Invalid request. Please check your input.'
        );
    });

    test('returns message for 401', () => {
        expect(getErrorMessage(401, '/api/test')).toBe(
            'Session expired. Please log in again.'
        );
    });

    test('returns message for 403', () => {
        expect(getErrorMessage(403, '/api/test')).toBe(
            'You do not have permission to access this resource.'
        );
    });

    test('returns message for 404', () => {
        expect(getErrorMessage(404, '/api/test')).toBe(
            'The requested resource was not found.'
        );
    });

    test('returns message for 429', () => {
        expect(getErrorMessage(429, '/api/test')).toBe(
            'Too many requests. Please wait a moment.'
        );
    });

    test('returns message for 500', () => {
        expect(getErrorMessage(500, '/api/test')).toBe(
            'Server error. Our team has been notified.'
        );
    });

    test('returns message for 502', () => {
        expect(getErrorMessage(502, '/api/test')).toBe(
            'Service temporarily unavailable. Please try again.'
        );
    });

    test('returns message for 503', () => {
        expect(getErrorMessage(503, '/api/test')).toBe(
            'Service is under maintenance. Please try again later.'
        );
    });

    test('returns generic message for unknown status', () => {
        expect(getErrorMessage(418, '/api/test')).toBe('An error occurred (418)');
    });
});
