/**
 * Certify Intel - Global State Module
 * Shared state variables accessed by multiple page functions.
 */

// ============== Core Data State ==============
export let competitors = [];
export let changes = [];
export let stats = {};

// ============== Chart Instances ==============
export let threatChart = null;
export let topThreatsChart = null;
export let threatTrendChart = null;
export let marketShareChart = null;

// ============== WebSocket State ==============
export let wsConnection = null;
export let wsReconnectAttempts = 0;
export const MAX_RECONNECT_ATTEMPTS = 5;
export const RECONNECT_DELAY = 3000;

// ============== Polling Flags ==============
export let _refreshPolling = false;
export let _refreshPollInterval = null;
export let _newsFetchProgressKey = null;
export let _newsFetchPolling = false;
export let _discoveryTaskId = null;
export let _discoveryPolling = false;
export let _discoveryResult = null;
export let _discoverySummary = null;
export let _discoveryError = null;
export let _verifyPollInterval = null;
export let _verifyPolling = false;
export let _verifyLastProgress = null;

// ============== UI State ==============
export let loadingOverlay = null;
export let commandPaletteOpen = false;
export let keyboardHelpOpen = false;
export let goPending = false;
export let bulkSelectedItems = new Set();
export let bulkActionBarVisible = false;
export let lastDataRefresh = null;
export let corporateProfile = null;
export let discoveredCompetitors = [];
export let currentNewsPage = 1;
export const NEWS_PAGE_SIZE = 25;
export let newsFeedData = [];
export let newsRefreshInProgress = false;

// ============== Caches ==============
export const _battlecardStrategyCache = {};
export const _chatWidgetRegistry = {};
export const _promptCache = {};
export const sourceCache = {};
export const manualEditCache = {};
export const _sourceVerificationCache = {};

// ============== Setters (for mutable state) ==============
export function setCompetitors(val) { competitors = val; }
export function setChanges(val) { changes = val; }
export function setStats(val) { stats = val; }
export function setThreatChart(val) { threatChart = val; }
export function setTopThreatsChart(val) { topThreatsChart = val; }
export function setThreatTrendChart(val) { threatTrendChart = val; }
export function setMarketShareChart(val) { marketShareChart = val; }
export function setWsConnection(val) { wsConnection = val; }
export function setWsReconnectAttempts(val) { wsReconnectAttempts = val; }
export function setRefreshPolling(val) { _refreshPolling = val; }
export function setRefreshPollInterval(val) { _refreshPollInterval = val; }
export function setNewsFetchProgressKey(val) { _newsFetchProgressKey = val; }
export function setNewsFetchPolling(val) { _newsFetchPolling = val; }
export function setDiscoveryTaskId(val) { _discoveryTaskId = val; }
export function setDiscoveryPolling(val) { _discoveryPolling = val; }
export function setDiscoveryResult(val) { _discoveryResult = val; }
export function setDiscoverySummary(val) { _discoverySummary = val; }
export function setDiscoveryError(val) { _discoveryError = val; }
export function setVerifyPollInterval(val) { _verifyPollInterval = val; }
export function setVerifyPolling(val) { _verifyPolling = val; }
export function setVerifyLastProgress(val) { _verifyLastProgress = val; }
export function setLoadingOverlay(val) { loadingOverlay = val; }
export function setCommandPaletteOpen(val) { commandPaletteOpen = val; }
export function setKeyboardHelpOpen(val) { keyboardHelpOpen = val; }
export function setGoPending(val) { goPending = val; }
export function setBulkSelectedItems(val) { bulkSelectedItems = val; }
export function setBulkActionBarVisible(val) { bulkActionBarVisible = val; }
export function setLastDataRefresh(val) { lastDataRefresh = val; }
export function setCorporateProfile(val) { corporateProfile = val; }
export function setDiscoveredCompetitors(val) { discoveredCompetitors = val; }
export function setCurrentNewsPage(val) { currentNewsPage = val; }
export function setNewsFeedData(val) { newsFeedData = val; }
export function setNewsRefreshInProgress(val) { newsRefreshInProgress = val; }

// Expose on window for backward compatibility (conditional to avoid clobbering app_v2.js)
if (window.competitors === undefined) window.competitors = competitors;
if (window.currentNewsPage === undefined) window.currentNewsPage = currentNewsPage;
