
import time
def run(config, ctx):
    time.sleep(config["seconds"])
    return {"slept": config["seconds"]}
