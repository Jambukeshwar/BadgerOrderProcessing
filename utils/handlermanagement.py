from utils.sfmanagement import SalesforceManagement
from utils.processing import Processing
from schemas.migrationsetting import MigrationSetting
#import logging
from utils.logger import Logger

#logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s',
#                    datefmt='%Y-%m-%d %H:%M:%S',
#                    level=logging.INFO)
#logger = logging.getLogger(__name__)

logger = Logger().get_logger()

class HandlerManagement(object):
    def __init__(self, migrationsetting : MigrationSetting, sfenvironment : str) -> None:
        
        self.process = Processing( 
            migrationsetting = migrationsetting,
            sf = SalesforceManagement(environment = sfenvironment)
        )
    def businessAccounts(self, entity):
        return self.process.startmigrationentity(
            entity = entity,
            businessfile = None,
            billingfile = None,
            individualfile=None,
            suborderfile = None
        )
        
    def getOrderItemsFiles(self):
        return self.process.getOrderFilesinDirectory()    
        
    def billingAccounts(self,entity, businessfilename):
        return self.process.startmigrationentity(
            entity = entity,
            businessfile = businessfilename, 
            billingfile = None,
            individualfile=None,
            suborderfile = None
        )
    def paymentMethods(self,entity, billingfile): 
        try:
            res = self.process.startmigrationentity(
                entity = entity,
                businessfile = None,
                billingfile = billingfile,
                individualfile=None,
                suborderfile = None
            )
        except Exception as e:
            logger.exception(f'Fail | Read S3 from AWS - {entity} | | ')

        return 
    def individual(self,entity): 
        return self.process.startmigrationentity(
            entity = entity,
            businessfile = None,
            billingfile = None,
            individualfile=None,
            suborderfile = None
        )
    def contact(self,entity, businessfile,individualfile): 
        return self.process.startmigrationentity(
            entity = entity,
            businessfile = businessfile,
            billingfile = None,
            individualfile=individualfile,
            suborderfile = None
        )
    def consent(self,entity,individualfile): 
        return self.process.startmigrationentity(
            entity = entity,
            businessfile = None,
            billingfile = None,
            individualfile = individualfile,
            suborderfile = None
        )
    def contract(self,entity,subordersfile): 
        return self.process.startmigrationentity(
            entity = entity,
            businessfile = None,
            billingfile = None,
            individualfile = None,
            suborderfile = subordersfile
        )
    def serviceaccounts(self,entity,billingfile):
        # Cargar archivo de OrderItem 
        # Cruzarlo con Archivo de Billing obtener el parentid 
        return self.process.createservice(entity=entity, billingfile=billingfile)
    
    def createAriaMatrixx(self):
        return self.process.createAriaMatrix()
    def invokeariaaccountcreation(self, billingfile):
        return self.process.invokeariaaccountcreation(billingfile = billingfile, batch=200)
    def invokeariapaymentmethod(self, billingfile):
        return self.process.invokeariapaymentmethod(billingfile = billingfile, batch=200)
    def invokeariaupdatepaymentmethod(self, billingfile):
        return self.process.invokeariaupdatepaymentmethod(billingfile = billingfile, batch=200)
    def invokematrixxcustomercreation(self,businessfile):
        return self.process.invokematrixxcustomercreation(businessfile=businessfile, batch=200)
    def invokematrixxaccountcreation(self,billingfile):
        return self.process.invokematrixxaccountcreation(billingfile=billingfile, batch=200)
    def createBanCanBusiness(self, businessfile):
        return self.process.createBanCanBusiness(businessfile) #jfrc
    def createBanCanBilling(self, billingfile):
        return self.process.createBanCanBilling(billingfile) #jfrc
    def generetestaticmito(self):
        return self.process.generaremitoresponse()
    def generateMitoresponse(self, suborderfile):
        return self.process.generateordermitoresponse(suborderfile=suborderfile)
    def updateAccSegment(self, accFile):
        return self.process.updateAccountSegment(accFile) #jfrc
    def gets3file(self, entity):
        self.process.gets3filetocsv(entity=entity) #jfrc   
    def uploadlogfiles(self):
        self.process.uploadfilestos3(self)
    def generateresponsereportprocess(self):
        return self.process.generateresponsereport()
    def generateMitoresponseall(self, suborderfile):
        return self.process.generateordermitoresponseall(suborderfile=suborderfile)
    def gets3filepath(self, entity):
        return self.process.gets3filepayloadpath(entity=entity) #jfrc       
    def postcartitem(self):
        return self.process.postcartItemapi()    
