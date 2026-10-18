import json, sys
from character_master import CharacterAssetMaster
r=CharacterAssetMaster().acceptance_test()
print(json.dumps(r,indent=2))
sys.exit(0 if r['passed'] else 1)
