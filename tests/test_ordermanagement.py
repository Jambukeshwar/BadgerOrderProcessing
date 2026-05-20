import unittest
from unittest.mock import Mock, patch
from utils.ordermanagement import OrderManagement
from schemas.orderpayload import Offer, ChildProduct,OrderPayload
import pandas as pd
import uuid
import json
import ast

class TestOrderManagement(unittest.TestCase):
   
    def test_payload_by_business(self):
        order_management = OrderManagement()
        df_order = pd.read_csv('test/sf_order_item_2023-09-02.csv')
        business_data = {
            'ParentId_x': 'business01',
            'Count': 3
        }
        uniqueid = 'test_uuid'
        result = order_management.payloadbybusiness(dforder=df_order,business=business_data,uniqueid=uniqueid)    
        self.assertIsNotNone(result)
        try:
            order_payload_dict =result
        except json.JSONDecodeError:
            self.fail("La salida no es un JSON válido")

    def test_get_master_orders(self):
        order_management = OrderManagement()
        df_order = pd.read_csv('test/sf_order_item_2023-08-18.csv')
        df_result = order_management.getmasterorders(df_order)
        self.assertIsNotNone(df_result)
        self.assertIsInstance(df_result, pd.DataFrame)
        expected_columns = ['ParentId_x','order_id','Count']
        self.assertCountEqual(df_result.columns.tolist(), expected_columns)
    def test_generate_orderi_tem_response_onedict(self):
        order_management = OrderManagement()
        dict_result = {'MasterOrder': '80174000000AQglAAG', '192556': '80174000000AQgmAAG','12121':'asdadasdasd','order_id':'1234'}
        dfresult = order_management.generateorderitemresponse(dict_result=dict_result)
        self.assertEqual('log/res_suborders.csv' , dfresult, msg='Error to Generate')
    def test_generate_orderi_tem_response_multidict(self):
        order_management = OrderManagement()
        
        dict_result = [{'MasterOrder': 'masterorder1', '192556': 'suborder11','12121':'suborder12','order_id':'1234'},
                       {'MasterOrder': 'masterorder2', '192552': 'suborder21','12121':'suborder22','order_id':'1234'}
                       ]
        dfresult = order_management.generateorderitemresponse(dict_result=dict_result)
        self.assertEqual('log/res_suborders.csv' , dfresult, msg='Error to Generate')

if __name__ == '__main__':
    unittest.main()
