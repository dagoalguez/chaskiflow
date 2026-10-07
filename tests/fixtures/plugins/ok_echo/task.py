
import os
def run(config, ctx):
    return {"echo": config.get("value"), "pid": os.getpid()}
