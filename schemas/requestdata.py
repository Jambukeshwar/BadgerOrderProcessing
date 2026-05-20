from typing import List
from pydantic import BaseModel

class FtpSetup(BaseModel):
    userName: str
    serverName: str
    port: str
    password: str
    remoteFolder: str

class Query(BaseModel):
    fields: str
    object: str
    conditions: str

class Mapping(BaseModel):
    salesforcefield: str
    csvfield: str

class Setting(BaseModel):
    ftpSetup: FtpSetup
    query: Query
    mappings: dict

class Environment(BaseModel):
    name: str
    id: str

class Vendor(BaseModel):
    name: str
    id: str

class RequestData(BaseModel):
    setting: Setting
    environment: Environment
    vendor: Vendor
