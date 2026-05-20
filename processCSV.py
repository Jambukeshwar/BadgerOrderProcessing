import csv

def process_csv(input_file, output_file):
    """
    Processes a CSV file, generating two lines per ICCID with specific values,
    and adjusting the values of product_attributes and fieldstoupdate.
    """
    try:
        with open(input_file, 'r', newline='', encoding='utf-8') as csv_input, \
             open(output_file, 'w', newline='', encoding='utf-8') as csv_output:

            reader = csv.DictReader(csv_input)
            fieldnames = [
                'order_item_id', 'prnt_order_item_id', 'order_id', 'subsrptn_id', 'pricebook2',
                'quantity', 'unitprice', 'vlocity_cmt__linenumber__c', 'product2id', 'currencyisocode',
                'vlocity_cmt__billingaccountid__c', 'vlocity_cmt__monthlytotal__c',
                'vlocity_cmt__onetimecost__c', 'vlocity_cmt__recurringuom__c',
                'product_attributes', 'fieldstoupdate'
            ]
            #writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
            writer = csv.DictWriter(csv_output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)

            writer.writeheader()

            order_item_id = 1000001
            order_id = 8000001

            for row in reader:
                iccid = row.get('ICCID', '').strip()  # Get ICCID and remove leading/trailing spaces

                if not iccid:
                    print("Warning: A row with an empty ICCID was found and will be skipped.")
                    continue

                # Check if ICCID is numeric and has at least 11 digits
                if not iccid.isdigit() or len(iccid) < 11:
                    print(f"Warning: ICCID '{iccid}' is invalid (non-numeric or too short), skipping row.")
                    continue

                # Use last 11 digits of ICCID as subsrptn_id
                subsrptn_id = iccid[-11:]

                # First line for PR_B2B_Badger
                writer.writerow({
                    'order_item_id': order_item_id,
                    'prnt_order_item_id': order_item_id,
                    'order_id': order_id,
                    'subsrptn_id': subsrptn_id,
                    'pricebook2': '01s740000009RznAAE',
                    'quantity': 1,
                    'unitprice': '',
                    'vlocity_cmt__linenumber__c': '1.0',
                    'product2id': 'PR_B2B_Badger',
                    'currencyisocode': 'USD',
                    'vlocity_cmt__billingaccountid__c': '41001269',
                    'vlocity_cmt__monthlytotal__c': '',
                    'vlocity_cmt__onetimecost__c': '',
                    'vlocity_cmt__recurringuom__c': 'monthly',
                    'product_attributes': f"{{'PRB2C_ATT_Mobile_SIM_Card_Type':'MFF2 eSim','PR_B2C_Mb_ATT_ICCID':'{iccid}','PR_B2C_ATT_Pool_ID':'7002'}}",
                    'fieldstoupdate': f"{{'PR_ICCID__c':'{iccid}', 'vlocity_cmt__RecurringCharge__c':'0.15'}}"
                })

                parent_order_item_id = order_item_id
                order_item_id += 1

                # Second line for PR_B2C_SIM_Card
                writer.writerow({
                    'order_item_id': order_item_id,
                    'prnt_order_item_id': parent_order_item_id,
                    'order_id': order_id,
                    'subsrptn_id': subsrptn_id,
                    'pricebook2': '01s740000009RznAAE',  # Adjusted to match expected
                    'quantity': 1,
                    'unitprice': '',
                    'vlocity_cmt__linenumber__c': '1.1',
                    'product2id': 'PR_B2C_SIM_Card',
                    'currencyisocode': 'USD',
                    'vlocity_cmt__billingaccountid__c': '41001269',
                    'vlocity_cmt__monthlytotal__c': '',
                    'vlocity_cmt__onetimecost__c': '',
                    'vlocity_cmt__recurringuom__c': 'monthly',
                    'product_attributes': f"{{'PRB2C_ATT_Mobile_SIM_Card_Type':'MFF2 eSim','PR_B2C_ATT_Plan_Type':'B2B','PR_B2C_Mb_ATT_SKU':'109211','PR_B2C_Mb_ATT_ICCID':'{iccid}'}}",
                    'fieldstoupdate': ""  # Fixed to include correct value
                })

                order_item_id += 1
                order_id += 1

        print(f"File '{output_file}' successfully created.")

        # Call function to clean up the file
        clean_output_file(output_file)

    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

def clean_output_file(output_file):
    """ Removes ,'PR_MSISDN_c':'' from all lines in the output file. """
    try:
        with open(output_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        with open(output_file, 'w', encoding='utf-8') as file:
            for line in lines:
                cleaned_line = line.replace(",'PR_MSISDN_c':''", "")  # Adjust if more cleanup needed
                file.write(cleaned_line)

        print(f"File '{output_file}' cleaned successfully.")
    
    except Exception as e:
        print(f"An error occurred while cleaning the file: {e}")

# Script usage
input_file = r'data/LBPR00015_4500006921.csv'
output_file = r'data/Order_item_M2M.csv'
process_csv(input_file, output_file)
