import csv
import os
from datetime import datetime

def read_iccid_from_csv(input_csv_file, iccid_column='ICCID'):
    iccids = []
    with open(input_csv_file, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile) if iccid_column else csv.reader(csvfile)
        if iccid_column:
            for row in reader:
                iccid_value = row.get(iccid_column, '').strip()
                if iccid_value:
                    iccids.append(iccid_value)
        else:
            for row in reader:
                if row and row[0].strip():
                    iccids.append(row[0].strip())
    return iccids

def read_last_po_number(file_path='last_po_number.txt'):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            val = f.read().strip()
            if val.isdigit():
                return int(val)
    return 2000000000  # Start here so first PO_NUMBER starts with '2'

def save_last_po_number(last_number, file_path='last_po_number.txt'):
    with open(file_path, 'w') as f:
        f.write(str(last_number))

def generate_batch_name():
    return 'prod_' + datetime.now().strftime('%m%d%Y')

def generate_po_numbers(start, count):
    return [str(num).zfill(10) for num in range(start + 1, start + 1 + count)]

def generate_csv_from_iccid(input_csv_file, output_csv_file, iccid_column='ICCID'):
    iccids = read_iccid_from_csv(input_csv_file, iccid_column)
    if not iccids:
        print(f"No ICCID values found in the input CSV file '{input_csv_file}'.")
        return

    last_po = read_last_po_number()
    batch_name = generate_batch_name()
    po_numbers = generate_po_numbers(last_po, len(iccids))

    try:
        with open(output_csv_file, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ICCID', 'BATCH', 'PO_NUMBER'])
            for iccid, po_number in zip(iccids, po_numbers):
                writer.writerow([iccid, batch_name, po_number])
        print(f"CSV file '{output_csv_file}' generated successfully with {len(iccids)} records.")
    except Exception as e:
        print(f"Error writing CSV file: {e}")
        return

    # Save the last PO_NUMBER generated
    save_last_po_number(last_po + len(iccids))

if __name__ == "__main__":
    input_file = 'input_iccid.csv'  # Your input CSV file path
    output_file = 'LBPR00015_4500006921.csv'      # Output CSV file path
    iccid_column_name = 'ICCID'     # Set your ICCID column name here

    generate_csv_from_iccid(input_file, output_file, iccid_column=iccid_column_name)
