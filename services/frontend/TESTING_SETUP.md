# Testing Setup for Advanced Search Weights

## Quick Start

### 1. Install Testing Dependencies

```bash
cd services/frontend

# Install Jest and React Testing Library
npm install --save-dev jest @jest/globals @testing-library/react @testing-library/jest-dom @testing-library/user-event jest-environment-jsdom

# Install TypeScript types
npm install --save-dev @types/jest

# Install SWC for fast TypeScript compilation
npm install --save-dev @swc/core @swc/jest
```

### 2. Create Jest Configuration

Create `jest.config.js` in `services/frontend/`:

```javascript
const nextJest = require('next/jest')

const createJestConfig = nextJest({
  // Provide the path to your Next.js app to load next.config.js and .env files in your test environment
  dir: './',
})

// Add any custom config to be passed to Jest
const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testMatch: [
    '**/__tests__/**/*.[jt]s?(x)',
    '**/?(*.)+(spec|test).[jt]s?(x)'
  ],
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.stories.{js,jsx,ts,tsx}',
    '!src/**/__tests__/**',
  ],
}

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = createJestConfig(customJestConfig)
```

### 3. Create Jest Setup File

Create `jest.setup.js` in `services/frontend/`:

```javascript
// Learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom'
```

### 4. Add Test Scripts to package.json

Add to `services/frontend/package.json`:

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  }
}
```

### 5. Run Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test:watch

# Run with coverage
npm test:coverage

# Run specific test file
npm test normalizeWeights.test.ts
```

## Test Structure

The test file is located at:
```
services/frontend/src/__tests__/normalizeWeights.test.ts
```

It includes comprehensive tests for:
- Weight normalization
- Slider updates
- Preset application
- Lock functionality
- Edge cases
- Floating-point stability

## Expected Test Output

All tests should pass:

```
PASS  src/__tests__/normalizeWeights.test.ts
  normalizeWeights
    isNormalized
      ✓ returns true for weights that sum to 1.0
      ✓ returns false for weights that do not sum to 1.0
      ✓ handles floating point precision within epsilon
    getWeightsSum
      ✓ calculates correct sum
      ✓ returns 0 for empty array
    normalizeWeights
      ✓ normalizes weights that sum to more than 1
      ✓ normalizes weights that sum to less than 1
      ✓ handles all weights at 0
      ✓ respects locked signals
      ✓ handles multiple locked signals
      ✓ handles locked signals exceeding 1.0
      ✓ returns empty array for empty input
    updateWeight
      ✓ updates single weight and normalizes others proportionally
      ✓ handles increasing weight to 1.0
      ✓ handles decreasing weight to 0.0
      ✓ respects locked signals when updating
      ✓ handles non-existent key gracefully
      ✓ clamps values above 1.0
      ✓ clamps values below 0.0
    applyPreset
      ✓ applies preset weights correctly
      ✓ handles partial preset (missing keys)
      ✓ normalizes preset that does not sum to 1.0
      ✓ preserves locked state when applying preset
    roundToStep
      ✓ rounds to nearest step
      ✓ handles exact multiples
      ✓ handles edge cases
    weightToPercentage
      ✓ converts weight to percentage string
      ✓ respects decimal places
    percentageToWeight
      ✓ converts percentage to weight
      ✓ clamps out-of-range values
    Complex scenarios
      ✓ handles rapid successive updates
      ✓ handles locking and unlocking during adjustments
      ✓ handles all signals locked (edge case)
      ✓ maintains stability with floating point arithmetic

Test Suites: 1 passed, 1 total
Tests:       35 passed, 35 total
```

## Coverage Goals

Aim for:
- **Statements**: >95%
- **Branches**: >90%
- **Functions**: >95%
- **Lines**: >95%

## Alternative: Vitest

If you prefer Vitest (faster, more modern):

```bash
npm install --save-dev vitest @vitest/ui

# Update package.json
{
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest --coverage"
  }
}

# Create vitest.config.ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

## Troubleshooting

### Module Resolution Issues

If you get "Cannot find module '@/lib/normalizeWeights'":

1. Check `tsconfig.json` has correct paths:
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

2. Ensure Jest config has matching `moduleNameMapper`

### TypeScript Errors in Tests

If you get TypeScript errors:

```bash
# Install type definitions
npm install --save-dev @types/node

# Ensure test files are included in tsconfig
```

### Slow Test Execution

1. Use `@swc/jest` for faster TypeScript compilation
2. Run tests in parallel (Jest does this by default)
3. Use `.only` to run specific tests during development

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: services/frontend/package-lock.json

    - name: Install dependencies
      working-directory: services/frontend
      run: npm ci

    - name: Run tests
      working-directory: services/frontend
      run: npm test -- --coverage

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: services/frontend/coverage/lcov.info
```

## Next Steps

1. Run the tests: `npm test`
2. Check coverage: `npm test:coverage`
3. Add tests for the React component (AdvancedSearchWeights.tsx)
4. Set up pre-commit hooks to run tests automatically

## Resources

- [Jest Documentation](https://jestjs.io/)
- [Testing Library](https://testing-library.com/react)
- [Next.js Testing Guide](https://nextjs.org/docs/testing)
