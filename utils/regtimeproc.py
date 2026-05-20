import datetime
import time
from prettytable import PrettyTable

class Regtimeproc:
  _instance = None
  proc_invoque = []
 
  def __new__(cls):
    if cls._instance is None:
      cls._instance = super(Regtimeproc, cls).__new__(cls)
      #cls._instance.proc_invoque = []
    return cls._instance 
  
  #def __init__(self):
 
  def registrar_valores(self, proc_name, start_date, end_date, method_name,elapsetTime,recordsAffected):
    # Almacenar los valores en el arreglo
    self.proc_invoque.append({
        'proc_name': proc_name,
        'start_date': start_date,
        'end_date': end_date,
        'method_name': method_name,
        'elapset_Time' : elapsetTime,
        'total_records' : recordsAffected,
    }) 
    
    
  def print_Results_table(self):
    tabla = PrettyTable()
    tabla.field_names = ["Subproceso", "Hora de Inicio", "Hora de Fin","Tiempo Total","# de Registros"]
    for subproceso in self.proc_invoque:
        tabla.add_row([subproceso.proc_name , subproceso.start_date, subproceso.end_date,subproceso.elapset_Time,subproceso.total_records])
    print(tabla)
 
  
  
  
  