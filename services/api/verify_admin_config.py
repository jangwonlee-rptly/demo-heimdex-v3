#!/usr/bin/env python3
"""
Verify admin configuration is loaded correctly.

Usage:
    cd services/api
    python3 verify_admin_config.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import settings

def main():
    print("=" * 60)
    print("Heimdex Admin Configuration Verification")
    print("=" * 60)
    print()

    # Check raw value
    print(f"1. Raw ADMIN_USER_IDS value:")
    print(f"   {repr(settings.admin_user_ids)}")
    print()

    # Check parsed list
    print(f"2. Parsed admin user IDs list:")
    if settings.admin_user_ids_list:
        for idx, user_id in enumerate(settings.admin_user_ids_list, 1):
            print(f"   [{idx}] {user_id}")
    else:
        print("   (empty - no admin users configured)")
    print()

    # Verification
    print("3. Configuration Status:")
    if not settings.admin_user_ids:
        print("   ❌ ADMIN_USER_IDS environment variable is NOT set")
        print()
        print("   To fix:")
        print("   1. Edit services/api/.env")
        print("   2. Add line: ADMIN_USER_IDS=your-user-id-here")
        print("   3. Restart API service")
        print()
        print("   Get your user ID:")
        print("   - Log in to Heimdex frontend")
        print("   - Open browser console (F12)")
        print("   - Run: (await supabase.auth.getSession()).data.session?.user?.id")
        return False

    elif not settings.admin_user_ids_list:
        print("   ⚠️  ADMIN_USER_IDS is set but empty or invalid")
        print(f"   Raw value: {repr(settings.admin_user_ids)}")
        return False

    else:
        print(f"   ✅ {len(settings.admin_user_ids_list)} admin user(s) configured")
        print()
        print("4. Next Steps:")
        print("   - Start API service: uvicorn src.main:app --reload")
        print("   - Log in as admin user to frontend")
        print("   - Navigate to http://localhost:3000/admin")
        print("   - Verify admin dashboard loads")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
