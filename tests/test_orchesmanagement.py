import unittest
from unittest.mock import Mock, patch
from utils.orchesmanagement import OrchesManagement
from utils.sfmanagement import SalesforceManagement
import pandas as pd
import uuid
import json
import ast
from unittest.mock import patch
import os

class TestOrchesManagement(unittest.TestCase):

    def test_getorchitembysuborder(self):
        with patch.dict(os.environ, {'SALESFORCE_USER':'camilo.alfonso@cwc.com', 'SALESFORCE_PASS':''}):
            sf = SalesforceManagement(environment='qasales')
            ochm = OrchesManagement(sf=sf)
            dfsuborder = pd.read_csv('test/res_suborders.csv')
            dfres = ochm.getorchitembysuborder(dfsuborders=dfsuborder)
            self.assertIsNotNone(dfres)
            self.assertIsInstance(dfres, pd.DataFrame)
            expected_columns = ['Id', 
                                'Name', 
                                'OrderId',
                                'OrderItemId', 
                                'State',
                                'OrchestrationPlanId', 
                                'Error',
                                'status']
            self.assertCountEqual(dfres.columns.tolist(), expected_columns)
            
    def test_transformochitems(self):
        with patch.dict(os.environ, {'SALESFORCE_USER':'camilo.alfonso@cwc.com', 'SALESFORCE_PASS':''}):
            sf = SalesforceManagement(environment='qasales')
            ochm = OrchesManagement(sf=sf)
            df = pd.read_csv('test/res_orchitems.csv')
            dfres = ochm.transformochitems(dfochitems=df)
            self.assertIsNotNone(dfres)
            self.assertIsInstance(dfres, pd.DataFrame)
    
    def test_processorch(self):
        
        with patch.dict(os.environ, {'SALESFORCE_USER':'camilo.alfonso@cwc.com', 'SALESFORCE_PASS':''}):
            sf = SalesforceManagement(environment='qasales')
            ochm = OrchesManagement(sf=sf)
            dfres = ochm.processorch(suborderfile='test/res_suborders.csv')
            self.assertIsNotNone(dfres)
            self.assertIsInstance(dfres, pd.DataFrame)

    def test_transformochitemsresponse(self):
        with patch.dict(os.environ, {'SALESFORCE_USER':'camilo.alfonso@cwc.com', 'SALESFORCE_PASS':''}):
            sf = SalesforceManagement(environment='qasales')
            ochm = OrchesManagement(sf=sf)
            df = pd.read_csv('test/res_orchitems.csv')
            dfres = ochm.transformochitemsresponse(dfochitems=df)
            self.assertIsNotNone(dfres)
            self.assertIsInstance(dfres, pd.DataFrame)

    def test_getorderitembysuborder(self):
        with patch.dict(os.environ, {'SALESFORCE_USER':'camilo.alfonso@cwc.com', 'SALESFORCE_PASS':''}):
            sf = SalesforceManagement(environment='qasales')
            ochm = OrchesManagement(sf=sf)
            dfsuborder = pd.read_csv('test/res_suborders.csv')
            dfres = ochm.getorderitembysuborder(dfsuborders=dfsuborder)
            self.assertIsNotNone(dfres)
            self.assertIsInstance(dfres, pd.DataFrame)
            