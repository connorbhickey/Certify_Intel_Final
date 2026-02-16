"""
Fix system_prompts table schema and re-seed all 41 prompts.

This script:
1. Checks if category/description columns exist
2. Adds them if missing
3. Re-runs the seeder to insert all 41 prompts
"""

import sys
import logging

sys.path.insert(0, '.')

from database import SessionLocal, SystemPrompt  # noqa: E402
from sqlalchemy import text  # noqa: E402
from prompt_seeder import seed_system_prompts  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()

    try:
        # Step 1: Check current table schema
        logger.info("Step 1: Checking system_prompts table schema...")
        try:
            # Try to query with category column
            result = db.execute(text("SELECT category FROM system_prompts LIMIT 1"))
            logger.info("[OK] 'category' column exists")
        except Exception as e:
            logger.warning(f"[!] 'category' column missing: {e}")
            logger.info("Adding 'category' column...")
            db.execute(text("ALTER TABLE system_prompts ADD COLUMN category VARCHAR"))
            db.commit()
            logger.info("[OK] Added 'category' column")

        try:
            # Try to query with description column
            result = db.execute(text("SELECT description FROM system_prompts LIMIT 1"))
            logger.info("[OK] 'description' column exists")
        except Exception as e:
            logger.warning(f"[!] 'description' column missing: {e}")
            logger.info("Adding 'description' column...")
            db.execute(text("ALTER TABLE system_prompts ADD COLUMN description VARCHAR"))
            db.commit()
            logger.info("[OK] Added 'description' column")

        # Step 2: Check current prompt count
        logger.info("\nStep 2: Checking current prompt count...")
        count = db.query(SystemPrompt).filter(SystemPrompt.user_id.is_(None)).count()
        logger.info("Current global prompts: %d", count)

        # Step 3: Run seeder
        logger.info("\nStep 3: Running prompt seeder...")
        result = seed_system_prompts(db)
        logger.info("[OK] Seeder results:")
        logger.info("  - Inserted: %d", result['inserted'])
        logger.info("  - Updated: %d", result['updated'])
        logger.info("  - Skipped: %d", result['skipped'])
        logger.info("  - Total prompts defined: %d", result['total'])

        # Step 4: Verify final count
        logger.info("\nStep 4: Verifying final count...")
        final_count = db.query(SystemPrompt).filter(SystemPrompt.user_id.is_(None)).count()
        logger.info("Final global prompts: %d", final_count)

        if final_count == result['total']:
            logger.info(f"[SUCCESS] All {final_count} prompts are now in the database!")
        else:
            logger.warning(f"[WARNING] Expected {result['total']} prompts, but have {final_count}")

        # Step 5: Show sample prompts by category
        logger.info("\nStep 5: Sample prompts by category:")
        categories = db.execute(text(
            "SELECT category, COUNT(*) as count FROM system_prompts "
            "WHERE user_id IS NULL GROUP BY category ORDER BY category"
        )).fetchall()

        for cat, count in categories:
            logger.info(f"  - {cat or '(no category)'}: {count} prompts")

    except Exception as e:
        logger.error(f"[ERROR] {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
