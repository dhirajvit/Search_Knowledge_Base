from mangum import Mangum
from app.server import app

# Create the Lambda handler
handler = Mangum(app)