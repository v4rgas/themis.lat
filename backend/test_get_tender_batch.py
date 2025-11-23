import asyncio
import time
from datetime import datetime
from typing import Tuple, Optional
from app.utils.get_tender import get_tender, TenderResponse
from test_tender_ids import TENDER_IDS


RATE_LIMIT_DELAY = 60 / 9


async def test_with_retry(tender_id: str) -> Tuple[bool, Optional[str], Optional[TenderResponse]]:
    try:
        result = await get_tender(tender_id)
        if result:
            return True, None, result
        else:
            return False, "No result returned", None
    except Exception as e:
        try:
            await asyncio.sleep(RATE_LIMIT_DELAY)
            result = await get_tender(tender_id)
            if result:
                return True, None, result
            else:
                return False, f"Retry failed: No result returned", None
        except Exception as retry_error:
            return False, f"Initial error: {str(e)} | Retry error: {str(retry_error)}", None


async def main():
    failures = []
    na_cases = []
    total = len(TENDER_IDS)
    
    print(f"Testing {total} tender IDs...")
    print(f"Rate limit: 9 requests per minute ({RATE_LIMIT_DELAY:.2f}s delay between requests)")
    print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    for idx, tender_id in enumerate(TENDER_IDS, 1):
        print(f"[{idx}/{total}] Testing {tender_id}...", end=" ", flush=True)
        
        success, error, result = await test_with_retry(tender_id)
        
        if success:
            type_info = "N/A"
            if result.type and result.type.description:
                type_info = result.type.description
            print(f"✓ Success" + (f" (Type: {type_info})" if type_info != "N/A" else " (Type: N/A)"))
            if not result.type or not result.type.description:
                na_cases.append({
                    "tender_id": tender_id,
                    "timestamp": datetime.now().isoformat()
                })
        else:
            print(f"✗ Failed: {error}")
            failures.append({
                "tender_id": tender_id,
                "error": error,
                "timestamp": datetime.now().isoformat()
            })
        
        if idx < total:
            await asyncio.sleep(RATE_LIMIT_DELAY)
    
    print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total: {total}, Success: {total - len(failures)}, Failed: {len(failures)}, N/A Type: {len(na_cases)}")
    
    if failures:
        error_file = "get_tender_failures.txt"
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(f"Get Tender Test Failures\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Total failures: {len(failures)}\n\n")
            f.write("=" * 80 + "\n\n")
            
            for failure in failures:
                f.write(f"Tender ID: {failure['tender_id']}\n")
                f.write(f"Timestamp: {failure['timestamp']}\n")
                f.write(f"Error: {failure['error']}\n")
                f.write("-" * 80 + "\n\n")
        
        print(f"\nFailures saved to: {error_file}")
    
    if na_cases:
        na_file = "get_tender_na_types.txt"
        with open(na_file, "w", encoding="utf-8") as f:
            f.write(f"Get Tender Test - N/A Type Cases\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Total N/A cases: {len(na_cases)}\n\n")
            f.write("=" * 80 + "\n\n")
            
            for na_case in na_cases:
                f.write(f"Tender ID: {na_case['tender_id']}\n")
                f.write(f"Timestamp: {na_case['timestamp']}\n")
                f.write("-" * 80 + "\n\n")
        
        print(f"N/A type cases saved to: {na_file}")
    
    if not failures and not na_cases:
        print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

