"""Update embedder dimensions in database config"""
from app.database import SessionLocal
from app.models import Config

db = SessionLocal()
try:
    config = db.query(Config).filter(Config.key == 'main').first()
    if config:
        config_data = config.value
        if 'mem0' in config_data and 'embedder' in config_data['mem0']:
            if 'config' not in config_data['mem0']['embedder']:
                config_data['mem0']['embedder']['config'] = {}
            config_data['mem0']['embedder']['config']['embedding_dims'] = 2560
            config.value = config_data
            db.commit()
            print('✅ Updated embedder config with embedding_dims=2560')
        else:
            print('❌ embedder config not found in database')
    else:
        print('❌ No config found in database')
finally:
    db.close()