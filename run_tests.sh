#!/bin/bash
# Run all tests and generate report

set -e

echo "🧪 Running Fertility Support Scoring Tests"
echo "========================================"
echo ""

# Run unit tests
echo "📝 Running unit tests..."
uv run pytest tests/ -v --tb=short

echo ""
echo "✅ All tests passed!"
echo ""

# Run security tests specifically
echo "🛡️  Running security tests..."
uv run pytest tests/test_attacks.py -v

echo ""
echo "📊 Test Summary"
echo "==============="
echo "✓ Unit tests: PASSED"
echo "✓ Security tests: PASSED"
echo ""
echo "💡 To run with coverage:"
echo "  uv run pytest --cov=. --cov-report=html"
