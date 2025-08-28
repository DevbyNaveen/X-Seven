#!/usr/bin/env python3
"""
Complete database migration script from SQLite to Supabase.
This script handles:
1. Database connection setup
2. Data extraction from SQLite
3. Data transformation for Supabase compatibility
4. Batch insertion into Supabase
5. Progress tracking and error handling
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your models and database setup
try:
    from app.config.database import SessionLocal, engine, Base
    from app.models import (
        Business, SubscriptionPlan, BusinessCategory, 
        MenuCategory, MenuItem, PhoneNumberType
    )
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running this script from the project root")
    sys.exit(1)

class SupabaseMigration:
    def __init__(self):
        """Initialize Supabase client and check environment variables."""
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_API_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            print("❌ Missing required environment variables:")
            print("   SUPABASE_URL and SUPABASE_API_KEY must be set")
            print("   Create a .env file or set environment variables:")
            print("   SUPABASE_URL=https://your-project.supabase.co")
            print("   SUPABASE_API_KEY=your-anon-key-from-supabase")
            sys.exit(1)
            
        try:
            from supabase import create_client, Client
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            self.sqlite_session = SessionLocal()
            self.migration_stats = {
                'businesses': 0,
                'menu_categories': 0,
                'menu_items': 0,
                'errors': []
            }
        except ImportError as e:
            print(f"❌ Import error: {e}")
            print("💡 Install required packages: pip3 install supabase sqlalchemy")
            sys.exit(1)
    
    def check_supabase_connection(self) -> bool:
        """Test connection to Supabase."""
        try:
            response = self.supabase.auth.get_user()
            print("✅ Successfully connected to Supabase")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Supabase: {e}")
            return False
    
    def migrate_businesses(self) -> bool:
        """Migrate all businesses from SQLite to Supabase."""
        try:
            businesses = self.sqlite_session.query(Business).all()
            print(f"📊 Found {len(businesses)} businesses to migrate")
            
            for business in businesses:
                # Transform data for Supabase
                # Generate UUID from integer ID to maintain consistency
                import uuid
                business_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(business.id)))
                
                business_data = {
                    'id': business_uuid,
                    'name': business.name,
                    'slug': business.slug,
                    'description': business.description,
                    'category': business.category.value if hasattr(business.category, 'value') else str(business.category),
                    'phone_config': business.phone_config.value if hasattr(business.phone_config, 'value') else str(business.phone_config),
                    'subscription_plan': business.subscription_plan.value if hasattr(business.subscription_plan, 'value') else str(business.subscription_plan),
                    'subscription_status': business.subscription_status.value if hasattr(business.subscription_status, 'value') else str(business.subscription_status),
                    'is_active': business.is_active,
                    'trial_ends_at': business.trial_ends_at.isoformat() if business.trial_ends_at else None,
                    'stripe_customer_id': business.stripe_customer_id,
                    'stripe_subscription_id': business.stripe_subscription_id,
                    'custom_phone_number': business.custom_phone_number,
                    'custom_whatsapp_number': business.custom_whatsapp_number,
                    'custom_phone_sid': business.custom_phone_sid,
                    'custom_number_monthly_cost': float(business.custom_number_monthly_cost) if business.custom_number_monthly_cost else None,
                    'created_at': business.created_at.isoformat() if business.created_at else None,
                    'updated_at': business.updated_at.isoformat() if business.updated_at else None,
                    'contact_info': json.dumps(business.contact_info) if business.contact_info else '{}',
                    'settings': json.dumps(business.settings) if business.settings else '{}',
                    'branding_config': json.dumps(business.branding_config) if business.branding_config else '{}',
                }
                
                try:
                    # Check if business already exists
                    existing = self.supabase.table('businesses').select('id').eq('id', business_uuid).execute()
                    if existing.data:
                        # Update existing business
                        self.supabase.table('businesses').update(business_data).eq('id', business_uuid).execute()
                    else:
                        # Insert new business
                        self.supabase.table('businesses').insert(business_data).execute()
                    
                    self.migration_stats['businesses'] += 1
                    print(f"   ✅ Migrated business: {business.name} ({business.slug})")
                    
                except Exception as e:
                    error_msg = f"Failed to migrate business {business.name}: {e}"
                    self.migration_stats['errors'].append(error_msg)
                    print(f"   ❌ {error_msg}")
                    
            return True
            
        except Exception as e:
            error_msg = f"Failed to migrate businesses: {e}"
            self.migration_stats['errors'].append(error_msg)
            print(f"❌ {error_msg}")
            return False
    
    def run_migration(self) -> bool:
        """Run the complete migration process."""
        print("🚀 Starting database migration to Supabase...")
        print("=" * 50)
        
        # Check Supabase connection
        if not self.check_supabase_connection():
            return False
        
        # Run migrations in order
        success = True
        
        print("\n1️⃣  Migrating businesses...")
        if not self.migrate_businesses():
            success = False
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 MIGRATION SUMMARY")
        print("=" * 50)
        print(f"✅ Businesses migrated: {self.migration_stats['businesses']}")
        
        if self.migration_stats['errors']:
            print(f"❌ Errors encountered: {len(self.migration_stats['errors'])}")
            print("\nError details:")
            for error in self.migration_stats['errors']:
                print(f"   - {error}")
        
        return success
    
    def close(self):
        """Clean up resources."""
        if self.sqlite_session:
            self.sqlite_session.close()


def main():
    """Main migration entry point."""
    migration = SupabaseMigration()
    
    try:
        success = migration.run_migration()
        if success:
            print("\n🎉 Migration completed successfully!")
            return 0
        else:
            print("\n⚠️  Migration completed with errors!")
            return 1
    except KeyboardInterrupt:
        print("\n❌ Migration interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return 1
    finally:
        migration.close()


if __name__ == "__main__":
    sys.exit(main())
