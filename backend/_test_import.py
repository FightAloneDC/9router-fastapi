from app.routers.providers import router
print("Import OK")
print("Routes:", [r.path for r in router.routes])
