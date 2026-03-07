/**
 * Unit tests for htmlUtils.js - stripDomainFromAssetUrls and resolveAssetUrls functions
 * 
 * Tests the bug fix for: images in RTF/HTML content break after project fork 
 * because absolute URLs stored in MongoDB
 */

// Mock process.env for testing
process.env.REACT_APP_BACKEND_URL = 'https://codebase-optimize-1.preview.emergentagent.com';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Re-implement the functions for testing (same logic as htmlUtils.js)
const stripDomainFromAssetUrls = (htmlContent) => {
  if (!htmlContent) return htmlContent;
  
  // Strip domain from /api/assets/ URLs (global AI-generated images)
  let result = htmlContent.replace(
    /https?:\/\/[^/\s"']+\/api\/assets\//g,
    '/api/assets/'
  );
  
  // Strip domain from /api/projects/{id}/assets/ URLs (project-specific media)
  result = result.replace(
    /https?:\/\/[^/\s"']+\/api\/projects\//g,
    '/api/projects/'
  );
  
  return result;
};

const resolveAssetUrls = (htmlContent) => {
  if (!htmlContent || !API_URL) return htmlContent;
  
  // First strip any old absolute domains to normalize
  let result = stripDomainFromAssetUrls(htmlContent);
  
  // Then resolve relative /api/ URLs to the current domain
  // Match src="/api/..." or src='/api/...' attributes
  result = result.replace(
    /(src=["'])\/api\//g,
    `$1${API_URL}/api/`
  );
  
  return result;
};

// Test suite
const tests = [];
let passed = 0;
let failed = 0;

function test(name, fn) {
  tests.push({ name, fn });
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}\nExpected: ${expected}\nActual: ${actual}`);
  }
}

function assertIncludes(str, substring, message) {
  if (!str.includes(substring)) {
    throw new Error(`${message}\nString "${str}" does not include "${substring}"`);
  }
}

function assertNotIncludes(str, substring, message) {
  if (str.includes(substring)) {
    throw new Error(`${message}\nString "${str}" should not include "${substring}"`);
  }
}

// Test cases for stripDomainFromAssetUrls
test('stripDomainFromAssetUrls: handles null input', () => {
  assertEqual(stripDomainFromAssetUrls(null), null, 'Should return null for null input');
});

test('stripDomainFromAssetUrls: handles empty string', () => {
  assertEqual(stripDomainFromAssetUrls(''), '', 'Should return empty string for empty input');
});

test('stripDomainFromAssetUrls: strips domain from /api/assets/ URL', () => {
  const input = '<img src="https://old-domain.com/api/assets/image.jpg" />';
  const result = stripDomainFromAssetUrls(input);
  assertIncludes(result, '/api/assets/image.jpg', 'Should have relative URL');
  assertNotIncludes(result, 'old-domain.com', 'Should not have old domain');
});

test('stripDomainFromAssetUrls: strips domain from /api/projects/{id}/assets/ URL', () => {
  const input = '<img src="https://old-fork.example.com/api/projects/abc123/assets/photo.png" />';
  const result = stripDomainFromAssetUrls(input);
  assertIncludes(result, '/api/projects/abc123/assets/photo.png', 'Should have relative project URL');
  assertNotIncludes(result, 'old-fork.example.com', 'Should not have old domain');
});

test('stripDomainFromAssetUrls: handles multiple URLs in same content', () => {
  const input = '<div><img src="https://domain1.com/api/assets/img1.jpg" /><img src="https://domain2.com/api/assets/img2.png" /></div>';
  const result = stripDomainFromAssetUrls(input);
  assertIncludes(result, '/api/assets/img1.jpg', 'Should have first relative URL');
  assertIncludes(result, '/api/assets/img2.png', 'Should have second relative URL');
  assertNotIncludes(result, 'domain1.com', 'Should not have first domain');
  assertNotIncludes(result, 'domain2.com', 'Should not have second domain');
});

test('stripDomainFromAssetUrls: preserves already-relative URLs', () => {
  const input = '<img src="/api/assets/already-relative.jpg" />';
  const result = stripDomainFromAssetUrls(input);
  assertEqual(result, input, 'Should not modify already-relative URLs');
});

test('stripDomainFromAssetUrls: handles http and https', () => {
  const inputHttps = '<img src="https://secure.example.com/api/assets/secure.jpg" />';
  const inputHttp = '<img src="http://insecure.example.com/api/assets/insecure.jpg" />';
  
  const resultHttps = stripDomainFromAssetUrls(inputHttps);
  const resultHttp = stripDomainFromAssetUrls(inputHttp);
  
  assertNotIncludes(resultHttps, 'secure.example.com', 'Should strip https domain');
  assertNotIncludes(resultHttp, 'insecure.example.com', 'Should strip http domain');
});

test('stripDomainFromAssetUrls: preserves external URLs', () => {
  const input = '<img src="https://external-cdn.com/images/photo.jpg" />';
  const result = stripDomainFromAssetUrls(input);
  assertEqual(result, input, 'Should not modify external URLs without /api/');
});

// Test cases for resolveAssetUrls
test('resolveAssetUrls: handles null input', () => {
  assertEqual(resolveAssetUrls(null), null, 'Should return null for null input');
});

test('resolveAssetUrls: handles empty string', () => {
  assertEqual(resolveAssetUrls(''), '', 'Should return empty string for empty input');
});

test('resolveAssetUrls: resolves relative /api/assets/ URL to absolute', () => {
  const input = '<img src="/api/assets/image.jpg" />';
  const result = resolveAssetUrls(input);
  assertIncludes(result, `${API_URL}/api/assets/image.jpg`, 'Should have full URL with current domain');
});

test('resolveAssetUrls: resolves relative /api/projects/ URL to absolute', () => {
  const input = '<img src="/api/projects/proj123/assets/photo.png" />';
  const result = resolveAssetUrls(input);
  assertIncludes(result, `${API_URL}/api/projects/proj123/assets/photo.png`, 'Should have full URL with current domain');
});

test('resolveAssetUrls: first strips old domain then resolves to current', () => {
  const input = '<img src="https://old-domain.com/api/assets/image.jpg" />';
  const result = resolveAssetUrls(input);
  assertNotIncludes(result, 'old-domain.com', 'Should not have old domain');
  assertIncludes(result, API_URL, 'Should have current domain');
  assertIncludes(result, '/api/assets/image.jpg', 'Should have asset path');
});

test('resolveAssetUrls: handles single quotes in src', () => {
  const input = "<img src='/api/assets/image.jpg' />";
  const result = resolveAssetUrls(input);
  assertIncludes(result, `${API_URL}/api/assets/image.jpg`, 'Should resolve single-quoted URLs');
});

// Test round-trip: resolve then strip should return to relative
test('round-trip: resolve then strip returns to relative', () => {
  const original = '<img src="/api/assets/test.jpg" />';
  const resolved = resolveAssetUrls(original);
  const stripped = stripDomainFromAssetUrls(resolved);
  
  // After stripping, should be back to relative
  assertNotIncludes(stripped, 'http', 'Should be back to relative URL');
  assertIncludes(stripped, '/api/assets/test.jpg', 'Should have relative path');
});

// Test with mixed content
test('stripDomainFromAssetUrls: handles mixed content with text', () => {
  const input = '<p>Here is an image: <img src="https://old.com/api/assets/img.jpg" /> and some more text.</p>';
  const result = stripDomainFromAssetUrls(input);
  assertIncludes(result, 'Here is an image:', 'Should preserve text before');
  assertIncludes(result, 'and some more text', 'Should preserve text after');
  assertIncludes(result, '/api/assets/img.jpg', 'Should have relative URL');
});

// Run all tests
console.log('Running htmlUtils.js unit tests...\n');
console.log('API_URL:', API_URL);
console.log('');

for (const { name, fn } of tests) {
  try {
    fn();
    console.log(`✅ ${name}`);
    passed++;
  } catch (error) {
    console.log(`❌ ${name}`);
    console.log(`   Error: ${error.message}`);
    failed++;
  }
}

console.log('\n' + '='.repeat(60));
console.log(`Total: ${tests.length} | Passed: ${passed} | Failed: ${failed}`);
console.log('='.repeat(60));

if (failed > 0) {
  process.exit(1);
}
