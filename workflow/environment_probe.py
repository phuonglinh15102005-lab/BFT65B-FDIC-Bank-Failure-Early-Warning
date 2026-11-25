"""Observe an existing interpreter using metadata only; never install/import models."""
import importlib.metadata as metadata,json,platform,sys
values={}
for distribution in metadata.distributions():
    name=distribution.metadata.get('Name')
    if name:values[name.casefold()]=distribution.version
print(json.dumps(dict(python=platform.python_version(),executable=sys.executable,platform=platform.platform(),packages=values)))
