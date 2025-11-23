import asyncio
import traceback
from datetime import datetime
from typing import Tuple, Optional
from app.utils.get_tender import get_tender, TenderResponse

TENDER_ID = "741-51-L125"


RATE_LIMIT_DELAY = 60 / 9


def log_result_details(result: TenderResponse, attempt: str = "initial") -> None:
    print(f"\n[{attempt}] Result details:")
    print(f"  Type: {type(result)}")
    
    if isinstance(result, TenderResponse):
        print(f"  tenderId: {result.tenderId}")
        print(f"  name: {result.name[:100] if result.name else None}...")
        print(f"  status: {result.status}")
        print(f"  statusCode: {result.statusCode}")
        print(f"  type: {result.type}")
        if result.type:
            print(f"    description: {result.type.description}")
            print(f"    currency: {result.type.currency}")
        else:
            print(f"    type is None (N/A)")
        print(f"  TenderDate: publish={result.TenderDate.publish}, close={result.TenderDate.close}")
        print(f"  TenderEvaluationCriteria count: {len(result.TenderEvaluationCriteria)}")
        print(f"  TenderGuarantees count: {len(result.TenderGuarantees)}")
        print(f"  tenderPurchaseData:")
        print(f"    organization: {result.tenderPurchaseData.organization.name}")
        print(f"    orgUnit: {result.tenderPurchaseData.orgUnit.name}")
    else:
        print(f"  Value: {str(result)[:200]}")


async def test_with_retry(tender_id: str) -> Tuple[bool, Optional[str], Optional[TenderResponse]]:
    try:
        print(f"  Invoking get_tender with tender_id='{tender_id}'...")
        result = await get_tender(tender_id)
        log_result_details(result, "initial")
        
        if result:
            return True, None, result
        else:
            return False, "No result returned", None
    except Exception as e:
        print(f"  Exception on initial attempt:")
        print(f"    Type: {type(e).__name__}")
        print(f"    Message: {str(e)}")
        print(f"    Traceback:\n{''.join(traceback.format_tb(e.__traceback__))}")
        
        try:
            print(f"  Retrying after {RATE_LIMIT_DELAY:.2f}s delay...")
            await asyncio.sleep(RATE_LIMIT_DELAY)
            result = await get_tender(tender_id)
            log_result_details(result, "retry")
            
            if result:
                return True, None, result
            else:
                return False, f"Retry failed: No result returned", None
        except Exception as retry_error:
            print(f"  Exception on retry attempt:")
            print(f"    Type: {type(retry_error).__name__}")
            print(f"    Message: {str(retry_error)}")
            print(f"    Traceback:\n{''.join(traceback.format_tb(retry_error.__traceback__))}")
            error_msg = f"Initial error: {type(e).__name__}: {str(e)} | Retry error: {type(retry_error).__name__}: {str(retry_error)}"
            return False, error_msg, None


async def main():
    total = 1
    
    print(f"Testing {total} tender IDs...")
    print(f"Rate limit: 9 requests per minute ({RATE_LIMIT_DELAY:.2f}s delay between requests)")
    print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"[{1}/{total}] Testing {TENDER_ID}...")
        
    success, error, result = await test_with_retry(TENDER_ID)
        
    print(f"\n[{1}/{total}] Result: ", end="", flush=True)
    if success:
        type_info = "N/A"
        if result and result.type and result.type.description:
            type_info = result.type.description
        print(f"✓ Success" + (f" (Type: {type_info})" if type_info != "N/A" else " (Type: N/A)"))
        if result:
            print(f"  Result summary:")
            print(f"    tenderId: {result.tenderId}")
            print(f"    status: {result.status}")
            if result.type:
                print(f"    type.description: {result.type.description or 'N/A'}")
                print(f"    type.currency: {result.type.currency or 'N/A'}")
            else:
                print(f"    type: None (N/A)")
            print(f"    TenderEvaluationCriteria count: {len(result.TenderEvaluationCriteria)}")
            print(f"    TenderGuarantees count: {len(result.TenderGuarantees)}")
    else:
        print(f"✗ Failed: {error}")
        if result:
            print(f"  Failed result structure:")
            print(f"    Type: {type(result)}")
            print(f"    tenderId: {result.tenderId}")
            print(f"    status: {result.status}")
            print(f"    type: {result.type}")
            if result.type:
                print(f"      description: {result.type.description}")
                print(f"      currency: {result.type.currency}")
        
    print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total: {total}, Success: {1 if success else 0}, Failed: {0 if success else 1}")
    
    error_file = f"get_tender_failures_{TENDER_ID}.txt"
    with open(error_file, "w", encoding="utf-8") as f:
        f.write(f"Get Tender Test Failures for {TENDER_ID}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Error: {error}\n")
        f.write("-" * 80 + "\n\n")
        if result:
            f.write(f"Result structure:\n")
            f.write(f"  Type: {type(result)}\n")
            f.write(f"  tenderId: {result.tenderId}\n")
            f.write(f"  name: {result.name}\n")
            f.write(f"  status: {result.status}\n")
            f.write(f"  statusCode: {result.statusCode}\n")
            f.write(f"  type: {result.type}\n")
            if result.type:
                f.write(f"    description: {result.type.description}\n")
                f.write(f"    currency: {result.type.currency}\n")
            f.write(f"  TenderDate: publish={result.TenderDate.publish}, close={result.TenderDate.close}\n")
            f.write(f"  TenderEvaluationCriteria count: {len(result.TenderEvaluationCriteria)}\n")
            f.write(f"  TenderGuarantees count: {len(result.TenderGuarantees)}\n")
            f.write(f"  tenderPurchaseData:\n")
            f.write(f"    organization: {result.tenderPurchaseData.organization.name}\n")
            f.write(f"    orgUnit: {result.tenderPurchaseData.orgUnit.name}\n")
    
    print(f"\nFailure saved to: {error_file}")


if __name__ == "__main__":
    asyncio.run(main())

