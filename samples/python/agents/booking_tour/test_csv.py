#!/usr/bin/env python3
"""
Test script for CSV functionality in the booking tour agent.
"""

import os
import sys
import csv

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Now import from the agent module
from agent import test_csv_writing, create_booking_form, CSV_FILE_PATH

def display_csv_content(file_path, title="CSV content"):
    """Display the content of a CSV file."""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"{title}:")
                print(content)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
    else:
        print(f"CSV file does not exist at {file_path}")

def test_booking_form():
    """Test the create_booking_form function to ensure it saves to CSV."""
    print("\n=== Testing create_booking_form function ===")

    # Create a booking form with test data
    booking_form = create_booking_form(
        destination="Paris",
        start_date="15/05/2025",
        end_date="25/05/2025",
        num_people=4,
        budget="5000 EUR"
    )

    booking_id = booking_form["booking_id"]
    print(f"Created booking form with ID: {booking_id}")

    # Check if the booking was saved to the CSV file
    if os.path.exists(CSV_FILE_PATH):
        with open(CSV_FILE_PATH, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            found = False
            for row in rows:
                if row.get('booking_id') == booking_id:
                    found = True
                    print(f"Booking form found in CSV with data: {row}")
                    break

            if not found:
                print(f"ERROR: Booking form with ID {booking_id} not found in CSV file")
                return False
    else:
        print(f"ERROR: CSV file does not exist at {CSV_FILE_PATH}")
        return False

    print("Booking form test completed successfully")
    return True

def main():
    """Run the CSV tests and display the results."""
    print("Testing CSV functionality...")
    print(f"CSV file path: {CSV_FILE_PATH}")

    # Check if the CSV file exists and display its content
    if os.path.exists(CSV_FILE_PATH):
        print(f"CSV file exists at {CSV_FILE_PATH}")
        display_csv_content(CSV_FILE_PATH, "Current CSV content")
    else:
        print(f"CSV file does not exist at {CSV_FILE_PATH}")

    # Run the general CSV test
    try:
        test_csv_writing()
        print("General CSV test completed successfully")
        display_csv_content(CSV_FILE_PATH, "Updated CSV content after general test")
    except Exception as e:
        print(f"General CSV test failed: {e}")
        return 1

    # Run the booking form test
    try:
        if not test_booking_form():
            print("Booking form test failed")
            return 1
        display_csv_content(CSV_FILE_PATH, "Final CSV content after booking form test")
    except Exception as e:
        print(f"Booking form test failed with exception: {e}")
        return 1

    print("\nAll tests completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
