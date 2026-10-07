
def run(config, ctx):
    return {"total": sum(len(r.get("rows", [])) for r in ctx.inputs.values()),
            "names": sorted(ctx.inputs)}
