# 3704-39-LE25

import time
import traceback
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from app.tools.read_award_result import read_award_result

TENDER_ID = "741-51-L125"


RATE_LIMIT_DELAY = 60 / 9


def log_result_details(result: Any, attempt: str = "initial") -> None:
    print(f"\n[{attempt}] Result details:")
    print(f"  Type: {type(result)}")
    
    if isinstance(result, dict):
        print(f"  Keys: {list(result.keys())}")
        print(f"  'ok' value: {result.get('ok')} (type: {type(result.get('ok'))})")
        
        for key, value in result.items():
            if key == 'ok':
                continue
            value_type = type(value).__name__
            if isinstance(value, (list, dict)):
                print(f"  '{key}': {value_type} (length: {len(value) if hasattr(value, '__len__') else 'N/A'})")
                if isinstance(value, list) and len(value) > 0:
                    print(f"    First item type: {type(value[0]).__name__}")
                    if isinstance(value[0], dict):
                        print(f"    First item keys: {list(value[0].keys())}")
                elif isinstance(value, dict) and len(value) > 0:
                    print(f"    Dict keys: {list(value.keys())[:5]}{'...' if len(value) > 5 else ''}")
            else:
                print(f"  '{key}': {value_type} = {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
    else:
        print(f"  Value: {str(result)[:200]}")


def test_with_retry(tender_id: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    try:
        print(f"  Invoking read_award_result with id='{tender_id}'...")
        result = read_award_result.invoke({"id": tender_id})
        log_result_details(result, "initial")
        
        if result.get("ok"):
            return True, None, result
        else:
            error_msg = f"Award information not available (ok=False)"
            return False, error_msg, result
    except Exception as e:
        print(f"  Exception on initial attempt:")
        print(f"    Type: {type(e).__name__}")
        print(f"    Message: {str(e)}")
        print(f"    Traceback:\n{''.join(traceback.format_tb(e.__traceback__))}")
        
        try:
            print(f"  Retrying after {RATE_LIMIT_DELAY:.2f}s delay...")
            time.sleep(RATE_LIMIT_DELAY)
            result = read_award_result.invoke({"id": tender_id})
            log_result_details(result, "retry")
            
            if result.get("ok"):
                return True, None, result
            else:
                error_msg = f"Retry failed: Award information not available (ok=False)"
                return False, error_msg, result
        except Exception as retry_error:
            print(f"  Exception on retry attempt:")
            print(f"    Type: {type(retry_error).__name__}")
            print(f"    Message: {str(retry_error)}")
            print(f"    Traceback:\n{''.join(traceback.format_tb(retry_error.__traceback__))}")
            error_msg = f"Initial error: {type(e).__name__}: {str(e)} | Retry error: {type(retry_error).__name__}: {str(retry_error)}"
            return False, error_msg, None


def main():
    total = 1
    
    print(f"Testing {total} tender IDs...")
    print(f"Rate limit: 9 requests per minute ({RATE_LIMIT_DELAY:.2f}s delay between requests)")
    print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"[{1}/{total}] Testing {TENDER_ID}...")
        
    success, error, result = test_with_retry(TENDER_ID)
        
    print(f"\n[{1}/{total}] Result: ", end="", flush=True)
    if success:
        print("✓ Success")
        if result:
            print(f"  Result summary:")
            print(f"    ok: {result.get('ok')}")
            print(f"    attachments count: {len(result.get('attachments', []))}")
            print(f"    award_result items count: {len(result.get('award_result', []))}")
            print(f"    overview keys: {list(result.get('overview', {}).keys())}")
            print(f"    award_act keys: {list(result.get('award_act', {}).keys())}")
    else:
        print(f"✗ Failed: {error}")
        if result:
            print(f"  Failed result structure:")
            print(f"    Type: {type(result)}")
            print(f"    Keys: {list(result.keys())}")
            for key, value in result.items():
                print(f"    {key}: {type(value).__name__} = {str(value)[:150]}")
        
    print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total: {total}, Success: {1 if success else 0}, Failed: {0 if success else 1}")
    
    error_file = f"read_award_result_failures_{TENDER_ID}.txt"
    with open(error_file, "w", encoding="utf-8") as f:
        f.write(f"Read Award Result Test Failures for {TENDER_ID}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Error: {error}\n")
        f.write("-" * 80 + "\n\n")
        if result:
            f.write(f"Result structure:\n")
            f.write(f"  Type: {type(result)}\n")
            f.write(f"  Keys: {list(result.keys())}\n")
            for key, value in result.items():
                f.write(f"  {key}: {type(value).__name__}\n")
                if isinstance(value, dict):
                    f.write(f"    Dict keys: {list(value.keys())}\n")
                elif isinstance(value, list):
                    f.write(f"    List length: {len(value)}\n")
                    if len(value) > 0:
                        f.write(f"    First item type: {type(value[0]).__name__}\n")
                        if isinstance(value[0], dict):
                            f.write(f"    First item keys: {list(value[0].keys())}\n")
    
    print(f"\nFailure saved to: {error_file}")


if __name__ == "__main__":
    main()

