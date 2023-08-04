import pandas as pd

import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from streamlit.connections import ExperimentalBaseConnection
from streamlit.runtime.caching import cache_data

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

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
        
        args_str = f"{collection}{sorted(kwargs)}"
        return _query(args_str, **kwargs)
    
    def distinct(self, collection: str, fields: str, ttl: int = 3600, **kwargs):
        @cache_data(ttl=ttl)
        def _distinct(args_str: str, **kwargs):
            col = self.collection(collection)
            return list(col.distinct(fields, **kwargs))
        
        args_str = f"{collection}{fields}{sorted(kwargs)}"
        return _distinct(args_str, **kwargs)
    
    def aggregate(self, collection: str, pipeline: list, ttl: int = 3600, **kwargs):
        @cache_data(ttl=ttl)
        def _aggregate(args_str: str, **kwargs):
            col = self.collection(collection)
            agg = list(col.aggregate(pipeline, **kwargs))
            df = pd.DataFrame([item["_id"] for item in agg])
            return df
        
        args_str = f"{collection}{pipeline}{sorted(kwargs)}"
        return _aggregate(args_str, **kwargs)
    
class SpotifyConnection(ExperimentalBaseConnection[spotipy.client.Spotify]):
    
    def _connect(self, **kwargs) -> spotipy.client.Spotify:
        client_id      = kwargs.pop("id") if "id" in kwargs else self._secrets["id"]
        client_secret  = kwargs.pop("secret") if "secret" in kwargs else self._secrets["secret"]
        credentials = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        return spotipy.Spotify(client_credentials_manager=credentials)
    
    def client(self):
        return self._instance
    
    def get_song_artist(self, track: str):
        return self.client().track(f"spotify:track:{track}")["artists"][0]["id"]

    def get_artist_image(self, artist: str):
        return self.client().artist(artist)["images"][0]["url"]

