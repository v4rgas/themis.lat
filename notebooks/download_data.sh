#!/bin/bash

# Script to download and process zip files from transparenciachc in parallel
# Uses 16 threads for parallel processing

# Create downloads directory if it doesn't exist
DOWNLOADS_DIR="downloads"
mkdir -p "$DOWNLOADS_DIR"

# Function to process a single year-month combination
process_month() {
    local year=$1
    local month=$2
    local url="https://transparenciachc.blob.core.windows.net/lic-da/${year}-${month}.zip"
    local zip_file="${DOWNLOADS_DIR}/${year}-${month}.zip"
    local extract_dir="${DOWNLOADS_DIR}/${year}-${month}"
    
    echo "Processing ${year}-${month}..."
    
    # Download the zip file
    if wget -q "$url" -O "$zip_file" 2>/dev/null; then
        # Create temporary extraction directory
        mkdir -p "$extract_dir"
        
        # Unzip the file
        if unzip -q "$zip_file" -d "$extract_dir" 2>/dev/null; then
            # Move CSV files to downloads directory root
            find "$extract_dir" -type f -name "*.csv" -exec mv {} "$DOWNLOADS_DIR/" \;
            
            # Remove the extraction directory
            rm -rf "$extract_dir"
            
            # Delete the zip file
            rm -f "$zip_file"
            
            echo "Completed ${year}-${month}"
        else
            echo "Error: Failed to unzip ${year}-${month}.zip"
            rm -f "$zip_file"
            rm -rf "$extract_dir"
        fi
    else
        echo "Error: Failed to download ${year}-${month}.zip"
    fi
}

# Export the function so it can be used by parallel processes
export -f process_month
export DOWNLOADS_DIR

# Generate list of year-month combinations
# Years: 2020-2025, Months: 1-12, except 2025-12
combinations=()
for year in {2007..2019}; do
    for month in {1..12}; do
        # Skip 2025-12
        if [ "$year" -eq 2025 ] && [ "$month" -eq 12 ]; then
            continue
        fi
        combinations+=("$year $month")
    done
done

# Process in parallel using xargs with 16 threads
printf '%s\n' "${combinations[@]}" | xargs -n 2 -P 16 -I {} bash -c 'process_month {}'

echo "All downloads completed!"

