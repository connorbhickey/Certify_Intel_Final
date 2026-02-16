/**
 * Tests for pure utility functions from testable-utils.js
 */
const {
    escapeHtml,
    truncateText,
    extractDomain,
    debounce,
    getScoreColor,
    getMatchScore,
} = require('../testable-utils');

// ---------------------------------------------------------------------------
// escapeHtml
// ---------------------------------------------------------------------------
describe('escapeHtml', () => {
    test('escapes HTML special characters', () => {
        expect(escapeHtml('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert("xss")&lt;/script&gt;'
        );
    });

    test('escapes ampersands', () => {
        expect(escapeHtml('Tom & Jerry')).toBe('Tom &amp; Jerry');
    });

    test('escapes angle brackets', () => {
        expect(escapeHtml('a < b > c')).toBe('a &lt; b &gt; c');
    });

    test('returns empty string for null', () => {
        expect(escapeHtml(null)).toBe('');
    });

    test('returns empty string for undefined', () => {
        expect(escapeHtml(undefined)).toBe('');
    });

    test('returns empty string for empty string', () => {
        expect(escapeHtml('')).toBe('');
    });

    test('passes through safe text unchanged', () => {
        expect(escapeHtml('Hello World')).toBe('Hello World');
    });
});

// ---------------------------------------------------------------------------
// truncateText
// ---------------------------------------------------------------------------
describe('truncateText', () => {
    test('truncates text longer than maxLength', () => {
        expect(truncateText('Hello World Test', 5)).toBe('Hello...');
    });

    test('does not truncate text shorter than maxLength', () => {
        expect(truncateText('Hi', 10)).toBe('Hi');
    });

    test('does not truncate text equal to maxLength', () => {
        expect(truncateText('Hello', 5)).toBe('Hello');
    });

    test('returns em dash for null', () => {
        expect(truncateText(null, 10)).toBe('\u2014');
    });

    test('returns em dash for undefined', () => {
        expect(truncateText(undefined, 10)).toBe('\u2014');
    });

    test('returns em dash for empty string', () => {
        expect(truncateText('', 10)).toBe('\u2014');
    });

    test('converts numbers to string', () => {
        expect(truncateText(12345, 3)).toBe('123...');
    });
});

// ---------------------------------------------------------------------------
// extractDomain
// ---------------------------------------------------------------------------
describe('extractDomain', () => {
    test('extracts domain from full URL', () => {
        expect(extractDomain('https://www.example.com/path')).toBe('example.com');
    });

    test('strips www prefix', () => {
        expect(extractDomain('https://www.google.com')).toBe('google.com');
    });

    test('handles URLs without www', () => {
        expect(extractDomain('https://api.example.com')).toBe('api.example.com');
    });

    test('returns empty string for invalid URL', () => {
        expect(extractDomain('not-a-url')).toBe('');
    });

    test('returns empty string for empty string', () => {
        expect(extractDomain('')).toBe('');
    });
});

// ---------------------------------------------------------------------------
// debounce
// ---------------------------------------------------------------------------
describe('debounce', () => {
    beforeEach(() => {
        jest.useFakeTimers();
    });

    afterEach(() => {
        jest.useRealTimers();
    });

    test('delays function execution', () => {
        const fn = jest.fn();
        const debounced = debounce(fn, 300);

        debounced();
        expect(fn).not.toHaveBeenCalled();

        jest.advanceTimersByTime(300);
        expect(fn).toHaveBeenCalledTimes(1);
    });

    test('resets delay on subsequent calls', () => {
        const fn = jest.fn();
        const debounced = debounce(fn, 300);

        debounced();
        jest.advanceTimersByTime(200);
        debounced(); // reset the timer
        jest.advanceTimersByTime(200);
        expect(fn).not.toHaveBeenCalled();

        jest.advanceTimersByTime(100);
        expect(fn).toHaveBeenCalledTimes(1);
    });

    test('passes arguments to the original function', () => {
        const fn = jest.fn();
        const debounced = debounce(fn, 100);

        debounced('a', 'b');
        jest.advanceTimersByTime(100);
        expect(fn).toHaveBeenCalledWith('a', 'b');
    });
});

// ---------------------------------------------------------------------------
// getScoreColor
// ---------------------------------------------------------------------------
describe('getScoreColor', () => {
    test('returns green for scores >= 70', () => {
        expect(getScoreColor(70)).toBe('#22c55e');
        expect(getScoreColor(100)).toBe('#22c55e');
    });

    test('returns orange for scores >= 50 and < 70', () => {
        expect(getScoreColor(50)).toBe('#f59e0b');
        expect(getScoreColor(69)).toBe('#f59e0b');
    });

    test('returns red for scores < 50', () => {
        expect(getScoreColor(0)).toBe('#ef4444');
        expect(getScoreColor(49)).toBe('#ef4444');
    });
});

// ---------------------------------------------------------------------------
// getMatchScore
// ---------------------------------------------------------------------------
describe('getMatchScore', () => {
    test('returns match_score when present', () => {
        expect(getMatchScore({ match_score: 85 })).toBe(85);
    });

    test('falls back to qualification_score', () => {
        expect(getMatchScore({ qualification_score: 72 })).toBe(72);
    });

    test('falls back to relevance_score', () => {
        expect(getMatchScore({ relevance_score: 60 })).toBe(60);
    });

    test('falls back to score', () => {
        expect(getMatchScore({ score: 55 })).toBe(55);
    });

    test('returns null when no score fields exist', () => {
        expect(getMatchScore({})).toBeNull();
    });

    test('prefers match_score over others', () => {
        expect(getMatchScore({
            match_score: 90,
            qualification_score: 80,
            relevance_score: 70,
            score: 60
        })).toBe(90);
    });

    test('handles zero scores correctly', () => {
        expect(getMatchScore({ match_score: 0 })).toBe(0);
    });
});
