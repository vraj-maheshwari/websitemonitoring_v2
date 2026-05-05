from app import create_app

import os
print("RAILWAY PORT =", os.getenv("PORT"))
app = create_app()