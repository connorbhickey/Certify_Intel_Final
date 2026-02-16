/**
 * DESKTOP-002: Auto-Update Testing Script
 *
 * This script provides a mock update server and test utilities for
 * validating the auto-update functionality of the Certify Intel desktop app.
 *
 * Usage:
 *   1. Start the mock server: node tests/test-auto-update.js server
 *   2. Run tests: node tests/test-auto-update.js test
 *   3. Start app in test mode: UPDATE_TEST_MODE=true npm start
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

// Mock update server configuration
const MOCK_SERVER_PORT = 9999;
const MOCK_VERSION = '99.0.0';  // Higher than current to trigger update

// Current version from package.json
const packagePath = path.join(__dirname, '..', 'package.json');
const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
const CURRENT_VERSION = packageJson.version;

console.log('=== Certify Intel Auto-Update Testing ===');
console.log(`Current version: ${CURRENT_VERSION}`);
console.log(`Mock version: ${MOCK_VERSION}`);
console.log('');

// Mock update manifest (latest.yml format for electron-updater)
function generateMockManifest() {
    return `version: ${MOCK_VERSION}
path: Certify_Intel_v${MOCK_VERSION}_Setup.exe
sha512: mockhash1234567890abcdef
releaseDate: '${new Date().toISOString()}'
releaseNotes: |
  ## Test Release v${MOCK_VERSION}
  - This is a test update
  - Auto-update testing validation
  - [TEST] Test release marker
`;
}

// Mock update server
function startMockServer() {
    const server = http.createServer((req, res) => {
        console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);

        // Handle update manifest requests
        if (req.url === '/latest.yml' || req.url === '/latest-mac.yml') {
            res.writeHead(200, { 'Content-Type': 'text/yaml' });
            res.end(generateMockManifest());
            console.log('  -> Served mock manifest');
            return;
        }

        // Handle download requests (return 404 to test error handling)
        if (req.url.includes('.exe') || req.url.includes('.dmg')) {
            res.writeHead(404);
            res.end('Mock server: Download not available in test mode');
            console.log('  -> Returned 404 for download (expected in test mode)');
            return;
        }

        // Handle health check
        if (req.url === '/health') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
                status: 'ok',
                mockVersion: MOCK_VERSION,
                currentVersion: CURRENT_VERSION
            }));
            return;
        }

        // Default 404
        res.writeHead(404);
        res.end('Not found');
    });

    server.listen(MOCK_SERVER_PORT, () => {
        console.log(`Mock update server running at http://localhost:${MOCK_SERVER_PORT}`);
        console.log('');
        console.log('Endpoints:');
        console.log(`  GET /latest.yml     - Returns mock update manifest (v${MOCK_VERSION})`);
        console.log('  GET /health         - Server health check');
        console.log('');
        console.log('To test auto-updates:');
        console.log('  1. Keep this server running');
        console.log('  2. In another terminal, run:');
        console.log('     UPDATE_TEST_MODE=true UPDATE_TEST_SERVER=http://localhost:9999 npm start');
        console.log('');
        console.log('Press Ctrl+C to stop the server');
    });
}

// Test runner
async function runTests() {
    console.log('Running auto-update tests...\n');

    const tests = [
        {
            name: 'Mock server health check',
            run: async () => {
                const res = await fetch(`http://localhost:${MOCK_SERVER_PORT}/health`);
                if (!res.ok) throw new Error('Server not responding');
                const data = await res.json();
                if (data.status !== 'ok') throw new Error('Invalid health response');
                return `Server OK, mock version: ${data.mockVersion}`;
            }
        },
        {
            name: 'Mock manifest available',
            run: async () => {
                const res = await fetch(`http://localhost:${MOCK_SERVER_PORT}/latest.yml`);
                if (!res.ok) throw new Error('Manifest not found');
                const text = await res.text();
                if (!text.includes(`version: ${MOCK_VERSION}`)) {
                    throw new Error('Invalid manifest version');
                }
                return 'Manifest contains correct version';
            }
        },
        {
            name: 'Version comparison',
            run: async () => {
                const current = CURRENT_VERSION.split('.').map(Number);
                const mock = MOCK_VERSION.split('.').map(Number);
                const isNewer = mock[0] > current[0] ||
                    (mock[0] === current[0] && mock[1] > current[1]) ||
                    (mock[0] === current[0] && mock[1] === current[1] && mock[2] > current[2]);
                if (!isNewer) throw new Error('Mock version should be higher than current');
                return `${MOCK_VERSION} > ${CURRENT_VERSION}`;
            }
        },
        {
            name: 'IPC handlers registered (requires running app)',
            run: async () => {
                // This test validates the code structure
                const mainPath = path.join(__dirname, '..', 'electron', 'main.js');
                const mainCode = fs.readFileSync(mainPath, 'utf8');

                const requiredHandlers = [
                    'update-test-check',
                    'update-test-download',
                    'update-test-install',
                    'update-get-version',
                    'update-get-status'
                ];

                const missing = requiredHandlers.filter(h => !mainCode.includes(h));
                if (missing.length > 0) {
                    throw new Error(`Missing IPC handlers: ${missing.join(', ')}`);
                }
                return `All ${requiredHandlers.length} IPC handlers present`;
            }
        },
        {
            name: 'Sentry integration present',
            run: async () => {
                const mainPath = path.join(__dirname, '..', 'electron', 'main.js');
                const mainCode = fs.readFileSync(mainPath, 'utf8');

                if (!mainCode.includes('initSentry')) {
                    throw new Error('Sentry initialization not found');
                }
                if (!mainCode.includes('@sentry/electron')) {
                    throw new Error('Sentry import not found');
                }
                return 'Sentry integration code present';
            }
        }
    ];

    let passed = 0;
    let failed = 0;

    for (const test of tests) {
        try {
            const result = await test.run();
            console.log(`  ✓ ${test.name}`);
            console.log(`    ${result}`);
            passed++;
        } catch (error) {
            console.log(`  ✗ ${test.name}`);
            console.log(`    Error: ${error.message}`);
            failed++;
        }
    }

    console.log('');
    console.log(`Results: ${passed} passed, ${failed} failed`);

    return failed === 0;
}

// Main entry point
const command = process.argv[2] || 'help';

switch (command) {
    case 'server':
        startMockServer();
        break;
    case 'test':
        runTests().then(success => {
            process.exit(success ? 0 : 1);
        });
        break;
    case 'help':
    default:
        console.log('Usage:');
        console.log('  node test-auto-update.js server  - Start mock update server');
        console.log('  node test-auto-update.js test    - Run auto-update tests');
        console.log('');
        console.log('Environment variables for app testing:');
        console.log('  UPDATE_TEST_MODE=true            - Enable test mode in app');
        console.log('  UPDATE_TEST_SERVER=<url>         - Mock server URL');
        console.log('  FORCE_UPDATE=true                - Force update check');
        console.log('  SENTRY_DSN=<dsn>                 - Sentry DSN for crash reporting');
        break;
}
