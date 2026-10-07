
def run(config, ctx):
    for i in range(1000):
        print("basura %d" % i)
    ctx.log("hola desde el plugin")
    ctx.progress(1, 3, "paso uno")
    return {"ok": 1}
