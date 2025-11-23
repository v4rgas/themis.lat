import time
from datetime import datetime
from typing import Tuple, Optional
from app.tools.read_award_result import read_award_result
from test_tender_ids import TENDER_IDS


RATE_LIMIT_DELAY = 60 / 9


def test_with_retry(tender_id: str) -> Tuple[bool, Optional[str]]:
    try:
        result = read_award_result.invoke({"id": tender_id})
        if result.get("ok"):
            return True, None
        else:
            return False, "Award information not available (ok=False)"
    except Exception as e:
        try:
            time.sleep(RATE_LIMIT_DELAY)
            result = read_award_result.invoke({"id": tender_id})
            if result.get("ok"):
                return True, None
            else:
                return False, f"Retry failed: Award information not available (ok=False)"
        except Exception as retry_error:
            return False, f"Initial error: {str(e)} | Retry error: {str(retry_error)}"


def main():
    failures = []
    total = len(TENDER_IDS)
    
    print(f"Testing {total} tender IDs...")
    print(f"Rate limit: 9 requests per minute ({RATE_LIMIT_DELAY:.2f}s delay between requests)")
    print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    for idx, tender_id in enumerate(TENDER_IDS, 1):
        print(f"[{idx}/{total}] Testing {tender_id}...", end=" ", flush=True)
        
        success, error = test_with_retry(tender_id)
        
        if success:
            print("✓ Success")
        else:
            print(f"✗ Failed: {error}")
            failures.append({
                "tender_id": tender_id,
                "error": error,
                "timestamp": datetime.now().isoformat()
            })
        
        if idx < total:
            time.sleep(RATE_LIMIT_DELAY)
    
    print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total: {total}, Success: {total - len(failures)}, Failed: {len(failures)}")
    
    if failures:
        error_file = "read_award_result_failures.txt"
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"Read Award Result Test Failures\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Total failures: {len(failures)}\n\n")
            f.write("=" * 80 + "\n\n")
            
            for failure in failures:
                f.write(f"Tender ID: {failure['tender_id']}\n")
                f.write(f"Timestamp: {failure['timestamp']}\n")
                f.write(f"Error: {failure['error']}\n")
                f.write("-" * 80 + "\n\n")
        
        print(f"\nFailures saved to: {error_file}")
    else:
        print("\nAll tests passed!")


if __name__ == "__main__":
    main()

