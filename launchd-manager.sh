#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Solar Update - launchd Management Script
# ═══════════════════════════════════════════════════════════════════════════
# launchd is the macOS-native alternative to cron, offering better reliability,
# logging, and integration with macOS system events.
# ═══════════════════════════════════════════════════════════════════════════

PLIST_FILE="com.solar.update.plist"
PLIST_SOURCE="/Users/bhargav/repos/solar_intelligence/com.solar.update.plist"
PLIST_DESTINATION="$HOME/Library/LaunchAgents/com.solar.update.plist"

show_help() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Solar Update - launchd Manager"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Usage: ./launchd-manager.sh [command]"
    echo ""
    echo "Commands:"
    echo "  install   - Copy plist to LaunchAgents and load it"
    echo "  uninstall - Unload and remove the plist"
    echo "  status    - Check if the agent is running"
    echo "  logs      - View the update logs"
    echo "  test      - Run an immediate update"
    echo ""
}

install() {
    echo "📦 Installing launchd agent..."
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$HOME/Library/LaunchAgents"
    
    # Copy plist file
    cp "$PLIST_SOURCE" "$PLIST_DESTINATION"
    echo "✅ Copied plist to $PLIST_DESTINATION"
    
    # Load the agent
    launchctl load "$PLIST_DESTINATION"
    echo "✅ launchd agent loaded"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Installation complete!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Your solar updates will now run automatically at:"
    echo "  • 7:00 AM IST"
    echo "  • 10:00 AM IST"
    echo "  • 1:00 PM IST"
    echo "  • 4:00 PM IST"
    echo "  • 7:00 PM IST"
    echo ""
}

uninstall() {
    echo "🗑️  Uninstalling launchd agent..."
    
    # Unload the agent
    launchctl unload "$PLIST_DESTINATION" 2>/dev/null
    echo "✅ launchd agent unloaded"
    
    # Remove plist file
    rm -f "$PLIST_DESTINATION"
    echo "✅ Removed plist file"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Uninstallation complete!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

status() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Solar Update Agent Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if launchctl list | grep -q "com.solar.update"; then
        echo "✅ Agent is LOADED and ACTIVE"
        echo ""
        launchctl list | grep "com.solar.update"
    else
        echo "❌ Agent is NOT loaded"
        echo ""
        echo "To install: ./launchd-manager.sh install"
    fi
    echo ""
}

logs() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Solar Update Logs"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Standard Output:"
    echo "----------------"
    tail -20 /tmp/solar-update.log 2>/dev/null || echo "No logs yet"
    echo ""
    echo "Errors:"
    echo "-------"
    tail -20 /tmp/solar-update-error.log 2>/dev/null || echo "No errors"
    echo ""
}

test() {
    echo "🧪 Running test update..."
    echo ""
    cd /Users/bhargav/repos/solar_intelligence
    ./update-local.sh
}

# Main command handler
case "$1" in
    install)
        install
        ;;
    uninstall)
        uninstall
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    test)
        test
        ;;
    *)
        show_help
        ;;
esac
