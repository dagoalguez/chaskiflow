
def run(config, ctx):
    token = ctx.secrets.require("api_token")
    try:
        ctx.secrets.get("no_declarado")
        denied = False
    except PermissionError:
        denied = True
    ctx.log("el token es " + token)
    return {"len": len(token), "denied": denied}
