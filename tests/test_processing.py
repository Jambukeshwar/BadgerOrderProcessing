import unittest
from unittest.mock import Mock, patch
from utils.processing import Processing
from utils.sfmanagement import SalesforceManagement
from schemas.migrationsetting import MigrationSetting,S3Files
import pandas as pd
import requests
import uuid
import json
import ast
import os

class TestProcessing(unittest.TestCase):
    """Class for Testing Processing 
    Args:
        unittest (unittest): testing processing 
    """
    def setUp(self):
        print('setUp called')
        listfiles = list()
        accountfile = S3Files(entity='business',
                          filename='Business_Account_2023-09-14.csv',
                          sourcepath='Salesforce/Customer_Feed_b2b/cust_account/load/',
                          targetpath='Salesforce/Customer_Feed_b2b/sf_response/cust_account/load/',
                          logpath='log/',
                          errorpath='')
        billingfile = S3Files(entity='billing',
                          filename='Billing_Account_2023-09-14.csv',
                          sourcepath='Salesforce/Customer_Feed_b2b/billing_account/load/',
                          targetpath='Salesforce/Customer_Feed_b2b/sf_response/billing_account/load/',
                          logpath='log/',
                          errorpath='')
        contactfile = S3Files(entity='contact',
                          filename='sf_cust_contact_data_2023-09-14.csv',
                          sourcepath='Salesforce/Customer_Feed_b2b/cust_contact/load/',
                          targetpath='Salesforce/Customer_Feed_b2b/sf_response/cust_contact/load/',
                          logpath='',
                          errorpath='')
        individualfile = S3Files(entity='individual',
                          filename='sf_cust_individual_data_2023-09-14.csv',
                          sourcepath='Salesforce/Customer_Feed_b2b/cust_individual/load/',
                          targetpath='Salesforce/Customer_Feed_b2b/sf_response/cust_individual/load/',
                          logpath='log/',
                          errorpath='')
        
        paymentfile = S3Files(entity='paymentmethod',
                          filename='sf_cust_payment_data_2023-09-14.csv',
                          sourcepath='Salesforce/Customer_Feed_b2b/cust_payment/load/',
                          targetpath='Salesforce/Customer_Feed_b2b/sf_response/cust_payment/load/',
                          logpath='log/',
                          errorpath='')
        
        contractfile = S3Files(entity='contract',
                          filename='sf_cust_contact_data_2023-09-14.csv',
                          sourcepath='Salesforce/Customer_Feed_b2b/cust_contract/load/',
                          targetpath='Salesforce/Customer_Feed_b2b/sf_response/cust_contract/load/',
                          logpath='log/',
                          errorpath='')
    
        orderitemfile = S3Files(entity='order_item',
                          filename='sf_order_item_2023-09-14.csv',
                          sourcepath='Salesforce/Customer_Feed_b2b/cust_order_item/load/',
                          targetpath='Salesforce/Customer_Feed_b2b/sf_response/cust_order_item/load/',
                          logpath='log/',
                          errorpath='')
        

        listfiles.append(accountfile)
        listfiles.append(billingfile)
        listfiles.append(contactfile)
        listfiles.append(individualfile)
        listfiles.append(paymentfile)
        listfiles.append(contractfile)
        listfiles.append(orderitemfile)

        self.migration = MigrationSetting(
            bucketname='lla-orchestrator-peacock-qa-us-transform',
            mitobasepath='b2b-sf-reponse-uat',
            sfenvironment='qasales',
            s3files = listfiles
        )
        with patch.dict(os.environ, {
                'AWS_RESPONSE_MITO_STATIC' : 'https://8zxqynqvgc.execute-api.us-east-1.amazonaws.com',
                'SALESFORCE_USER':'camilo.alfonso@cwc.com', 
                'SALESFORCE_PASS':'J4m3sM0rr1s0n*'}):
            self.sf = SalesforceManagement(environment='qasales')
        
        

    def test_generaremitoresponse(self):
        """test Generate Mito Response 
        """        
        processing = Processing(migrationsetting = self.migration, sf = self.sf)
        res = processing.generaremitoresponse()
        print(res)
        self.assertEqual(res, 'Completed', msg='Error in generate mito response')

    def test_generateordermitoresponse(self):
        """test Generate Order Item Response 
        """
        process = Processing(migrationsetting=self.migration, sf=self.sf)
        ressuborderfile = 'test/res_suborders.csv'
        r = process.generateordermitoresponse(suborderfile = ressuborderfile)

if __name__ == '__main__':
    unittest.main()