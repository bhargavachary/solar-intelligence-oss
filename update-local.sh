#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Local Solar Data Update Script - REAL PORTAL DATA ONLY
# ═══════════════════════════════════════════════════════════════════════════
# This script ONLY fetches REAL data from the Waaree monitoring portal.
# NO synthetic/fake data generation is permitted.
# 
# If the portal is unreachable, the update will FAIL (by design).
# This ensures data integrity and prevents reporting false information.
#
# Usage: ./update-local.sh
# ═══════════════════════════════════════════════════════════════════════════

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Solar Data Update - LIVE PORTAL ONLY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if we're in the right directory
if [ ! -f "waaree_deep_crawler.py" ]; then
    echo "❌ Error: Not in the correct directory"
    echo "Please run this from the waaree_api_access directory"
    exit 1
fi

# Check if credentials exist
if [ ! -f "credentials.json" ]; then
    echo "❌ Error: credentials.json not found"
    exit 1
fi

echo "🔄 Fetching LIVE data from Waaree portal..."
echo "⚠️  NO FALLBACK TO SYNTHETIC DATA - Portal must be accessible"
python waaree_deep_crawler.py

if [ ! -f "scraped_data.json" ]; then
    echo "❌ Scraper failed - no REAL data available from portal"
    echo "❌ Aborting update - will NOT use fake/synthetic data"
    exit 1
fi

echo "✅ REAL portal data fetched successfully"
echo ""

echo "🔄 Running data pipeline..."
python scripts/update_data.py --source live

echo "✅ Data pipeline complete"
echo ""

echo "🔄 Committing changes..."
git add data/dashboard_data.json data/energy_logs/*.json
git commit -m "🤖 Manual update: $(date +'%Y-%m-%d %H:%M')"

echo "✅ Changes committed"
echo ""

echo "📤 Pushing to GitHub..."
git push

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Solar data updated successfully!"
echo "  🌐 GitHub Pages will auto-deploy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
