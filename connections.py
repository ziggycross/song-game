import pandas as pd

import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from streamlit.connections import ExperimentalBaseConnection
from streamlit.runtime.caching import cache_data

class MongoDBConnection(ExperimentalBaseConnection[pymongo.collection.Collection]):

    def _connect(self, **kwargs) -> pymongo.collection.Collection:
        uri = kwargs.pop("uri") if "uri" in kwargs else self._secrets["uri"]
        db  = kwargs.pop("database") if "database" in kwargs else self._secrets["database"]
        return MongoClient(uri, server_api=ServerApi('1'))[db]

    def database(self):
        return self._instance
    
    def collection(self, collection: str):
        return self.database()[collection]
    
    def query(self, collection: str, ttl: int = 3600, **kwargs):
        @cache_data(ttl=ttl)
        def _query(args_str: str, **kwargs):
            col = self.collection(collection)
            df = pd.DataFrame(list(col.find(**kwargs)))
            return df.set_index("_id")
        
        args_str = collection+str(sorted(kwargs))
        return _query(args_str, **kwargs)
    
    def distinct(self, collection: str, fields: str, ttl: int = 3600, **kwargs):
        @cache_data(ttl=ttl)
        def _distinct(args_str: str, **kwargs):
            col = self.collection(collection)
            return list(col.distinct(fields, **kwargs))
        
        args_str = collection+fields+str(sorted(kwargs))
        return _distinct(args_str, **kwargs)
    
class SpotifyConnection(ExperimentalBaseConnection[None]):
    pass