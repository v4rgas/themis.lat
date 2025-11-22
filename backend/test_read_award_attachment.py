from app.tools.read_award_result import read_award_result, read_award_result_attachment


def test_read_award_attachment():
    tender_id = "4074-24-LE19"
    
    print(f"Fetching award result for tender: {tender_id}")
    result = read_award_result.invoke({"id": tender_id})
    
    if not result.get("ok"):
        print("No award information available")
        return
    
    attachments = result.get("attachments", [])
    print(f"\nFound {len(attachments)} attachments:")
    for att in attachments:
        print(f"  [{att['row_id']}] {att['file']} - {att['type']} ({att['size']})")
    
    if not attachments:
        print("No attachments to download")
        return
    
    row_id = attachments[0]["row_id"]
    filename = attachments[0]["file"]
    
    print(f"\nDownloading attachment row_id={row_id}: {filename}")
    file_bytes = read_award_result_attachment.invoke({
        "id": tender_id,
        "row_id": row_id
    })
    
    print(f"Downloaded {len(file_bytes)} bytes")
    
    output_path = f"downloaded_{filename}"
    with open(output_path, "wb") as f:
        f.write(file_bytes)
    
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    test_read_award_attachment()

